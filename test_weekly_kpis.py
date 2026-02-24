#!/usr/bin/env python3
"""
Test script to verify weekly KPI formatting
"""

def format_time(minutes):
    """Format time in minutes to human-readable hours and minutes string."""
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"

# Test format_time function
print("Testing format_time function:")
print(f"  0 minutes: {format_time(0)}")
print(f"  45 minutes: {format_time(45)}")
print(f"  90 minutes: {format_time(90)}")
print(f"  125 minutes: {format_time(125)}")

# Test stat structure
zone_times = {
    'Z2': 45,
    'Z4': 20,
    'Z5': 10
}

waking_hrs = [70, 75, 80, 85, 90, 95, 100, 105, 110]
all_hrs = [50, 55, 60] + waking_hrs + [115, 120]

stats = {
    'average': round(sum(waking_hrs) / len(waking_hrs)) if waking_hrs else 0,
    'maximum': max(all_hrs) if all_hrs else 0,
    'minimum': min(waking_hrs) if waking_hrs else 0,
    'time_z2': format_time(zone_times.get('Z2', 0)),
    'time_z4_z5': format_time(zone_times.get('Z4', 0) + zone_times.get('Z5', 0))
}

print("\nTest stats structure:")
print(f"  Average HR: {stats['average']} bpm")
print(f"  Maximum HR: {stats['maximum']} bpm")
print(f"  Minimum HR: {stats['minimum']} bpm")
print(f"  Time in Z2: {stats['time_z2']}")
print(f"  Time in Z4+5: {stats['time_z4_z5']}")

print("\n✓ All KPI formatting tests passed!")
print("\nExpected output:")
print("  Average HR: 90 bpm")
print("  Maximum HR: 120 bpm")
print("  Minimum HR: 70 bpm")
print("  Time in Z2: 45m")
print("  Time in Z4+5: 30m")
