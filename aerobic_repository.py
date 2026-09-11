"""SQLite persistence for Garmin source data and reproducible aerobic scores."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
import json
import sqlite3


class AerobicRepository:
    def __init__(self, db_path: str | Path = "data/garmin_cache.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_database(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS aerobic_activities (
                    activity_id TEXT PRIMARY KEY,
                    start_time_gmt TEXT NOT NULL,
                    activity_type TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    detail_json TEXT,
                    source_fetched_at TEXT NOT NULL,
                    source_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_aerobic_activities_start
                    ON aerobic_activities(start_time_gmt);
                CREATE TABLE IF NOT EXISTS aerobic_wellness (
                    date TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    source_fetched_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS aerobic_activity_metrics (
                    activity_id TEXT NOT NULL,
                    settings_hash TEXT NOT NULL,
                    source_hash TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    PRIMARY KEY (activity_id, settings_hash)
                );
                CREATE TABLE IF NOT EXISTS aerobic_week_scores (
                    week_key TEXT NOT NULL,
                    sport_filter TEXT NOT NULL,
                    settings_hash TEXT NOT NULL,
                    source_revision TEXT NOT NULL,
                    score_json TEXT NOT NULL,
                    settings_json TEXT NOT NULL,
                    calculated_at TEXT NOT NULL,
                    PRIMARY KEY (week_key, sport_filter, settings_hash, source_revision)
                );
                CREATE TABLE IF NOT EXISTS aerobic_import_days (
                    date TEXT PRIMARY KEY,
                    activities_imported_at TEXT NOT NULL,
                    wellness_imported_at TEXT
                );
                CREATE TABLE IF NOT EXISTS aerobic_sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    error TEXT
                );
            """)

    def upsert_activity(self, summary: dict[str, Any], detail: Optional[dict[str, Any]]) -> None:
        activity_id = str(summary["activityId"])
        activity_type = (summary.get("activityType") or {}).get("typeKey", "unknown")
        start = summary.get("startTimeGMT") or summary.get("beginTimestamp") or summary.get("startTimeLocal")
        summary_json = json.dumps(summary, sort_keys=True, separators=(",", ":"))
        source_hash = __import__("hashlib").sha256(
            (summary_json + json.dumps(detail, sort_keys=True, separators=(",", ":"))).encode()
        ).hexdigest()
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO aerobic_activities VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(activity_id) DO UPDATE SET
                    start_time_gmt=excluded.start_time_gmt,
                    activity_type=excluded.activity_type,
                    summary_json=excluded.summary_json,
                    detail_json=excluded.detail_json,
                    source_fetched_at=excluded.source_fetched_at,
                    source_hash=excluded.source_hash
            """, (activity_id, str(start), activity_type, summary_json,
                  json.dumps(detail, separators=(",", ":")) if detail is not None else None,
                  datetime.now(timezone.utc).isoformat(), source_hash))

    def upsert_wellness(self, day: str, data: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO aerobic_wellness VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET data_json=excluded.data_json,
                    source_fetched_at=excluded.source_fetched_at
            """, (day, json.dumps(data, separators=(",", ":")), datetime.now(timezone.utc).isoformat()))

    def get_activity_metrics(self, activity_id: str, settings_hash: str,
                             source_hash: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("""
                SELECT metrics_json FROM aerobic_activity_metrics
                WHERE activity_id=? AND settings_hash=? AND source_hash=?
            """, (activity_id, settings_hash, source_hash)).fetchone()
        return json.loads(row["metrics_json"]) if row else None

    def save_activity_metrics(self, activity_id: str, settings_hash: str,
                              source_hash: str, metrics: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO aerobic_activity_metrics VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(activity_id, settings_hash) DO UPDATE SET
                    source_hash=excluded.source_hash,
                    metrics_json=excluded.metrics_json,
                    calculated_at=excluded.calculated_at
            """, (activity_id, settings_hash, source_hash,
                  json.dumps(metrics, separators=(",", ":")), datetime.now(timezone.utc).isoformat()))

    def activities_between(self, start_gmt: str, end_gmt: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM aerobic_activities
                WHERE substr(start_time_gmt, 1, 10) BETWEEN ? AND ? ORDER BY start_time_gmt
            """, (start_gmt, end_gmt)).fetchall()
        return [{"summary": json.loads(r["summary_json"]),
                 "detail": json.loads(r["detail_json"]) if r["detail_json"] else None,
                 "source_fetched_at": r["source_fetched_at"], "source_hash": r["source_hash"]}
                for r in rows]

    def wellness_between(self, start: str, end: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT data_json FROM aerobic_wellness WHERE date BETWEEN ? AND ? ORDER BY date",
                                (start, end)).fetchall()
        return [json.loads(r["data_json"]) for r in rows]

    def coverage(self, start: str, end: str) -> dict[str, Any]:
        with self._connect() as conn:
            activity_count = conn.execute(
                "SELECT COUNT(*) FROM aerobic_activities WHERE substr(start_time_gmt,1,10) BETWEEN ? AND ?",
                (start, end)).fetchone()[0]
            wellness_days = conn.execute(
                "SELECT COUNT(*) FROM aerobic_wellness WHERE date BETWEEN ? AND ?", (start, end)).fetchone()[0]
        expected = max(1, (datetime.fromisoformat(end).date() - datetime.fromisoformat(start).date()).days + 1)
        return {"activity_count": activity_count, "wellness_days": wellness_days,
                "wellness_percent": round(100 * wellness_days / expected, 1),
                "start": start, "end": end}

    def mark_imported_range(self, start: date, end: date, include_wellness: bool) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        rows = []
        current = start
        while current <= end:
            rows.append((current.isoformat(), timestamp, timestamp if include_wellness else None))
            current += timedelta(days=1)
        with self._connect() as conn:
            conn.executemany("""
                INSERT INTO aerobic_import_days VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    activities_imported_at=excluded.activities_imported_at,
                    wellness_imported_at=COALESCE(excluded.wellness_imported_at, aerobic_import_days.wellness_imported_at)
            """, rows)

    def calendar_import_status(self, start: date, end: date) -> dict[str, Any]:
        return self._import_status(start, end, "activities_imported_at")

    def wellness_import_status(self, start: date, end: date) -> dict[str, Any]:
        return self._import_status(start, end, "wellness_imported_at")

    def _import_status(self, start: date, end: date, column: str) -> dict[str, Any]:
        if column not in {"activities_imported_at", "wellness_imported_at"}:
            raise ValueError("unsupported import coverage column")
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT date FROM aerobic_import_days WHERE date BETWEEN ? AND ? AND {column} IS NOT NULL",
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        imported = {row["date"] for row in rows}
        expected = (end - start).days + 1
        missing: list[date] = []
        current = start
        while current <= end:
            if current.isoformat() not in imported:
                missing.append(current)
            current += timedelta(days=1)
        ranges = []
        index = 0
        while index < len(missing):
            range_start = missing[index]
            range_end = range_start
            index += 1
            while (index < len(missing) and missing[index] == range_end + timedelta(days=1)
                   and (missing[index] - range_start).days < 28):
                range_end = missing[index]
                index += 1
            ranges.append({"start": range_start.isoformat(), "end": range_end.isoformat()})
        return {
            "start": start.isoformat(), "end": end.isoformat(), "expected_days": expected,
            "imported_days": expected - len(missing),
            "coverage_percent": round(100 * (expected - len(missing)) / expected, 1) if expected else 100,
            "missing_ranges": ranges,
        }

    def record_sync_run(self, started_at: str, status: str, summary: dict[str, Any],
                        error: Optional[str] = None) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO aerobic_sync_runs
                    (started_at, finished_at, status, summary_json, error)
                VALUES (?, ?, ?, ?, ?)
            """, (started_at, datetime.now(timezone.utc).isoformat(), status,
                  json.dumps(summary, separators=(",", ":")), error))

    def latest_sync_run(self) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("""
                SELECT started_at, finished_at, status, summary_json, error
                FROM aerobic_sync_runs ORDER BY id DESC LIMIT 1
            """).fetchone()
        if row is None:
            return None
        return {
            "started_at": row["started_at"], "finished_at": row["finished_at"],
            "status": row["status"], "summary": json.loads(row["summary_json"]),
            "error": row["error"],
        }

    def source_revision(self, start: str, end: str) -> str:
        with self._connect() as conn:
            a = conn.execute("SELECT COALESCE(MAX(source_fetched_at),'') FROM aerobic_activities WHERE substr(start_time_gmt,1,10) BETWEEN ? AND ?", (start, end)).fetchone()[0]
            w = conn.execute("SELECT COALESCE(MAX(source_fetched_at),'') FROM aerobic_wellness WHERE date BETWEEN ? AND ?", (start, end)).fetchone()[0]
        return f"{a}|{w}"

    def save_week_score(self, result: dict[str, Any], sport: str, settings: dict[str, Any], revision: str) -> None:
        with self._connect() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO aerobic_week_scores VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (result["week"], sport, result["settings_fingerprint"], revision,
                  json.dumps(result, separators=(",", ":")), json.dumps(settings, separators=(",", ":")),
                  datetime.now(timezone.utc).isoformat()))
