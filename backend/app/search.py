"""Keyword (BM25) and semantic retrieval over one eligible course set, fused by RRF."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi

from . import config
from .catalog import Catalog, bm25_text

STOPWORDS = frozenset(
    """a an and are as at be but by can do for from get have help how i i'm im in into is it its
    learn me my next of on or so some start that the this to want what which will with you your
    would like know about move become need should take what's""".split()
)
_TOKEN = re.compile(r"[a-z0-9]+(?:[+#]+)?")


def tokenize(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(text.lower()):
        if token in STOPWORDS or len(token) < 2 and token not in ("r", "c"):
            continue
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


@dataclass
class Filters:
    difficulty: str | None = None
    organization: str | None = None
    min_rating: float | None = None

    def active(self) -> dict[str, Any]:
        return {k: v for k, v in (("difficulty", self.difficulty), ("organization", self.organization),
                                  ("min_rating", self.min_rating)) if v not in (None, "")}


@dataclass
class Hit:
    pos: int
    course_id: str
    fused_rank: int = 0
    rrf: float = 0.0
    bm25_rank: int | None = None
    bm25_score: float | None = None
    semantic_rank: int | None = None
    semantic_similarity: float | None = None
    matched_terms: list[str] = field(default_factory=list)


class Embedder:
    """Wraps the pinned sentence-transformer; loads from the local cache only."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            config.MODEL_NAME, revision=config.MODEL_REVISION, cache_folder=str(config.MODEL_DIR),
            device="cpu", local_files_only=True,
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


class SearchEngine:
    def __init__(self, catalog: Catalog, embedder: Embedder | None) -> None:
        self.catalog = catalog
        self.embedder = embedder
        self.doc_tokens = [tokenize(bm25_text(c)) for c in catalog.courses]
        self.doc_token_sets = [set(t) for t in self.doc_tokens]
        self.bm25 = BM25Okapi(self.doc_tokens)
        self.ids = np.array([c["course_id"] for c in catalog.courses])

    @property
    def mode(self) -> str:
        return "hybrid" if self.embedder is not None else "keyword_only"

    # Filters ---------------------------------------------------------------
    def eligible(self, filters: Filters) -> np.ndarray:
        mask = np.ones(len(self.catalog.courses), dtype=bool)
        if filters.difficulty:
            mask &= self.catalog.difficulty == filters.difficulty  # Unknown never satisfies an explicit filter
        if filters.organization:
            mask &= self.catalog.org_key == filters.organization.casefold()
        if filters.min_rating is not None:
            with np.errstate(invalid="ignore"):
                mask &= np.nan_to_num(self.catalog.rating, nan=-1.0) >= filters.min_rating
        return mask

    # Channels ----------------------------------------------------------------
    def keyword(self, query: str, mask: np.ndarray, depth: int = config.CHANNEL_DEPTH) -> list[tuple[int, float, list[str]]]:
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self.bm25.get_scores(q_tokens)
        order = np.lexsort((self.ids, -scores))  # score desc, course_id asc for determinism
        out = []
        unique_q = list(dict.fromkeys(q_tokens))
        for pos in order:
            if len(out) >= depth:
                break
            if not mask[pos] or scores[pos] <= 0:
                continue
            matched = [t for t in unique_q if t in self.doc_token_sets[pos]]
            if not matched:  # zero-evidence hits are excluded
                continue
            out.append((int(pos), float(scores[pos]), matched))
        return out

    def encode_query(self, query: str) -> np.ndarray | None:
        if self.embedder is None or not query.strip():
            return None
        return self.embedder.encode([query])[0]

    def semantic(self, query_vec: np.ndarray | None, mask: np.ndarray, depth: int = config.CHANNEL_DEPTH,
                 min_similarity: float = config.SEMANTIC_MIN_SIMILARITY) -> list[tuple[int, float]]:
        if query_vec is None:
            return []
        sims = self.catalog.embeddings @ query_vec
        sims = np.where(mask, sims, -1.0)
        order = np.lexsort((self.ids, -sims))
        out = []
        for pos in order[:depth]:
            if sims[pos] < min_similarity:
                break
            out.append((int(pos), float(sims[pos])))
        return out

    # Fusion ----------------------------------------------------------------
    def hybrid(self, query: str, filters: Filters, depth: int = config.CHANNEL_DEPTH,
               query_vec: np.ndarray | None = None, mode: str = "hybrid") -> list[Hit]:
        mask = self.eligible(filters)
        hits: dict[int, Hit] = {}
        if mode in ("hybrid", "bm25"):
            for rank, (pos, score, matched) in enumerate(self.keyword(query, mask, depth), start=1):
                hit = hits.setdefault(pos, Hit(pos, self.catalog.courses[pos]["course_id"]))
                hit.bm25_rank, hit.bm25_score, hit.matched_terms = rank, score, matched
                hit.rrf += 1.0 / (config.RRF_K + rank)
        if mode in ("hybrid", "semantic"):
            if query_vec is None:
                query_vec = self.encode_query(query)
            for rank, (pos, sim) in enumerate(self.semantic(query_vec, mask, depth), start=1):
                hit = hits.setdefault(pos, Hit(pos, self.catalog.courses[pos]["course_id"]))
                hit.semantic_rank, hit.semantic_similarity = rank, sim
                hit.rrf += 1.0 / (config.RRF_K + rank)
        ordered = sorted(hits.values(), key=lambda h: (-h.rrf, h.course_id))
        for i, hit in enumerate(ordered, start=1):
            hit.fused_rank = i
        return ordered

    def search(self, query: str, mode: str, filters: Filters, top_k: int) -> tuple[list[Hit], int]:
        if mode != "bm25" and self.embedder is None:
            raise RuntimeError("Semantic retrieval is unavailable: the embedding model is not loaded.")
        eligible_count = int(self.eligible(filters).sum())
        return self.hybrid(query, filters, mode=mode)[:top_k], eligible_count
