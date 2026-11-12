import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from time import sleep
import unittest
from unittest.mock import patch

from app.ingestion.chunker import CHUNK_BYTES, chunks
from app.ingestion.indexer import Indexer, rule_records
from app.ingestion.scanner import scan
from app.retrieval.retriever import Retriever
from app.security.permissions import AccessDenied, Permissions


class TestEmbedder:
    """Only a deterministic storage test double; never a production fallback."""
    identity = "test-only"

    def encode(self, texts):
        return [[1.0, 0.5, 0.25] for _ in texts]


class FoundationTests(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1] / ".local"
        directory.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="foundation-test-", dir=directory)
        self.indexers = []
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        (self.root / "safe.cpp").write_text("int safe() { return 1; }\n", encoding="utf-8")
        self.rules = self.base / "rules.md"
        self.rules.write_text("RULE PTR-001\nTitle: Pointers\nCategory: pointer\nCheck before dereference.\n")
        self.token = "synthetic-secret"
        config = {"credentials": {hashlib.sha256(self.token.encode()).hexdigest(): "developer"},
                  "repositories": {"repo": {"root": str(self.root), "users": {"developer": ["."]}}}}
        self.permissions = Permissions(config)
        self.scope = self.permissions.authorize(self.token, "repo")

    def tearDown(self):
        for indexer in self.indexers:
            if indexer.store is not None:
                indexer.store.close()
        # The pinned Rust SQLite pool releases Windows handles asynchronously.
        for attempt in range(10):
            try:
                self.temp.cleanup()
                break
            except PermissionError:
                if attempt == 9:
                    raise
                sleep(0.05)

    def indexer(self):
        indexer = Indexer(self.permissions, self.base / "data", TestEmbedder(), self.rules)
        self.indexers.append(indexer)
        return indexer

    def test_tiny_index_repeated_filtered_queries_and_restart(self):
        indexer = self.indexer()
        result = indexer.index(self.token, "repo")
        for reopening in range(2):
            for repeat in range(20):
                found = Retriever(indexer).retrieve(self.token, "repo", "find safe function")
                self.assertEqual(found["snapshot"], result["snapshot"])
                self.assertEqual(found["related_code"][0]["symbol"], "safe")
            if not reopening:
                indexer.store.close()
                indexer.store = None
                indexer.catalog = None

    def test_unknown_user_and_repository_denied_before_filesystem(self):
        with patch("pathlib.Path.resolve", side_effect=AssertionError("Filesystem accessed")):
            for token, repo in [("unknown", "repo"), (self.token, "unknown")]:
                with self.assertRaises(AccessDenied):
                    self.permissions.authorize(token, repo)

    def test_denial_before_storage_scan_embedding(self):
        indexer = self.indexer()
        with patch("app.ingestion.indexer.scan", side_effect=AssertionError("read")):
            with self.assertRaises(AccessDenied):
                indexer.index("bad-token", "repo")
        with patch.object(indexer, "open_storage", side_effect=AssertionError("storage")):
            with self.assertRaises(AccessDenied):
                Retriever(indexer).retrieve("bad-token", "repo", "secret")
        self.assertFalse((self.base / "data").exists())

    def test_scanner_extensions_secrets_generated_binary_and_large(self):
        (self.root / "header.hpp").write_text("int api();")
        (self.root / "unsafe.txt").write_text("secret")
        (self.root / ".env").write_text("token=x")
        (self.root / "build").mkdir()
        (self.root / "build" / "generated.cpp").write_text("int generated();")
        (self.root / "big.c").write_text("x" * 101)
        (self.root / "binary.cpp").write_bytes(b"code\x00binary")
        (self.root / "key.cpp").write_text("-----BEGIN RSA PRIVATE KEY-----")
        (self.root / "generated.cpp").write_text("// automatically generated\nint generated();")
        result = scan(self.scope, max_bytes=100)
        self.assertEqual(set(result.files), {"safe.cpp", "header.hpp"})
        reasons = {item["reason"] for item in result.skipped}
        self.assertTrue({"ignored_directory", "size_limit", "binary_content", "private_key_material",
                         "generated_source", "unsupported_or_secret_extension"} <= reasons)

    def test_unreadable_file_does_not_terminate_scan(self):
        real_open = os.open

        def fake_open(path, *args, **kwargs):
            if Path(path).name == "blocked.cpp":
                raise PermissionError("synthetic unreadable source")
            return real_open(path, *args, **kwargs)
        (self.root / "blocked.cpp").write_text("int blocked();")
        with patch("app.ingestion.scanner.os.open", side_effect=fake_open):
            result = scan(self.scope)
        self.assertIn("safe.cpp", result.files)
        self.assertEqual(result.summary()["scanner_status"], "degraded")
        self.assertEqual(result.failed[0]["file"], "blocked.cpp")

    def test_missing_repository_handled(self):
        self.permissions.config["repositories"]["repo"]["root"] = str(self.base / "absent")
        with self.assertRaises(FileNotFoundError):
            self.permissions.authorize(self.token, "repo")

    def test_paths_cannot_escape_or_bypass_prefix(self):
        self.permissions.config["repositories"]["repo"]["users"]["developer"] = ["allowed"]
        (self.root / "allowed").mkdir()
        (self.root / "allowed" / "yes.cpp").write_text("int yes();")
        scope = self.permissions.authorize(self.token, "repo")
        self.assertEqual(list(scan(scope).files), ["allowed/yes.cpp"])
        for path in ("../outside.cpp", "allowed/../safe.cpp", "safe.cpp", "C:/secret.cpp",
                     "allowed/yes.cpp:stream", "allowed\\yes.cpp", "/safe.cpp"):
            with self.subTest(path=path), self.assertRaises(AccessDenied):
                scope.resolve(path)

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_escape(self):
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "secret.cpp").write_text("int proprietary();")
        junction = self.root / "escape"
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True)
        self.assertEqual(made.returncode, 0, made.stderr.decode(errors="replace"))
        try:
            result = scan(self.scope)
            self.assertNotIn("escape/secret.cpp", result.files)
            self.assertTrue(any(s["file"] == "escape" for s in result.skipped))
        finally:
            # Remove only this verified fixture junction, never its target.
            self.assertEqual(junction.parent.resolve(), self.root.resolve())
            junction.rmdir()
        self.assertTrue((outside / "secret.cpp").exists())

    def test_parser_boundaries_and_unicode(self):
        text = "// café\nnamespace ecu { int pressure(int x) { return x; } }\n"
        parsed, status = chunks("repo", "snapshot", "test.cpp", text)
        self.assertEqual(status, "ok")
        target = next(c for c in parsed if c.symbol == "ecu::pressure")
        self.assertEqual(target.start_line, 2)
        self.assertEqual(target.end_line, 2)
        self.assertEqual(text.encode()[target.start_byte:target.end_byte].decode(), target.text)

    def test_cpp_class_methods_and_c(self):
        cpp, status = chunks("repo", "s", "test.cpp", "struct Sensor { int read() { return 1; } };\n")
        self.assertEqual(status, "ok")
        self.assertIn("Sensor::read", [c.symbol for c in cpp])
        c, status = chunks("repo", "s", "test.c", "int c_api(void) { return 1; }\n")
        self.assertEqual(status, "ok")
        self.assertIn("c_api", [part.symbol for part in c])

    def test_parser_failure_and_large_line_fallback(self):
        text = "int broken( {\n" + "é" * 4000
        parsed, status = chunks("repo", "s", "broken.cpp", text)
        self.assertEqual(status, "failed")
        self.assertGreater(len(parsed), 1)
        self.assertTrue(all(len(c.text.encode()) <= CHUNK_BYTES for c in parsed))
        self.assertEqual("".join(c.text for c in parsed), text)

    def test_parser_failure_does_not_abort_other_indexed_files(self):
        (self.root / "broken.cpp").write_text("int broken( {\n")
        indexer = self.indexer()
        result = indexer.index(self.token, "repo")
        self.assertEqual(result["index_status"], "degraded")
        self.assertEqual(result["parser_status"]["broken.cpp"], "failed")
        evidence = Retriever(indexer).retrieve(self.token, "repo", "safe", symbol="safe")
        self.assertEqual(evidence["target"][0]["symbol"], "safe")

    def test_retrieval_query_bound_is_enforced(self):
        indexer = self.indexer()
        for query, k in [("", 3), ("x" * 1801, 3), ("safe", 0), ("safe", 11)]:
            with self.subTest(query_length=len(query), k=k), self.assertRaises(ValueError):
                Retriever(indexer).retrieve(self.token, "repo", query, k=k)
        self.assertIsNone(indexer.catalog)

    def test_unchanged_changed_deleted_and_restart(self):
        indexer = self.indexer()
        first = indexer.index(self.token, "repo")
        previous = indexer.catalog.current(self.scope)
        second = indexer.index(self.token, "repo")
        self.assertEqual(first["snapshot"], second["snapshot"])
        self.assertEqual(second["index_status"], "unchanged")
        self.assertEqual(indexer.store.code.count(), first["chunks"])
        (self.root / "safe.cpp").write_text("int safe() { return 42; }\n")
        (self.root / "extra.cpp").write_text("int extra() { return 8; }\n")
        third = indexer.index(self.token, "repo")
        self.assertNotEqual(third["snapshot"], first["snapshot"])
        (self.root / "extra.cpp").unlink()
        fourth = indexer.index(self.token, "repo")
        self.assertEqual(indexer.store.code.count(), fourth["chunks"])
        restarted = self.indexer()
        result = Retriever(restarted).retrieve(self.token, "repo", "safe", symbol="safe")
        self.assertIn("return 42", result["target"][0]["text"])
        self.assertEqual(result["snapshot"], fourth["snapshot"])
        self.assertEqual(Retriever(restarted).retrieve(self.token, "repo", "extra", symbol="extra")["retrieval_status"], "not_found")
        self.assertIn("return 1", previous["source"]["safe.cpp"])

    def test_failed_staging_or_publication_preserves_old_snapshot(self):
        indexer = self.indexer()
        first = indexer.index(self.token, "repo")
        (self.root / "safe.cpp").write_text("int safe() { return 2; }")
        for layer in (indexer.embedder, indexer.store, indexer.catalog):
            method = "encode" if layer is indexer.embedder else "stage" if layer is indexer.store else "publish"
            with patch.object(layer, method, side_effect=RuntimeError("interrupted")):
                with self.assertRaisesRegex(RuntimeError, "previous active snapshot preserved"):
                    indexer.index(self.token, "repo")
            self.assertEqual(indexer.catalog.current(self.scope)["snapshot"], first["snapshot"])
        result = Retriever(indexer).retrieve(self.token, "repo", "safe", symbol="safe")
        self.assertEqual(result["target"][0]["text"], "int safe() { return 1; }")

    def test_ambiguity_missing_target_and_path_denial(self):
        (self.root / "other.cpp").write_text("int safe(int x) { return x; }")
        indexer = self.indexer()
        indexer.index(self.token, "repo")
        retriever = Retriever(indexer)
        self.assertEqual(retriever.retrieve(self.token, "repo", "safe", symbol="safe")["retrieval_status"], "ambiguous")
        result = retriever.retrieve(self.token, "repo", "safe", file="safe.cpp", symbol="safe")
        self.assertEqual(len(result["target"]), 1)
        self.assertEqual(retriever.retrieve(self.token, "repo", "absent", symbol="absent")["retrieval_status"], "not_found")
        with self.assertRaises(AccessDenied):
            retriever.retrieve(self.token, "repo", "secret", file="../secret.cpp")

    def test_git_metadata_not_required(self):
        indexer = self.indexer()
        first = indexer.index(self.token, "repo")
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref: refs/heads/demo")
        self.assertEqual(first["snapshot"], indexer.index(self.token, "repo")["snapshot"])

    def test_storage_inside_repository_rejected(self):
        indexer = Indexer(self.permissions, self.root / ".data", TestEmbedder(), self.rules)
        with self.assertRaises(ValueError):
            indexer.index(self.token, "repo")

    def test_scope_change_does_not_expose_old_manifest(self):
        indexer = self.indexer()
        indexer.index(self.token, "repo")
        (self.root / "restricted").mkdir()
        self.permissions.config["repositories"]["repo"]["users"]["developer"] = ["restricted"]
        with self.assertRaisesRegex(ValueError, "No active index"):
            Retriever(indexer).retrieve(self.token, "repo", "safe")

    def test_demo_corpus_labels_and_ids(self):
        root = Path(__file__).resolve().parents[1]
        labels = json.loads((root / "tests/fixtures/expected_defects.json").read_text())
        symbols = set()
        for path in (root / "demo_ecu/src").glob("*.cpp"):
            parsed, status = chunks("demo", "s", path.name, path.read_text())
            self.assertEqual(status, "ok", path.name)
            symbols.update(c.symbol for c in parsed if c.symbol)
            ids = [c.chunk_id for c in parsed]
            self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(symbols, set(labels))

    def test_rules_metadata_and_duplicate_rejection(self):
        text = self.rules.read_text()
        rules = rule_records(text, "repo", "s")
        self.assertEqual(rules[0]["title"], "Pointers")
        self.assertEqual(rules[0]["category"], "pointer")
        self.assertEqual(rules[0]["start_line"], 1)
        with self.assertRaises(ValueError):
            rule_records(text + text, "repo", "s")
        with self.assertRaises(ValueError):
            rule_records("RULE BAD-001\nMissing title/category", "repo", "s")

    def test_failed_storage_initialization_can_retry(self):
        indexer = self.indexer()
        with patch("app.ingestion.indexer.VectorStore", side_effect=RuntimeError("initialization interrupted")):
            with self.assertRaises(RuntimeError):
                indexer.index(self.token, "repo")
        self.assertIsNone(indexer.catalog)
        self.assertEqual(indexer.index(self.token, "repo")["index_status"], "ok")

    def test_changed_embedding_identity_requires_rebuild(self):
        indexer = self.indexer()
        indexer.index(self.token, "repo")
        indexer.embedder.identity = "different-model"
        with self.assertRaisesRegex(ValueError, "embedding identity mismatch"):
            Retriever(indexer).retrieve(self.token, "repo", "safe")


if __name__ == "__main__":
    unittest.main()
