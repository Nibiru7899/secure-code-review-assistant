import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.db.database import Catalog
from app.llm.context import build_context, estimated_tokens
from app.llm.schemas import Finding, ReviewDecision
from app.main import create_app
from app.reviewer import decide, report
from app.retrieval.retriever import Retriever
from app.security.permissions import AccessDenied
from app.validation.evidence_validator import InvalidEvidence
import test_review as fixture


class ReviewerTests(unittest.TestCase):
    setUp = fixture.ReviewTests.setUp
    tearDown = fixture.ReviewTests.tearDown
    run_review = fixture.ReviewTests.run_review

    def decision(self, finding, action, revision=0, edited=None):
        return decide(self.indexer, self.token, finding["id"], ReviewDecision(
            repository="repo", action=action, expected_revision=revision, edited_finding=edited, note="Human review"))

    def test_accept_edit_reject_and_restart_keep_original_immutable(self):
        run = self.run_review()
        finding = run["findings"][0]
        original = copy.deepcopy(finding)
        accepted = self.decision(finding, "ACCEPTED")
        self.assertEqual((accepted["revision"], accepted["user"]), (1, "dev"))
        edited = Finding.model_validate({k: finding[k] for k in Finding.model_fields})
        edited.explanation = "Candidate null dereference; caller contract must be reviewed"
        self.decision(finding, "EDITED", 1, edited)
        self.decision(finding, "REJECTED", 2)
        self.indexer.catalog = Catalog(self.indexer.catalog.path)
        document = report(self.indexer, self.token, "repo", run["id"])
        entry = document["reviewed_findings"][0]
        self.assertEqual(entry["original"], original)
        self.assertEqual([r["action"] for r in entry["history"]], ["ACCEPTED", "EDITED", "REJECTED"])
        self.assertEqual(entry["effective_finding"]["explanation"], edited.explanation)
        self.assertEqual(entry["disposition"], "REJECTED")
        self.assertEqual(self.indexer.catalog.runs(self.scope, run["id"])[0], run)

    def test_fabricated_edited_evidence_and_concurrent_decision_rejected(self):
        run = self.run_review()
        finding = run["findings"][0]
        for field, value in [("file", "imaginary.cpp"), ("start_line", 999), ("applicable_rules", ["RES-001"])]:
            edited = Finding.model_validate({k: finding[k] for k in Finding.model_fields})
            setattr(edited, field, value)
            with self.assertRaises(InvalidEvidence):
                self.decision(finding, "EDITED", edited=edited)
        self.assertEqual(self.indexer.catalog.history(self.scope, finding["id"]), [])
        self.decision(finding, "ACCEPTED")
        with self.assertRaisesRegex(ValueError, "history changed"):
            self.decision(finding, "REJECTED")
        self.assertEqual(len(self.indexer.catalog.history(self.scope, finding["id"])), 1)

    def test_historical_review_validates_old_captured_source_after_reindex(self):
        run = self.run_review()
        (self.root / "test.cpp").write_text("int safe() { return 0; }\n")
        self.indexer.index(self.token, "repo")
        self.assertNotEqual(self.indexer.catalog.current(self.scope)["snapshot"], run["snapshot"])
        accepted = self.decision(run["findings"][0], "ACCEPTED")
        self.assertEqual(accepted["snapshot"], run["snapshot"])

    def test_approved_history_is_filtered_before_candidate_limit(self):
        run = self.run_review()
        finding = run["findings"][0]
        self.decision(finding, "ACCEPTED")
        for number in range(105):
            later = copy.deepcopy(run)
            later["id"] = "later-run-" + str(number)
            later["created"] = "2099-01-01"
            later["findings"][0].update(id="later-finding-" + str(number), run_id=later["id"])
            self.indexer.catalog.save_run(self.scope, later)
        self.assertNotIn(finding, self.indexer.catalog.findings(self.scope))
        self.assertEqual(self.indexer.catalog.approved_findings(self.scope), [finding])
        self.decision(finding, "REJECTED", 1)
        self.assertEqual(self.indexer.catalog.approved_findings(self.scope), [])

    def test_reports_reviews_and_approved_history_deny_before_storage(self):
        with TestClient(create_app(self.service)) as api, patch.object(self.indexer, "open_storage", side_effect=AssertionError("read")):
            auth = {"Authorization": "Bearer invalid"}
            for path in ["/analysis-runs?repository=repo", "/analysis-runs/none/report?repository=repo", "/approved-findings?repository=repo"]:
                self.assertEqual(api.get(path, headers=auth).status_code, 401)
            body = {"repository": "repo", "action": "ACCEPTED", "expected_revision": 0}
            self.assertEqual(api.post("/findings/none/review", json=body, headers=auth).status_code, 401)

    def test_review_report_api_success_failure_and_scope_revocation(self):
        run = self.run_review()
        identifier = run["findings"][0]["id"]
        with TestClient(create_app(self.service)) as api:
            auth = {"Authorization": "Bearer " + self.token}
            self.assertEqual(api.get("/repositories", headers=auth).json(), ["repo"])
            body = {"repository": "repo", "action": "ACCEPTED", "expected_revision": 0}
            self.assertEqual(api.post(f"/findings/{identifier}/review", json=body | {"user": "attacker"}, headers=auth).status_code, 422)
            self.assertEqual(api.post(f"/findings/{identifier}/review", json=body, headers=auth).status_code, 200)
            self.assertEqual(len(api.get("/approved-findings?repository=repo", headers=auth).json()), 1)
            self.assertEqual(api.get(f'/analysis-runs/{run["id"]}/report?repository=repo', headers=auth).json()["reviewed_findings"][0]["disposition"], "ACCEPTED")
            self.assertEqual(api.post(f"/findings/{identifier}/review", json=body, headers=auth).status_code, 409)
            with patch.object(self.indexer.catalog, "history", side_effect=RuntimeError("db down")):
                self.assertEqual(api.get(f'/analysis-runs/{run["id"]}/report?repository=repo', headers=auth).status_code, 503)
            (self.root / "limited").mkdir()
            self.permissions.config["repositories"]["repo"]["users"]["dev"] = ["limited"]
            self.assertEqual(api.get("/approved-findings?repository=repo", headers=auth).json(), [])
            self.assertEqual(api.get(f'/analysis-runs/{run["id"]}/report?repository=repo', headers=auth).status_code, 404)

    def test_bounded_review_retry_trims_optional_evidence_and_rebuilds_schema(self):
        with self.indexer.rules_file.open("a") as rules:
            rules.write("Original test guidance. " * 40)
        self.indexer.index(self.token, "repo")
        self.manifest = self.indexer.catalog.current(self.scope)
        self.request.snapshot = self.manifest["snapshot"]
        retrieved = Retriever(self.indexer).retrieve(self.token, "repo", "unsafe", file="test.cpp", symbol="unsafe")
        context = build_context("review_function", self.request, retrieved, self.analyzer.run.return_value, self.manifest)
        self.service.input_budget = estimated_tokens(context) + 180
        original_request = self.client.request.side_effect
        attempts = []
        def model(endpoint, body=None):
            result = original_request(endpoint, body)
            if endpoint == "generate":
                attempts.append(copy.deepcopy(body))
                if len(attempts) == 1:
                    invalid = json.loads(result["response"])
                    invalid["findings"][0]["applicable_rules"] = ["invented"]
                    result["response"] = json.dumps(invalid)
                else:
                    corrected = json.loads(result["response"])
                    corrected["findings"][0]["applicable_rules"] = []
                    result["response"] = json.dumps(corrected)
            return result
        self.client.request.side_effect = model
        run = self.run_review()
        self.assertEqual(run["outcome"], "CANDIDATES")
        self.assertEqual(run["model_attempts"], 2)
        self.assertLessEqual(run["corrective_input_estimate"], self.service.input_budget)
        self.assertIn("return *value;", attempts[1]["prompt"])
        self.assertEqual(attempts[1]["format"]["$defs"]["GeneratedFinding"]["properties"]["applicable_rules"]["maxItems"], 0)


