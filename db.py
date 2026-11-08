"""SQLite log of every story seen, so nothing is posted twice."""
import sqlite3
import time

from config import DB_PATH, DEDUPE_HOURS


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.execute(
        """CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, fp TEXT, stems TEXT, headline TEXT,
            source TEXT, status TEXT, ig_id TEXT, note TEXT)"""
    )
    return c


def _jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def seen(fp: str, stems: set) -> bool:
    """True if this story (or a near-duplicate) was handled recently."""
    cutoff = time.time() - DEDUPE_HOURS * 3600
    with _conn() as c:
        rows = c.execute(
            "SELECT fp, stems FROM posts WHERE ts > ?", (cutoff,)
        ).fetchall()
    for old_fp, old_stems in rows:
        if old_fp == fp or _jaccard(stems, set(old_stems.split())) >= 0.5:
            return True
    return False


def record(fp, stems, headline, source, status, ig_id="", note=""):
    with _conn() as c:
        c.execute(
            "INSERT INTO posts (ts, fp, stems, headline, source, status, ig_id, note) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (time.time(), fp, " ".join(sorted(stems)), headline, source, status, ig_id, note),
        )


def update_status(fp, status, ig_id="", note=""):
    with _conn() as c:
        c.execute(
            "UPDATE posts SET status=?, ig_id=?, note=? WHERE fp=?",
            (status, ig_id, note, fp),
        )
