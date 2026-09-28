"""Paths and tuned constants shared by the service, scripts and tests."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("PRIOR_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
RULES_DIR = DATA_DIR / "rules"
EVAL_DIR = DATA_DIR / "evaluation"
MODEL_DIR = Path(os.environ.get("PRIOR_MODEL_DIR", REPO_ROOT / "models"))
FEEDBACK_DB = Path(os.environ.get("PRIOR_FEEDBACK_DB", REPO_ROOT / "backend" / "feedback.sqlite3"))

RAW_CSV = RAW_DIR / "coursera_course_2024.csv"
COURSES_JSON = PROCESSED_DIR / "courses.json"
EMBEDDINGS_NPY = PROCESSED_DIR / "embeddings.npy"
COURSE_IDS_JSON = PROCESSED_DIR / "course_ids.json"
MANIFEST_JSON = PROCESSED_DIR / "manifest.json"
DATA_QUALITY_JSON = PROCESSED_DIR / "data_quality.json"
EVAL_REPORT_JSON = EVAL_DIR / "report.json"

SKILL_ALIASES_JSON = RULES_DIR / "skill_aliases.json"
GOAL_SKILLS_JSON = RULES_DIR / "goal_skills.json"
COURSE_PREREQS_JSON = RULES_DIR / "course_prerequisites.json"
COURSE_OVERRIDES_JSON = RULES_DIR / "course_overrides.json"

SOURCE = {
    "name": "azrai99/coursera-course-dataset",
    "url": "https://huggingface.co/datasets/azrai99/coursera-course-dataset",
    "file": "coursera_course_2024.csv",
    "revision": "ccd36c1660fee9610d5262e7517d8397c343168b",
    "downloaded": "2026-09-28",
}

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

PREPROCESSING_VERSION = "prep-2026-09-28.1"
# Title and skills first; the description fills what remains of the model's 256 word-piece window.
EMBEDDING_RECIPE = "title. Skills: skill list. first 160 words of the validated description (omitted when Missing or Suspect)"
EMBED_DESCRIPTION_WORDS = 160

# Retrieval settings (starting configuration, see docs/design.md).
RRF_K = 60
CHANNEL_DEPTH = 50
PERSONALIZE_DEPTH = 10
# Cosine floor for the semantic channel; chosen on development queries only (docs/evaluation.md).
SEMANTIC_MIN_SIMILARITY = 0.30
# A description whose similarity to its own title and skills falls below this is flagged Suspect.
SUSPECT_DESCRIPTION_SIMILARITY = 0.12
# A tagged track skill counts as a course's primary subject when the course embedding is at least this
# close to the skill query (title evidence always counts). Below it the skill is only 'listed'.
PRIMARY_SKILL_SIMILARITY = 0.38

MAX_PATH_STEPS = 5
MAX_GOAL_CHARS = 500
MAX_COMMENT_CHARS = 1000
MAX_SKILLS_IN_PROFILE = 40

CORS_ORIGINS = [o for o in os.environ.get("PRIOR_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o]
