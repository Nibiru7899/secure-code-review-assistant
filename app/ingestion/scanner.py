import ctypes
import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from app.security.permissions import AccessDenied, Scope

EXTENSIONS = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp"}
IGNORED = {".git", "build", "dist", "vendor", "third_party", "node_modules", ".local", ".venv"}


def is_link(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def check_opened_path(stream, scope):
    # Verify the actual opened handle before reading, including a parent-junction
    # swap between path validation and open on Windows.
    if os.name == "nt":
        import msvcrt
        from ctypes import wintypes
        function = ctypes.WinDLL("kernel32", use_last_error=True).GetFinalPathNameByHandleW
        function.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
        function.restype = wintypes.DWORD
        buffer = ctypes.create_unicode_buffer(32768)
        length = function(msvcrt.get_osfhandle(stream.fileno()), buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise AccessDenied("Cannot verify opened source path")
        value = buffer.value
        value = "\\\\" + value[8:] if value.startswith("\\\\?\\UNC\\") else value.removeprefix("\\\\?\\")
        actual = Path(value).resolve()
        if not actual.is_relative_to(scope.root) or not scope.allows(actual.relative_to(scope.root).as_posix()):
            raise AccessDenied("Opened source is outside authorized scope")


@dataclass
class ScanResult:
    repository: str
    root: str
    files: dict[str, str] = field(default_factory=dict)
    skipped: list[dict] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    discovered: int = 0

    def summary(self):
        return {"repository": self.repository, "root": self.root, "files_discovered": self.discovered,
                "files_accepted": len(self.files), "files_skipped": len(self.skipped),
                "skipped": self.skipped, "failures": self.failed,
                "scanner_status": "degraded" if self.failed else "ok"}


def scan(scope: Scope, max_bytes=1_048_576):
    result = ScanResult(scope.repository, str(scope.root))
    visited = set()

    def skip(path, reason, failed=False):
        record = {"file": path, "reason": reason}
        result.skipped.append(record)
        if failed:
            result.failed.append(record)

    def visit(path):
        relative = path.relative_to(scope.root).as_posix()
        if relative in visited or not scope.allows(relative):
            return
        visited.add(relative)
        try:
            scope.resolve(relative)
            if is_link(path):
                skip(relative, "link_or_junction")
                return
            if path.is_dir():
                if path.name.lower() in IGNORED:
                    skip(relative, "ignored_directory")
                    return
                for child in sorted(path.iterdir()):
                    visit(child)
                return
            result.discovered += 1
            if path.name.lower() in {"secrets.h", "credentials.h", "private_key.h"}:
                skip(relative, "secret_filename")
                return
            if path.suffix.lower() not in EXTENSIONS:
                skip(relative, "unsupported_or_secret_extension")
                return
            info = path.stat()
            if not stat.S_ISREG(info.st_mode):
                skip(relative, "not_regular_file")
                return
            if info.st_size > max_bytes:
                skip(relative, "size_limit")
                return
            # O_NOFOLLOW is available on POSIX; Windows verifies the opened handle.
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                check_opened_path(stream, scope)
                opened = os.fstat(stream.fileno())
                if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                    raise OSError("Source changed before read")
                raw = stream.read(max_bytes + 1)
                after = os.fstat(stream.fileno())
                if opened.st_mtime_ns != after.st_mtime_ns or opened.st_size != after.st_size:
                    raise OSError("Source changed during read")
            if len(raw) > max_bytes:
                skip(relative, "size_limit")
            elif b"\x00" in raw:
                skip(relative, "binary_content")
            else:
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    skip(relative, "unsupported_encoding", failed=True)
                    return
                if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text):
                    skip(relative, "private_key_material")
                elif re.search(r"(?:automatically generated|generated file|do not edit)", text[:1024], re.I):
                    skip(relative, "generated_source")
                else:
                    result.files[relative] = text
        except AccessDenied:
            skip(relative, "path_escape_or_denied")
        except OSError:
            skip(relative, "unreadable_or_changed", failed=True)

    for prefix in scope.prefixes:
        visit(scope.root / prefix)
    return result
