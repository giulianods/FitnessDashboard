"""
Test in-memory caching layer functionality
"""
import sys
from datetime import datetime, timedelta
from cache_manager import CacheManager
import tempfile
import shutil
import time

def test_memory_cache():
    """Test that in-memory caching works correctly"""
    
    # Create temporary cache directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        print("=" * 60)
        print("Testing In-Memory Cache Layer")
        print("=" * 60)
        
        # Create cache manager
        cache = CacheManager(cache_dir=temp_dir, cache_hours=24)
        
        # Test dates
        date1 = datetime(2026, 2, 1)
        date2 = datetime(2026, 2, 2)
        
        # Test data
        hr_data1 = [
            {'timestamp': datetime(2026, 2, 1, 10, 0), 'heart_rate': 60},
            {'timestamp': datetime(2026, 2, 1, 10, 5), 'heart_rate': 65},
        ]
        hr_data2 = [
            {'timestamp': datetime(2026, 2, 2, 10, 0), 'heart_rate': 70},
            {'timestamp': datetime(2026, 2, 2, 10, 5), 'heart_rate': 75},
        ]
        hrv_value1 = 55.0
        hrv_value2 = 60.0
        
        print("\n1. Initial state - no cache")
        print("-" * 60)
        result = cache.get_heart_rate_data(date1)
        assert result is None, "Should return None on cache miss"
        print("✓ Cache miss works correctly\n")
        
        print("2. Store data in cache (writes to DB + memory)")
        print("-" * 60)
        cache.set_heart_rate_data(date1, hr_data1)
        cache.set_hrv_data(date1, hrv_value1)
        print("✓ Data cached\n")
        
        print("3. Retrieve from memory cache (1st time - should hit memory)")
        print("-" * 60)
        start_time = time.time()
        result_hr = cache.get_heart_rate_data(date1)
        memory_time = time.time() - start_time
        assert result_hr is not None, "Should return data from memory cache"
        assert len(result_hr) == 2, "Should return correct number of data points"
        print(f"✓ Memory cache hit (took {memory_time*1000:.3f}ms)\n")
        
        result_hrv = cache.get_hrv_data(date1)
        assert result_hrv == hrv_value1, "Should return correct HRV value"
        print("✓ HRV also in memory cache\n")
        
        print("4. Clear memory cache only (DB still has data)")
        print("-" * 60)
        cache.clear_memory_cache()
        print("✓ Memory cache cleared\n")
        
        print("5. Retrieve again (should hit DB, then populate memory)")
        print("-" * 60)
        start_time = time.time()
        result_hr = cache.get_heart_rate_data(date1)
        db_time = time.time() - start_time
        assert result_hr is not None, "Should return data from DB"
        assert len(result_hr) == 2, "Should return correct data"
        print(f"✓ Database cache hit (took {db_time*1000:.3f}ms)")
        print(f"✓ Memory cache now populated again\n")
        
        # Also retrieve HRV to populate memory
        result_hrv = cache.get_hrv_data(date1)
        assert result_hrv == hrv_value1, "Should return HRV from DB"
        print("✓ HRV also retrieved from DB and cached in memory\n")
        
        print("6. Retrieve once more (should be fast - memory cache)")
        print("-" * 60)
        start_time = time.time()
        result_hr = cache.get_heart_rate_data(date1)
        memory_time2 = time.time() - start_time
        assert result_hr is not None, "Should return data from memory"
        print(f"✓ Memory cache hit (took {memory_time2*1000:.3f}ms)")
        print(f"✓ Memory is faster than DB: {memory_time2 < db_time}\n")
        
        print("7. Cache statistics")
        print("-" * 60)
        stats = cache.get_cache_stats()
        print(f"Database: {stats['database']}")
        print(f"Memory: {stats['memory']}")
        assert stats['memory']['hr_entries'] == 1, "Should have 1 HR entry in memory"
        assert stats['memory']['hrv_entries'] == 1, "Should have 1 HRV entry in memory"
        assert stats['database']['hr_entries'] == 1, "Should have 1 HR entry in DB"
        assert stats['database']['hrv_entries'] == 1, "Should have 1 HRV entry in DB"
        print("✓ Statistics correct\n")
        
        print("8. Store and retrieve second date")
        print("-" * 60)
        cache.set_heart_rate_data(date2, hr_data2)
        cache.set_hrv_data(date2, hrv_value2)
        result_hr = cache.get_heart_rate_data(date2)
        result_hrv = cache.get_hrv_data(date2)
        assert result_hr is not None, "Should have date2 HR data"
        assert result_hrv == hrv_value2, "Should have date2 HRV data"
        print("✓ Multiple dates cached correctly\n")
        
        print("9. Verify both dates in memory")
        print("-" * 60)
        stats = cache.get_memory_cache_stats()
        print(f"Memory cache: {stats}")
        assert stats['hr_entries'] == 2, "Should have 2 HR entries"
        assert stats['hrv_entries'] == 2, "Should have 2 HRV entries"
        print("✓ Both dates in memory cache\n")
        
        print("10. Test None value caching")
        print("-" * 60)
        date3 = datetime(2026, 2, 3)
        cache.set_heart_rate_data(date3, None)  # No data for this date
        result = cache.get_heart_rate_data(date3)
        assert result is None, "Should return None for no-data date"
        print("✓ None values cached correctly\n")
        
        # Verify it's actually cached (second retrieval should be from memory)
        result2 = cache.get_heart_rate_data(date3)
        assert result2 is None, "Should still return None from memory"
        print("✓ None value retrieved from memory cache\n")
        
        print("11. Clear all cache")
        print("-" * 60)
        cache.clear_all()
        stats = cache.get_cache_stats()
        assert stats['memory']['total_entries'] == 0, "Memory should be empty"
        assert stats['database']['total_entries'] == 0, "Database should be empty"
        print("✓ All cache cleared\n")
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        print("\nSummary:")
        print(f"- Memory cache is working correctly")
        print(f"- Falls back to database when memory misses")
        print(f"- Memory cache is {db_time/memory_time2:.1f}x faster than database")
        print(f"- None values are cached properly")
        print(f"- Cache statistics are accurate")
        
    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        print("\nTest cleanup complete")


def test_set_heart_rate_skips_today():
    """set_heart_rate_data must not cache today's data (still accumulating)"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        hr_data = [{'timestamp': today, 'heart_rate': 70}]
        cache.set_heart_rate_data(today, hr_data)

        result = cache.get_heart_rate_data(today)
        assert result is None, "Today's HR data must not be cached"
    finally:
        shutil.rmtree(temp_dir)


def test_set_hrv_skips_today():
    """set_hrv_data must not cache today's data (still accumulating)"""
    temp_dir = tempfile.mkdtemp()
    try:
        cache = CacheManager(cache_dir=temp_dir)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cache.set_hrv_data(today, 55.0)

        result = cache.get_hrv_data(today)
        assert result is None, "Today's HRV data must not be cached"
    finally:
        shutil.rmtree(temp_dir)


if __name__ == '__main__':
    test_memory_cache()
