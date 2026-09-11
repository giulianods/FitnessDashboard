from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from aerobic_base import (
    BUCHAREST, ActivityMetrics, AerobicBaseSettings, assemble_week,
    daily_aerobic_statuses, iso_week_bounds, score_adherence, score_durability, score_efficiency,
    score_frequency, score_recovery, week_key_for,
)
from aerobic_repository import AerobicRepository
from aerobic_service import build_daily_calendar, derive_activity, import_range
from sync_aerobic_data import build_sync_plan, parse_args


def activity(activity_id="1", start=None, base=30, moving=30, sport="cycling",
             drift=None, efficiency=None, warnings=None):
    start = start or datetime(2026, 3, 2, 8, tzinfo=BUCHAREST)
    return ActivityMetrics(
        activity_id=str(activity_id), activity_type=sport, start_local=start,
        duration_minutes=moving, moving_minutes=moving, distance_m=10000,
        average_hr=120, average_power=None, average_speed=7,
        zone1_minutes=0, zone2_minutes=base,
        zone_minutes={"Z1": 0, "Z2": base, "Z3": max(0, moving-base), "Z4": 0, "Z5": 0},
        base_minutes=base, easy_minutes=base, easy_proportion=base/moving if moving else None,
        hr_coverage=1, signal_coverage=1, indoor=False, drift=drift,
        efficiency=efficiency, warnings=warnings or [],
    )


@pytest.mark.parametrize("ratio,expected", [
    (.5999, 0), (.60, 3), (.75, 7), (.90, 10), (1.10, 10),
    (1.1001, 7), (1.20, 7), (1.2001, 3), (1.30, 3), (1.3001, 0),
])
def test_adherence_boundaries_choose_higher_band(ratio, expected):
    assert score_adherence(ratio * 100, 100, False, True).earned_points == expected


@pytest.mark.parametrize("drift,expected", [
    (-2, 10), (3, 10), (3.01, 8), (5, 8), (5.01, 5),
    (7.5, 5), (7.51, 2), (10, 2), (10.01, 0),
])
def test_cardiac_drift_boundaries(drift, expected):
    value = {"decoupling_percent": drift, "confidence": "Low"}
    assert score_durability([activity(drift=value)]).earned_points == expected


def test_frequency_counts_a_day_only_once():
    first = activity("1", base=20)
    second = activity("2", start=first.start_local + timedelta(hours=5), base=15)
    third = activity("3", start=first.start_local + timedelta(days=1), base=29)
    result = score_frequency([first, second, third], 30)
    assert result.raw_value["qualifying_days"] == 1
    assert result.earned_points == 2


def test_bucharest_iso_week_and_cross_midnight_assignment():
    start, end = iso_week_bounds("2026-W01")
    assert start.weekday() == 0 and end.weekday() == 6
    crossing = datetime(2025, 12, 28, 23, 30, tzinfo=BUCHAREST)
    assert week_key_for(crossing) == "2025-W52"
    # The whole session remains assigned by its start even if it ends in W01.
    assert week_key_for(crossing + timedelta(hours=2)) == "2026-W01"
    result = assemble_week("2025-W52", [activity(start=crossing, base=90, moving=120)], [], [], AerobicBaseSettings())
    assert next(c for c in result["components"] if c["identifier"] == "volume")["raw_value"]["abm"] == 90


def _summary(activity_type="cycling"):
    return {
        "activityId": 99, "activityType": {"typeKey": activity_type},
        "startTimeGMT": "2026-03-02 06:00:00", "duration": 3600,
        "movingDuration": 3600, "distance": 20000, "averageHR": 120,
        "averageSpeed": 6, "hrTimeInZone_1": 1200, "hrTimeInZone_2": 1800,
        "hrTimeInZone_3": 600, "hrTimeInZone_4": 0, "hrTimeInZone_5": 0,
    }


def test_zone_fallback_and_missing_power_are_explicit():
    result = derive_activity(_summary(), None, AerobicBaseSettings())
    assert result.base_minutes == 40
    assert any("fallback" in warning for warning in result.warnings)
    assert result.average_power is None


