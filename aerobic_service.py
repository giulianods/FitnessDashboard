"""Garmin normalisation and orchestration for the Aerobic Base dashboard."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from statistics import mean
from typing import Any, Optional
import json

from aerobic_base import (
    BUCHAREST, ActivityMetrics, AerobicBaseSettings, DataConfidence,
    assemble_week, daily_aerobic_statuses, iso_week_bounds, is_eligible_activity, week_key_for,
)
from aerobic_repository import AerobicRepository


def load_aerobic_settings(config_path: str = "config.json") -> AerobicBaseSettings:
    with open(config_path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    return AerobicBaseSettings.from_mapping(config.get("aerobic_base"))


def _seconds(value: Any) -> float:
    try:
        return max(0.0, float(value or 0))
    except (TypeError, ValueError):
        return 0.0


def _parse_start(summary: dict[str, Any]) -> datetime:
    raw = summary.get("startTimeGMT")
    if raw:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(BUCHAREST)
    raw = summary.get("beginTimestamp")
    if raw is not None:
        return datetime.fromtimestamp(float(raw) / 1000, timezone.utc).astimezone(BUCHAREST)
    parsed = datetime.fromisoformat(str(summary["startTimeLocal"]))
    return parsed.replace(tzinfo=BUCHAREST) if parsed.tzinfo is None else parsed.astimezone(BUCHAREST)


def _canonical_sport(summary: dict[str, Any]) -> str:
    key = str((summary.get("activityType") or {}).get("typeKey", "unknown")).lower()
    mappings = (
        ("strength", "strength_training"), ("cycling", "cycling"), ("biking", "cycling"),
        ("running", "running"), ("walking", "walking"), ("hiking", "hiking"),
        ("swimming", "swimming"), ("indoor_row", "indoor_rowing"),
        ("rowing", "rowing"), ("elliptical", "elliptical"),
    )
    return next((sport for token, sport in mappings if token in key), key)


def _timestamp(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric > 10_000_000_000:
            numeric /= 1000
        return datetime.fromtimestamp(numeric, timezone.utc)
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except ValueError:
        return None


def normalise_samples(detail: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
    if not detail:
        return []
    descriptor_map = {
        str(item.get("key")): int(item["metricsIndex"])
        for item in detail.get("metricDescriptors", [])
        if item.get("key") is not None and item.get("metricsIndex") is not None
    }

    def index_for(*names: str) -> Optional[int]:
        for name in names:
            if name in descriptor_map:
                return descriptor_map[name]
        return None

    indexes = {
        "timestamp": index_for("directTimestamp"),
        "heart_rate": index_for("directHeartRate"),
        "speed": index_for("directSpeed"),
        "power": index_for("directPower", "directBikePower", "directWatts"),
        "cadence": index_for("directCadence", "directRunCadence", "directDoubleCadence"),
        "altitude": index_for("directElevation", "directCorrectedElevation"),
        "moving_duration": index_for("sumMovingDuration"),
    }
    result = []
    for row in detail.get("activityDetailMetrics", []):
        values = row.get("metrics") or []
        sample: dict[str, Any] = {}
        for name, index in indexes.items():
            sample[name] = values[index] if index is not None and index < len(values) else None
        sample["timestamp"] = _timestamp(sample["timestamp"])
        if sample["timestamp"] is not None:
            result.append(sample)
    return sorted(result, key=lambda item: item["timestamp"])


def _zone_for(hr: float, settings: AerobicBaseSettings) -> int:
    bounds = settings.heart_rate_zones
    if bounds[0] <= hr < bounds[1]:
        return 1
    if bounds[1] <= hr < bounds[2]:
        return 2
    if bounds[2] <= hr < bounds[3]:
        return 3
    if bounds[3] <= hr < bounds[4]:
        return 4
    if bounds[4] <= hr:
        return 5
    return 0


def _intervals(samples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intervals = []
    for current, following in zip(samples, samples[1:]):
        seconds = (following["timestamp"] - current["timestamp"]).total_seconds()
        if seconds <= 0 or seconds > 300:
            continue
        current_moving = current.get("moving_duration")
        next_moving = following.get("moving_duration")
        if current_moving is not None and next_moving is not None:
            moving = float(next_moving) > float(current_moving)
        else:
            moving = current.get("speed") is None or float(current.get("speed") or 0) > 0.2
        intervals.append({**current, "seconds": seconds, "moving": moving})
    return intervals


def _weighted(rows: list[dict[str, Any]], key: str) -> Optional[float]:
    available = [r for r in rows if r.get(key) is not None]
    seconds = sum(r["seconds"] for r in available)
    if not seconds:
        return None
    return sum(float(r[key]) * r["seconds"] for r in available) / seconds


def _trim_and_split(rows: list[dict[str, Any]], warmup: float, cooldown: float) -> tuple[list[dict], list[dict]]:
    total = sum(r["seconds"] for r in rows)
    lower, upper = warmup * 60, total - cooldown * 60
    if upper <= lower:
        return [], []
    midpoint = lower + (upper - lower) / 2
    first: list[dict] = []
    second: list[dict] = []
    cursor = 0.0
    for row in rows:
        row_start, row_end = cursor, cursor + row["seconds"]
        cursor = row_end
        for start, end, target in ((lower, midpoint, first), (midpoint, upper, second)):
            overlap = max(0.0, min(row_end, end) - max(row_start, start))
            if overlap:
                target.append({**row, "seconds": overlap})
    return first, second


def derive_activity(summary: dict[str, Any], detail: Optional[dict[str, Any]],
                    settings: AerobicBaseSettings) -> Optional[ActivityMetrics]:
    sport = _canonical_sport(summary)
    if not is_eligible_activity(sport, settings):
        return None
    activity_id = str(summary.get("activityId"))
    start = _parse_start(summary)
    duration = _seconds(summary.get("duration")) / 60
    moving = _seconds(summary.get("movingDuration") or summary.get("duration")) / 60
    samples = normalise_samples(detail)
    rows = [r for r in _intervals(samples) if r["moving"]]
    moving_seconds = moving * 60
    represented = sum(r["seconds"] for r in rows)
    hr_seconds = sum(r["seconds"] for r in rows if r.get("heart_rate") is not None)
    speed_seconds = sum(r["seconds"] for r in rows if r.get("speed") is not None)
    power_seconds = sum(r["seconds"] for r in rows if r.get("power") is not None)
    denominator = moving_seconds or represented
    hr_coverage = min(1.0, hr_seconds / denominator) if denominator else 0
    has_power = power_seconds >= settings.minimum_signal_coverage * denominator if denominator else False
    signal_seconds = power_seconds if has_power else speed_seconds
    signal_coverage = min(1.0, signal_seconds / denominator) if denominator else 0
    warnings: list[str] = []

    if rows and hr_coverage >= settings.minimum_hr_coverage:
        zone_seconds = {
            zone: sum(r["seconds"] for r in rows if r.get("heart_rate") is not None and _zone_for(float(r["heart_rate"]), settings) == zone)
            for zone in range(1, 6)
        }
        z1_seconds, z2_seconds = zone_seconds[1], zone_seconds[2]
        if settings.lt1_heart_rate is not None:
            easy_seconds = sum(r["seconds"] for r in rows if r.get("heart_rate") is not None and float(r["heart_rate"]) < settings.lt1_heart_rate)
        else:
            easy_seconds = z1_seconds + z2_seconds
    else:
        zone_seconds = {zone: _seconds(summary.get(f"hrTimeInZone_{zone}")) for zone in range(1, 6)}
        z1_seconds, z2_seconds = zone_seconds[1], zone_seconds[2]
        easy_seconds = z1_seconds + z2_seconds
        if z1_seconds or z2_seconds:
            warnings.append("Garmin zone-duration fallback used because sample HR coverage was insufficient.")
            zoned_seconds = sum(zone_seconds.values())
            hr_coverage = max(hr_coverage, min(1.0, zoned_seconds / denominator) if denominator else 0)
        else:
            warnings.append("Heart-rate samples and Garmin zone durations are unavailable.")

    if sport == "walking" and hr_coverage < settings.minimum_hr_coverage:
        return None
    zone1, zone2, easy = z1_seconds / 60, z2_seconds / 60, easy_seconds / 60
    base = zone2 + .5 * zone1
    indoor = "indoor" in str((summary.get("activityType") or {}).get("typeKey", "")).lower() or (
        summary.get("startLatitude") is None and summary.get("startLongitude") is None
    )
    average_hr = summary.get("averageHR")
    average_speed = summary.get("averageSpeed")
    average_power = summary.get("averagePower") or summary.get("avgPower")
    drift = None
    efficiency = None

    duration_eligible = moving >= settings.minimum_drift_duration_minutes
    easy_proportion = easy / moving if moving else None
    if sport in ("cycling", "running") and duration_eligible and easy_proportion is not None and easy_proportion >= .80 and rows:
        first, second = _trim_and_split(rows, settings.warmup_trim_minutes, settings.cooldown_trim_minutes)
        measurement = "power" if has_power else "speed"
        first_hr, second_hr = _weighted(first, "heart_rate"), _weighted(second, "heart_rate")
        first_signal, second_signal = _weighted(first, measurement), _weighted(second, measurement)
        if (first_hr and second_hr and first_signal is not None and second_signal is not None
                and hr_coverage >= settings.minimum_hr_coverage
                and signal_coverage >= settings.minimum_signal_coverage):
            first_eff, second_eff = first_signal / first_hr, second_signal / second_hr
            decoupling = 100 * (first_eff - second_eff) / first_eff if first_eff else 0
            if measurement == "power":
                confidence = DataConfidence.HIGH if indoor and moving >= 90 and min(hr_coverage, signal_coverage) >= settings.excellent_sensor_coverage else DataConfidence.MEDIUM
            else:
                confidence = DataConfidence.LOW
            drift = {
                "activity_id": activity_id, "date": start.date().isoformat(),
                "decoupling_percent": decoupling, "measurement_type": measurement,
                "proxy": measurement == "speed", "confidence": confidence.value,
                "duration_minutes": moving, "sport": sport,
            }
        else:
            warnings.append("Drift unavailable because heart-rate or power/speed coverage was incomplete.")

    low_rows = [r for r in rows if r.get("heart_rate") is not None and (
        float(r["heart_rate"]) < settings.lt1_heart_rate if settings.lt1_heart_rate is not None
        else _zone_for(float(r["heart_rate"]), settings) in (1, 2)
    )]
    low_seconds = sum(r["seconds"] for r in low_rows)
    measurement = "power" if has_power else "speed"
    signal = _weighted(low_rows, measurement)
    hr = _weighted(low_rows, "heart_rate")
    if sport in ("cycling", "running") and low_seconds >= settings.qualifying_session_minutes * 60 and signal is not None and hr:
        efficiency = {
            "activity_id": activity_id, "date": start.date().isoformat(), "sport": sport,
            "value": signal / hr, "measurement_type": f"{measurement}_hr",
            "proxy": measurement == "speed" and sport == "cycling",
            "qualifying_minutes": low_seconds / 60,
        }

    return ActivityMetrics(
        activity_id=activity_id, activity_type=sport, start_local=start,
        duration_minutes=duration, moving_minutes=moving,
        distance_m=float(summary["distance"]) if summary.get("distance") is not None else None,
        average_hr=float(average_hr) if average_hr is not None else None,
        average_power=float(average_power) if average_power is not None else None,
        average_speed=float(average_speed) if average_speed is not None else None,
        zone1_minutes=zone1, zone2_minutes=zone2, base_minutes=base,
        zone_minutes={f"Z{zone}": seconds / 60 for zone, seconds in zone_seconds.items()},
        easy_minutes=easy, easy_proportion=easy_proportion,
        hr_coverage=hr_coverage, signal_coverage=signal_coverage, indoor=indoor,
        drift=drift, efficiency=efficiency, warnings=warnings,
    )


def _activity_from_dict(value: dict[str, Any]) -> ActivityMetrics:
    data = dict(value)
    parsed = datetime.fromisoformat(data["start_local"])
    data["start_local"] = parsed.replace(tzinfo=BUCHAREST) if parsed.tzinfo is None else parsed.astimezone(BUCHAREST)
    return ActivityMetrics(**data)


def _body_battery_at_wake(stats: dict[str, Any], body: Any) -> Optional[float]:
    value = stats.get("bodyBatteryAtWakeTime")
    if value is not None:
        return float(value)
    if isinstance(body, list) and body:
        values = body[0].get("bodyBatteryValuesArray") or []
        for item in values:
            if isinstance(item, list) and len(item) >= 2 and item[1] is not None:
                return float(item[1])
    return None


def import_range(client: Any, repository: AerobicRepository, start: date, end: date,
                 settings: AerobicBaseSettings, include_wellness: bool = True) -> dict[str, Any]:
    today = datetime.now(BUCHAREST).date()
    end = min(end, today)
    if end < start:
        return {"activities": 0, "wellness_days": 0, "start": start.isoformat(), "end": end.isoformat()}
    activities = client.client.get_activities_by_date(start.isoformat(), end.isoformat(), sortorder="asc")
    imported = 0
    for summary in activities:
        sport = _canonical_sport(summary)
        detail = None
        if is_eligible_activity(sport, settings):
            try:
                detail = client.client.get_activity_details(str(summary["activityId"]), maxchart=2000, maxpoly=0)
            except Exception:
                detail = None
        repository.upsert_activity(summary, detail)
        imported += 1

    wellness_days = 0
    if include_wellness:
        current = start
        while current <= end:
            day = current.isoformat()
            sleep: dict[str, Any] = {}
            stats: dict[str, Any] = {}
            body: Any = []
            try:
                sleep = client.client.get_sleep_data(day) or {}
            except Exception:
                pass
            try:
                stats = client.client.get_stats(day) or {}
            except Exception:
                pass
            try:
                body = client.client.get_body_battery(day, day) or []
            except Exception:
                pass
            dto = sleep.get("dailySleepDTO") or {}
            sleep_seconds = dto.get("sleepTimeSeconds")
            repository.upsert_wellness(day, {
                "date": day,
                "hrv": sleep.get("avgOvernightHrv"),
                "resting_hr": sleep.get("restingHeartRate") or stats.get("restingHeartRate"),
                "sleep_hours": float(sleep_seconds) / 3600 if sleep_seconds is not None else None,
                "sleep_score": ((dto.get("sleepScores") or {}).get("overall") or {}).get("value") if isinstance(dto.get("sleepScores"), dict) else None,
                "body_battery": _body_battery_at_wake(stats, body),
                "training_readiness": None,
                "provenance": ["sleep", "daily_stats", "body_battery"],
            })
            wellness_days += 1
            current += timedelta(days=1)
    repository.mark_imported_range(start, end, include_wellness)
    return {"activities": imported, "wellness_days": wellness_days,
            "start": start.isoformat(), "end": end.isoformat(),
            "include_wellness": include_wellness}


def build_daily_calendar(repository: AerobicRepository, settings: AerobicBaseSettings,
                         year: int) -> dict[str, Any]:
    """Build a year calendar from the same daily guide used under the dashboard title."""
    current = datetime.now(BUCHAREST).date()
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), current) if year == current.year else date(year, 12, 31)
    calculation_start = start - timedelta(days=56)
    rows = repository.activities_between((calculation_start - timedelta(days=1)).isoformat(), end.isoformat())
    settings_hash = settings.fingerprint()
    activities: list[ActivityMetrics] = []
    for row in rows:
        activity_id = str(row["summary"].get("activityId"))
        cached = repository.get_activity_metrics(activity_id, settings_hash, row["source_hash"])
        item = _activity_from_dict(cached) if cached is not None else derive_activity(row["summary"], row["detail"], settings)
        if item is not None and calculation_start <= item.start_local.date() <= end:
            if cached is None:
                repository.save_activity_metrics(activity_id, settings_hash, row["source_hash"], item.to_dict())
            activities.append(item)

    wellness = repository.wellness_between((start - timedelta(days=28)).isoformat(), end.isoformat())
    calendar_days = []
    weekly_scores = []
    week_monday = start - timedelta(days=start.weekday())
    while week_monday <= end:
        iso = week_monday.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        week_activities = [item for item in activities if week_key_for(item.start_local) == week_key]
        calendar_days.extend(
            day for day in daily_aerobic_statuses(week_key, week_activities, settings)
            if start <= date.fromisoformat(day["date"]) <= end
        )
        weekly = assemble_week(week_key, week_activities, activities, wellness, settings, "auto")
        weekly_scores.append({
            "week": week_key, "week_start": weekly["week_start"], "week_end": weekly["week_end"],
            "score": weekly["normalized_score"], "coverage": weekly["data_coverage"],
            "status": weekly["status"], "provisional": weekly["provisional"],
            "missing": weekly["missing"], "explanation": weekly["explanation"],
            "recommendation": weekly["recommendation"],
        })
        week_monday += timedelta(days=7)
    calendar_days.sort(key=lambda item: item["date"])

    months = []
    for month in range(1, end.month + 1):
        month_days = [item for item in calendar_days if date.fromisoformat(item["date"]).month == month]
        scored = [item["score"] for item in month_days if item["score"] is not None]
        counts = {band: sum(item["band"] == band for item in month_days)
                  for band in ("green", "blue", "yellow", "neutral")}
        months.append({
            "month": month, "name": date(year, month, 1).strftime("%B"),
            "average_training_day_score": round(mean(scored), 1) if scored else None,
            "total_abm": round(sum(item["abm"] for item in month_days), 1),
            "training_days": len(scored), "bands": counts,
        })
    scored_days = [item for item in calendar_days if item["score"] is not None]
    return {
        "year": year, "start": start.isoformat(), "end": end.isoformat(),
        "days": calendar_days, "months": months, "weeks": weekly_scores,
        "summary": {
            "average_training_day_score": round(mean(item["score"] for item in scored_days), 1) if scored_days else None,
            "total_abm": round(sum(item["abm"] for item in calendar_days), 1),
            "training_days": len(scored_days),
            "strong_days": sum(item["band"] == "green" for item in calendar_days),
        },
        "import_status": repository.calendar_import_status(calculation_start, end),
        "calculation_start": calculation_start.isoformat(),
        "settings_fingerprint": settings_hash,
        "scheduled_sync": repository.latest_sync_run(),
    }


def build_dashboard(repository: AerobicRepository, settings: AerobicBaseSettings,
                    selected_week: str, range_weeks: int, sport: str = "auto") -> dict[str, Any]:
    selected_start, selected_end = iso_week_bounds(selected_week)
    range_start = selected_start - timedelta(weeks=range_weeks - 1)
    preload_start = range_start - timedelta(days=56)
    rows = repository.activities_between(preload_start.date().isoformat(), selected_end.date().isoformat())
    derived = []
    settings_hash = settings.fingerprint()
    for row in rows:
        activity_id = str(row["summary"].get("activityId"))
        cached = repository.get_activity_metrics(activity_id, settings_hash, row["source_hash"])
        item = _activity_from_dict(cached) if cached is not None else derive_activity(row["summary"], row["detail"], settings)
        if item is not None:
            if cached is None:
                repository.save_activity_metrics(activity_id, settings_hash, row["source_hash"], item.to_dict())
            derived.append(item)
    wellness = repository.wellness_between((range_start - timedelta(days=28)).date().isoformat(), selected_end.date().isoformat())

    weeks = []
    range_activities = [a for a in derived if range_start.date() <= a.start_local.date() <= selected_end.date()]
    range_sport_totals: dict[str, float] = {}
    for item in range_activities:
        range_sport_totals[item.activity_type] = range_sport_totals.get(item.activity_type, 0) + item.base_minutes
    resolved_sport = sport if sport != "auto" else max(range_sport_totals, key=range_sport_totals.get, default="cycling")
    for offset in range(range_weeks - 1, -1, -1):
        week_start = selected_start - timedelta(weeks=offset)
        key = week_key_for(week_start)
        in_week = [a for a in derived if week_key_for(a.start_local) == key]
        result = assemble_week(key, in_week, derived, wellness, settings, resolved_sport)
        weeks.append(result)
    selected = weeks[-1]
    revision = repository.source_revision(preload_start.date().isoformat(), selected_end.date().isoformat())
    repository.save_week_score(selected, sport, asdict(settings), revision)
    coverage = repository.coverage(preload_start.date().isoformat(), min(selected_end.date(), datetime.now(BUCHAREST).date()).isoformat())
    all_recorded_minutes = []
    for result in weeks:
        total = 0.0
        for row in rows:
            try:
                if week_key_for(_parse_start(row["summary"])) == result["week"]:
                    total += _seconds(row["summary"].get("movingDuration") or row["summary"].get("duration")) / 60
            except (KeyError, ValueError, TypeError):
                continue
        all_recorded_minutes.append({"week": result["week"], "minutes": total})
    return {
        "selected": selected,
        "weeks": weeks,
        "settings": asdict(settings),
        "import_status": coverage,
        "range_weeks": range_weeks,
        "sport_filter": sport,
        "last_source_revision": revision,
        "drift_sessions": [a.drift for a in derived if a.drift is not None and range_start.date() <= a.start_local.date() <= selected_end.date()],
        "efficiency_sessions": [a.efficiency for a in derived if a.efficiency is not None and range_start.date() <= a.start_local.date() <= selected_end.date()],
        "recovery_trends": [w for w in wellness if range_start.date() <= date.fromisoformat(w["date"]) <= selected_end.date()],
        "all_recorded_minutes": all_recorded_minutes,
        "scheduled_sync": repository.latest_sync_run(),
    }
