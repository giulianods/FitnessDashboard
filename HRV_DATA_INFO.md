# HRV Data Retrieval - Technical Documentation

## Problem Statement
The Garmin API's direct HRV endpoint (`/hrv-service/hrv/{date}`) was returning None/empty for all dates, even though heart rate data was available for the same dates.

## Root Cause
The direct HRV endpoint has limited availability. However, HRV data is actually available through the sleep data endpoint.

## Solution Implemented

The HRV data is retrieved from the **sleep data endpoint** which returns the following structure:

```json
{
    "avgOvernightHrv": 62.0,
    "bodyBatteryChange": 50,
    "dailySleepDTO": { ... },
    "hrvData": [ ... ]
}
```

The `avgOvernightHrv` field at the top level of the response contains the average overnight HRV value in milliseconds.

### Implementation
```python
def get_hrv_data(self, date: datetime) -> Optional[float]:
    sleep_data = self.client.get_sleep_data(date_str)
    return sleep_data.get('avgOvernightHrv') if sleep_data else None
```

## Expected Behavior

### When HRV Data is Available:
- Method returns `avgOvernightHrv` value (in milliseconds)
- Logs the retrieved value
- Chart displays HRV trends

### When HRV Data is Not Available:
- Method returns `None`
- Logs that no sleep data was found
- Chart gracefully handles missing HRV values (shows gaps)

## Data Structure Details

The `get_sleep_data()` response includes:

- **`avgOvernightHrv`**: Average overnight HRV (the main field we use)
- **`hrvData`**: Array of HRV measurements throughout the night with timestamps
- **`dailySleepDTO`**: Detailed sleep metrics including sleep stages
- **`bodyBatteryChange`**: Body battery change during sleep

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
- Device must be worn overnight for sleep tracking
- Data must be synced to Garmin Connect

## API Limitations

- HRV data only available for dates when device was worn overnight
- Sleep data must be successfully recorded
- Some devices only measure HRV during specific sleep stages
- Historical HRV data may have limited retention period

## Testing Recommendations

Since HRV data requires actual Garmin device data:

1. **With Real Credentials**: 
   - Test with actual Garmin account that has HRV-capable device
   - Verify `avgOvernightHrv` appears in sleep data response
   - Check that data appears in historical trends chart
   - Verify logs show successful HRV retrieval

2. **Without HRV Data**:
   - Verify application doesn't crash
   - Confirm `None` is returned gracefully
   - Ensure UI shows empty/missing data appropriately

## Related Files

- `garmin_client.py` - HRV data retrieval implementation
- `app.py` - Chart generation with HRV data
- `templates/index.html` - UI for historical trends view

## Support Resources

- [Garmin Connect API Documentation](https://github.com/cyberjunky/python-garminconnect)
- [Garmin HRV Explanation](https://www.garmin.com/en-US/garmin-technology/health-science/heart-rate-variability/)