def _sample_detail(minutes=61, include_speed=True):
    descriptors = [
        {"key": "directTimestamp", "metricsIndex": 0},
        {"key": "directHeartRate", "metricsIndex": 1},
        {"key": "sumMovingDuration", "metricsIndex": 2},
    ]
    if include_speed:
        descriptors.append({"key": "directSpeed", "metricsIndex": 3})
    origin = datetime(2026, 3, 2, 6, tzinfo=timezone.utc).timestamp() * 1000
    rows = []
    for i in range(minutes):
        metrics = [origin + i * 60_000, 120, i * 60]
        if include_speed:
            metrics.append(5)
        rows.append({"metrics": metrics})
    return {"metricDescriptors": descriptors, "activityDetailMetrics": rows}


def test_cycling_without_power_uses_low_confidence_speed_proxy():
    summary = _summary()
    summary["duration"] = summary["movingDuration"] = 3600
    result = derive_activity(summary, _sample_detail(), AerobicBaseSettings(warmup_trim_minutes=0, cooldown_trim_minutes=0))
    assert result.drift is not None
    assert result.drift["measurement_type"] == "speed"
    assert result.drift["proxy"] is True
    assert result.drift["confidence"] == "Low"


def test_incomplete_sensor_coverage_does_not_calculate_drift():
    detail = _sample_detail(minutes=3)
    result = derive_activity(_summary(), detail, AerobicBaseSettings())
    assert result.drift is None
    assert any("fallback" in warning for warning in result.warnings)
    assert any("coverage was incomplete" in warning for warning in result.warnings)


def test_strength_is_excluded_and_walking_requires_hr_coverage():
    settings = AerobicBaseSettings()
    assert derive_activity(_summary("strength_training"), None, settings) is None
    walking = _summary("walking")
    for key in ("hrTimeInZone_1", "hrTimeInZone_2", "hrTimeInZone_3"):
        walking[key] = 0
    assert derive_activity(walking, None, settings) is None


def test_planned_deload_can_score_full():
    settings = AerobicBaseSettings(planned_weekly_targets={"2026-W10": {"target_abm": 180, "deload": True}})
    result = assemble_week("2026-W10", [activity(base=180, moving=200)], [], [], settings)
    adherence = next(c for c in result["components"] if c["identifier"] == "adherence")
    assert adherence["earned_points"] == 10
    assert adherence["raw_value"]["deload"] is True


def test_missing_recovery_fields_are_not_zero_points():
    start, _ = iso_week_bounds("2026-W10")
    rows = []
    for i in range(1, 29):
        rows.append({"date": (start.date()-timedelta(days=i)).isoformat(), "hrv": 50,
                     "resting_hr": None, "sleep_hours": None, "body_battery": None})
    for i in range(7):
        rows.append({"date": (start.date()+timedelta(days=i)).isoformat(), "hrv": 50,
                     "resting_hr": None, "sleep_hours": None, "body_battery": None})
    result = score_recovery(rows, start, 8)
    assert result.availability is True
    assert result.earned_points == 10
    assert result.raw_value["available_metrics"] == ["hrv"]


def test_efficiency_never_mixes_measurement_types():
    _, end = iso_week_bounds("2026-W10")
    samples = []
    for i in range(3):
        samples.append(activity(f"p{i}", start=end-timedelta(days=30+i), efficiency={"value": 2, "measurement_type": "power_hr"}))
        samples.append(activity(f"r{i}", start=end-timedelta(days=i), efficiency={"value": 2.04, "measurement_type": "power_hr"}))
        samples.append(activity(f"s{i}", start=end-timedelta(days=i), efficiency={"value": .07, "measurement_type": "speed_hr"}))
    result = score_efficiency(samples, end, "cycling", 3)
    assert result.availability is True
    assert result.raw_value["measurement_type"] == "power_hr"
    assert result.raw_value["recent_samples"] == 3


