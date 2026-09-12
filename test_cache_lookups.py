"""Tests for cache hit/miss distinction, historical TTL, and bulk HRV."""
import sqlite3
import tempfile
import shutil
from datetime import datetime, timedelta

import pytest

from cache_manager import CacheManager
from garmin_client import GarminClient


def _hr_point(ts, bpm):
    return {'timestamp': datetime.fromisoformat(ts), 'heart_rate': bpm}


def _backdate(db_path, table, date_str, hours=48):
    cached_at = (datetime.now() - timedelta(hours=hours)).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f'UPDATE {table} SET cached_at = ? WHERE date = ?',
            (cached_at, date_str),
        )
        conn.commit()


def test_lookup_hr_distinguishes_miss_from_no_data():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        day = datetime(2026, 3, 1)
        miss = cache.lookup_heart_rate_data(day)
        assert miss.hit is False

        cache.set_heart_rate_data(day, None)
        cached_empty = cache.lookup_heart_rate_data(day)
        assert cached_empty.hit is True
        assert cached_empty.value is None
    finally:
        shutil.rmtree(temp_dir)


def test_lookup_hrv_distinguishes_miss_from_null():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        day = datetime(2026, 3, 2)
        miss = cache.lookup_hrv_data(day)
        assert miss.hit is False

        cache.set_hrv_data(day, None)
        cached_empty = cache.lookup_hrv_data(day)
        assert cached_empty.hit is True
        assert cached_empty.value is None

        cache.set_hrv_data(day, 42.5)
        cached = cache.lookup_hrv_data(day)
        assert cached.hit is True
        assert cached.value == 42.5
    finally:
        shutil.rmtree(temp_dir)


def test_hrv_bulk_includes_null_and_omits_misses():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        cache.set_hrv_data(datetime(2026, 4, 1), None)
        cache.set_hrv_data(datetime(2026, 4, 2), 55.0)

        result = cache.get_hrv_data_bulk(['2026-04-01', '2026-04-02', '2026-04-03'])
        assert '2026-04-01' in result
        assert result['2026-04-01'] is None
        assert result['2026-04-02'] == 55.0
        assert '2026-04-03' not in result
    finally:
        shutil.rmtree(temp_dir)


def test_historical_hr_does_not_expire():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir, cache_hours=24)
        day = datetime.now() - timedelta(days=10)
        day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        pts = [_hr_point(day.isoformat(), 70)]
        cache.set_heart_rate_data(day, pts)
        _backdate(cache.db_path, 'heart_rate_data', day.strftime('%Y-%m-%d'), hours=72)
        cache.clear_memory_cache()

        result = cache.get_heart_rate_data(day)
        assert result is not None
        assert result[0]['heart_rate'] == 70
        assert day.strftime('%Y-%m-%d') in cache.get_heart_rate_data_bulk(
            [day.strftime('%Y-%m-%d')]
        )
    finally:
        shutil.rmtree(temp_dir)


def test_yesterday_hr_still_expires():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir, cache_hours=24)
        yesterday = datetime.now() - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        pts = [_hr_point(yesterday.isoformat(), 68)]
        cache.set_heart_rate_data(yesterday, pts)
        _backdate(cache.db_path, 'heart_rate_data', yesterday.strftime('%Y-%m-%d'), hours=25)
        cache.clear_memory_cache()

        assert cache.get_heart_rate_data(yesterday) is None
        assert yesterday.strftime('%Y-%m-%d') not in cache.get_heart_rate_data_bulk(
            [yesterday.strftime('%Y-%m-%d')]
        )
    finally:
        shutil.rmtree(temp_dir)


