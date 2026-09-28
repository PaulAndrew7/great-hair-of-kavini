"""Stage 2: embed the cleaned catalog and write the index artifacts + manifest.

Usage (from backend/):  .venv/Scripts/python scripts/build_index.py
Downloads the pinned model into models/ on first run; afterwards works offline.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.catalog import embedding_text  # noqa: E402
from app.cleaning import first_words  # noqa: E402


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    from sentence_transformers import SentenceTransformer

    if not config.COURSES_JSON.exists():
        sys.exit("courses.json missing: run scripts/prepare_data.py first.")
    courses = json.loads(config.COURSES_JSON.read_text(encoding="utf-8"))
    quality = json.loads(config.DATA_QUALITY_JSON.read_text(encoding="utf-8"))

    model = SentenceTransformer(
        config.MODEL_NAME, revision=config.MODEL_REVISION, cache_folder=str(config.MODEL_DIR), device="cpu"
    )

    # 1. Similarity check between each course's own title/skills and its description.
    checkable = [c for c in courses if c["description"] and c["description_quality"] == "Unreviewed"]
    heads = model.encode(
        [c["title"] + (". " + ", ".join(c["skills"]) if c["skills"] else "") for c in checkable],
        batch_size=128, normalize_embeddings=True, show_progress_bar=False,
    )
    bodies = model.encode(
        [first_words(c["description"], config.EMBED_DESCRIPTION_WORDS) for c in checkable],
        batch_size=64, normalize_embeddings=True, show_progress_bar=False,
    )
    sims = (heads * bodies).sum(axis=1)
    flagged = []
    for course, sim in zip(checkable, sims):
        if sim < config.SUSPECT_DESCRIPTION_SIMILARITY:
            course["description_quality"] = "Suspect"
            course["quality_notes"].append(
                f"Description reads as unrelated to the title (similarity {sim:.2f} < {config.SUSPECT_DESCRIPTION_SIMILARITY})."
            )
            flagged.append({"course_id": course["course_id"], "title": course["title"], "similarity": round(float(sim), 3)})
    quality["title_description_similarity"] = {
        "checked": len(checkable),
        "threshold": config.SUSPECT_DESCRIPTION_SIMILARITY,
        "percentiles": {str(p): round(float(np.percentile(sims, p)), 3) for p in (1, 5, 25, 50)},
        "flagged": flagged,
    }

    # 2. Course embeddings with the recorded recipe.
    texts = [embedding_text(c) for c in courses]
    vectors = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True).astype(np.float32)
    ids = [c["course_id"] for c in courses]

    courses_bytes = json.dumps(courses, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")
    config.COURSES_JSON.write_bytes(courses_bytes)
    np.save(config.EMBEDDINGS_NPY, vectors)
    config.COURSE_IDS_JSON.write_text(json.dumps(ids), encoding="utf-8")

    quality["description_quality"] = {
        q: sum(1 for c in courses if c["description_quality"] == q) for q in ("Unreviewed", "Reviewed", "Suspect", "Missing")
    }
    config.DATA_QUALITY_JSON.write_text(json.dumps(quality, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "data_version": f"{quality['source']['sha256'][:8]}-{sha256_bytes(courses_bytes)[:8]}",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": quality["source"],
        "preprocessing_version": config.PREPROCESSING_VERSION,
        "rules": {
            p.name: sha256_bytes(p.read_bytes())[:12]
            for p in (config.SKILL_ALIASES_JSON, config.GOAL_SKILLS_JSON, config.COURSE_OVERRIDES_JSON)
        },
        "model": {"name": config.MODEL_NAME, "revision": config.MODEL_REVISION, "dimensions": int(vectors.shape[1])},
        "embedding_recipe": config.EMBEDDING_RECIPE,
        "course_count": len(courses),
        "courses_sha256": sha256_bytes(courses_bytes),
        "course_ids_sha256": sha256_bytes(config.COURSE_IDS_JSON.read_bytes()),
        "embeddings_shape": list(vectors.shape),
    }
    config.MANIFEST_JSON.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: manifest[k] for k in ("data_version", "course_count", "embeddings_shape")}, indent=2))
    print("description quality:", quality["description_quality"], "similarity-flagged:", len(flagged))


if __name__ == "__main__":
    main()
