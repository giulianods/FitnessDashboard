"""
Cache Manager for Garmin Data
Provides local filesystem caching using SQLite to improve performance
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path


class CacheManager:
    """Manages local caching of Garmin data using SQLite"""
    
    def __init__(self, cache_dir: str = "data", cache_hours: int = 24):
        """
        Initialize cache manager
        
        Args:
            cache_dir: Directory to store cache database
            cache_hours: Number of hours before cache expires (default: 24)
        """
        self.cache_dir = Path(cache_dir)
        self.cache_hours = cache_hours
        self.db_path = self.cache_dir / "garmin_cache.db"
        
        # Create cache directory if it doesn't exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
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
        conn.close()
    
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
        
        Args:
            date: Date to retrieve data for
            
        Returns:
            List of heart rate data points or None if not cached/expired
        """
        date_str = date.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT data, cached_at FROM heart_rate_data WHERE date = ?',
            (date_str,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            data_json, cached_at = result
            
            # Check if cache is still valid
            if self._is_cache_valid(cached_at):
                print(f"Cache HIT for HR data {date_str} (cached at {cached_at})")
                # Parse JSON back to list of dicts with datetime objects
                data = json.loads(data_json)
                # Convert timestamp strings back to datetime objects
                for point in data:
                    point['timestamp'] = datetime.fromisoformat(point['timestamp'])
                return data
            else:
                print(f"Cache EXPIRED for HR data {date_str}")
                # Clean up expired cache
                self._delete_heart_rate_data(date)
        
        print(f"Cache MISS for HR data {date_str}")
        return None
    
    def set_heart_rate_data(self, date: datetime, data: List[Dict]) -> None:
        """
        Cache heart rate data for a specific date
        
        Args:
            date: Date of the data
            data: List of heart rate data points
        """
        date_str = date.strftime('%Y-%m-%d')
        cached_at = datetime.now().isoformat()
        
        # Convert datetime objects to ISO format strings for JSON serialization
        serializable_data = []
        for point in data:
            serializable_point = point.copy()
            if isinstance(serializable_point.get('timestamp'), datetime):
                serializable_point['timestamp'] = serializable_point['timestamp'].isoformat()
            serializable_data.append(serializable_point)
        
        data_json = json.dumps(serializable_data)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO heart_rate_data (date, data, cached_at)
            VALUES (?, ?, ?)
        ''', (date_str, data_json, cached_at))
        
        conn.commit()
        conn.close()
        
        print(f"Cached HR data for {date_str} ({len(data)} points)")
    
    def get_hrv_data(self, date: datetime) -> Optional[float]:
        """
        Get cached HRV data for a specific date
        
        Args:
            date: Date to retrieve data for
            
        Returns:
            HRV value or None if not cached/expired
        """
        date_str = date.strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT value, cached_at FROM hrv_data WHERE date = ?',
            (date_str,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            value, cached_at = result
            
            # Check if cache is still valid
            if self._is_cache_valid(cached_at):
                print(f"Cache HIT for HRV data {date_str} (cached at {cached_at})")
                return value
            else:
                print(f"Cache EXPIRED for HRV data {date_str}")
                # Clean up expired cache
                self._delete_hrv_data(date)
        
        print(f"Cache MISS for HRV data {date_str}")
        return None
    
    def set_hrv_data(self, date: datetime, value: Optional[float]) -> None:
        """
        Cache HRV data for a specific date
        
        Args:
            date: Date of the data
            value: HRV value (can be None)
        """
        date_str = date.strftime('%Y-%m-%d')
        cached_at = datetime.now().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO hrv_data (date, value, cached_at)
            VALUES (?, ?, ?)
        ''', (date_str, value, cached_at))
        
        conn.commit()
        conn.close()
        
        print(f"Cached HRV data for {date_str} (value: {value})")
    
    def _delete_heart_rate_data(self, date: datetime) -> None:
        """Delete heart rate data for a specific date"""
        date_str = date.strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM heart_rate_data WHERE date = ?', (date_str,))
        conn.commit()
        conn.close()
    
    def _delete_hrv_data(self, date: datetime) -> None:
        """Delete HRV data for a specific date"""
        date_str = date.strftime('%Y-%m-%d')
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM hrv_data WHERE date = ?', (date_str,))
        conn.commit()
        conn.close()
    
    def cleanup_expired(self) -> Dict[str, int]:
        """
        Remove all expired cache entries
        
        Returns:
            Dictionary with counts of deleted entries
        """
        expiry_time = datetime.now() - timedelta(hours=self.cache_hours)
        expiry_str = expiry_time.isoformat()
        
        conn = sqlite3.connect(self.db_path)
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
        conn.close()
        
        if hr_deleted > 0 or hrv_deleted > 0:
            print(f"Cleaned up {hr_deleted} HR entries and {hrv_deleted} HRV entries")
        
        return {'hr_deleted': hr_deleted, 'hrv_deleted': hrv_deleted}
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get statistics about cached data
        
        Returns:
            Dictionary with cache statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM heart_rate_data')
        hr_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM hrv_data')
        hrv_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'hr_entries': hr_count,
            'hrv_entries': hrv_count,
            'total_entries': hr_count + hrv_count
        }
    
    def clear_all(self) -> None:
        """Clear all cached data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM heart_rate_data')
        cursor.execute('DELETE FROM hrv_data')
        
        conn.commit()
        conn.close()
        
        print("Cleared all cached data")
