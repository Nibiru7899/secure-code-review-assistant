import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from time import perf_counter
from dataclasses import asdict
from pathlib import Path

from app.db.database import Catalog
from app.ingestion.chunker import POLICY, chunks
from app.ingestion.scanner import scan
from app.retrieval.vector_store import VectorStore


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def rule_records(text, repository, snapshot, source_file="rules/coding_rules.md"):
    records = []
    identifiers = set()
    for match in re.finditer(r"^RULE ([A-Z]+-\d+)\n(.*?)(?=^RULE |\Z)", text, re.M | re.S):
        identifier, body = match.groups()
        if identifier in identifiers or len(body.encode()) > 1800:
            raise ValueError("Duplicate or oversized approved coding rule")
        title = re.search(r"^Title: (.+)$", body, re.M)
        category = re.search(r"^Category: (.+)$", body, re.M)
        if title is None or category is None:
            raise ValueError("Approved rules require title and category")
        identifiers.add(identifier)
        records.append({"chunk_id": digest(f"{repository}/{snapshot}/{identifier}/{body}"),
                        "repository": repository, "snapshot": snapshot, "rule_id": identifier,
                        "title": title.group(1), "category": category.group(1),
                        "start_line": text[:match.start()].count("\n") + 1,
                        "end_line": text[:match.end()].rstrip().count("\n") + 1,
                        "text": f"RULE {identifier}\n{body.strip()}", "file": source_file})
    if not records:
        raise ValueError("No valid approved coding rules")
    return records


class Indexer:
    def __init__(self, permissions, data_dir, embedder, rules_file, database_url=None, code_aware=False):
        self.permissions = permissions
        self.data_dir = Path(data_dir).resolve()
        self.embedder = embedder
        self.rules_file = Path(rules_file)
        self.lock = threading.Lock()
        self.catalog = None
        self.store = None
        self.database_url = database_url
        self.code_aware = code_aware

    def open_storage(self, scope):
        if self.data_dir.is_relative_to(scope.root):
            raise ValueError("Application data must be outside the scanned repository")
        if self.catalog is None:
            catalog = Catalog(self.data_dir / "catalog.sqlite3", self.database_url)
            store = VectorStore(self.data_dir / "chroma")
            self.catalog, self.store = catalog, store

    def index(self, token, repository, analysis_configuration=None):
        started = perf_counter()
        scope = self.permissions.authorize(token, repository)
        with self.lock:
            self.open_storage(scope)
            scan_started = perf_counter()
            scanned = scan(scope)
            scan_seconds = round(perf_counter() - scan_started, 3)
            summary = scanned.summary()
            if not scanned.files:
                raise ValueError("No accepted source files; previous active snapshot preserved")
            rules_text = self.rules_file.read_text(encoding="utf-8")
            from app.analysis.configuration import capture_configuration
            configuration = capture_configuration(analysis_configuration, scanned.files, scope)
            hashes = {file: digest(text) for file, text in sorted(scanned.files.items())}
            identity = {"repository": repository, "scope": scope.key, "files": hashes,
                        "policy": POLICY + ('/structural-facts-v1' if self.code_aware else ''), "embedding": self.embedder.identity, "rules": digest(rules_text),
                        "rules_source_file": str(self.rules_file.resolve())}
            if configuration is not None:
                identity['analysis_configuration'] = configuration
            snapshot = digest(json.dumps(identity, sort_keys=True))
            previous = self.catalog.current(scope)
            if previous and previous["snapshot"] == snapshot:
                result = dict(summary, snapshot=snapshot, chunks=len(previous["chunks"]),
                              index_status="unchanged", parser_status=previous["parser_status"],
                              indexed_at=datetime.now(timezone.utc).isoformat(), scan_seconds=scan_seconds,
                              index_seconds=round(perf_counter() - started, 3))
                if self.code_aware:
                    result['embedding_stats'] = {'computed': 0, 'reused': len(previous['chunks']) + len(previous['rules']), 'seconds': 0}
                    result['ast_seconds'] = 0
                self.catalog.record_index(scope, result)
                return result
            code = []
            statuses = {}
            facts = {}
            ast_started = perf_counter()
            for file, text in sorted(scanned.files.items()):
                parsed, status = chunks(repository, snapshot, file, text, structural=self.code_aware)
                code.extend(asdict(c) for c in parsed)
                statuses[file] = status
                if self.code_aware and status == 'ok':
                    from app.ingestion.code_facts import capture
                    try:
                        facts[file] = capture(text, 'c' if file.endswith('.c') else 'cpp', repository, snapshot, file)
                    except ValueError:
                        statuses[file] = 'failed'
            ast_seconds = round(perf_counter() - ast_started, 4)
            if not code:
                raise ValueError("No usable code chunks; previous active snapshot preserved")
            rules = rule_records(rules_text, repository, snapshot, str(self.rules_file.resolve()))
            try:
                if self.code_aware:
                    from app.retrieval.embedding_cache import encode_cached
                    vectors, embedding_stats = encode_cached(self, scope, code + rules)
                    code_vectors, rule_vectors = vectors[:len(code)], vectors[len(code):]
                else:
                    code_vectors = self.embedder.encode([c["text"] for c in code])
                    rule_vectors = self.embedder.encode([r["text"] for r in rules])
                self.store.stage(code, code_vectors, rules, rule_vectors)
                manifest = dict(identity, snapshot=snapshot, source=scanned.files, chunks=code,
                                indexed_at=datetime.now(timezone.utc).isoformat(), scan_seconds=scan_seconds,
                                rules=rules, rules_source=rules_text, parser_status=statuses, scan=summary)
                if self.code_aware:
                    manifest.update(code_facts=facts, ast_seconds=ast_seconds, embedding_stats=embedding_stats)
                self.catalog.publish(scope, manifest)
            except Exception:
                # Staged data is never active without the catalog transaction.
                # Leave it for an idempotent retry; no destructive cleanup here.
                raise RuntimeError("Indexing failed; previous active snapshot preserved") from None
            warnings = []
            if previous:
                try:
                    self.store.delete(repository, previous["snapshot"])
                except Exception:
                    warnings.append("Obsolete vector cleanup failed; active snapshot filters still apply")
            result = dict(summary, snapshot=snapshot, chunks=len(code), parser_status=statuses,
                        indexed_at=manifest["indexed_at"], scan_seconds=scan_seconds,
                        index_seconds=round(perf_counter() - started, 3),
                        index_status="degraded" if scanned.failed or "failed" in statuses.values() else "ok",
                        warnings=warnings)
            if self.code_aware:
                result.update(ast_seconds=ast_seconds, embedding_stats=embedding_stats)
            self.catalog.record_index(scope, result)
            return result
