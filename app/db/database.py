import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import psycopg

SCHEMA = """
CREATE TABLE IF NOT EXISTS repositories (id TEXT PRIMARY KEY, root TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS repository_permissions (
    repository TEXT NOT NULL, user_id TEXT NOT NULL, scope_key TEXT NOT NULL, prefixes TEXT NOT NULL,
    PRIMARY KEY(repository,user_id,scope_key));
CREATE TABLE IF NOT EXISTS snapshots (
    repository TEXT NOT NULL, snapshot TEXT NOT NULL, scope_key TEXT NOT NULL,
    manifest TEXT NOT NULL, PRIMARY KEY(repository,snapshot));
CREATE TABLE IF NOT EXISTS active (
    repository TEXT NOT NULL, scope_key TEXT NOT NULL, snapshot TEXT NOT NULL,
    PRIMARY KEY(repository,scope_key));
CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY, repository TEXT NOT NULL, scope_key TEXT NOT NULL,
    snapshot TEXT NOT NULL, "user" TEXT NOT NULL, created TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS findings (
    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, repository TEXT NOT NULL,
    scope_key TEXT NOT NULL, body TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES analysis_runs(id));
CREATE TABLE IF NOT EXISTS reviews (
    finding_id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(finding_id,revision), FOREIGN KEY(finding_id) REFERENCES findings(id));
CREATE TABLE IF NOT EXISTS repository_runs (
    id TEXT PRIMARY KEY, repository TEXT NOT NULL, scope_key TEXT NOT NULL,
    snapshot TEXT NOT NULL, created TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS index_events (
    repository TEXT NOT NULL, scope_key TEXT NOT NULL, body TEXT NOT NULL,
    PRIMARY KEY(repository,scope_key));
"""
TABLES = ("repositories", "users", "repository_permissions", "snapshots", "active", "analysis_runs", "findings", "reviews", "repository_runs", "index_events")


class Connection:
    def __init__(self, db, postgres):
        self.db, self.postgres = db, postgres

    def execute(self, sql, parameters=()):
        return self.db.execute(sql.replace("?", "%s") if self.postgres else sql, parameters)


