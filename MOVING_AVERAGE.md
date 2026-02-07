# Moving Average Feature Documentation

## Overview
This document describes the moving average feature added to the HRV and RHR (Resting Heart Rate) charts in the Fitness Dashboard.

## Feature Description

### What was added
Moving average lines have been added to two charts:
1. **Chart A: Daily Min/Max Heart Rate** - Shows moving average for Min HR (Resting Heart Rate)
2. **Chart D: Daily HRV** - Shows moving average for HRV (Heart Rate Variability)

### Moving Average Window Calculation
The moving average window is automatically calculated as **1/4 of the displayed period**:

| Display Period | Days | MA Window | 
|---------------|------|-----------|
| 4 weeks | 28 | 7 days |
| 8 weeks | 56 | 14 days |
| 12 weeks | 84 | 21 days |
| 16 weeks | 112 | 28 days |
| 24 weeks | 168 | 42 days |
| 48 weeks | 336 | 84 days |
| Monthly | ~30 | ~7 days |

### Key Features

1. **Starts from the beginning**: The moving average is calculated from day 1 by prefetching additional data before the display period
2. **Handles missing data**: None/null values are properly handled in the calculation
3. **Smooth visualization**: Moving average lines are displayed as thicker, darker-colored lines
4. **Consistent across views**: Works for both weekly period selection and monthly selection

## Implementation Details

### Code Changes

#### 1. Moving Average Function (`calculate_moving_average()`)
```python
def calculate_moving_average(values, window_size):
    """
    Calculate moving average for a list of values
    
    Args:
        values: List of numeric values (may contain None)
        window_size: Size of the moving average window
    
    Returns:
        List of moving average values (same length as input)
    """
```

**Key aspects:**
- Handles None values by skipping them in calculation
- Returns same-length list as input for proper date alignment
- Uses expanding window at the start (includes all available data up to window size)

#### 2. Data Prefetching
Both `get_historical_data()` and `get_monthly_data()` functions were modified to:
- Calculate MA window as `display_days // 4`
- Fetch additional data before the display period: `prefetch_start_date = start_date - timedelta(days=ma_window - 1)`
- Only include display period data in statistics (not prefetch data)

#### 3. Chart Visualization
**Min HR Moving Average (Chart A):**
- Color: Orange (#FF6B35) - provides contrast with blue data points
- Line width: 2 (thinner for cleaner appearance)
- Style: Solid line without markers
- Overlaid on the light blue min HR data points

**HRV Moving Average (Chart D):**
- Color: Green (#28B463) - provides contrast with purple data points
- Line width: 2 (thinner for cleaner appearance)
- Style: Solid line without markers
- Overlaid on the light purple HRV data points

### Data Flow

```
User selects period (e.g., 4 weeks)
    ↓
Calculate MA window (4 weeks * 7 days / 4 = 7 days)
    ↓
Fetch data from (start_date - 6 days) to end_date
    ↓
Calculate moving averages on all fetched data
    ↓
Display only the requested period with MA starting from day 1
```

### Example

For a 4-week (28 days) view:
- **Display period**: Days 1-28 (last 4 weeks)
- **Prefetch period**: Days -6 to 0 (6 days before)
- **Total data fetched**: 35 days
- **MA window**: 7 days
- **MA calculation**: Each point uses up to 7 previous days (including prefetch)
- **Result**: MA line starts from day 1 with proper context

## Visual Design

### Color Scheme
```
Raw Data (light) → Moving Average (dark)

Min HR:  Light Blue (#4A90E2) → Dark Blue (#1E3A8A)
HRV:     Light Purple (#9B59B6) → Dark Purple (#6A1B9A)
```

### Line Styles
- **Raw data**: Lines + markers (width=2, size=6)
- **Moving average**: Lines only (width=3, no markers)

This creates clear visual distinction while maintaining cohesive color families.

## Benefits

1. **Trend Identification**: Easier to see long-term trends in resting HR and HRV
2. **Noise Reduction**: Moving average smooths out daily fluctuations
3. **Recovery Tracking**: Better visibility of recovery patterns and training stress
4. **Adaptive Window**: Automatically adjusts to different time periods
5. **Complete Data**: Includes historical context from the start

## Technical Notes

### Caching
The prefetched data is also cached, so subsequent views of the same period benefit from the cache without additional API calls.

### Performance
- Minimal performance impact: O(n) calculation per dataset
- Leverages existing caching infrastructure
- No impact on API call limits (uses cached data when available)

### Browser Compatibility
The feature uses standard Plotly traces and is compatible with all browsers supported by Plotly.

## Testing

### Verification Steps
1. Select different time periods (4, 8, 12, 16, 24, 48 weeks)
2. Verify MA window adjusts proportionally (1/4 of period)
3. Verify MA line starts from first displayed day
4. Check that missing HRV data doesn't break the MA calculation
5. Verify visual distinction between raw data and MA lines

### Test Cases
- ✅ Empty data handling
- ✅ Single day (no MA possible)
- ✅ Partial data (some days missing)
- ✅ Full dataset with complete data
- ✅ Dataset with missing HRV values
- ✅ Different time periods (4-48 weeks)
- ✅ Monthly view

## Future Enhancements

Potential improvements:
1. Make MA window user-configurable
2. Add multiple MA lines (e.g., 7-day and 30-day)
3. Add MA for Max HR as well
4. Display MA value on hover
5. Add statistics comparing current vs MA trends
6. Export MA data

## Summary

The moving average feature provides a professional-grade analysis tool that helps users identify trends and patterns in their fitness data. The implementation is efficient, handles edge cases gracefully, and integrates seamlessly with the existing caching and visualization infrastructure.
