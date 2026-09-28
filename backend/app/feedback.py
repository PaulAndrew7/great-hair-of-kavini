"""SQLite feedback store. Parameterised statements only; feedback never retrains ranking."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at    TEXT NOT NULL,
    course_id     TEXT NOT NULL,
    label         TEXT NOT NULL CHECK (label IN ('relevant','not_relevant','too_advanced','too_basic','already_learned')),
    comment       TEXT,
    request_id    TEXT,
    goal          TEXT,
    goal_track    TEXT,
    known_skills  TEXT NOT NULL,
    simulated_skills TEXT NOT NULL,
    is_simulation INTEGER NOT NULL,
    data_version  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_course ON feedback(course_id);
"""


class FeedbackStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def add(self, *, course_id: str, label: str, comment: str | None, request_id: str | None, goal: str | None,
            goal_track: str | None, known_skills: list[str], simulated_skills: list[str], is_simulation: bool,
            data_version: str) -> tuple[int, str]:
        created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO feedback (created_at, course_id, label, comment, request_id, goal, goal_track, "
                "known_skills, simulated_skills, is_simulation, data_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (created, course_id, label, (comment or "").strip() or None, request_id, goal, goal_track,
                 json.dumps(known_skills), json.dumps(simulated_skills), int(is_simulation), data_version),
            )
            return int(cur.lastrowid), created

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute("SELECT label, COUNT(*) FROM feedback GROUP BY label").fetchall()
        return {label: n for label, n in rows}
