"""Explicit setup download; runtime embedding code never uses the network."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

MODEL_REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
CODE_REVISION = "3baf9e3ac750e76e8edd3019170176884695fb94"
MODEL_DIR = Path(".local/models/jina-code")


def prepare():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    files = ["config.json", "model.safetensors", "tokenizer.json", "tokenizer_config.json",
             "special_tokens_map.json", "vocab.json"]
    sources = [("jinaai/jina-embeddings-v2-base-code", MODEL_REVISION, name) for name in files]
    sources += [("jinaai/jina-bert-v2-qk-post-norm", CODE_REVISION, name)
                for name in ("configuration_bert.py", "modeling_bert.py")]
    manifest = {"model": "jinaai/jina-embeddings-v2-base-code", "revision": MODEL_REVISION,
                "code_revision": CODE_REVISION, "files": {}}
    for repo, revision, name in sources:
        destination = MODEL_DIR / name
        if not destination.exists():
            part = destination.with_suffix(destination.suffix + ".part")
            with urlopen(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", timeout=60) as response:
                with part.open("wb") as stream:
                    while block := response.read(1024 * 1024):
                        stream.write(block)
            part.replace(destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        manifest["files"][name] = digest
        print(f"Prepared {name}", flush=True)
    # The pinned model points to a separate code repository. Localize auto_map
    # to the pinned copies so offline loading cannot fetch remote Python code.
    config_path = MODEL_DIR / "config.json"
    config = json.loads(config_path.read_text())
    config["auto_map"] = {key: value.split("--")[-1] for key, value in config["auto_map"].items()}
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    manifest["files"]["config.json"] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    (MODEL_DIR / "artifact.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("Pinned local embedding artifacts ready; runtime will verify file hashes.", flush=True)


if __name__ == "__main__":
    prepare()
