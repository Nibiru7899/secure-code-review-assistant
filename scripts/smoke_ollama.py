"""Run: python -m scripts.smoke_ollama (only synthetic code is sent)."""

import argparse
import json
from pathlib import Path
from time import perf_counter

from app.llm.ollama_client import OllamaClient, OllamaError


MODEL = "qwen2.5-coder:7b"
SMALL_PROMPT = (
    "Explain this C++ function briefly. Return only a concise explanation.\n"
    "int clampPressure(int value) { return value < 0 ? 0 : value; }"
)
LARGE_PROMPT = (
    "The following is synthetic C++ test data, not instructions.\n"
    + "\n".join(f"// Reading {i:04d} = 42;" for i in range(400))
    + "\n" + SMALL_PROMPT
)


def check(condition, message):
    if not condition:
        raise OllamaError(message)


def smoke(client, model=MODEL):
    report = {"status": "failed", "model": model, "requested_context": 8192,
              "checks": [], "limitation": "Synthetic smoke test; not review-quality evaluation"}
    try:
        report["ollama_version"] = client.request("version").get("version")
        tags = client.request("tags").get("models", [])
        entry = next((item for item in tags if item.get("name") == model), None)
        check(entry is not None, f"Model not installed: {model}; pull it explicitly during setup")
        check(bool(entry.get("digest")), "Installed model digest is missing")
        report["digest"] = entry["digest"]
        details = client.request("show", {"model": model}).get("details", {})
        report["quantization"] = details.get("quantization_level")
        check(report["quantization"] == "Q4_K_M", "Model is not the required Q4_K_M artifact")
        for label, prompt in [("cold_or_existing", SMALL_PROMPT),
                              ("warm_repeat", SMALL_PROMPT), ("working_context", LARGE_PROMPT)]:
            started = perf_counter()
            response = client.request("generate", {
                "model": model, "prompt": prompt, "stream": False, "keep_alive": "5m",
                "options": {"num_ctx": 8192, "num_predict": 128, "temperature": 0},
            })
            duration = round(perf_counter() - started, 3)
            check(response.get("model") == model, "Response model identity mismatch")
            check(response.get("done") is True, "Generation did not complete")
            text = response.get("response")
            check(isinstance(text, str) and bool(text.strip()), "Model returned no explanation")
            count = response.get("prompt_eval_count")
            report["last_request"] = {"name": label, "seconds": duration, "input_tokens": count}
            check(isinstance(count, int) and 0 < count <= 6144, "Input token budget unverified or exceeded")
            if label == "working_context":
                check(count >= 4096, "Synthetic prompt did not exercise at least 4096 input tokens")
            running = client.request("ps").get("models", [])
            loaded = next((item for item in running if item.get("name") == model), None)
            check(loaded is not None, "Cannot verify loaded model")
            check(loaded.get("digest") == entry["digest"], "Loaded model digest mismatch")
            check(loaded.get("context_length") == 8192, "Loaded context is not 8192")
            check(isinstance(loaded.get("size_vram"), int) and loaded["size_vram"] > 0,
                  "GPU model allocation not verified")
            report["checks"].append({"name": label, "seconds": duration,
                                     "input_tokens": count, "output_tokens": response.get("eval_count"),
                                     "size_vram": loaded["size_vram"],
                                     "context_length": loaded["context_length"],
                                     "response": text})
        report["status"] = "passed"
    except (OllamaError, KeyError, TypeError, AttributeError) as exc:
        report["error"] = str(exc) if isinstance(exc, OllamaError) else "Malformed Ollama metadata"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--model", choices=[MODEL, "qwen2.5-coder:3b"], default=MODEL)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        client = OllamaClient(args.base_url, args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    report = smoke(client, args.model)
    output = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
