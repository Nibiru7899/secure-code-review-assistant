import hashlib
import json
import os
from pathlib import Path

MODEL_REVISION = "516f4baf13dec4ddddda8631e019b5737c8bc250"
CODE_REVISION = "3baf9e3ac750e76e8edd3019170176884695fb94"


class JinaEmbedder:
    identity = f"jina-code/{MODEL_REVISION}/{CODE_REVISION}/mean-normalized-cpu-v1"

    def __init__(self, model_dir, module_cache_dir=None):
        self.model_dir = Path(model_dir).resolve()
        self.module_cache_dir = Path(module_cache_dir).resolve() if module_cache_dir else self.model_dir.parent / "modules"
        self.model = None

    def _load(self):
        if self.model is not None:
            return
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["HF_MODULES_CACHE"] = str(self.module_cache_dir)
        try:
            manifest = json.loads((self.model_dir / "artifact.json").read_text())
            if manifest["revision"] != MODEL_REVISION or manifest["code_revision"] != CODE_REVISION:
                raise ValueError("Embedding artifact revision mismatch")
            for name, expected in manifest["files"].items():
                path = self.model_dir / name
                if not path.resolve().is_relative_to(self.model_dir):
                    raise ValueError("Embedding artifact path escape")
                if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    raise ValueError("Embedding artifact hash mismatch")
            import torch
            from transformers import AutoModel, AutoTokenizer
            torch.set_num_threads(min(4, os.cpu_count() or 1))
            self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir), local_files_only=True)
            # Custom code is pinned, hash-verified and local; no runtime Hub code.
            self.model = AutoModel.from_pretrained(str(self.model_dir), local_files_only=True,
                                                   trust_remote_code=True, use_safetensors=True)
            self.model.to("cpu").eval()
        except Exception as exc:
            self.model = None
            raise RuntimeError(f"Local embedding initialization failed: {type(exc).__name__}; run setup and inspect artifacts") from exc

    def encode(self, texts):
        self._load()
        import torch
        result = []
        for start in range(0, len(texts), 4):
            inputs = self.tokenizer(texts[start:start + 4], padding=True, truncation=False,
                                    return_tensors="pt")
            if inputs["input_ids"].shape[1] > 2048:
                raise ValueError("Embedding input exceeds bounded 2048-token limit; split evidence")
            with torch.inference_mode():
                output = self.model(**inputs)[0]
                mask = inputs["attention_mask"].unsqueeze(-1).expand(output.size()).float()
                mean = (output * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
                vectors = torch.nn.functional.normalize(mean, p=2, dim=1)
            result.extend(vectors.tolist())
        return result
