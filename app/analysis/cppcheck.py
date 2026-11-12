import hashlib
import json
import re
from pathlib import Path
import subprocess
import tempfile
from time import monotonic, sleep
import xml.etree.ElementTree as ET
from tree_sitter import Language, Parser
import tree_sitter_cpp

from app.security.permissions import relative_path

ISSUES = {
    "nullPointer": "null-pointer", "nullPointerRedundantCheck": "null-pointer",
    "nullPointerDefaultArg": "null-pointer", "arrayIndexOutOfBounds": "boundary",
    "bufferAccessOutOfBounds": "boundary", "negativeIndex": "boundary",
    "memleak": "resource", "resourceLeak": "resource", "deallocuse": "resource",
    "deallocret": "resource",
    "doubleFree": "resource", "uninitvar": "initialization", "uninitdata": "initialization",
    "ignoredReturnValue": "unchecked-return",
}
FAILURE_IDS = {"syntaxError", "internalError", "preprocessorErrorDirective", "missingInclude",
               "missingIncludeSystem", "unmatchedSuppression", "toomanyconfigs"}


def check_includes(text):
    tree = Parser(Language(tree_sitter_cpp.language())).parse(text.encode())
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        if node.type == "preproc_include":
            path = node.child_by_field_name("path")
            if path is None or path.type not in ("string_literal", "system_lib_string"):
                raise ValueError("Dynamic includes are not supported")
            raw = path.text.decode("utf-8")
            relative_path(raw[1:-1])
        elif node.type == "preproc_call" and re.search(r'#\s*(include_next|import|embed)\b', node.text.decode("utf-8")):
            raise ValueError("External preprocessor imports are not supported")
        pending.extend(node.children)


def normalize(xml, manifest, root):
    document = ET.fromstring(xml)
    if document.tag != "results" or document.find("errors") is None:
        raise ValueError("Invalid analyzer XML structure")
    findings, limitations = [], []
    for error in document.findall("errors/error"):
        rule = error.get("id", "")
        if rule in FAILURE_IDS:
            limitations.append(f"Cppcheck reported {rule}; analysis coverage is incomplete")
            continue
        location = error.find("location")
        if location is None:
            limitations.append("Analyzer finding lacks source location")
            continue
        raw_path = location.get("file", "").replace("\\", "/")
        path = Path(raw_path)
        if path.is_absolute():
            path = path.resolve().relative_to(root.resolve())
        file = relative_path(path.as_posix())
        line = int(location.get("line", "0"))
        if file not in manifest["source"] or not 1 <= line <= len(manifest["source"][file].splitlines()):
            raise ValueError("Analyzer source mapping is outside the captured snapshot")
        record = {"tool": "cppcheck", "repository": manifest["repository"],
                  "snapshot": manifest["snapshot"], "file": file, "line": line,
                  "severity": error.get("severity", "information"), "rule": rule,
                  "message": error.get("msg", ""), "category": ISSUES.get(rule, "performance" if error.get("severity") == "performance" else "other"),
                  "inconclusive": error.get("inconclusive") == "true"}
        record["id"] = "A" + hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:16]
        findings.append(record)
    return findings, limitations


class Cppcheck:
    def __init__(self, executable, work_dir, timeout=30, max_output=1_048_576):
        self.executable = Path(executable).resolve()
        self.work_dir = Path(work_dir)
        self.timeout = timeout
        self.max_output = max_output

    def run(self, manifest):
        from app.analysis.configuration import arguments
        configuration = manifest.get('analysis_configuration')
        result = {"status": "unavailable", "tool": "cppcheck", "version": None,
                  "repository": manifest["repository"], "snapshot": manifest["snapshot"],
                  "files": sorted(manifest["source"]),
                  "findings": [], "limitations": ["No build configuration supplied; default C++17/C11 analysis"]}
        result['configuration_mode'] = 'PROJECT_CONFIGURATION' if configuration is not None else 'DEFAULT_CONFIGURATION'
        if configuration is not None:
            result['limitations'] = list(configuration['limitations']) + [configuration['provenance']]
        if not self.executable.is_file():
            result["limitations"].append("Configured Cppcheck executable missing")
            return result
        result["status"] = "failed"
        process = None
        try:
            for text in manifest["source"].values():
                text = text.replace("\\\n", "").replace("\\\r\n", "")
                # Reject obfuscated directives rather than interpreting comments,
                # digraphs/trigraphs or alternate preprocessor spellings.
                if re.search(r'^\s*#\s*/\*', text, re.M) or "%:" in text or "??=" in text:
                    raise ValueError("Unsupported preprocessor directive spelling")
                check_includes(text)
                for directive, argument in re.findall(r'^\s*#\s*(include_next|include|import)\b([^\n]*)', text, re.M):
                    match = re.fullmatch(r'\s*[<"]([^>"\n]+)[>"]\s*(?://.*)?', argument)
                    if directive != "include" or match is None:
                        raise ValueError("Only literal snapshot-relative includes are supported")
                    relative_path(match[1])
            version = subprocess.run([str(self.executable), "--version"], capture_output=True,
                                     timeout=min(self.timeout, 5), check=False)
            if version.returncode or len(version.stdout) > 4096:
                raise ValueError("Analyzer version check failed")
            result["version"] = version.stdout.decode("utf-8").strip()
            self.work_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="cppcheck-", dir=self.work_dir) as directory:
                root = Path(directory)
                source_root = root / "source"
                source_root.mkdir()
                for file, text in manifest["source"].items():
                    relative_path(file)
                    destination = source_root / file
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(text.encode("utf-8"))
                # No addons, external compiler, build scripts, compilation DB,
                # repository config or shell is used. Only the captured source.
                arguments = [str(self.executable), "--xml", "--xml-version=2", "--enable=warning,style,performance,portability,information",
                             "--error-exitcode=0", "--max-configs=4"] + arguments(configuration) + ['.']
                stdout, stderr = root / "stdout", root / "stderr"
                with stdout.open("wb") as out, stderr.open("wb") as err:
                    process = subprocess.Popen(arguments, cwd=source_root, stdout=out, stderr=err, shell=False)
                    try:
                        started = monotonic()
                        while process.poll() is None:
                            if monotonic() - started > self.timeout:
                                raise TimeoutError("Analyzer timeout")
                            if stdout.stat().st_size + stderr.stat().st_size > self.max_output:
                                raise ValueError("Analyzer output limit exceeded")
                            sleep(0.02)
                        if process.returncode:
                            raise ValueError("Analyzer exited unsuccessfully")
                    finally:
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                if stdout.stat().st_size + stderr.stat().st_size > self.max_output:
                    raise ValueError("Analyzer output limit exceeded")
                raw = stderr.read_bytes()
                findings, limits = normalize(raw, manifest, source_root)
                result["findings"] = findings
                result["limitations"].extend(limits)
                result["status"] = "degraded" if limits else "ok"
        except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError, TimeoutError):
            result["limitations"].append("Cppcheck execution/output failed; no clean-review conclusion")
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
        return result
