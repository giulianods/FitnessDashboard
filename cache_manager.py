"""
Cache Manager for Garmin Data
Provides local filesystem caching using SQLite to improve performance
"""
import sqlite3
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

# Configure logger for cache operations
# By default, only WARNING and above will be logged (cache operations won't show)
# To enable cache debug logs, set: logging.getLogger('cache_manager').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


class CacheManager:
    """Manages local caching of Garmin data using SQLite with in-memory layer"""
    
    def __init__(self, cache_dir: str = "data", cache_hours: int = 24):
        """
        Initialize cache manager with two-tier caching (memory + database)
        
        Args:
            cache_dir: Directory to store cache database
            cache_hours: Number of hours before cache expires (default: 24)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_hours = cache_hours
        self.db_path = self.cache_dir / "garmin_cache.db"
        
        # In-memory cache for ultra-fast lookups (no disk I/O)
        # Structure: {'hr': {date_str: (data, cached_at)}, 'hrv': {date_str: (value, cached_at)}}
        self._memory_cache = {
            'hr': {},
            'hrv': {}
        }
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create heart_rate_data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS heart_rate_data (
                    date TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
            ''')
            
            # Create hrv_data table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS hrv_data (
                    date TEXT PRIMARY KEY,
                    value REAL,
                    cached_at TEXT NOT NULL
                )
            ''')
            
            # Create zone_training_cache table (stores pre-computed daily zone minutes)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS zone_training_cache (
                    date TEXT PRIMARY KEY,
                    z1_minutes REAL NOT NULL,
                    z2_minutes REAL NOT NULL,
                    z4_z5_minutes REAL NOT NULL,
                    cached_at TEXT NOT NULL
                )
            ''')

            # Migration: add z1_minutes column if it does not yet exist (older DBs)
            try:
                cursor.execute('ALTER TABLE zone_training_cache ADD COLUMN z1_minutes REAL')
            except Exception:
                pass  # column already exists

            # Create index on cached_at for efficient cleanup
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_hr_cached_at 
                ON heart_rate_data(cached_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_hrv_cached_at 
                ON hrv_data(cached_at)
            ''')
            
            conn.commit()
    
    def _is_cache_valid(self, cached_at_str: str) -> bool:
        """
        Check if cached data is still valid
        
        Args:
            cached_at_str: Timestamp string when data was cached
            
        Returns:
            True if cache is still valid, False otherwise
        """
        cached_at = datetime.fromisoformat(cached_at_str)
        expiry_time = cached_at + timedelta(hours=self.cache_hours)
        return datetime.now() < expiry_time
    
    def get_heart_rate_data(self, date: datetime) -> Optional[List[Dict]]:
        """
        Get cached heart rate data for a specific date
        Uses two-tier cache: memory first, then database
        
        Args:
            date: Date to retrieve data for
            
        Returns:
            List of heart rate data points or None if not cached/expired
        """
        date_str = date.strftime('%Y-%m-%d')
        
        # TIER 1: Check memory cache first (ultra-fast, no disk I/O)
        if date_str in self._memory_cache['hr']:
            data, cached_at = self._memory_cache['hr'][date_str]
            if self._is_cache_valid(cached_at):
                logger.debug(f"Memory cache HIT for HR data {date_str}")
                return data
            else:
                # Expired in memory, remove it
                logger.debug(f"Memory cache EXPIRED for HR data {date_str}")
                del self._memory_cache['hr'][date_str]
        
        # TIER 2: Check database cache (persistent)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT data, cached_at FROM heart_rate_data WHERE date = ?',
                (date_str,)
            )
            
            result = cursor.fetchone()
        
        if result:
            data_json, cached_at = result
            
            # Check if cache is still valid
            if self._is_cache_valid(cached_at):
                logger.debug(f"Database cache HIT for HR data {date_str} (cached at {cached_at})")
                
                # Check if this is a cached None value
                if data_json == '"NO_DATA"':
                    logger.debug(f"Cached None value for {date_str} (no data available)")
                    # Store None in memory cache
                    self._memory_cache['hr'][date_str] = (None, cached_at)
                    return None
                
                # Parse JSON back to list of dicts with datetime objects
                data = json.loads(data_json)
                # Convert timestamp strings back to datetime objects
                for point in data:
                    point['timestamp'] = datetime.fromisoformat(point['timestamp'])
                
                # Store in memory cache for next time
                self._memory_cache['hr'][date_str] = (data, cached_at)
                return data
            else:
                logger.debug(f"Database cache EXPIRED for HR data {date_str}")
                # Clean up expired cache
                self._delete_heart_rate_data(date)
        
        logger.debug(f"Cache MISS for HR data {date_str}")
        return None
    
    def set_heart_rate_data(self, date: datetime, data: Optional[List[Dict]]) -> None:
        """
        Cache heart rate data for a specific date in both database and memory
        
        Args:
            date: Date of the data
            data: List of heart rate data points, or None if no data available
        """
        date_str = date.strftime('%Y-%m-%d')
        cached_at = datetime.now().isoformat()
        
        # Handle None values (no data available for this date)
        if data is None:
            data_json = json.dumps("NO_DATA")
            logger.debug(f"Caching None value for {date_str} (no data available)")
            # Store None in memory cache
            self._memory_cache['hr'][date_str] = (None, cached_at)
        else:
            # Convert datetime objects to ISO format strings for JSON serialization
            serializable_data = []
            for point in data:
                serializable_point = {
                    'timestamp': point['timestamp'].isoformat() if isinstance(point.get('timestamp'), datetime) else point['timestamp'],
                    'heart_rate': point['heart_rate']
                }
                serializable_data.append(serializable_point)
            
            data_json = json.dumps(serializable_data)
            logger.debug(f"Cached HR data for {date_str} ({len(data)} points)")
            # Store in memory cache
            self._memory_cache['hr'][date_str] = (data, cached_at)
        
        # Store in database (persistent)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO heart_rate_data (date, data, cached_at)
                VALUES (?, ?, ?)
            ''', (date_str, data_json, cached_at))
            
            conn.commit()
    
    def get_hrv_data(self, date: datetime) -> Optional[float]:
        """
        Get cached HRV data for a specific date
        Uses two-tier cache: memory first, then database
        
        Args:
            date: Date to retrieve data for
            
        Returns:
            HRV value or None if not cached/expired
        """
        date_str = date.strftime('%Y-%m-%d')
        
        # TIER 1: Check memory cache first (ultra-fast)
        if date_str in self._memory_cache['hrv']:
            value, cached_at = self._memory_cache['hrv'][date_str]
            if self._is_cache_valid(cached_at):
                logger.debug(f"Memory cache HIT for HRV data {date_str}")
                return value
            else:
                # Expired in memory, remove it
                logger.debug(f"Memory cache EXPIRED for HRV data {date_str}")
                del self._memory_cache['hrv'][date_str]
        
        # TIER 2: Check database cache (persistent)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                'SELECT value, cached_at FROM hrv_data WHERE date = ?',
                (date_str,)
            )
            
            result = cursor.fetchone()
        
        if result:
            value, cached_at = result
            
            # Check if cache is still valid
            if self._is_cache_valid(cached_at):
                logger.debug(f"Database cache HIT for HRV data {date_str} (cached at {cached_at})")
                # Store in memory cache for next time
                self._memory_cache['hrv'][date_str] = (value, cached_at)
                return value
            else:
                logger.debug(f"Database cache EXPIRED for HRV data {date_str}")
                # Clean up expired cache
                self._delete_hrv_data(date)
        
        logger.debug(f"Cache MISS for HRV data {date_str}")
        return None
    
    def set_hrv_data(self, date: datetime, value: Optional[float]) -> None:
        """
        Cache HRV data for a specific date in both database and memory
        
        Args:
            date: Date of the data
            value: HRV value (can be None)
        """
        date_str = date.strftime('%Y-%m-%d')
        cached_at = datetime.now().isoformat()
        
        # Store in database (persistent)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO hrv_data (date, value, cached_at)
                VALUES (?, ?, ?)
            ''', (date_str, value, cached_at))
            
            conn.commit()
        
        # Store in memory cache
        self._memory_cache['hrv'][date_str] = (value, cached_at)
        logger.debug(f"Cached HRV data for {date_str} (value: {value})")
    
    def get_zone_training_day(self, date_str: str) -> Optional[Dict]:
        """
        Get cached zone training minutes for a specific date.

        Args:
            date_str: Date string in 'YYYY-MM-DD' format

        Returns:
            Dict with keys 'z1_minutes', 'z2_minutes' and 'z4_z5_minutes', or None on miss.
            Returns None for rows that were cached before Z1 tracking was added (z1_minutes IS NULL).
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT z1_minutes, z2_minutes, z4_z5_minutes FROM zone_training_cache WHERE date = ?',
                (date_str,)
            )
            result = cursor.fetchone()

        if result:
            z1, z2, z4_z5 = result
            # Treat old rows that pre-date Z1 tracking as a cache miss so they get recomputed
            if z1 is None:
                logger.debug(f"Zone training cache STALE (no z1) for {date_str}")
                return None
            logger.debug(f"Zone training cache HIT for {date_str}")
            return {'z1_minutes': z1, 'z2_minutes': z2, 'z4_z5_minutes': z4_z5}

        logger.debug(f"Zone training cache MISS for {date_str}")
        return None

    def set_zone_training_day(self, date_str: str, z1_minutes: float, z2_minutes: float, z4_z5_minutes: float) -> None:
        """
        Cache pre-computed zone training minutes for a specific date.
        Historical data does not change, so no expiry is applied.

        Args:
            date_str: Date string in 'YYYY-MM-DD' format
            z1_minutes: Minutes spent in Zone 1 for that day
            z2_minutes: Minutes spent in Zone 2 for that day
            z4_z5_minutes: Minutes spent in Zone 4+5 for that day
        """
        cached_at = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO zone_training_cache (date, z1_minutes, z2_minutes, z4_z5_minutes, cached_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (date_str, z1_minutes, z2_minutes, z4_z5_minutes, cached_at))
            conn.commit()
        logger.debug(f"Cached zone training for {date_str} (Z1={z1_minutes:.1f}m, Z2={z2_minutes:.1f}m, Z4+Z5={z4_z5_minutes:.1f}m)")

    def _delete_heart_rate_data(self, date: datetime) -> None:
        """Delete heart rate data for a specific date from both database and memory"""
        date_str = date.strftime('%Y-%m-%d')
        
        # Remove from memory cache if present
        if date_str in self._memory_cache['hr']:
            del self._memory_cache['hr'][date_str]
        
        # Remove from database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM heart_rate_data WHERE date = ?', (date_str,))
            conn.commit()
    
    def _delete_hrv_data(self, date: datetime) -> None:
        """Delete HRV data for a specific date from both database and memory"""
        date_str = date.strftime('%Y-%m-%d')
        
        # Remove from memory cache if present
        if date_str in self._memory_cache['hrv']:
            del self._memory_cache['hrv'][date_str]
        
        # Remove from database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM hrv_data WHERE date = ?', (date_str,))
            conn.commit()
    
    def cleanup_expired(self) -> Dict[str, int]:
        """
        Remove all expired cache entries from both database and memory
        
        Returns:
            Dictionary with counts of deleted entries
        """
        expiry_time = datetime.now() - timedelta(hours=self.cache_hours)
        expiry_str = expiry_time.isoformat()
        
        # Clean expired entries from memory cache
        expired_hr_keys = [
            date_str for date_str, (_, cached_at) in self._memory_cache['hr'].items()
            if not self._is_cache_valid(cached_at)
        ]
        expired_hrv_keys = [
            date_str for date_str, (_, cached_at) in self._memory_cache['hrv'].items()
            if not self._is_cache_valid(cached_at)
        ]
        
        for key in expired_hr_keys:
            del self._memory_cache['hr'][key]
        for key in expired_hrv_keys:
            del self._memory_cache['hrv'][key]
        
        # Clean expired entries from database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Delete expired HR data
            cursor.execute(
                'DELETE FROM heart_rate_data WHERE cached_at < ?',
                (expiry_str,)
            )
            hr_deleted = cursor.rowcount
            
            # Delete expired HRV data
            cursor.execute(
                'DELETE FROM hrv_data WHERE cached_at < ?',
                (expiry_str,)
            )
            hrv_deleted = cursor.rowcount
            
            conn.commit()
        
        if hr_deleted > 0 or hrv_deleted > 0:
            logger.debug(f"Cleaned up {hr_deleted} HR entries and {hrv_deleted} HRV entries from database")
        if len(expired_hr_keys) > 0 or len(expired_hrv_keys) > 0:
            logger.debug(f"Cleaned up {len(expired_hr_keys)} HR entries and {len(expired_hrv_keys)} HRV entries from memory")
        
        return {
            'hr_deleted': hr_deleted, 
            'hrv_deleted': hrv_deleted,
            'hr_memory_deleted': len(expired_hr_keys),
            'hrv_memory_deleted': len(expired_hrv_keys)
        }
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cached data in both database and memory
        
        Returns:
            Dictionary with cache statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM heart_rate_data')
            hr_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM hrv_data')
            hrv_count = cursor.fetchone()[0]
        
        return {
            'database': {
                'hr_entries': hr_count,
                'hrv_entries': hrv_count,
                'total_entries': hr_count + hrv_count
            },
            'memory': {
                'hr_entries': len(self._memory_cache['hr']),
                'hrv_entries': len(self._memory_cache['hrv']),
                'total_entries': len(self._memory_cache['hr']) + len(self._memory_cache['hrv'])
            }
        }
    
    def clear_all(self) -> None:
        """Clear all cached data from both database and memory"""
        # Clear memory cache
        self._memory_cache['hr'].clear()
        self._memory_cache['hrv'].clear()
        
        # Clear database cache
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM heart_rate_data')
            cursor.execute('DELETE FROM hrv_data')
            cursor.execute('DELETE FROM zone_training_cache')
            
            conn.commit()
        
        logger.debug("Cleared all cached data from database and memory")
    
    def clear_memory_cache(self) -> None:
        """Clear only the in-memory cache (database cache remains)"""
        hr_count = len(self._memory_cache['hr'])
        hrv_count = len(self._memory_cache['hrv'])
        
        self._memory_cache['hr'].clear()
        self._memory_cache['hrv'].clear()
        
        logger.debug(f"Cleared memory cache: {hr_count} HR entries, {hrv_count} HRV entries")
    
    def get_memory_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about in-memory cache only
        
        Returns:
            Dictionary with memory cache statistics
        """
        return {
            'hr_entries': len(self._memory_cache['hr']),
            'hrv_entries': len(self._memory_cache['hrv']),
            'total_entries': len(self._memory_cache['hr']) + len(self._memory_cache['hrv'])
        }
