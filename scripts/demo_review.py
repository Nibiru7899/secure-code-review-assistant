"""Run an authorized local review or cited explanation without an HTTP server."""
import argparse
import json
import os
from pathlib import Path

from app.llm.schemas import TargetRequest, DiagnosticRequest
from app.main import create_app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["review_function", "review_file", "explain_function", "explain_module", "qa", "diagnostics"])
    parser.add_argument("--repository", default="demo_ecu")
    parser.add_argument("--file")
    parser.add_argument("--function")
    parser.add_argument("--question", default="")
    parser.add_argument("--diagnostic", type=Path)
    parser.add_argument("--origin", default="user-imported local evidence")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    service = create_app().state.service
    try:
        token = os.environ.get("REVIEW_TOKEN", "")
        scope = service.indexer.permissions.authorize(token, args.repository)
        service.indexer.open_storage(scope)
        manifest = service.indexer.catalog.current(scope)
        if manifest is None:
            raise ValueError("Index this authorized scope first")
        kwargs = dict(repository=args.repository, snapshot=manifest["snapshot"], file=args.file,
                      function=args.function, question=args.question)
        if args.mode == "diagnostics":
            if args.diagnostic is None:
                raise ValueError("--diagnostic local text file is required")
            if args.diagnostic.stat().st_size > 6000:
                raise ValueError("Diagnostic import exceeds 6000 bytes; select a bounded excerpt")
            request = DiagnosticRequest(**kwargs, text=args.diagnostic.read_text(encoding="utf-8"), origin=args.origin)
        else:
            request = TargetRequest(**kwargs)
        run = service.analyze(token, request, args.mode)
        output = json.dumps(run, indent=2)
        if args.report:
            args.report.write_text(output, encoding="utf-8")
        print(output)
        return 1 if run["outcome"] == "FAILED" else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({"outcome": "FAILED", "error": str(exc)}))
        return 1
    finally:
        if service.indexer.store:
            service.indexer.store.close()


if __name__ == "__main__":
    raise SystemExit(main())
