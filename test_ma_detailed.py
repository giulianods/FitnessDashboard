#!/usr/bin/env python3
"""
Detailed test to verify moving average alignment.
This will help us understand if there's an alignment issue.
"""

def calculate_moving_average(values, window_size):
    """
    Calculate moving average with a trailing/backward-looking window.
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


# Test with simple data
print("=" * 80)
print("Test 1: Simple sequential data with 7-day MA")
print("=" * 80)

dates = [f"Jan {i}" for i in range(1, 15)]
values = list(range(10, 150, 10))  # 10, 20, 30, ..., 140

ma_values = calculate_moving_average(values, 7)

print(f"\n{'Date':<12} {'Value':<8} {'MA':<8} {'Expected MA Calculation':<40}")
print("-" * 80)

for i, (date, val, ma) in enumerate(zip(dates, values, ma_values)):
    # Calculate what the MA should be
    window_start = max(0, i - 6)  # 7-day window
    window = values[window_start:i+1]
    expected_ma = sum(window) / len(window) if window else None
    
    # Show which values are in the window
    if i < 7:
        window_desc = f"avg({', '.join(map(str, values[0:i+1]))})"
    else:
        window_desc = f"avg({', '.join(map(str, values[i-6:i+1]))})"
    
    match = "✓" if abs(ma - expected_ma) < 0.01 else "✗"
    print(f"{date:<12} {val:<8} {ma:<8.2f} {window_desc:<40} {match}")

print("\n" + "=" * 80)
print("Test 2: Data with None values")
print("=" * 80)

dates2 = [f"Day {i}" for i in range(1, 11)]
values2 = [10, None, 30, None, 50, 60, 70, None, 90, 100]

ma_values2 = calculate_moving_average(values2, 5)

print(f"\n{'Date':<12} {'Value':<8} {'MA':<8} {'Window':<30}")
print("-" * 70)

for i, (date, val, ma) in enumerate(zip(dates2, values2, ma_values2)):
    window_start = max(0, i - 4)
    window = [v for v in values2[window_start:i+1] if v is not None]
    window_desc = f"[{', '.join(map(str, window))}]"
    val_str = str(val) if val is not None else "None"
    ma_str = f"{ma:.2f}" if ma is not None else "None"
    print(f"{date:<12} {val_str:<8} {ma_str:<8} {window_desc:<30}")

print("\n" + "=" * 80)
print("Key Point: For 'Jan 7' with 7-day window, MA includes Jan 1-7")
print("This is CORRECT trailing/backward-looking behavior")
print("=" * 80)
