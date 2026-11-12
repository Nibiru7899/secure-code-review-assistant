"""Reproducible isolated PostgreSQL migration, query parity, restart, and rollback checks."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
from time import sleep
from unittest.mock import patch

import psycopg

from app.db.database import Catalog, Connection
from app.security.permissions import Scope
from scripts.migrate_postgres import migrate, table_rows


def evaluate(destination):
    project = Path(__file__).resolve().parents[1]
    container = "case4-migration-test-" + secrets.token_hex(4)
    result = {"created": datetime.now(timezone.utc).isoformat(), "checks": {}}
    with tempfile.TemporaryDirectory(prefix="postgres-test-", dir=project / ".local") as directory:
        base = Path(directory)
        password = secrets.token_hex(32)
        env_file = base / "postgres.env"
        env_file.write_text("POSTGRES_PASSWORD=" + password + "\n")
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        try:
            subprocess.run(["docker", "run", "-d", "--name", container, "--env-file", str(env_file),
                "-p", f"127.0.0.1:{port}:5432", "postgres:16.13-bookworm@sha256:472efd9a66f2b2f1a5aeb18b28de74332e6ef88c2b93a1a5d812fb6db67a5f60"], check=True, capture_output=True)
            url = f"postgresql://postgres:{password}@127.0.0.1:{port}/postgres"
            for attempt in range(60):
                try:
                    with psycopg.connect(url, connect_timeout=2) as db:
                        result["server_version"] = db.execute("SELECT version()").fetchone()[0]
                    break
                except psycopg.OperationalError:
                    if attempt == 59:
                        raise
                    sleep(0.5)
            scope = Scope("reviewer", "test", base, (".",))
            source = Catalog(base / "catalog.sqlite3")
            source.publish(scope, {"repository": "test", "snapshot": "snapshot", "source": {"code.cpp": "int safe() { return 0; }"}})
            finding = {"id": "stable-finding", "run_id": "stable-run", "disposition": "PENDING"}
            run = {"id": "stable-run", "snapshot": "snapshot", "created": "2026-10-03", "findings": [finding]}
            source.save_run(scope, run)
            source.save_review(scope, finding["id"], {"action": "ACCEPTED", "user": scope.user}, 0)
            before = table_rows(source)
            migrated = migrate(source.path, url, base / "backup.sqlite3")
            target = Catalog(source.path, url)
            result["checks"]["copy_exact_all_tables"] = table_rows(target) == before
            result["checks"]["representative_queries_equal"] = all([
                source.current(scope) == target.current(scope), source.findings(scope) == target.findings(scope),
                source.runs(scope, "stable-run") == target.runs(scope, "stable-run"),
                source.history(scope, "stable-finding") == target.history(scope, "stable-finding"),
                source.approved_findings(scope) == target.approved_findings(scope),
                target.findings(replace(scope, prefixes=("limited",))) == []])
            result["counts"] = migrated["counts"]
            result["checks"]["sqlite_retained_for_rollback"] = table_rows(Catalog(source.path)) == before
            subprocess.run(["docker", "restart", container], check=True, capture_output=True)
            for attempt in range(60):
                try:
                    result["checks"]["postgres_restart_persistence"] = table_rows(target) == before
                    break
                except psycopg.OperationalError:
                    if attempt == 59:
                        raise
                    sleep(0.5)
            try:
                migrate(source.path, url, base / "nonempty-backup.sqlite3")
                result["checks"]["nonempty_target_refused"] = False
            except ValueError:
                result["checks"]["nonempty_target_refused"] = table_rows(target) == before
            # Empty only the isolated test container's tables, never operational data.
            with target.connect(write=True) as db:
                db.execute("TRUNCATE " + ",".join(before) + " CASCADE")
            original_execute = Connection.execute
            def interrupt(db, sql, parameters=()):
                if db.postgres and sql.startswith("INSERT INTO findings"):
                    raise RuntimeError("Simulated interruption")
                return original_execute(db, sql, parameters)
            try:
                with patch.object(Connection, "execute", interrupt):
                    migrate(source.path, url, base / "interrupted-backup.sqlite3")
            except RuntimeError:
                result["checks"]["interrupted_copy_rolled_back"] = not any(table_rows(target).values())
            migrate(source.path, url, base / "retry-backup.sqlite3")
            target.save_review(scope, "stable-finding", {"action": "REJECTED", "user": "reviewer"}, 1)
            result["checks"]["rejected_revision_removed_from_approved"] = target.approved_findings(scope) == []
            try:
                target.save_review(scope, "stable-finding", {"action": "ACCEPTED"}, 1)
            except ValueError:
                result["checks"]["revision_conflict_refused"] = len(target.history(scope, "stable-finding")) == 2
            result["checks"]["originals_immutable"] = target.findings(scope) == source.findings(scope)
            result["status"] = "passed" if all(result["checks"].values()) else "failed"
        finally:
            subprocess.run(["docker", "rm", "-f", "--volumes", container], capture_output=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/postgres-smoke.json"))
    evaluate(parser.parse_args().report)