class Catalog:
    def __init__(self, path, database_url=None):
        self.path = Path(path)
        self.database_url = database_url
        if database_url and not database_url.startswith("postgresql://"):
            raise ValueError("Database URL must use PostgreSQL")
        if not database_url:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            for statement in SCHEMA.split(";"):
                if statement.strip():
                    db.execute(statement)

    @contextmanager
    def connect(self, write=False):
        if self.database_url:
            with psycopg.connect(self.database_url, connect_timeout=5) as db:
                yield Connection(db, True)
        else:
            db = sqlite3.connect(self.path, timeout=30)
            db.execute("PRAGMA foreign_keys=ON")
            try:
                if write:
                    db.execute("BEGIN IMMEDIATE")
                with db:
                    yield Connection(db, False)
            finally:
                db.close()

    def remember_scope(self, scope, db):
        # Audit observations only. Credential configuration stays authoritative.
        db.execute("INSERT INTO repositories VALUES(?,?) ON CONFLICT(id) DO UPDATE SET root=excluded.root",
                   (scope.repository, str(scope.root)))
        db.execute("INSERT INTO users VALUES(?) ON CONFLICT(id) DO NOTHING", (scope.user,))
        db.execute("INSERT INTO repository_permissions VALUES(?,?,?,?) ON CONFLICT DO NOTHING",
                   (scope.repository, scope.user, scope.key, json.dumps(scope.prefixes)))

    def snapshot(self, scope, snapshot):
        with self.connect() as db:
            row = db.execute("SELECT manifest FROM snapshots WHERE repository=? AND snapshot=? AND scope_key=?",
                             (scope.repository, snapshot, scope.key)).fetchone()
        if row is None:
            raise ValueError("Captured snapshot unavailable in authorized scope")
        return json.loads(row[0])

    def current(self, scope):
        with self.connect() as db:
            row = db.execute("SELECT s.manifest FROM snapshots s JOIN active a ON "
                             "s.repository=a.repository AND s.snapshot=a.snapshot "
                             "WHERE a.repository=? AND a.scope_key=?", (scope.repository, scope.key)).fetchone()
        return json.loads(row[0]) if row else None

    def publish(self, scope, manifest):
        with self.connect(write=True) as db:
            self.remember_scope(scope, db)
            db.execute("INSERT INTO snapshots VALUES(?,?,?,?) ON CONFLICT(repository,snapshot) DO NOTHING",
                       (scope.repository, manifest["snapshot"], scope.key, json.dumps(manifest)))
            db.execute("INSERT INTO active VALUES(?,?,?) ON CONFLICT(repository,scope_key) DO UPDATE SET snapshot=excluded.snapshot",
                       (scope.repository, scope.key, manifest["snapshot"]))

    def save_run(self, scope, run):
        with self.connect(write=True) as db:
            self.remember_scope(scope, db)
            db.execute("INSERT INTO analysis_runs VALUES(?,?,?,?,?,?,?)",
                       (run["id"], scope.repository, scope.key, run["snapshot"], scope.user,
                        run["created"], json.dumps(run)))
            for finding in run["findings"]:
                db.execute("INSERT INTO findings VALUES(?,?,?,?,?)", (finding["id"], run["id"],
                           scope.repository, scope.key, json.dumps(finding)))

    def findings(self, scope, finding_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT f.body FROM findings f JOIN analysis_runs a ON a.id=f.run_id "
                              "WHERE f.repository=? AND f.scope_key=? AND (CAST(? AS TEXT) IS NULL OR f.id=?) "
                              "ORDER BY a.created DESC,f.id DESC LIMIT 100",
                              (scope.repository, scope.key, finding_id, finding_id)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def runs(self, scope, run_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM analysis_runs WHERE repository=? AND scope_key=? "
                              "AND (CAST(? AS TEXT) IS NULL OR id=?) ORDER BY created DESC,id DESC LIMIT 100",
                              (scope.repository, scope.key, run_id, run_id)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def history(self, scope, finding_id):
        with self.connect() as db:
            rows = db.execute("SELECT r.body FROM reviews r JOIN findings f ON f.id=r.finding_id "
                              "WHERE f.repository=? AND f.scope_key=? AND f.id=? ORDER BY r.revision",
                              (scope.repository, scope.key, finding_id)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def approved_findings(self, scope):
        action = "CAST(r.body AS JSONB)->>'action'" if self.database_url else "json_extract(r.body,'$.action')"
        with self.connect() as db:
            rows = db.execute("SELECT f.body FROM findings f JOIN analysis_runs a ON a.id=f.run_id "
                "JOIN reviews r ON r.finding_id=f.id AND r.revision=(SELECT MAX(revision) FROM reviews WHERE finding_id=f.id) "
                "WHERE f.repository=? AND f.scope_key=? AND " + action + " IN ('ACCEPTED','EDITED') "
                "ORDER BY a.created DESC,f.id DESC LIMIT 100", (scope.repository, scope.key)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_review(self, scope, finding_id, decision, expected_revision):
        with self.connect(write=True) as db:
            suffix = " FOR UPDATE" if self.database_url else ""
            found = db.execute("SELECT id FROM findings WHERE repository=? AND scope_key=? AND id=?" + suffix,
                               (scope.repository, scope.key, finding_id)).fetchone()
            if not found:
                raise ValueError("Finding unavailable in authorized scope")
            revision = db.execute("SELECT COALESCE(MAX(revision),0) FROM reviews WHERE finding_id=?", (finding_id,)).fetchone()[0]
            if revision != expected_revision:
                raise ValueError("Reviewer history changed; reload before deciding")
            self.remember_scope(scope, db)
            decision = dict(decision, revision=revision + 1, finding_id=finding_id)
            db.execute("INSERT INTO reviews VALUES(?,?,?)", (finding_id, revision + 1, json.dumps(decision)))
        return decision

    def save_repository_run(self, scope, run):
        with self.connect(write=True) as db:
            db.execute("INSERT INTO repository_runs VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (run["id"], scope.repository, scope.key, run["snapshot"], run["created"], json.dumps(run)))

    def repository_runs(self, scope, run_id=None):
        with self.connect() as db:
            rows = db.execute("SELECT body FROM repository_runs WHERE repository=? AND scope_key=? "
                "AND (CAST(? AS TEXT) IS NULL OR id=?) ORDER BY created DESC,id DESC LIMIT 100",
                (scope.repository, scope.key, run_id, run_id)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def record_index(self, scope, event):
        with self.connect(write=True) as db:
            db.execute("INSERT INTO index_events VALUES(?,?,?) ON CONFLICT(repository,scope_key) DO UPDATE SET body=excluded.body",
                       (scope.repository, scope.key, json.dumps(event)))

    def last_index(self, scope):
        with self.connect() as db:
            row = db.execute("SELECT body FROM index_events WHERE repository=? AND scope_key=?", (scope.repository, scope.key)).fetchone()
        return json.loads(row[0]) if row else None
