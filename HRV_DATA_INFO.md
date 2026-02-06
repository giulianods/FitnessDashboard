# HRV Data Retrieval - Technical Documentation

## Problem Statement
The Garmin API's direct HRV endpoint (`/hrv-service/hrv/{date}`) was returning None/empty for all dates, even though heart rate data was available for the same dates.

## Root Cause
1. **Limited API Support**: The direct HRV endpoint may not have data for all Garmin users
2. **Device Requirements**: HRV tracking requires specific Garmin devices with advanced sensors
3. **Feature Availability**: Not all Garmin devices continuously track HRV
4. **Data Availability**: HRV is typically only measured during sleep periods

## Solution Implemented

The updated `get_hrv_data()` method now tries multiple sources in order:

### Method 1: Direct HRV Endpoint (Primary)
```python
hrv_data = self.client.get_hrv_data(date_str)
```
**Checks for fields:**
- `lastNightAvg` - Last night's average HRV (preferred)
- `weeklyAvg` - Weekly average HRV (fallback)
- `hrvValue` - Generic HRV value

### Method 2: Sleep Data Extraction (Secondary)
```python
sleep_data = self.client.get_sleep_data(date_str)
```
**Checks for fields:**
- `dailySleepDTO.averageHRV` - Average HRV during sleep
- `dailySleepDTO.sleepScores.hrv` - HRV from sleep quality scores
- `averageHRV` - Wellness data HRV value

### Method 3: Daily Stats (Tertiary)
```python
stats_data = self.client.get_stats(date_str)
```
**Checks for fields:**
- `hrvValue` - HRV in daily statistics

## Expected Behavior

### When HRV Data is Available:
- Method returns HRV value (in milliseconds)
- Logs which source provided the data
- Chart displays HRV trends

### When HRV Data is Not Available:
- Method returns `None`
- Logs attempts at all sources
- Displays helpful message about device requirements
- Chart gracefully handles missing HRV values (shows gaps)

## Testing Recommendations

Since HRV data requires actual Garmin device data:

1. **With Real Credentials**: 
   - Test with actual Garmin account that has HRV-capable device
   - Verify data appears in historical trends chart
   - Check logs to see which method succeeded

2. **Without HRV Data**:
   - Verify application doesn't crash
   - Confirm `None` is returned gracefully
   - Ensure UI shows empty/missing data appropriately

## Device Compatibility

**Garmin devices that track HRV:**
- Fenix series (6, 7, etc.)
- Forerunner series (945, 955, 265, etc.)
- Venu series
- MARQ series
- Epix series
- Some Vivoactive models

**Requirements:**
- Device must support Firstbeat analytics
- HRV tracking must be enabled in device settings
- Data must be synced to Garmin Connect

## API Limitations

- HRV endpoint may not be available for all account types
- Data typically only available for dates when device was worn overnight
- Some devices only measure HRV during specific sleep stages
- Historical HRV data may have limited retention period

## Future Improvements

Potential enhancements if issues persist:

1. Add caching to reduce API calls for known-empty dates
2. Implement user notification about HRV device requirements
3. Add configuration option to disable HRV chart if not available
4. Explore additional Garmin API endpoints as they become available
5. Consider alternative HRV calculation from raw HR data (advanced)

## Related Files

- `garmin_client.py` - HRV data retrieval implementation
- `app.py` - Chart generation with HRV data
- `templates/index.html` - UI for historical trends view

## Support Resources

- [Garmin Connect API Documentation](https://github.com/cyberjunky/python-garminconnect)
- [Garmin HRV Explanation](https://www.garmin.com/en-US/garmin-technology/health-science/heart-rate-variability/)
