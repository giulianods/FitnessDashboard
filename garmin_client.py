"""
Garmin Connect API Client
Handles authentication and data retrieval from Garmin Connect
"""
import json
import os
from datetime import datetime, timedelta
from garminconnect import Garmin
from typing import Optional, Dict, List


class GarminClient:
    """Client for interacting with Garmin Connect API"""
    
    def __init__(self, email: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize Garmin client
        
        Args:
            email: Garmin account email
            password: Garmin account password
        """
        self.email = email
        self.password = password
        self.client = None
        
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
    
    def get_heart_rate_data(self, date: datetime) -> List[Dict]:
        """
        Get heart rate data for a specific date
        
        Args:
            date: Date to retrieve heart rate data for
            
        Returns:
            List of heart rate data points with timestamps
        """
        if not self.client:
            raise Exception("Not logged in. Call login() first")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"Fetching heart rate data for {date_str}...")
            
            # Get heart rate data for the specified date
            hr_data = self.client.get_heart_rates(date_str)
            
            if not hr_data:
                print(f"No heart rate data found for {date_str}")
                return []
            
            # Parse the heart rate values
            heart_rate_values = hr_data.get('heartRateValues', [])
            
            if not heart_rate_values:
                print(f"No heart rate values found for {date_str}")
                return []
            
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
            
            print(f"Retrieved {len(parsed_data)} heart rate data points")
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
        
        Tries multiple sources:
        1. Direct HRV endpoint (get_hrv_data)
        2. Sleep data (may contain HRV metrics)
        3. Returns None if no HRV data is available
        
        Args:
            date: Date to retrieve HRV data for
            
        Returns:
            HRV value (nightly average in milliseconds) or None if not available
        """
        if not self.client:
            raise Exception("Not logged in. Call login() first")
        
        date_str = date.strftime('%Y-%m-%d')
        print(f"Fetching HRV data for {date_str}...")
        
        # Method 1: Try direct HRV endpoint
        try:
            hrv_data = self.client.get_hrv_data(date_str)
            
            if hrv_data and isinstance(hrv_data, dict):
                # Try to get last night's HRV value
                hrv_value = hrv_data.get('lastNightAvg')
                
                # Fallback to weeklyAvg if lastNightAvg not available
                if hrv_value is None:
                    hrv_value = hrv_data.get('weeklyAvg')
                
                # Also check for other possible field names
                if hrv_value is None:
                    hrv_value = hrv_data.get('hrvValue')
                
                if hrv_value is not None:
                    print(f"Retrieved HRV value from direct endpoint: {hrv_value} ms")
                    return hrv_value
        except Exception as e:
            print(f"Direct HRV endpoint failed: {e}")
        
        # Method 2: Try to extract HRV from sleep data
        try:
            print(f"Trying to extract HRV from sleep data...")
            sleep_data = self.client.get_sleep_data(date_str)
            
            if sleep_data and isinstance(sleep_data, dict):
                # Check various possible locations for HRV data in sleep response
                
                # Check in dailySleepDTO
                daily_sleep = sleep_data.get('dailySleepDTO', {})
                if daily_sleep:
                    # Some devices report average overnight HRV
                    hrv_value = daily_sleep.get('averageHRV')
                    if hrv_value is not None:
                        print(f"Retrieved HRV from sleep data (averageHRV): {hrv_value} ms")
                        return hrv_value
                    
                    # Check for HRV in sleep scores
                    sleep_scores = daily_sleep.get('sleepScores', {})
                    if isinstance(sleep_scores, dict):
                        hrv_value = sleep_scores.get('hrv')
                        if hrv_value is not None:
                            print(f"Retrieved HRV from sleep scores: {hrv_value} ms")
                            return hrv_value
                
                # Check for HRV in wellness data
                hrv_value = sleep_data.get('averageHRV')
                if hrv_value is not None:
                    print(f"Retrieved HRV from wellness data: {hrv_value} ms")
                    return hrv_value
                    
        except Exception as e:
            print(f"Sleep data HRV extraction failed: {e}")
        
        # Method 3: Try stats data which might contain HRV
        try:
            print(f"Trying to extract HRV from daily stats...")
            stats_data = self.client.get_stats(date_str)
            
            if stats_data and isinstance(stats_data, dict):
                hrv_value = stats_data.get('hrvValue')
                if hrv_value is not None:
                    print(f"Retrieved HRV from stats data: {hrv_value} ms")
                    return hrv_value
        except Exception as e:
            print(f"Stats data HRV extraction failed: {e}")
        
        print(f"No HRV data found for {date_str} from any source")
        print(f"Note: HRV data requires compatible Garmin device and may not be available for all dates")
        return None
