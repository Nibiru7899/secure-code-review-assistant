"""Offline SQLite-to-PostgreSQL copy. Retain SQLite for rollback; never overwrite a nonempty target."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from contextlib import closing
import sqlite3

from app.db.database import Catalog, TABLES


def table_rows(catalog):
    result = {}
    with catalog.connect() as db:
        for table in TABLES:
            result[table] = sorted(db.execute("SELECT * FROM " + table).fetchall(), key=repr)
    return result


def content_digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def migrate(source, target_url, backup):
    source, backup = Path(source).resolve(strict=True), Path(backup).resolve()
    if source == backup or backup.exists():
        raise ValueError("Backup must be a new separate file")
    backup.parent.mkdir(parents=True, exist_ok=True)
    # Consistent SQLite backup, including any committed WAL pages.
    with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as src, closing(sqlite3.connect(backup)) as dst:
        with dst:
            src.backup(dst)
    original = Catalog(backup)
    before = table_rows(original)
    target = Catalog(source, target_url)
    with target.connect(write=True) as db:
        db.execute("LOCK TABLE " + ",".join(TABLES) + " IN EXCLUSIVE MODE")
        if any(db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] for table in TABLES):
            raise ValueError("Migration target is not empty; no rows changed")
        for table in TABLES:
            for row in before[table]:
                placeholders = ",".join("?" for _ in row)
                db.execute("INSERT INTO " + table + " VALUES(" + placeholders + ")", row)
        # Validate inside the same transaction. Exceptions roll back all copied rows.
        after = {table: sorted(db.execute("SELECT * FROM " + table).fetchall(), key=repr) for table in TABLES}
        if before != after:
            raise ValueError("Migration verification failed; target transaction rolled back")
    return {"status": "verified", "counts": {table: len(rows) for table, rows in before.items()},
            "content_sha256": content_digest(before), "sqlite_backup": str(backup),
            "rollback": "Stop API and restore the SQLite configuration; the original SQLite was never modified. Decisions made after cutover need a separate reverse migration."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        url = os.environ.get("DATABASE_URL")
        if os.environ.get("DATABASE_URL_FILE"):
            url = Path(os.environ["DATABASE_URL_FILE"]).read_text().strip()
        if not url:
            raise ValueError("Configure a local PostgreSQL target")
        result = migrate(args.sqlite, url, args.backup)
    except Exception:
        # Never echo connection strings/passwords through tracebacks.
        raise SystemExit("Migration failed. Check database availability, empty target, and local backup; credentials were not logged.") from None
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
