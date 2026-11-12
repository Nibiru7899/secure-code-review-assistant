"""Checkpoint 1 CLI; never invokes review or repository commands."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets


def create_demo_config():
    directory = Path(".local")
    directory.mkdir(exist_ok=True)
    config_path = directory / "access.json"
    token_path = directory / "demo-token.txt"
    if config_path.exists() or token_path.exists():
        raise ValueError("Demo credentials already exist; refusing to overwrite")
    token = secrets.token_urlsafe(32)
    config = {"credentials": {hashlib.sha256(token.encode()).hexdigest(): "developer1"},
              "repositories": {"demo_ecu": {"root": str(Path("demo_ecu").resolve()),
                                             "users": {"developer1": ["."]}}}}
    token_path.write_text(token, encoding="utf-8")
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"status": "created", "config": str(config_path), "token_file": str(token_path),
            "note": "Load token into REVIEW_TOKEN; restrict .local using OS permissions"}


def build_indexer(args):
    from app.security.permissions import Permissions
    from app.ingestion.indexer import Indexer
    from app.retrieval.embedder import JinaEmbedder
    return Indexer(Permissions.load(args.config), args.data, JinaEmbedder(args.model_dir), args.rules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["setup-demo", "index", "status", "retrieve"])
    parser.add_argument("--config", default=".local/access.json")
    parser.add_argument("--data", default=".local/data")
    parser.add_argument("--model-dir", default=".local/models/jina-code")
    parser.add_argument("--rules", default="rules/coding_rules.md")
    parser.add_argument("--repository", default="demo_ecu")
    parser.add_argument("--query", default="")
    parser.add_argument("--file")
    parser.add_argument("--symbol")
    parser.add_argument("--signature")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()
    indexer = None
    try:
        if args.command == "setup-demo":
            result = create_demo_config()
        else:
            # Check credentials before importing the vector/model runtime.
            from app.security.permissions import Permissions
            token = os.environ.get("REVIEW_TOKEN", "")
            scope = Permissions.load(args.config).authorize(token, args.repository)
            indexer = build_indexer(args)
            if args.command == "index":
                result = indexer.index(token, args.repository)
            elif args.command == "status":
                indexer.open_storage(scope)
                manifest = indexer.catalog.current(scope)
                result = {"repository": args.repository, "snapshot": manifest["snapshot"] if manifest else None,
                          "chunks": len(manifest["chunks"]) if manifest else 0,
                          "status": "indexed" if manifest else "not_indexed"}
            else:
                from app.retrieval.retriever import Retriever
                result = Retriever(indexer).retrieve(token, args.repository, args.query, args.file,
                                                     args.symbol, args.signature, args.top_k)
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__, "error": str(exc)}))
        return 1
    finally:
        if indexer is not None and indexer.store is not None:
            indexer.store.close()


if __name__ == "__main__":
    raise SystemExit(main())
