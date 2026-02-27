"""
Tests for zone training cache methods in CacheManager
"""
import shutil
import sqlite3
import tempfile
from cache_manager import CacheManager


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
        cache.set_zone_training_day('2026-01-15', z1_minutes=30.0, z2_minutes=45.0, z4_z5_minutes=20.5)

        result = cache.get_zone_training_day('2026-01-15')
        assert result is not None, "Expected a cache hit"
        assert result['z1_minutes'] == 30.0, f"Expected z1=30.0, got {result['z1_minutes']}"
        assert result['z2_minutes'] == 45.0, f"Expected z2=45.0, got {result['z2_minutes']}"
        assert result['z4_z5_minutes'] == 20.5, f"Expected z4_z5=20.5, got {result['z4_z5_minutes']}"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_upsert():
    """set_zone_training_day overwrites an existing entry for the same date"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        cache.set_zone_training_day('2026-02-01', z1_minutes=10.0, z2_minutes=30.0, z4_z5_minutes=10.0)
        cache.set_zone_training_day('2026-02-01', z1_minutes=20.0, z2_minutes=50.0, z4_z5_minutes=15.0)

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
        cache.set_zone_training_day('2026-03-01', z1_minutes=15.0, z2_minutes=60.0, z4_z5_minutes=5.0)
        cache.set_zone_training_day('2026-03-02', z1_minutes=5.0, z2_minutes=0.0, z4_z5_minutes=90.0)

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
        cache1.set_zone_training_day('2026-04-10', z1_minutes=12.0, z2_minutes=75.0, z4_z5_minutes=25.0)

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
        cache.set_zone_training_day('2026-05-01', z1_minutes=8.0, z2_minutes=40.0, z4_z5_minutes=10.0)
        cache.clear_all()

        result = cache.get_zone_training_day('2026-05-01')
        assert result is None, "Expected zone training cache to be cleared"
    finally:
        shutil.rmtree(temp_dir)


def test_zone_training_cache_null_z1_treated_as_miss():
    """Rows written before Z1 tracking (z1_minutes is NULL after migration) are treated as cache misses"""
    temp_dir = tempfile.mkdtemp()
    try:
        # Simulate an old database that has the table without z1_minutes
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

        # Opening with a new CacheManager runs ALTER TABLE, leaving z1_minutes NULL for old rows
        cache = CacheManager(cache_dir=temp_dir)
        result = cache.get_zone_training_day('2025-12-01')
        assert result is None, "Row with NULL z1_minutes should be treated as a cache miss"
    finally:
        shutil.rmtree(temp_dir)
