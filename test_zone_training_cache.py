"""
Tests for zone training cache methods in CacheManager
"""
import shutil
import sqlite3
import tempfile
from datetime import datetime
from cache_manager import CacheManager


def _set(cache, date_str, *, z_neg1=0.0, z0=0.0, z1=0.0, z2=0.0, z3=0.0, z4_z5=0.0):
    """Helper to call set_zone_training_day with all required args."""
    cache.set_zone_training_day(date_str, z_neg1, z0, z1, z2, z3, z4_z5)


def test_zone_training_cache_miss():
    """get_zone_training_day returns None when no entry is stored"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        result = cache.get_zone_training_day('2026-01-01')
        assert result is None, "Expected None on cache miss"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_roundtrip():
    """Values stored with set_zone_training_day are returned by get_zone_training_day"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        _set(cache, '2026-01-15', z_neg1=200.0, z0=100.0, z1=30.0, z2=45.0, z3=10.0, z4_z5=20.5)

        result = cache.get_zone_training_day('2026-01-15')
        assert result is not None, "Expected a cache hit"
        assert result['z_neg1_minutes'] == 200.0
        assert result['z0_minutes'] == 100.0
        assert result['z1_minutes'] == 30.0, f"Expected z1=30.0, got {result['z1_minutes']}"
        assert result['z2_minutes'] == 45.0, f"Expected z2=45.0, got {result['z2_minutes']}"
        assert result['z3_minutes'] == 10.0
        assert result['z4_z5_minutes'] == 20.5, f"Expected z4_z5=20.5, got {result['z4_z5_minutes']}"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_upsert():
    """set_zone_training_day overwrites an existing entry for the same date"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        _set(cache, '2026-02-01', z1=10.0, z2=30.0, z4_z5=10.0)
        _set(cache, '2026-02-01', z1=20.0, z2=50.0, z4_z5=15.0)

        result = cache.get_zone_training_day('2026-02-01')
        assert result is not None
        assert result['z1_minutes'] == 20.0, "Expected updated z1 value"
        assert result['z2_minutes'] == 50.0, "Expected updated z2 value"
        assert result['z4_z5_minutes'] == 15.0, "Expected updated z4_z5 value"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_multiple_dates():
    """Each date has its own independent cache entry"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        _set(cache, '2026-03-01', z1=15.0, z2=60.0, z4_z5=5.0)
        _set(cache, '2026-03-02', z1=5.0, z2=0.0, z4_z5=90.0)

        r1 = cache.get_zone_training_day('2026-03-01')
        r2 = cache.get_zone_training_day('2026-03-02')
        assert r1['z1_minutes'] == 15.0
        assert r1['z2_minutes'] == 60.0
        assert r2['z2_minutes'] == 0.0
        assert r2['z4_z5_minutes'] == 90.0
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_persists_across_instances():
    """Cached values survive creating a new CacheManager pointing at the same directory"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache1 = CacheManager(cache_dir=temp_dir)
        _set(cache1, '2026-04-10', z1=12.0, z2=75.0, z4_z5=25.0)

        # New instance reads from same DB
        cache2 = CacheManager(cache_dir=temp_dir)
        result = cache2.get_zone_training_day('2026-04-10')
        assert result is not None, "Expected cache to persist across instances"
        assert result['z1_minutes'] == 12.0
        assert result['z2_minutes'] == 75.0
        assert result['z4_z5_minutes'] == 25.0
    finally:
        shutil.rmtree(temp_dir)


def test_clear_all_removes_zone_training_cache():
    """clear_all() also removes zone training cache entries"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        _set(cache, '2026-05-01', z1=8.0, z2=40.0, z4_z5=10.0)
        cache.clear_all()

        result = cache.get_zone_training_day('2026-05-01')
        assert result is None, "Expected zone training cache to be cleared"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_stale_row_treated_as_miss():
    """Rows written with old schema (missing zone columns, NULL after migration) are cache misses"""
    temp_dir = tempfile.mkdtemp()
    try:
        # Simulate an old database that has the table without z_neg1/z0/z3 columns
        db_path = f"{temp_dir}/garmin_cache.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute('''
                CREATE TABLE zone_training_cache (
                    date TEXT PRIMARY KEY,
                    z2_minutes REAL NOT NULL,
                    z4_z5_minutes REAL NOT NULL,
                    cached_at TEXT NOT NULL
                )
            ''')
            conn.execute(
                "INSERT INTO zone_training_cache (date, z2_minutes, z4_z5_minutes, cached_at) "
                "VALUES ('2025-12-01', 50.0, 10.0, '2025-12-01T10:00:00')"
            )
            conn.commit()

        # Opening with a new CacheManager runs ALTER TABLE, leaving new columns NULL for old rows
        cache = CacheManager(cache_dir=temp_dir)
        result = cache.get_zone_training_day('2025-12-01')
        assert result is None, "Stale row with NULL zone columns should be treated as a cache miss"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_all_zones_stored():
    """All 6 zone values are stored and retrieved correctly"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        _set(cache, '2026-06-01', z_neg1=400.0, z0=200.0, z1=120.0, z2=100.0, z3=60.0, z4_z5=80.0)

        result = cache.get_zone_training_day('2026-06-01')
        assert result is not None
        assert result['z_neg1_minutes'] == 400.0
        assert result['z0_minutes'] == 200.0
        assert result['z1_minutes'] == 120.0
        assert result['z2_minutes'] == 100.0
        assert result['z3_minutes'] == 60.0
        assert result['z4_z5_minutes'] == 80.0
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_skips_today():
    """set_zone_training_day must not persist today's date (data still accumulating)"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        today = datetime.now().strftime('%Y-%m-%d')
        _set(cache, today, z_neg1=100.0, z0=50.0, z1=30.0, z2=20.0, z3=10.0, z4_z5=5.0)

        result = cache.get_zone_training_day(today)
        assert result is None, "Today's zone data must not be cached"
    finally:
        shutil.rmtree(temp_dir)
