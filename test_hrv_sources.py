#!/usr/bin/env python3
"""
Test script to explore different sources for HRV data from Garmin API
"""
from datetime import datetime, timedelta

# Mock data structures based on Garmin API documentation
# Sleep data typically contains HRV information

print("Testing HRV data sources...")
print("\n1. Direct HRV endpoint: /hrv-service/hrv/{date}")
print("   - May return: {'lastNightAvg': value, 'weeklyAvg': value}")
print("   - Problem: Often returns None/empty for many users")

print("\n2. Sleep data endpoint: /wellness-service/wellness/dailySleepData")
print("   - Contains: sleepMovement, restingHeartRate, avgSleepStress")
print("   - May contain HRV in: 'dailySleepDTO' -> 'sleepTimeSeconds', 'avgSleepStress'")

print("\n3. Potential HRV fields in sleep data:")
sleep_data_fields = [
    "dailySleepDTO.avgSleepStress",
    "dailySleepDTO.restingHeartRate", 
    "dailySleepDTO.sleepScores",
    "sleepStress (array of values)",
    "averageStressLevel"
]
for field in sleep_data_fields:
    print(f"   - {field}")

print("\n4. The issue:")
print("   - get_hrv_data() endpoint may not have data for all users")
print("   - HRV calculation requires special devices/settings")
print("   - Some Garmin devices don't track HRV continuously")

print("\n5. Recommended solution:")
print("   - Try get_sleep_data() first")
print("   - Extract HRV from sleep metrics if available")
print("   - Fall back to None if no HRV data exists")
print("   - Add logging to show which method worked")

