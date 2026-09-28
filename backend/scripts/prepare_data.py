"""Stage 1: clean the frozen raw CSV into data/processed/courses.json.

Usage (from backend/):  .venv/Scripts/python scripts/prepare_data.py
Re-running on the same snapshot produces byte-identical output.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.cleaning import build_courses  # noqa: E402


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def main() -> None:
    if not config.RAW_CSV.exists():
        sys.exit(f"Raw CSV not found at {config.RAW_CSV}. See README 'Dataset' to download it.")
    df = pd.read_csv(config.RAW_CSV, dtype=str, keep_default_na=False, encoding="utf-8")
    df.columns = [c.strip() for c in df.columns]
    rows = df.to_dict(orient="records")

    aliases = load_json(config.SKILL_ALIASES_JSON, {"aliases": {}})["aliases"]
    goal_skills = load_json(config.GOAL_SKILLS_JSON, None)
    overrides = load_json(config.COURSE_OVERRIDES_JSON, {"overrides": {}})["overrides"]

    courses, report = build_courses(rows, aliases, goal_skills, overrides, source_file=config.RAW_CSV.name)
    report = {
        "source": {**config.SOURCE, "sha256": sha256(config.RAW_CSV), "columns": list(df.columns)},
        "preprocessing_version": config.PREPROCESSING_VERSION,
        **report,
    }

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    config.COURSES_JSON.write_text(json.dumps(courses, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    config.DATA_QUALITY_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"courses: {len(courses)} written to {config.COURSES_JSON}")
    print(json.dumps({k: report[k] for k in ("input_rows", "output_courses", "dropped", "missing", "difficulty")}, indent=2))


if __name__ == "__main__":
    main()