def test_example_week_scores_93_5():
    settings = AerobicBaseSettings(minimum_efficiency_samples=3)
    start, end = iso_week_bounds("2026-W10")
    bases = [120, 63.75, 63.75, 63.75, 63.75]
    week = []
    for i, base in enumerate(bases):
        moving = base / .88
        drift = {"decoupling_percent": 4.2, "confidence": "Medium"} if i == 0 else None
        week.append(activity(i, start=start+timedelta(days=i, hours=8), base=base, moving=moving, drift=drift))
    trends = []
    for i in range(3):
        trends.append(activity(f"old{i}", start=end-timedelta(days=32+i), efficiency={"value": 2.0, "measurement_type": "power_hr"}))
        trends.append(activity(f"new{i}", start=end-timedelta(days=2+i), efficiency={"value": 2.03, "measurement_type": "power_hr"}))
    wellness = []
    for i in range(1, 29):
        wellness.append({"date": (start.date()-timedelta(days=i)).isoformat(), "hrv":100, "resting_hr":50, "sleep_hours":8, "body_battery":80})
    for i in range(7):
        wellness.append({"date": (start.date()+timedelta(days=i)).isoformat(), "hrv":100, "resting_hr":50, "sleep_hours":8, "body_battery":50})
    result = assemble_week("2026-W10", week, trends, wellness, settings)
    scores = {c["identifier"]: c["earned_points"] for c in result["components"]}
    assert scores == {"volume":30, "frequency":10, "long_session":10, "intensity":10,
                      "adherence":10, "durability":8, "efficiency":8, "recovery":7.5}
    assert result["normalized_score"] == 93.5
    assert result["status"] == "Strong base-building week"


def test_normalized_score_and_coverage_distinguish_unavailable():
    result = assemble_week("2026-W10", [], [], [], AerobicBaseSettings())
    assert result["normalized_score"] == 0
    assert result["data_coverage"] == 60
    assert len(result["missing"]) == 4


def test_daily_aerobic_status_color_bands_and_neutral_rest_days():
    start, _ = iso_week_bounds("2026-W10")
    activities = [
        activity("green", start=start+timedelta(hours=8), base=72, moving=80),
        activity("blue", start=start+timedelta(days=1, hours=8), base=60, moving=80),
        activity("yellow", start=start+timedelta(days=2, hours=8), base=20, moving=40),
    ]
    days = daily_aerobic_statuses("2026-W10", activities, AerobicBaseSettings())
    assert [day["band"] for day in days[:4]] == ["green", "blue", "yellow", "neutral"]
    assert days[0]["daily_target_abm"] == 72
    assert days[0]["activity_minutes"] == 80
    assert days[0]["score"] > 85
    assert 70 <= days[1]["score"] <= 85
    assert days[2]["score"] < 70
    assert days[3]["score"] is None
    assert days[3]["activity_minutes"] == 0


def test_repository_deduplicates_garmin_activity(tmp_path):
    repository = AerobicRepository(tmp_path / "cache.db")
    summary = _summary()
    repository.upsert_activity(summary, None)
    repository.upsert_activity(summary, None)
    rows = repository.activities_between("2026-03-02", "2026-03-02")
    assert len(rows) == 1


def test_calendar_import_ledger_chunks_missing_ranges(tmp_path):
    repository = AerobicRepository(tmp_path / "calendar.db")
    start, end = date(2026, 1, 1), date(2026, 2, 9)
    empty = repository.calendar_import_status(start, end)
    assert empty["expected_days"] == 40
    assert empty["imported_days"] == 0
    assert empty["missing_ranges"] == [
        {"start": "2026-01-01", "end": "2026-01-28"},
        {"start": "2026-01-29", "end": "2026-02-09"},
    ]
    repository.mark_imported_range(start, end, include_wellness=False)
    complete = repository.calendar_import_status(start, end)
    assert complete["coverage_percent"] == 100
    assert complete["missing_ranges"] == []


