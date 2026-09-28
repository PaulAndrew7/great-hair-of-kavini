"""Stage 0: download the pinned dataset snapshot and embedding model. Run once; everything after works offline.

Usage (from backend/):  .venv/Scripts/python scripts/fetch_inputs.py
Skips files that are already present and verified.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402

# Hash of the snapshot every processed artifact and evaluation result in this repository was built from.
EXPECTED_CSV_SHA256 = "997a4813b0b9f0d808512f5370a85ae710ed7ecd06dc11c3029253310c3ed4a7"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fetch_csv() -> None:
    from huggingface_hub import hf_hub_download

    target = config.RAW_CSV
    if target.exists() and sha256(target) == EXPECTED_CSV_SHA256:
        print(f"dataset: present and verified ({target})")
        return
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    cached = hf_hub_download(config.SOURCE["name"], config.SOURCE["file"], repo_type="dataset",
                             revision=config.SOURCE["revision"])
    shutil.copyfile(cached, target)
    actual = sha256(target)
    if actual != EXPECTED_CSV_SHA256:
        sys.exit(f"dataset hash mismatch: expected {EXPECTED_CSV_SHA256}, got {actual}. Do not build on this file.")
    print(f"dataset: downloaded and verified ({target})")


def fetch_model() -> None:
    from huggingface_hub import snapshot_download

    # Only the PyTorch weights and configs Sentence Transformers loads (~90 MB); the repo also holds ONNX/OpenVINO/TF copies.
    wanted = ["*.json", "model.safetensors", "vocab.txt", "README.md"]
    skip = ["onnx/*", "openvino/*"]
    path = snapshot_download(config.MODEL_NAME, revision=config.MODEL_REVISION, cache_dir=str(config.MODEL_DIR),
                             allow_patterns=wanted, ignore_patterns=skip)
    print(f"model: {config.MODEL_NAME} @ {config.MODEL_REVISION[:12]} ready ({path})")


if __name__ == "__main__":
    fetch_csv()
    fetch_model()
