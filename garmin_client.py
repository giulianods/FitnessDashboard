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
        
        Args:
            date: Date to retrieve HRV data for
            
        Returns:
            HRV value (nightly average) or None if not available
        """
        if not self.client:
            raise Exception("Not logged in. Call login() first")
        
        try:
            date_str = date.strftime('%Y-%m-%d')
            print(f"Fetching HRV data for {date_str}...")
            
            # Get HRV data using get_hrv_data method from garminconnect
            hrv_data = self.client.get_hrv_data(date_str)
            
            if not hrv_data:
                print(f"No HRV data found for {date_str}")
                return None
            
            # Extract the weekly average HRV or last night's HRV
            # The API returns various HRV metrics
            hrv_value = None
            
            # Try to get last night's HRV value
            if isinstance(hrv_data, dict):
                # Check for lastNightAvg (most relevant for nightly HRV)
                hrv_value = hrv_data.get('lastNightAvg')
                
                # Fallback to weeklyAvg if lastNightAvg not available
                if hrv_value is None:
                    hrv_value = hrv_data.get('weeklyAvg')
            
            if hrv_value is not None:
                print(f"Retrieved HRV value: {hrv_value}")
            else:
                print(f"No HRV value found for {date_str}")
                
            return hrv_value
            
        except Exception as e:
            print(f"Failed to get HRV data for {date.strftime('%Y-%m-%d')}: {e}")
            return None