class UITests(unittest.TestCase):
    def test_only_explicit_local_container_origins_are_permitted(self):
        from app.llm.ollama_client import OllamaClient
        from ui.client import API, APIError
        import os
        for url in ("http://host.docker.internal:11434", "http://example.com:11434", "http://127.0.0.1@example.com"):
            with self.assertRaises(ValueError):
                OllamaClient(url)
        self.assertEqual(OllamaClient("http://host.docker.internal:11434", allow_container_host=True).base_url,
                         "http://host.docker.internal:11434")
        with self.assertRaises(ValueError):
            OllamaClient("http://example.com:11434", allow_container_host=True)
        for url in ("not a URL", "http://example.com", "http://127.0.0.1:8000/?redirect=yes"):
            with patch.dict(os.environ, {"REVIEW_API_URL": url}), self.assertRaises(APIError):
                API("test-only")
        with patch.dict(os.environ, {"REVIEW_API_URL": "http://api:8000", "CONTAINER_LOCAL_NETWORK": "1"}):
            self.assertEqual(API("test-only").origin, "http://api:8000")

    def test_credential_boundary_and_dependency_failure_visible(self):
        app = AppTest.from_file("ui/streamlit_app.py").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        with patch("ui.client.API.request", side_effect=__import__("ui.client", fromlist=["APIError"]).APIError("Local API unavailable")):
            app.text_input(key="credential").input("invalid").run()
            next(b for b in app.button if b.label == "Sign in").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any("unavailable" in t.value for t in app.text))

    def test_ui_review_evidence_human_decisions_and_report(self):
        finding = fixture.candidate()["findings"][0] | {"id": "finding", "run_id": "run", "support": "AI-ONLY CANDIDATE", "disposition": "PENDING"}
        run = {"id": "run", "mode": "review_function", "created": "2026-10-03", "snapshot": "snapshot", "outcome": "CANDIDATES",
               "analyzer": {"status": "degraded", "version": "test"}, "limitations": ["Build configuration missing"], "claims": [],
               "evidence": [{"id": "S1", "kind": "source", "file": "test.cpp", "start_line": 1, "end_line": 3, "text": fixture.SOURCE}]}
        entry = {"original": finding, "effective_finding": finding, "history": [], "revision": 0, "disposition": "PENDING"}
        document = {"run": run, "reviewed_findings": [entry]}
        decisions = []
        submitted = []
        def request(endpoint, body=None):
            if endpoint == "/repositories":
                return ["repo"]
            if endpoint.endswith("/status"):
                return {"status": "indexed", "snapshot": "snapshot", "files": ["test.cpp"], "functions": [], "parser_status": {}}
            if "/source?" in endpoint:
                return {"text": fixture.SOURCE,"start_line":1,"end_line":3,"selection_start":1,"selection_end":3,"has_more":False,"parser_status":"ok"}
            if endpoint.startswith("/repository-reviews?"):
                return []
            if endpoint.startswith("/analysis-runs?") or endpoint.startswith("/approved-findings"):
                return []
            if endpoint.endswith("/review"):
                decisions.append(body)
                entry["revision"] += 1
                entry["disposition"] = body["action"]
                entry["history"].append(body | {"support": "AI-ONLY CANDIDATE"})
                if body["action"] == "EDITED":
                    entry["effective_finding"] = body["edited_finding"]
                return entry["history"][-1]
            if "/report?" in endpoint:
                return document
            submitted.append((endpoint, body))
            return run
        with patch("ui.client.API.request", side_effect=request):
            app = AppTest.from_file("ui/streamlit_app.py").run()
            app.text_input(key="credential").input("test-only").run()
            next(b for b in app.button if b.label == "Sign in").click().run()
            app.radio(key="navigation").set_value("Analyze Source").run()
            next(b for b in app.button if b.label in ("Review selected code", "Ask about this code")).click().run()
            self.assertFalse(app.exception)
            self.assertTrue(any("limited" in w.value for w in app.warning))
            for action in ("Accept", "Edit", "Reject"):
                app.radio(key="action-finding").set_value(action).run()
                if action == "Edit":
                    next(t for t in app.text_area if t.label == "Issue").input("Reviewer clarified issue").run()
                next(b for b in app.button if b.label == "Save reviewer decision").click().run()
                self.assertFalse(app.exception)
            self.assertEqual([d["action"] for d in decisions], ["ACCEPTED", "EDITED", "REJECTED"])
            self.assertEqual(entry["disposition"], "REJECTED")
            self.assertEqual(decisions[1]["edited_finding"]["issue"], "Reviewer clarified issue")
            self.assertEqual(decisions[1]["edited_finding"]["evidence"], finding["evidence"])
            self.assertTrue(app.get("download_button"))
            app.radio(key="task-group").set_value("Ask a Question").run()
            next(t for t in app.text_input if t.label == "Your code question").input("What does the source return?").run()
            next(b for b in app.button if b.label in ("Review selected code", "Ask about this code")).click().run()
            self.assertEqual(submitted[-1][0], "/qa")
            self.assertEqual(submitted[-1][1]["question"], "What does the source return?")


if __name__ == "__main__":
    unittest.main()
