"""Deterministic aerobic-base calculations.

This module deliberately contains no Flask, Garmin, or database code.  Inputs are
normalised dictionaries so the scoring rules can be tested independently.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from hashlib import sha256
from statistics import mean, median
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo
import json


BUCHAREST = ZoneInfo("Europe/Bucharest")


class DataConfidence(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNAVAILABLE = "Unavailable"


@dataclass(frozen=True)
class AerobicBaseSettings:
    weekly_target_abm: float = 360.0
    qualifying_session_minutes: float = 30.0
    long_session_target: float = 120.0
    primary_sport: str = "auto"
    eligible_activity_types: tuple[str, ...] = (
        "cycling", "running", "swimming", "hiking", "walking",
        "rowing", "indoor_rowing", "elliptical",
    )
    excluded_activity_types: tuple[str, ...] = (
        "strength_training", "strength", "cardio_strength",
    )
    # Z1 and Z2 retain the boundaries already used by this project (50-70% of 190).
    heart_rate_zones: tuple[float, float, float, float, float, float] = (
        95.0, 114.0, 133.0, 152.0, 171.0, 190.0,
    )
    lt1_heart_rate: Optional[float] = None
    planned_weekly_targets: dict[str, dict[str, Any]] = field(default_factory=dict)
    warmup_trim_minutes: float = 10.0
    cooldown_trim_minutes: float = 5.0
    minimum_drift_duration_minutes: float = 60.0
    minimum_efficiency_samples: int = 3
    minimum_hr_coverage: float = 0.80
    minimum_signal_coverage: float = 0.80
    excellent_sensor_coverage: float = 0.95
    sleep_goal_hours: float = 8.0
    scoring_thresholds: dict[str, Any] = field(default_factory=lambda: {
        "intensity": {"full": 0.80, "eight": 0.70, "five": 0.60},
        "adherence": {"full_low": 0.90, "full_high": 1.10, "seven_low": 0.75,
                      "seven_high": 1.20, "three_low": 0.60, "three_high": 1.30},
        "drift": {"full": 3.0, "eight": 5.0, "five": 7.5, "two": 10.0},
        "efficiency": {"full": 3.0, "eight": 1.0, "stable_low": -1.0, "three_low": -3.0},
        "recovery": {"hrv_full": 0.90, "hrv_half": 0.80, "rhr_full_delta": 3.0,
                     "rhr_half_delta": 5.0, "sleep_full": 0.90, "sleep_half": 0.80,
                     "battery_full": 0.90, "battery_half": 0.75},
    })

    @classmethod
    def from_mapping(cls, value: Optional[dict[str, Any]]) -> "AerobicBaseSettings":
        value = value or {}
        defaults = cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}
        data = {k: v for k, v in value.items() if k in known}
        for key in ("eligible_activity_types", "excluded_activity_types", "heart_rate_zones"):
            if key in data:
                data[key] = tuple(data[key])
        if "scoring_thresholds" in data:
            merged = {group: dict(values) for group, values in defaults.scoring_thresholds.items()}
            for group, values in data["scoring_thresholds"].items():
                if group in merged and isinstance(values, dict):
                    merged[group].update(values)
            data["scoring_thresholds"] = merged
        settings = cls(**data)
        if len(settings.heart_rate_zones) != 6:
            raise ValueError("aerobic_base.heart_rate_zones must contain six ascending boundaries")
        if list(settings.heart_rate_zones) != sorted(settings.heart_rate_zones):
            raise ValueError("aerobic_base.heart_rate_zones must be ascending")
        if settings.weekly_target_abm <= 0 or settings.long_session_target <= 0:
            raise ValueError("aerobic-base targets must be positive")
        return settings

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()


@dataclass
class ComponentScore:
    identifier: str
    name: str
    earned_points: float
    maximum_points: float
    availability: bool
    confidence: DataConfidence
    raw_value: Any
    display_unit: str
    explanation: str
    contributing_activity_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["confidence"] = self.confidence.value
        return result


@dataclass
class ActivityMetrics:
    activity_id: str
    activity_type: str
    start_local: datetime
    duration_minutes: float
    moving_minutes: float
    distance_m: Optional[float]
    average_hr: Optional[float]
    average_power: Optional[float]
    average_speed: Optional[float]
    zone1_minutes: float
    zone2_minutes: float
    zone_minutes: dict[str, float]
    base_minutes: float
    easy_minutes: float
    easy_proportion: Optional[float]
    hr_coverage: float
    signal_coverage: float
    indoor: bool
    drift: Optional[dict[str, Any]] = None
    efficiency: Optional[dict[str, Any]] = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["start_local"] = self.start_local.isoformat()
        return d


def iso_week_bounds(week_key: str) -> tuple[datetime, datetime]:
    """Return inclusive Bucharest-local Monday and Sunday bounds."""
    try:
        year, week = week_key.split("-W")
        monday = date.fromisocalendar(int(year), int(week), 1)
    except (ValueError, TypeError) as exc:
        raise ValueError("week must use YYYY-Www ISO format") from exc
    start = datetime.combine(monday, datetime.min.time(), BUCHAREST)
    return start, start + timedelta(days=7) - timedelta(microseconds=1)


def week_key_for(value: datetime) -> str:
    local = value.astimezone(BUCHAREST) if value.tzinfo else value.replace(tzinfo=BUCHAREST)
    iso = local.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def is_eligible_activity(activity_type: str, settings: AerobicBaseSettings) -> bool:
    key = (activity_type or "").lower()
    if "strength" in key or key in settings.excluded_activity_types:
        return False
    return key in settings.eligible_activity_types


def _component(identifier: str, name: str, points: float, maximum: float,
               raw: Any, unit: str, explanation: str, *,
               available: bool = True, confidence: DataConfidence = DataConfidence.HIGH,
               activity_ids: Iterable[str] = (), warnings: Iterable[str] = ()) -> ComponentScore:
    return ComponentScore(identifier, name, round(points, 4), maximum, available,
                          confidence if available else DataConfidence.UNAVAILABLE,
                          raw, unit, explanation, list(activity_ids), list(warnings))


def score_volume(activities: list[ActivityMetrics], target: float) -> ComponentScore:
    z1 = sum(a.zone1_minutes for a in activities)
    z2 = sum(a.zone2_minutes for a in activities)
    abm = z2 + 0.5 * z1
    points = 30.0 * min(abm / target, 1.0)
    return _component("volume", "Low-intensity volume", points, 30, {
        "zone1_minutes": z1, "zone2_minutes": z2, "abm": abm,
        "target": target, "completion_percent": 100 * abm / target,
        "excess_minutes": max(0.0, abm - target),
    }, "ABM", f"You reached {100 * abm / target:.0f}% of the weekly aerobic-volume target.",
        activity_ids=[a.activity_id for a in activities])


def score_frequency(activities: list[ActivityMetrics], minimum: float) -> ComponentScore:
    by_day: dict[date, float] = {}
    for activity in activities:
        by_day[activity.start_local.date()] = by_day.get(activity.start_local.date(), 0) + activity.base_minutes
    qualifying = sum(minutes >= minimum for minutes in by_day.values())
    return _component("frequency", "Frequency", min(2.0 * qualifying, 10.0), 10,
                      {"qualifying_days": qualifying, "minimum_minutes": minimum}, "days",
                      f"{qualifying} day{'s' if qualifying != 1 else ''} contained at least {minimum:g} aerobic-base minutes.",
                      activity_ids=[a.activity_id for a in activities])


def score_long_session(activities: list[ActivityMetrics], target: float) -> ComponentScore:
    longest = max((a.base_minutes for a in activities), default=0.0)
    winner = [a.activity_id for a in activities if a.base_minutes == longest and longest > 0]
    return _component("long_session", "Long-session stimulus", 10 * min(longest / target, 1), 10,
                      {"longest_base_minutes": longest, "target": target}, "minutes",
                      f"The longest easy session supplied {longest:.0f} aerobic-base minutes.",
                      activity_ids=winner)


def score_intensity(activities: list[ActivityMetrics], thresholds: Optional[dict[str, float]] = None) -> ComponentScore:
    total = sum(a.moving_minutes for a in activities)
    easy = sum(a.easy_minutes for a in activities)
    if total <= 0:
        return _component("intensity", "Intensity discipline", 0, 10, None, "%",
                          "No eligible endurance time was available.", available=False)
    proportion = easy / total
    t = thresholds or {"full": .8, "eight": .7, "five": .6}
    points = 10 if proportion >= t["full"] else 8 if proportion >= t["eight"] else 5 if proportion >= t["five"] else 0
    return _component("intensity", "Intensity discipline", points, 10,
                      {"easy_proportion": proportion, "easy_minutes": easy, "eligible_minutes": total}, "%",
                      f"{proportion:.0%} of eligible endurance time stayed at low intensity.",
                      confidence=DataConfidence.MEDIUM if any("zone-duration fallback" in w for a in activities for w in a.warnings) else DataConfidence.HIGH,
                      activity_ids=[a.activity_id for a in activities])


def planned_target(settings: AerobicBaseSettings, week_key: str) -> tuple[float, bool, bool]:
    item = settings.planned_weekly_targets.get(week_key)
    if item is None:
        return settings.weekly_target_abm, False, False
    if isinstance(item, (int, float)):
        return float(item), False, True
    return float(item.get("target_abm", settings.weekly_target_abm)), bool(item.get("deload", False)), True


def score_adherence(actual_abm: float, target: float, deload: bool, explicit: bool,
                    thresholds: Optional[dict[str, float]] = None) -> ComponentScore:
    ratio = actual_abm / target if target else 0
    t = thresholds or {"full_low": .90, "full_high": 1.10, "seven_low": .75,
                       "seven_high": 1.20, "three_low": .60, "three_high": 1.30}
    # Higher-scoring category owns an overlapping boundary.
    if t["full_low"] <= ratio <= t["full_high"]:
        points = 10
    elif t["seven_low"] <= ratio < t["full_low"] or t["full_high"] < ratio <= t["seven_high"]:
        points = 7
    elif t["three_low"] <= ratio < t["seven_low"] or t["seven_high"] < ratio <= t["three_high"]:
        points = 3
    else:
        points = 0
    label = "planned deload" if deload else "week-specific plan" if explicit else "default target"
    return _component("adherence", "Plan adherence and progression", points, 10,
                      {"actual_abm": actual_abm, "planned_abm": target, "ratio": ratio,
                       "deload": deload, "uses_default_target": not explicit}, "%",
                      f"Actual volume was {ratio:.0%} of the {label}.")


def _drift_points(value: float, thresholds: Optional[dict[str, float]] = None) -> float:
    t = thresholds or {"full": 3, "eight": 5, "five": 7.5, "two": 10}
    return 10 if value <= t["full"] else 8 if value <= t["eight"] else 5 if value <= t["five"] else 2 if value <= t["two"] else 0


def score_durability(activities: list[ActivityMetrics], thresholds: Optional[dict[str, float]] = None) -> ComponentScore:
    values = [a for a in activities if a.drift is not None]
    if not values:
        warnings = sorted({w for a in activities for w in a.warnings if "drift" in w.lower() or "coverage" in w.lower()})
        return _component("durability", "Aerobic durability / cardiac drift", 0, 10, None, "%",
                          "No session qualified for cardiac-drift analysis.", available=False, warnings=warnings)
    raw = median(float(a.drift["decoupling_percent"]) for a in values)
    confidences = [a.drift["confidence"] for a in values]
    confidence = DataConfidence.LOW if "Low" in confidences else DataConfidence.MEDIUM if "Medium" in confidences else DataConfidence.HIGH
    return _component("durability", "Aerobic durability / cardiac drift", _drift_points(raw, thresholds), 10,
                      {"median_decoupling_percent": raw, "sessions": [a.drift for a in values]}, "%",
                      f"Median cardiac drift was {raw:.1f}% across {len(values)} qualifying session(s).",
                      confidence=confidence, activity_ids=[a.activity_id for a in values])


def _efficiency_points(change: float, thresholds: Optional[dict[str, float]] = None) -> float:
    t = thresholds or {"full": 3, "eight": 1, "stable_low": -1, "three_low": -3}
    if change >= t["full"]:
        return 10
    if change >= t["eight"]:
        return 8
    if change >= t["stable_low"]:
        return 6
    if change >= t["three_low"]:
        return 3
    return 0


def score_efficiency(activities: list[ActivityMetrics], week_end: datetime,
                     primary_sport: str, minimum_samples: int,
                     thresholds: Optional[dict[str, float]] = None) -> ComponentScore:
    series = [a for a in activities if a.efficiency and a.activity_type == primary_sport]
    # Never mix watts/HR and speed/HR; prefer power when a complete comparison exists.
    candidates: list[tuple[str, list[ActivityMetrics], list[ActivityMetrics]]] = []
    recent_start = week_end - timedelta(days=27)
    previous_start = week_end - timedelta(days=55)
    for measurement in ("power_hr", "speed_hr"):
        typed = [a for a in series if a.efficiency["measurement_type"] == measurement]
        recent = [a for a in typed if recent_start.date() <= a.start_local.date() <= week_end.date()]
        previous = [a for a in typed if previous_start.date() <= a.start_local.date() < recent_start.date()]
        if len(recent) >= minimum_samples and len(previous) >= minimum_samples:
            candidates.append((measurement, recent, previous))
    if not candidates:
        return _component("efficiency", "Aerobic-efficiency trend", 0, 10, None, "%",
                          f"At least {minimum_samples} {primary_sport} samples are required in each 28-day window.",
                          available=False)
    measurement, recent, previous = candidates[0]
    recent_median = median(a.efficiency["value"] for a in recent)
    previous_median = median(a.efficiency["value"] for a in previous)
    change = 100 * (recent_median - previous_median) / previous_median if previous_median else 0
    proxy = measurement == "speed_hr"
    return _component("efficiency", "Aerobic-efficiency trend", _efficiency_points(change, thresholds), 10, {
        "change_percent": change, "recent_median": recent_median, "previous_median": previous_median,
        "recent_samples": len(recent), "previous_samples": len(previous), "sport": primary_sport,
        "measurement_type": measurement,
    }, "%", f"{primary_sport.title()} aerobic efficiency changed {change:+.1f}% versus the preceding 28 days.",
        confidence=DataConfidence.LOW if proxy else DataConfidence.MEDIUM,
        activity_ids=[a.activity_id for a in recent + previous],
        warnings=["Speed/heart-rate proxy; do not compare with power-based efficiency."] if proxy else [])


def _ratio_grade(value: Optional[float], baseline: Optional[float], half_threshold: float,
                 full_threshold: float = .90) -> Optional[float]:
    if value is None or baseline in (None, 0):
        return None
    ratio = value / baseline
    return 1.0 if ratio >= full_threshold else .5 if ratio >= half_threshold else 0.0


def score_recovery(wellness: list[dict[str, Any]], week_start: datetime,
                   sleep_goal_hours: float, thresholds: Optional[dict[str, float]] = None) -> ComponentScore:
    t = thresholds or {"hrv_full": .90, "hrv_half": .80, "rhr_full_delta": 3,
                       "rhr_half_delta": 5, "sleep_full": .90, "sleep_half": .80,
                       "battery_full": .90, "battery_half": .75}
    recent_dates = {week_start.date() + timedelta(days=i) for i in range(7)}
    baseline_dates = {week_start.date() - timedelta(days=i) for i in range(1, 29)}
    recent = [w for w in wellness if date.fromisoformat(w["date"]) in recent_dates]
    baseline = [w for w in wellness if date.fromisoformat(w["date"]) in baseline_dates]

    def vals(rows: list[dict[str, Any]], key: str) -> list[float]:
        return [float(w[key]) for w in rows if w.get(key) is not None]

    grades: dict[str, Optional[float]] = {}
    raw: dict[str, Any] = {}
    rh, bh = vals(recent, "hrv"), vals(baseline, "hrv")
    raw["hrv"] = {"recent": median(rh) if rh else None, "baseline": median(bh) if bh else None}
    grades["hrv"] = _ratio_grade(raw["hrv"]["recent"], raw["hrv"]["baseline"], t["hrv_half"], t["hrv_full"])

    rr, br = vals(recent, "resting_hr"), vals(baseline, "resting_hr")
    raw["resting_hr"] = {"recent": mean(rr) if rr else None, "baseline": mean(br) if br else None}
    if rr and br:
        delta = raw["resting_hr"]["recent"] - raw["resting_hr"]["baseline"]
        grades["resting_hr"] = 1 if delta <= t["rhr_full_delta"] else .5 if delta <= t["rhr_half_delta"] else 0
        raw["resting_hr"]["delta"] = delta
    else:
        grades["resting_hr"] = None

    rs = vals(recent, "sleep_hours")
    raw["sleep"] = {"recent": mean(rs) if rs else None, "goal": sleep_goal_hours}
    grades["sleep"] = _ratio_grade(raw["sleep"]["recent"], sleep_goal_hours, t["sleep_half"], t["sleep_full"])

    rb, bb = vals(recent, "body_battery"), vals(baseline, "body_battery")
    raw["body_battery"] = {"recent": mean(rb) if rb else None, "baseline": mean(bb) if bb else None}
    grades["body_battery"] = _ratio_grade(raw["body_battery"]["recent"], raw["body_battery"]["baseline"], t["battery_half"], t["battery_full"])

    available = {k: v for k, v in grades.items() if v is not None}
    if not available:
        return _component("recovery", "Recovery and absorption", 0, 10, raw, "points",
                          "No recovery metrics had both current and baseline data.", available=False,
                          warnings=["HRV, resting HR, sleep, and Body Battery are unavailable."])
    points = 10 * mean(available.values())
    missing = [k for k, v in grades.items() if v is None]
    return _component("recovery", "Recovery and absorption", points, 10,
                      {"metrics": raw, "grades": grades, "available_metrics": list(available)}, "points",
                      f"Recovery used {len(available)} of 4 available personal-baseline metrics.",
                      confidence=DataConfidence.HIGH if len(available) == 4 else DataConfidence.MEDIUM,
                      warnings=[f"Missing recovery metrics: {', '.join(missing)}"] if missing else [])


def status_for(score: float) -> str:
    if score >= 90:
        return "Strong base-building week"
    if score >= 75:
        return "Productive aerobic development"
    if score >= 60:
        return "Adequate aerobic stimulus"
    if score >= 45:
        return "Mostly maintenance"
    return "Insufficient stimulus or poor absorption"


def daily_aerobic_statuses(week_key: str, activities: list[ActivityMetrics],
                           settings: AerobicBaseSettings) -> list[dict[str, Any]]:
    """Build a transparent daily guide; this does not alter the weekly score.

    The daily volume guide is the planned weekly target divided by the five days
    that already earn the maximum frequency score.  Volume contributes 70%,
    reaching the qualifying-session minimum contributes 10%, and the existing
    intensity-discipline bands contribute 20%.
    """
    start, _ = iso_week_bounds(week_key)
    target, deload, explicit = planned_target(settings, week_key)
    daily_target = target / 5.0
    intensity_thresholds = settings.scoring_thresholds["intensity"]
    today = datetime.now(BUCHAREST).date()
    results = []
    for offset in range(7):
        day = start.date() + timedelta(days=offset)
        day_activities = [a for a in activities if a.start_local.date() == day]
        abm = sum(a.base_minutes for a in day_activities)
        moving = sum(a.moving_minutes for a in day_activities)
        easy = sum(a.easy_minutes for a in day_activities)
        easy_proportion = easy / moving if moving else None
        if not day_activities:
            label = "Upcoming" if day > today else "No eligible aerobic activity"
            results.append({
                "date": day.isoformat(), "day": day.strftime("%a"), "score": None,
                "band": "neutral", "label": label, "abm": 0.0,
                "daily_target_abm": daily_target, "easy_proportion": None,
                "activity_count": 0, "activity_minutes": 0.0,
                "deload": deload, "uses_default_target": not explicit,
                "explanation": f"0 minutes of eligible aerobic activity. {label}. Neutral days do not change the weekly score by themselves.",
            })
            continue
        volume_points = 70 * min(abm / daily_target, 1) if daily_target else 0
        qualifying_points = 10 * min(abm / settings.qualifying_session_minutes, 1)
        if easy_proportion is None:
            discipline_points = 0
        elif easy_proportion >= intensity_thresholds["full"]:
            discipline_points = 20
        elif easy_proportion >= intensity_thresholds["eight"]:
            discipline_points = 16
        elif easy_proportion >= intensity_thresholds["five"]:
            discipline_points = 10
        else:
            discipline_points = 0
        score = round(volume_points + qualifying_points + discipline_points, 1)
        band = "green" if score > 85 else "blue" if score >= 70 else "yellow"
        label = "Strong" if band == "green" else "Productive" if band == "blue" else "Below daily guide"
        results.append({
            "date": day.isoformat(), "day": day.strftime("%a"), "score": score,
            "band": band, "label": label, "abm": round(abm, 2),
            "daily_target_abm": daily_target, "easy_proportion": easy_proportion,
            "activity_count": len(day_activities), "activity_minutes": round(moving, 2),
            "deload": deload,
            "uses_default_target": not explicit,
            "raw_points": {"volume": round(volume_points, 2),
                           "qualifying_session": round(qualifying_points, 2),
                           "intensity_discipline": round(discipline_points, 2)},
            "explanation": (f"{moving:.0f} minutes of eligible aerobic activity; "
                            f"{abm:.0f}/{daily_target:.0f} daily-guide ABM; "
                            f"{easy_proportion:.0%} easy intensity. This guide does not alter the weekly formula."),
        })
    return results


def assemble_week(week_key: str, week_activities: list[ActivityMetrics],
                  trend_activities: list[ActivityMetrics], wellness: list[dict[str, Any]],
                  settings: AerobicBaseSettings, sport: str = "auto") -> dict[str, Any]:
    start, end = iso_week_bounds(week_key)
    target, deload, explicit = planned_target(settings, week_key)
    sport_totals: dict[str, float] = {}
    for activity in week_activities:
        sport_totals[activity.activity_type] = sport_totals.get(activity.activity_type, 0) + activity.base_minutes
    primary = sport if sport != "auto" else max(sport_totals, key=sport_totals.get, default="cycling")
    volume = score_volume(week_activities, target)
    components = [
        volume,
        score_frequency(week_activities, settings.qualifying_session_minutes),
        score_long_session(week_activities, settings.long_session_target),
        score_intensity(week_activities, settings.scoring_thresholds["intensity"]),
        score_adherence(volume.raw_value["abm"], target, deload, explicit, settings.scoring_thresholds["adherence"]),
        score_durability(week_activities, settings.scoring_thresholds["drift"]),
        score_efficiency(trend_activities, end, primary, settings.minimum_efficiency_samples, settings.scoring_thresholds["efficiency"]),
        score_recovery(wellness, start, settings.sleep_goal_hours, settings.scoring_thresholds["recovery"]),
    ]
    available_points = sum(c.maximum_points for c in components if c.availability)
    earned = sum(c.earned_points for c in components if c.availability)
    normalized = 100 * earned / available_points if available_points else 0
    available = [c for c in components if c.availability]
    strongest = max(available, key=lambda c: c.earned_points / c.maximum_points, default=None)
    weakest = min(available, key=lambda c: c.earned_points / c.maximum_points, default=None)
    explanation = "No score components were available."
    recommendation = "Import more activity and wellness data before changing training."
    if strongest and weakest:
        explanation = f"{strongest.name} was strongest; {weakest.name} was the main limiter."
        recs = {
            "volume": "Build low-intensity minutes gradually toward the weekly target.",
            "frequency": "Distribute easy training across more qualifying days.",
            "long_session": "Extend one easy session progressively, while preserving recovery.",
            "intensity": "Keep more endurance time below LT1 or in the configured easy zones.",
            "adherence": "Align weekly volume with the planned target, including deloads.",
            "durability": "Hold easy intensity steady and build duration before adding intensity.",
            "efficiency": "Keep easy sessions consistent enough to establish a reliable trend.",
            "recovery": "Prioritize recovery; do not add volume solely to raise the score.",
        }
        recommendation = recs[weakest.identifier]
    missing = [c.name for c in components if not c.availability]
    return {
        "week": week_key,
        "week_start": start.date().isoformat(),
        "week_end": end.date().isoformat(),
        "primary_sport": primary,
        "sport_totals": sport_totals,
        "normalized_score": round(normalized, 1),
        "earned_points": round(earned, 1),
        "available_points": available_points,
        "data_coverage": available_points,
        "status": status_for(normalized),
        "explanation": explanation,
        "recommendation": recommendation,
        "missing": missing,
        "components": [c.to_dict() for c in components],
        "activities": [a.to_dict() for a in week_activities],
        "daily_statuses": daily_aerobic_statuses(week_key, week_activities, settings),
        "settings_fingerprint": settings.fingerprint(),
        "provisional": datetime.now(BUCHAREST) <= end,
    }
