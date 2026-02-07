"""
Garmin Connect API Client
Handles authentication and data retrieval from Garmin Connect
"""
import json
import os
from datetime import datetime, timedelta
from garminconnect import Garmin
from typing import Optional, Dict, List
from cache_manager import CacheManager


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
            print("Successfully logged in to Garmin Connect")
        except Exception as e:
            raise Exception(f"Failed to login to Garmin Connect: {e}")
    
    def _is_future_date(self, date: datetime) -> bool:
        """
        Check if a date is in the future
        
        Args:
            date: Date to check
            
        Returns:
            True if date is in the future, False otherwise
        """
        return date.date() > datetime.now().date()
    
    def get_heart_rate_data(self, date: datetime) -> List[Dict]:
        """
        Get heart rate data for a specific date
        Uses cache if available, otherwise fetches from API
        
        Args:
            date: Date to retrieve heart rate data for
            
        Returns:
            List of heart rate data points with timestamps
        """
        # Skip future dates entirely - they never have data
        if self._is_future_date(date):
            print(f"Skipping future date: {date.strftime('%Y-%m-%d')}")
            return None
        
        # Check cache first
        if self.use_cache and self.cache:
            cached_data = self.cache.get_heart_rate_data(date)
            if cached_data is not None:
                return cached_data
        
        # Cache miss or caching disabled - fetch from API
        if not self.client:
            raise Exception("Not logged in. Call login() first")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"Fetching heart rate data from Garmin API for {date_str}...")
            
            # Get heart rate data for the specified date
            hr_data = self.client.get_heart_rates(date_str)
            
            if not hr_data:
                print(f"No heart rate data found for {date_str}")
                # Cache None for past dates (not future dates which are already filtered)
                if self.use_cache and self.cache:
                    self.cache.set_heart_rate_data(date, None)
                return None
            
            # Parse the heart rate values
            heart_rate_values = hr_data.get('heartRateValues', [])
            
            if not heart_rate_values:
                print(f"No heart rate values found for {date_str}")
                # Cache None for past dates
                if self.use_cache and self.cache:
                    self.cache.set_heart_rate_data(date, None)
                return None
            
            # Convert to list of dicts with timestamp and value
            parsed_data = []
            for timestamp, value in heart_rate_values:
                if value is not None and value > 0:
                    # Timestamp is in milliseconds
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    parsed_data.append({
                        'timestamp': dt,
                        'heart_rate': value
                    })
            
            print(f"Retrieved {len(parsed_data)} heart rate data points from API")
            
            # Cache the data
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
    
    def get_hrv_data(self, date: datetime) -> Optional[float]:
        """
        Get HRV (Heart Rate Variability) data for a specific date
        Uses cache if available, otherwise fetches from API
        
        The HRV data is retrieved from the sleep data endpoint, which returns
        avgOvernightHrv at the top level of the response.
        
        Args:
            date: Date to retrieve HRV data for
            
        Returns:
            HRV value (average overnight HRV in milliseconds) or None if not available
        """
        # Skip future dates entirely - they never have data
        if self._is_future_date(date):
            print(f"Skipping future date for HRV: {date.strftime('%Y-%m-%d')}")
            return None
        
        # Check cache first
        if self.use_cache and self.cache:
            cached_value = self.cache.get_hrv_data(date)
            if cached_value is not None:
                return cached_value
        
        # Cache miss or caching disabled - fetch from API
        if not self.client:
            raise Exception("Not logged in. Call login() first")
        
        date_str = date.strftime('%Y-%m-%d')
        print(f"Fetching HRV data from Garmin API for {date_str}...")
        
        hrv_value = None
        try:
            # Get sleep data which contains avgOvernightHrv
            sleep_data = self.client.get_sleep_data(date_str)
            
            if sleep_data and isinstance(sleep_data, dict):
                # Extract avgOvernightHrv from the top level of the response
                hrv_value = sleep_data.get('avgOvernightHrv')
                
                if hrv_value is not None:
                    print(f"Retrieved HRV value from API: {hrv_value} ms")
                else:
                    print(f"No avgOvernightHrv found in sleep data for {date_str}")
            else:
                print(f"No sleep data found for {date_str}")
                
        except Exception as e:
            print(f"Failed to get HRV data for {date_str}: {e}")
        
        # Cache the result (even if None) to avoid repeated API calls
        if self.use_cache and self.cache:
            self.cache.set_hrv_data(date, hrv_value)
        
        return hrv_value
