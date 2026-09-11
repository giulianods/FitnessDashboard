#!/usr/bin/env python3
"""Non-interactive Garmin sync for cron or a systemd timer."""
from __future__ import annotations

import argparse
import fcntl
import json
import logging
import os
import sys
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from aerobic_base import BUCHAREST, AerobicBaseSettings
from aerobic_repository import AerobicRepository
from aerobic_service import (
    build_daily_calendar, build_dashboard, import_range, load_aerobic_settings,
)
from garmin_client import GarminClient


logger = logging.getLogger("aerobic_sync")
PROJECT_DIR = Path(__file__).resolve().parent


@contextmanager
def exclusive_sync_lock(lock_path: Path):
    """Prevent cron from starting a second sync while one is still running."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another aerobic sync is already running") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def build_sync_plan(repository: AerobicRepository, today: date, recent_days: int,
                    backfill: bool) -> dict[str, Any]:
    """Return bounded, idempotent source ranges required by a daily sync."""
    calculation_start = date(today.year, 1, 1) - timedelta(days=56)
    activity_ranges = []
    if backfill:
        activity_ranges = repository.calendar_import_status(calculation_start, today)["missing_ranges"]
    wellness_start = today - timedelta(days=34)
    wellness_ranges = repository.wellness_import_status(wellness_start, today)["missing_ranges"]
    recent_start = today - timedelta(days=recent_days - 1)
    return {
        "activity_ranges": activity_ranges,
        "wellness_ranges": wellness_ranges,
        "recent_range": {"start": recent_start.isoformat(), "end": today.isoformat()},
        "calculation_start": calculation_start.isoformat(),
        "wellness_start": wellness_start.isoformat(),
    }


def run_sync(client: GarminClient, repository: AerobicRepository, today: date,
             recent_days: int = 3, backfill: bool = True,
             settings: AerobicBaseSettings | None = None) -> dict[str, Any]:
    settings = settings or load_aerobic_settings("config.json")
    plan = build_sync_plan(repository, today, recent_days, backfill)
    summary: dict[str, Any] = {
        "date": today.isoformat(), "activity_backfill_chunks": 0,
        "wellness_backfill_chunks": 0, "recent_days": recent_days,
        "activities_imported": 0, "wellness_days_imported": 0,
        "errors": [],
    }

    def import_chunks(ranges: list[dict[str, str]], include_wellness: bool,
                      counter: str) -> None:
        for item in ranges:
            start, end = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
            try:
                logger.info("Importing %s through %s (wellness=%s)", start, end, include_wellness)
                result = import_range(client, repository, start, end, settings,
                                      include_wellness=include_wellness)
                summary[counter] += 1
                summary["activities_imported"] += result["activities"]
                summary["wellness_days_imported"] += result["wellness_days"]
            except Exception as exc:  # Continue other independent chunks and report partial status.
                logger.exception("Sync chunk failed: %s through %s", start, end)
                summary["errors"].append(f"{start}..{end}: {exc}")

    import_chunks(plan["activity_ranges"], False, "activity_backfill_chunks")
    import_chunks(plan["wellness_ranges"], True, "wellness_backfill_chunks")
    import_chunks([plan["recent_range"]], True, "wellness_backfill_chunks")

    # Keep the legacy daily HR/HRV dashboards warm for recently completed days.
    for offset in range(1, recent_days + 1):
        day = today - timedelta(days=offset)
        try:
            client.get_heart_rate_data(datetime.combine(day, time.min))
            client.get_hrv_data(datetime.combine(day, time.min))
        except Exception as exc:
            logger.warning("Legacy cache refresh failed for %s: %s", day, exc)
            summary["errors"].append(f"legacy {day}: {exc}")

    try:
        build_daily_calendar(repository, settings, today.year)
        iso = today.isocalendar()
        build_dashboard(repository, settings, f"{iso.year}-W{iso.week:02d}", 52, "auto")
        summary["dashboards_recalculated"] = True
    except Exception as exc:
        logger.exception("Dashboard recalculation failed")
        summary["dashboards_recalculated"] = False
        summary["errors"].append(f"recalculation: {exc}")
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh FitnessDashboard Garmin data for cron")
    parser.add_argument("--config", default="config.json", help="Config path, relative to the project directory")
    parser.add_argument("--recent-days", type=int, default=3,
                        help="Recent days to force-refresh for delayed Garmin updates (default: 3)")
    parser.add_argument("--no-backfill", action="store_true",
                        help="Skip unchecked year-to-date activity dates")
    parser.add_argument("--log-level", default="INFO", choices=("DEBUG", "INFO", "WARNING", "ERROR"))
    args = parser.parse_args(argv)
    if not 1 <= args.recent_days <= 28:
        parser.error("--recent-days must be between 1 and 28")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    os.chdir(PROJECT_DIR)
    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_DIR / config_path
    started_at = datetime.now(timezone.utc).isoformat()
    repository = AerobicRepository(PROJECT_DIR / "data" / "garmin_cache.db")
    try:
        with exclusive_sync_lock(PROJECT_DIR / "data" / "aerobic_sync.lock"):
            client = GarminClient()
            client.load_credentials(str(config_path))
            client.login()
            settings = load_aerobic_settings(str(config_path))
            summary = run_sync(client, repository, datetime.now(BUCHAREST).date(),
                               args.recent_days, not args.no_backfill, settings)
            status = "success" if not summary["errors"] else "partial"
            repository.record_sync_run(started_at, status, summary,
                                       "\n".join(summary["errors"]) if summary["errors"] else None)
            print(json.dumps({"status": status, **summary}, indent=2))
            return 0 if status == "success" else 1
    except Exception as exc:
        logger.exception("Scheduled sync failed")
        repository.record_sync_run(started_at, "failed", {}, str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