def test_cleanup_expired_keeps_historical_rows():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir, cache_hours=24)
        historical = datetime.now() - timedelta(days=8)
        historical = historical.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday = datetime.now() - timedelta(days=1)
        yesterday = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        cache.set_heart_rate_data(historical, [_hr_point(historical.isoformat(), 60)])
        cache.set_heart_rate_data(yesterday, [_hr_point(yesterday.isoformat(), 61)])
        _backdate(cache.db_path, 'heart_rate_data', historical.strftime('%Y-%m-%d'), hours=72)
        _backdate(cache.db_path, 'heart_rate_data', yesterday.strftime('%Y-%m-%d'), hours=72)
        cache.clear_memory_cache()

        removed = cache.cleanup_expired()
        assert removed['hr_deleted'] == 1
        assert cache.get_heart_rate_data(historical) is not None
        assert cache.get_heart_rate_data(yesterday) is None
    finally:
        shutil.rmtree(temp_dir)


def test_client_returns_cached_hr_none_without_login():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        day = datetime(2026, 5, 1)
        cache.set_heart_rate_data(day, None)

        client = GarminClient(use_cache=True)
        client.cache = cache
        assert client.get_heart_rate_data(day) is None
    finally:
        shutil.rmtree(temp_dir)


def test_client_returns_cached_hrv_none_without_login():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        day = datetime(2026, 5, 2)
        cache.set_hrv_data(day, None)

        client = GarminClient(use_cache=True)
        client.cache = cache
        assert client.get_hrv_data(day) is None
    finally:
        shutil.rmtree(temp_dir)


def test_client_miss_still_requires_login():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        client = GarminClient(use_cache=True)
        client.cache = cache
        with pytest.raises(Exception, match="Not logged in"):
            client.get_heart_rate_data(datetime(2026, 5, 3))
        with pytest.raises(Exception, match="Not logged in"):
            client.get_hrv_data(datetime(2026, 5, 3))
    finally:
        shutil.rmtree(temp_dir)


def test_range_helpers_use_cached_empty_without_login():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        d1 = datetime(2026, 6, 1)
        d2 = datetime(2026, 6, 2)
        pts = [_hr_point('2026-06-01T09:00:00', 64)]
        cache.set_heart_rate_data(d1, pts)
        cache.set_heart_rate_data(d2, None)
        cache.set_hrv_data(d1, 40.0)
        cache.set_hrv_data(d2, None)

        client = GarminClient(use_cache=True)
        client.cache = cache
        hr = client.get_heart_rate_data_for_dates([d1, d2])
        hrv = client.get_hrv_data_for_dates([d1, d2])

        assert hr['2026-06-01'][0]['heart_rate'] == 64
        assert hr['2026-06-02'] is None
        assert hrv['2026-06-01'] == 40.0
        assert hrv['2026-06-02'] is None
    finally:
        shutil.rmtree(temp_dir)


def test_force_refetch_ignores_cached_no_data():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        day = datetime(2026, 5, 4)
        cache.set_heart_rate_data(day, None)
        client = GarminClient(use_cache=True)
        client.cache = cache
        assert client.get_heart_rate_data(day) is None
        with pytest.raises(Exception, match="Not logged in"):
            client.get_heart_rate_data(day, force=True)
    finally:
        shutil.rmtree(temp_dir)


def test_hrv_api_failure_does_not_cache():
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        client = GarminClient(use_cache=True)
        client.cache = cache

        class FakeGarmin:
            def get_sleep_data(self, date_str):
                raise RuntimeError('network down')

        client.client = FakeGarmin()
        day = datetime(2026, 5, 5)
        assert client.get_hrv_data(day, force=True) is None
        assert client.cache.lookup_hrv_data(day).hit is False
    finally:
        shutil.rmtree(temp_dir)


def test_contiguous_date_ranges_split_long_span():
    from app import _contiguous_date_ranges
    days = [f'2025-04-{day:02d}' for day in range(1, 16)]
    ranges = _contiguous_date_ranges(days, 7)
    assert ranges == [
        ('2025-04-01', '2025-04-07'),
        ('2025-04-08', '2025-04-14'),
        ('2025-04-15', '2025-04-15'),
    ]
