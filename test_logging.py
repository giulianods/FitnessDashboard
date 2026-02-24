"""
Test script to demonstrate the logging configuration for cache_manager
"""
import logging
from datetime import datetime
from cache_manager import CacheManager

print("=" * 80)
print("Testing Cache Manager Logging Configuration")
print("=" * 80)

# Test 1: Default logging (WARNING level - cache operations won't show)
print("\n1. Default Logging (WARNING level - cache operations are SILENT)")
print("-" * 80)
cache = CacheManager(cache_dir='test_data')

# These operations won't produce any output because default level is WARNING
test_date = datetime(2026, 2, 7)
cache.set_heart_rate_data(test_date, [{'timestamp': test_date, 'heart_rate': 75}])
result = cache.get_heart_rate_data(test_date)
print(f"Retrieved HR data: {len(result) if result else 0} points")
print("✓ No cache debug messages shown (as expected with WARNING level)")

# Test 2: Enable DEBUG logging to see cache operations
print("\n2. Enable DEBUG Logging (cache operations are VISIBLE)")
print("-" * 80)

# Configure logging to show DEBUG messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing configuration
)

# Enable debug logging for cache_manager
cache_logger = logging.getLogger('cache_manager')
cache_logger.setLevel(logging.DEBUG)

# Create a new cache instance
cache2 = CacheManager(cache_dir='test_data2')

# Now these operations will show debug messages
test_date2 = datetime(2026, 2, 8)
print("\nStoring data (should show debug message):")
cache2.set_heart_rate_data(test_date2, [{'timestamp': test_date2, 'heart_rate': 80}])

print("\nRetrieving data from memory cache (should show HIT):")
result2 = cache2.get_heart_rate_data(test_date2)

print("\nRetrieving again (should show memory cache HIT):")
result2 = cache2.get_heart_rate_data(test_date2)

# Test 3: Set to INFO level (shows important operations, not verbose cache hits)
print("\n3. INFO Logging Level (shows important operations only)")
print("-" * 80)
cache_logger.setLevel(logging.INFO)

print("\nCache operations at INFO level:")
cache2.cleanup_expired()
cache2.clear_memory_cache()

# Test 4: Disable all cache logging
print("\n4. Disable Cache Logging (set to WARNING)")
print("-" * 80)
cache_logger.setLevel(logging.WARNING)

print("\nPerforming operations (no output expected):")
cache2.set_heart_rate_data(test_date2, [{'timestamp': test_date2, 'heart_rate': 85}])
cache2.get_heart_rate_data(test_date2)
print("✓ Operations completed silently")

# Summary
print("\n" + "=" * 80)
print("SUMMARY: How to Control Cache Logging")
print("=" * 80)
print("""
By default, cache operations are SILENT (logging level = WARNING).

To enable cache debug messages, add this to your application:

    import logging
    logging.getLogger('cache_manager').setLevel(logging.DEBUG)

To configure different levels:
    - logging.DEBUG:   Show all cache operations (hits, misses, stores)
    - logging.INFO:    Show important operations only (cleanup, clear)
    - logging.WARNING: Silent (default - best for production)

You can also use environment variables or config files to control this.
""")

# Cleanup
import shutil
shutil.rmtree('test_data', ignore_errors=True)
shutil.rmtree('test_data2', ignore_errors=True)

print("✓ Test completed successfully!")
