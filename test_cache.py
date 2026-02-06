#!/usr/bin/env python3
"""
Test script to verify cache functionality
"""
from datetime import datetime, timedelta
from cache_manager import CacheManager

def test_cache():
    """Test basic cache operations"""
    print("Testing Cache Manager...")
    print("=" * 60)
    
    # Initialize cache
    cache = CacheManager(cache_dir="test_data", cache_hours=24)
    
    # Test HR data caching
    test_date = datetime.now() - timedelta(days=1)
    print(f"\n1. Testing HR data cache for {test_date.strftime('%Y-%m-%d')}")
    
    # Should be a cache miss
    result = cache.get_heart_rate_data(test_date)
    assert result is None, "Expected cache miss"
    print("   ✓ Cache miss as expected")
    
    # Store test data
    test_hr_data = [
        {'timestamp': datetime.now(), 'heart_rate': 75},
        {'timestamp': datetime.now(), 'heart_rate': 80},
        {'timestamp': datetime.now(), 'heart_rate': 70}
    ]
    cache.set_heart_rate_data(test_date, test_hr_data)
    print("   ✓ Stored test HR data")
    
    # Should be a cache hit
    cached_data = cache.get_heart_rate_data(test_date)
    assert cached_data is not None, "Expected cache hit"
    assert len(cached_data) == 3, "Expected 3 data points"
    print(f"   ✓ Cache hit! Retrieved {len(cached_data)} points")
    
    # Test HRV data caching
    print(f"\n2. Testing HRV data cache for {test_date.strftime('%Y-%m-%d')}")
    
    # Should be a cache miss
    result = cache.get_hrv_data(test_date)
    assert result is None, "Expected cache miss"
    print("   ✓ Cache miss as expected")
    
    # Store test data
    test_hrv = 65.5
    cache.set_hrv_data(test_date, test_hrv)
    print(f"   ✓ Stored test HRV data: {test_hrv}")
    
    # Should be a cache hit
    cached_hrv = cache.get_hrv_data(test_date)
    assert cached_hrv == test_hrv, "Expected cached HRV value"
    print(f"   ✓ Cache hit! Retrieved HRV: {cached_hrv}")
    
    # Test cache stats
    print("\n3. Testing cache statistics")
    stats = cache.get_cache_stats()
    print(f"   HR entries: {stats['hr_entries']}")
    print(f"   HRV entries: {stats['hrv_entries']}")
    print(f"   Total entries: {stats['total_entries']}")
    assert stats['hr_entries'] == 1, "Expected 1 HR entry"
    assert stats['hrv_entries'] == 1, "Expected 1 HRV entry"
    print("   ✓ Statistics correct")
    
    # Test cleanup
    print("\n4. Testing cache cleanup")
    cache.clear_all()
    stats_after = cache.get_cache_stats()
    assert stats_after['total_entries'] == 0, "Expected empty cache"
    print("   ✓ Cache cleared successfully")
    
    # Clean up test database
    import shutil
    import os
    if os.path.exists("test_data"):
        shutil.rmtree("test_data")
        print("   ✓ Cleaned up test data directory")
    
    print("\n" + "=" * 60)
    print("✓ All cache tests passed!")

if __name__ == '__main__':
    test_cache()
