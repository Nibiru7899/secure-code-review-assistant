"""Explicit local Docker configuration; reuse credentials, never print secrets."""
import json
from pathlib import Path
import secrets


def prepare():
    project = Path(__file__).resolve().parents[1]
    destination = project / ".local/docker"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / "postgres-password.txt"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    config = json.loads((project / ".local/access.json").read_text())
    demo = config["repositories"]["demo_ecu"]
    # Only the demo is mounted; do not carry other host repositories into Docker.
    config["repositories"] = {"demo_ecu": dict(demo, root="/repositories/demo_ecu")}
    (destination / "access.json").write_text(json.dumps(config), encoding="utf-8")
    password = path.read_text().strip()
    (destination / "database-url.txt").write_text(f"postgresql://review:{password}@postgres:5432/review", encoding="utf-8")
    print("Local Docker secret files prepared. Credential values were not displayed.")


if __name__ == "__main__":
    prepare()
