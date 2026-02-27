"""
Tests for the Zone Calendar (6th dashboard) logic:
- 5-week window calculation (current ISO week + 4 prior)
- Stacked zone data per day
- Cache read/write integration via CacheManager
"""
import shutil
import tempfile
from datetime import date, timedelta

from cache_manager import CacheManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _monday_of(d: date) -> date:
    """Return the Monday of the ISO week containing *d*."""
    return d - timedelta(days=d.weekday())


def _build_five_weeks(today: date):
    """Return a list of 5 lists of dates, oldest first (Mon–Sun rows).
    Mirrors the logic in get_zone_calendar_data."""
    current_monday = _monday_of(today)
    weeks = []
    for w in range(4, -1, -1):
        monday = current_monday - timedelta(weeks=w)
        weeks.append([monday + timedelta(days=d) for d in range(7)])
    return weeks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_five_week_window_count():
    """Exactly 5 rows of 7 days are generated."""
    weeks = _build_five_weeks(date(2026, 2, 27))  # a Friday
    assert len(weeks) == 5
    for row in weeks:
        assert len(row) == 7


def test_five_week_window_starts_on_monday():
    """Every row starts on a Monday."""
    weeks = _build_five_weeks(date(2026, 2, 27))
    for row in weeks:
        assert row[0].weekday() == 0, f"Expected Monday, got {row[0].strftime('%A')}"


def test_five_week_window_ends_on_sunday():
    """Every row ends on a Sunday."""
    weeks = _build_five_weeks(date(2026, 2, 27))
    for row in weeks:
        assert row[6].weekday() == 6, f"Expected Sunday, got {row[6].strftime('%A')}"


def test_five_week_window_last_row_contains_today():
    """The last (5th) row contains the current date when today is in range Mon–Sun."""
    today = date(2026, 2, 27)  # a Friday
    weeks = _build_five_weeks(today)
    last_row_dates = [d.isoformat() for d in weeks[-1]]
    assert today.isoformat() in last_row_dates


def test_five_week_window_consecutive():
    """Rows are consecutive weeks (no gaps, no overlaps)."""
    weeks = _build_five_weeks(date(2026, 3, 10))  # a Tuesday
    for i in range(1, 5):
        prev_sunday = weeks[i - 1][6]
        next_monday = weeks[i][0]
        assert next_monday == prev_sunday + timedelta(days=1), (
            f"Gap between week {i-1} and week {i}: {prev_sunday} -> {next_monday}"
        )


def test_cache_stores_all_zones_and_calendar_reads_them():
    """CacheManager stores all zone values; calendar logic can reconstruct them."""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        date_str = '2026-01-20'

        # Simulate storing a day's worth of zone data (all zones)
        cache.set_zone_training_day(date_str, 300.0, 150.0, 90.0, 60.0, 30.0, 50.0)

        # Simulate the calendar endpoint reading back cached values
        cached = cache.get_zone_training_day(date_str)
        assert cached is not None

        # Reconstruct the zone dict as done in get_zone_calendar_data
        zone_dict = {
            'Z-1': cached['z_neg1_minutes'],
            'Z0':  cached['z0_minutes'],
            'Z1':  cached['z1_minutes'],
            'Z2':  cached['z2_minutes'],
            'Z3':  cached['z3_minutes'],
            'Z4':  cached['z4_z5_minutes'],
            'Z5':  0.0,
        }
        assert zone_dict['Z-1'] == 300.0
        assert zone_dict['Z0'] == 150.0
        assert zone_dict['Z1'] == 90.0
        assert zone_dict['Z2'] == 60.0
        assert zone_dict['Z3'] == 30.0
        assert zone_dict['Z4'] == 50.0
    finally:
        shutil.rmtree(temp_dir)


def test_cache_miss_returns_none_for_calendar():
    """Calendar logic gets None for a date not yet cached."""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        result = cache.get_zone_training_day('2026-02-01')
        assert result is None
    finally:
        shutil.rmtree(temp_dir)
