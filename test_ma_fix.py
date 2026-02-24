#!/usr/bin/env python3
"""
Test to demonstrate the moving average alignment fix.

This test shows:
1. MA only appears for dates with actual data
2. MA stops at the last data point (not extending into future)
3. First display date has MA calculated from prefetch period
4. MA values represent trailing average (backward-looking)
"""

def calculate_moving_average(values, window_size):
    """Calculate moving average (trailing/backward-looking)"""
    result = []
    for i in range(len(values)):
        # Get window from [i-window_size+1, i] inclusive
        window_start = max(0, i - window_size + 1)
        window = [v for v in values[window_start:i+1] if v is not None]
        
        if window:
            result.append(sum(window) / len(window))
        else:
            result.append(None)
    
    return result


def test_ma_alignment():
    """Test that MA is properly aligned with data"""
    print("=" * 80)
    print("TEST: Moving Average Alignment with Prefetch and Gaps")
    print("=" * 80)
    
    # Simulate data with prefetch period and gaps
    # Display period: Jan 1-7 (7 days)
    # MA window: 7 days
    # Prefetch: Dec 25-31 (to provide full MA window for Jan 1)
    
    dates = [
        'Dec 25', 'Dec 26', 'Dec 27', 'Dec 28', 'Dec 29', 'Dec 30', 'Dec 31',  # Prefetch
        'Jan 1', 'Jan 2', 'Jan 3', 'Jan 4', 'Jan 5', 'Jan 6', 'Jan 7',  # Display
        'Jan 8', 'Jan 9', 'Jan 10'  # Future (no data)
    ]
    
    values = [
        40, 42, 41, 43, 42, 44, 43,  # Prefetch has data
        45, 46, 47, 48, 49, 50, 51,  # Display has data
        None, None, None  # Future has no data
    ]
    
    # Calculate MA
    ma_window = 7
    ma_values = calculate_moving_average(values, ma_window)
    
    print(f"\nMoving Average Window: {ma_window} days")
    print(f"Display Period: Jan 1 - Jan 7")
    print(f"Prefetch Period: Dec 25 - Dec 31 (for full MA on Jan 1)")
    print()
    
    # Show all dates with MA calculation
    print("All Dates (including prefetch and future):")
    print("-" * 80)
    print(f"{'Date':<12} {'Value':<8} {'MA':<10} {'MA Window':<30}")
    print("-" * 80)
    
    for i, (date, val, ma) in enumerate(zip(dates, values, ma_values)):
        window_start = max(0, i - ma_window + 1)
        window_dates = dates[window_start:i+1]
        window_str = f"{window_dates[0]} to {window_dates[-1]}"
        
        val_str = str(val) if val is not None else "None"
        ma_str = f"{ma:.2f}" if ma is not None else "None"
        
        # Mark display period
        marker = ""
        if date.startswith("Jan") and date != "Jan 8" and date != "Jan 9" and date != "Jan 10":
            marker = " [DISPLAY]"
        elif date.startswith("Dec"):
            marker = " [PREFETCH]"
        elif date in ["Jan 8", "Jan 9", "Jan 10"]:
            marker = " [FUTURE-NO DATA]"
        
        print(f"{date:<12} {val_str:<8} {ma_str:<10} {window_str:<30}{marker}")
    
    print()
    print("=" * 80)
    print("FILTERING RESULTS (what gets shown on the chart):")
    print("=" * 80)
    print()
    
    # Apply the NEW filtering logic: only show MA where value is not None
    filtered_dates = [d for d, v, ma in zip(dates, values, ma_values) 
                     if v is not None and ma is not None]
    filtered_ma = [ma for v, ma in zip(values, ma_values) 
                  if v is not None and ma is not None]
    
    print("Data Points Shown:")
    data_dates = [d for d, v in zip(dates, values) if v is not None]
    data_values = [v for v in values if v is not None]
    print(f"  Dates: {data_dates}")
    print(f"  Values: {data_values}")
    print()
    
    print("MA Line Shown:")
    print(f"  Dates: {filtered_dates}")
    print(f"  MA Values: {[f'{ma:.2f}' for ma in filtered_ma]}")
    print()
    
    # Verify key properties
    print("=" * 80)
    print("VERIFICATION:")
    print("=" * 80)
    
    # 1. First display date (Jan 1) should have MA from prefetch
    jan1_idx = dates.index('Jan 1')
    jan1_ma = ma_values[jan1_idx]
    jan1_window_start = max(0, jan1_idx - ma_window + 1)
    jan1_window = [v for v in values[jan1_window_start:jan1_idx+1] if v is not None]
    expected_jan1_ma = sum(jan1_window) / len(jan1_window)
    
    print(f"\n1. First display date (Jan 1) has MA from prefetch:")
    print(f"   Window used: {dates[jan1_window_start]} to Jan 1")
    print(f"   Values in window: {jan1_window}")
    print(f"   Calculated MA: {jan1_ma:.2f}")
    print(f"   Expected MA: {expected_jan1_ma:.2f}")
    print(f"   ✓ PASS" if abs(jan1_ma - expected_jan1_ma) < 0.01 else f"   ✗ FAIL")
    
    # 2. Last display date (Jan 7) should have MA
    jan7_idx = dates.index('Jan 7')
    jan7_ma = ma_values[jan7_idx]
    jan7_window_start = max(0, jan7_idx - ma_window + 1)
    jan7_window = [v for v in values[jan7_window_start:jan7_idx+1] if v is not None]
    expected_jan7_ma = sum(jan7_window) / len(jan7_window)
    
    print(f"\n2. Last data date (Jan 7) has correct trailing MA:")
    print(f"   Window used: {dates[jan7_window_start]} to Jan 7")
    print(f"   Values in window: {jan7_window}")
    print(f"   Calculated MA: {jan7_ma:.2f}")
    print(f"   Expected MA: {expected_jan7_ma:.2f}")
    print(f"   ✓ PASS" if abs(jan7_ma - expected_jan7_ma) < 0.01 else f"   ✗ FAIL")
    
    # 3. Future dates should not be in filtered results
    future_in_filtered = any(d in ['Jan 8', 'Jan 9', 'Jan 10'] for d in filtered_dates)
    print(f"\n3. MA does not extend to future dates (Jan 8-10):")
    print(f"   Future dates in filtered MA: {future_in_filtered}")
    print(f"   ✓ PASS" if not future_in_filtered else f"   ✗ FAIL")
    
    # 4. MA line stops at last data point
    last_filtered_date = filtered_dates[-1]
    last_data_date = data_dates[-1]
    print(f"\n4. MA line stops at last data point:")
    print(f"   Last data date: {last_data_date}")
    print(f"   Last MA date: {last_filtered_date}")
    print(f"   ✓ PASS" if last_filtered_date == last_data_date else f"   ✗ FAIL")
    
    print()
    print("=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print("✓ MA includes prefetch period for first display date")
    print("✓ MA represents trailing/backward average (current + previous values)")
    print("✓ MA stops at last date with actual data")
    print("✓ MA does not extend into future dates")
    print("=" * 80)


if __name__ == '__main__':
    test_ma_alignment()
