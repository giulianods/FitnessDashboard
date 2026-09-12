"""
Garmin Connect API Client
Handles authentication and data retrieval from Garmin Connect
"""
import json
import os
import logging
from datetime import datetime, timedelta
from garminconnect import Garmin
from typing import Optional, Dict, List
from cache_manager import CacheManager

logger = logging.getLogger(__name__)


class GarminClient:
    """Client for interacting with Garmin Connect API"""
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None, use_cache: bool = True):
        """
        Initialize Garmin client
        
        Args:
            email: Garmin account email
            password: Garmin account password
            use_cache: Whether to use local caching (default: True)
        """
        self.email = email
        self.password = password
        self.client = None
        self.use_cache = use_cache
        self.cache = CacheManager() if use_cache else None
        
    def load_credentials(self, config_path: str = 'config.json') -> None:
        """
        Load credentials from config file
        
        Args:
            config_path: Path to config JSON file
        """
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.email = config.get('email')
                self.password = config.get('password')
        else:
            raise FileNotFoundError(
                f"Config file not found: {config_path}. "
                f"Please create it from config.json.example"
            )
    
    def login(self) -> None:
        """Authenticate with Garmin Connect"""
        if not self.email or not self.password:
            raise ValueError("Email and password are required")
        
        try:
            self.client = Garmin(self.email, self.password)
            self.client.login()
            logger.info("Successfully logged in to Garmin Connect")
        except Exception as e:
            raise Exception(f"Failed to login to Garmin Connect: {e}")

    def _ensure_login(self) -> None:
        if self.client is None:
            if not self.email or not self.password:
                raise Exception("Not logged in. Call login() first")
            self.login()

    def _is_auth_failure(self, exc: Exception) -> bool:
        text = str(exc).lower()
        return any(token in text for token in (
            'oauth', 'token', 'unauthorized', '401', 'login', 'forbidden',
        ))

    def _garmin_call(self, fn):
        """Call Garmin, retrying once after a fresh login on auth failures."""
        self._ensure_login()
        try:
            return fn()
        except Exception as exc:
            if not self._is_auth_failure(exc):
                raise
            logger.warning("Garmin auth failed (%s); logging in again", exc)
            self.login()
            return fn()
    
    def _is_future_date(self, date: datetime) -> bool:
        """
        Check if a date is in the future
        
        Args:
            date: Date to check
            
        Returns:
            True if date is in the future, False otherwise
        """
        return date.date() > datetime.now().date()
    
    def get_heart_rate_data(self, date: datetime, force: bool = False) -> List[Dict]:
        """
        Get heart rate data for a specific date
        Uses cache if available, otherwise fetches from API
        
        Args:
            date: Date to retrieve heart rate data for
            force: Ignore cache and fetch from Garmin
            
        Returns:
            List of heart rate data points with timestamps
        """
        # Skip future dates entirely - they never have data
        if self._is_future_date(date):
            logger.debug(f"Skipping future date: {date.strftime('%Y-%m-%d')}")
            return None
        
        # Check cache first
        if not force and self.use_cache and self.cache:
            cached = self.cache.lookup_heart_rate_data(date)
            if cached.hit:
                return cached.value
        
        self._ensure_login()
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            logger.info("Fetching heart rate data from Garmin for %s", date_str)
            
            hr_data = self._garmin_call(lambda: self.client.get_heart_rates(date_str))
            
            if not hr_data:
                logger.debug(f"No heart rate data found for {date_str}")
                if self.use_cache and self.cache:
                    self.cache.set_heart_rate_data(date, None)
                return None
            
            heart_rate_values = hr_data.get('heartRateValues', [])
            
            if not heart_rate_values:
                logger.debug(f"No heart rate values found for {date_str}")
                if self.use_cache and self.cache:
                    self.cache.set_heart_rate_data(date, None)
                return None
            
            parsed_data = []
            for timestamp, value in heart_rate_values:
                if value is not None and value > 0:
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    parsed_data.append({
                        'timestamp': dt,
                        'heart_rate': value
                    })
            
            logger.info("Cached %s heart-rate points for %s", len(parsed_data), date_str)
            
            if self.use_cache and self.cache:
                self.cache.set_heart_rate_data(date, parsed_data)
            
            return parsed_data
            
        except Exception as e:
            raise Exception(f"Failed to get heart rate data: {e}")
    
    def get_yesterday_heart_rate(self) -> List[Dict]:
        """
        Get heart rate data for yesterday
        
        Returns:
            List of heart rate data points with timestamps
        """
        yesterday = datetime.now() - timedelta(days=1)
        return self.get_heart_rate_data(yesterday)
    
    def get_hrv_data(self, date: datetime, force: bool = False) -> Optional[float]:
        """
        Get HRV (Heart Rate Variability) data for a specific date
        Uses cache if available, otherwise fetches from API
        """
        if self._is_future_date(date):
            logger.debug(f"Skipping future date for HRV: {date.strftime('%Y-%m-%d')}")
            return None
        
        if not force and self.use_cache and self.cache:
            cached = self.cache.lookup_hrv_data(date)
            if cached.hit:
                return cached.value
        
        self._ensure_login()
        
        date_str = date.strftime('%Y-%m-%d')
        logger.info("Fetching HRV data from Garmin for %s", date_str)
        
        try:
            sleep_data = self._garmin_call(lambda: self.client.get_sleep_data(date_str))
        except Exception as e:
            logger.warning("Failed to get HRV data for %s: %s", date_str, e)
            return None
        
        hrv_value = None
        if sleep_data and isinstance(sleep_data, dict):
            hrv_value = sleep_data.get('avgOvernightHrv')
            if hrv_value is not None:
                logger.debug(f"Retrieved HRV value from API: {hrv_value} ms")
            else:
                logger.debug(f"No avgOvernightHrv found in sleep data for {date_str}")
        else:
            logger.debug(f"No sleep data found for {date_str}")
        
        if self.use_cache and self.cache:
            self.cache.set_hrv_data(date, hrv_value)
        
        return hrv_value

    def get_heart_rate_data_for_dates(
        self, dates: List[datetime], refetch_empty: bool = False
    ) -> Dict[str, Optional[List[Dict]]]:
        """Load heart-rate series for many dates, using one bulk cache read."""
        date_strs = [d.strftime('%Y-%m-%d') for d in dates]
        result: Dict[str, Optional[List[Dict]]] = {}
        if self.use_cache and self.cache:
            result.update(self.cache.get_heart_rate_data_bulk(date_strs))
        for date, date_str in zip(dates, date_strs):
            cached_hit = date_str in result
            cached_empty = cached_hit and result[date_str] is None
            if cached_hit and not (refetch_empty and cached_empty):
                continue
            try:
                result[date_str] = self.get_heart_rate_data(
                    date, force=refetch_empty and cached_empty
                )
            except Exception as exc:
                logger.warning("Could not fetch HR data for %s: %s", date_str, exc)
        return result

    def get_hrv_data_for_dates(
        self, dates: List[datetime], refetch_empty: bool = False
    ) -> Dict[str, Optional[float]]:
        """Load HRV values for many dates, using one bulk cache read."""
        date_strs = [d.strftime('%Y-%m-%d') for d in dates]
        result: Dict[str, Optional[float]] = {}
        if self.use_cache and self.cache:
            result.update(self.cache.get_hrv_data_bulk(date_strs))
        for date, date_str in zip(dates, date_strs):
            cached_hit = date_str in result
            cached_empty = cached_hit and result[date_str] is None
            if cached_hit and not (refetch_empty and cached_empty):
                continue
            try:
                result[date_str] = self.get_hrv_data(
                    date, force=refetch_empty and cached_empty
                )
            except Exception as exc:
                logger.warning("Could not fetch HRV data for %s: %s", date_str, exc)
        return result