def test_wellness_coverage_is_tracked_separately(tmp_path):
    repository = AerobicRepository(tmp_path / "wellness-ledger.db")
    start, end = date(2026, 1, 1), date(2026, 1, 3)
    repository.mark_imported_range(start, end, include_wellness=False)
    assert repository.calendar_import_status(start, end)["coverage_percent"] == 100
    assert repository.wellness_import_status(start, end)["coverage_percent"] == 0
    repository.mark_imported_range(start, end, include_wellness=True)
    assert repository.wellness_import_status(start, end)["coverage_percent"] == 100


def test_daily_sync_plan_backfills_sources_and_refreshes_recent_days(tmp_path):
    repository = AerobicRepository(tmp_path / "sync-plan.db")
    today = date(2026, 8, 5)
    plan = build_sync_plan(repository, today, recent_days=3, backfill=True)
    assert plan["calculation_start"] == "2025-11-06"
    assert plan["wellness_start"] == "2026-07-02"
    assert plan["recent_range"] == {"start": "2026-08-03", "end": "2026-08-05"}
    assert plan["activity_ranges"]
    assert plan["wellness_ranges"]
    repository.mark_imported_range(date(2025, 11, 6), today, include_wellness=False)
    repository.mark_imported_range(date(2026, 7, 2), today, include_wellness=True)
    complete = build_sync_plan(repository, today, recent_days=3, backfill=True)
    assert complete["activity_ranges"] == []
    assert complete["wellness_ranges"] == []


def test_sync_run_status_roundtrip(tmp_path):
    repository = AerobicRepository(tmp_path / "sync-status.db")
    assert repository.latest_sync_run() is None
    repository.record_sync_run("2026-08-05T01:00:00+00:00", "success", {"activities_imported": 4})
    latest = repository.latest_sync_run()
    assert latest["status"] == "success"
    assert latest["summary"]["activities_imported"] == 4
    assert latest["error"] is None


def test_sync_cli_defaults():
    args = parse_args([])
    assert args.recent_days == 3
    assert args.no_backfill is False


def test_activity_only_calendar_import_skips_wellness_calls(tmp_path):
    class FakeApi:
        def get_activities_by_date(self, *args, **kwargs):
            return []

    class FakeClient:
        client = FakeApi()

    repository = AerobicRepository(tmp_path / "activity-only.db")
    result = import_range(FakeClient(), repository, date(2025, 1, 1), date(2025, 1, 3),
                          AerobicBaseSettings(), include_wellness=False)
    assert result["wellness_days"] == 0
    assert result["include_wellness"] is False
    assert repository.calendar_import_status(date(2025, 1, 1), date(2025, 1, 3))["coverage_percent"] == 100


def test_empty_year_calendar_has_every_past_day_and_month(tmp_path):
    result = build_daily_calendar(AerobicRepository(tmp_path / "year.db"), AerobicBaseSettings(), 2025)
    assert len(result["days"]) == 365
    assert len(result["months"]) == 12
    assert len(result["weeks"]) == 53
    assert result["weeks"][0]["week"] == "2025-W01"
    assert {"score", "coverage", "status", "missing", "explanation", "recommendation"} <= result["weeks"][0].keys()
    assert result["summary"]["training_days"] == 0
    assert all(day["band"] == "neutral" for day in result["days"])


def test_flask_dashboard_api_and_first_view(monkeypatch, tmp_path):
    import app as app_module
    monkeypatch.setattr(app_module, "aerobic_repository", AerobicRepository(tmp_path / "api.db"))
    client = app_module.app.test_client()
    page = client.get("/")
    assert page.status_code == 200
    assert b'id="aerobic-base-view" class="view active' in page.data
    response = client.get("/get_aerobic_base_data?week=2026-W10&range=4&sport=auto")
    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["weeks"]) == 4
    assert len(payload["selected"]["components"]) == 8
    assert payload["selected"]["data_coverage"] == 60
    calendar = client.get("/get_aerobic_calendar_data?year=2025")
    assert calendar.status_code == 200
    calendar_payload = calendar.get_json()
    assert len(calendar_payload["days"]) == 365
    assert len(calendar_payload["months"]) == 12
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"
