#!/usr/bin/env python3
"""
Test to verify moving average alignment
"""

def calculate_moving_average(values, window_size):
    """
    Calculate moving average for a list of values
    
    Args:
        values: List of numeric values (may contain None)
        window_size: Size of the moving average window
    
    Returns:
        List of moving average values (same length as input)
    """
    if not values or window_size <= 0:
        return values
    
    result = []
    for i in range(len(values)):
        # Get window of values, handling None values
        window_start = max(0, i - window_size + 1)
        window = [v for v in values[window_start:i+1] if v is not None]
        
        if window:
            result.append(sum(window) / len(window))
        else:
            result.append(None)
    
    return result


# Test with simple example
dates = ['Jan 1', 'Jan 2', 'Jan 3', 'Jan 4', 'Jan 5', 'Jan 6', 'Jan 7']
values = [10, 20, 30, 40, 50, 60, 70]
window = 7

ma = calculate_moving_average(values, window)

print("Testing 7-day moving average alignment:")
print("=" * 70)
print(f"{'Date':<10} {'Value':<10} {'MA':<15} {'Window Used':<30}")
print("=" * 70)

for i, (date, val, ma_val) in enumerate(zip(dates, values, ma)):
    window_start = max(0, i - window + 1)
    window_dates = dates[window_start:i+1]
    window_vals = values[window_start:i+1]
    window_str = f"{window_dates[0]}-{window_dates[-1]}"
    print(f"{date:<10} {val:<10} {ma_val:<15.2f} {window_str:<30}")

print("\n" + "=" * 70)
print("Expected behavior:")
print("  - Jan 1 MA = avg(Jan 1) = 10")
print("  - Jan 7 MA = avg(Jan 1-7) = 40")
print("  - Each date's MA includes that date and previous dates")
print("=" * 70)
