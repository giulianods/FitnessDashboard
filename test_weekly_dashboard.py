#!/usr/bin/env python3
"""
Test script for weekly dashboard functionality
Tests ISO week calculation and data structure
"""

from datetime import datetime, timedelta
import json

def get_iso_week_boundaries(year, week):
    """Calculate the Monday-Sunday boundaries for an ISO week"""
    # ISO week: Week 1 contains January 4th
    jan_4 = datetime(year, 1, 4)
    week_1_monday = jan_4 - timedelta(days=jan_4.weekday())
    target_monday = week_1_monday + timedelta(weeks=week-1)
    target_sunday = target_monday + timedelta(days=6)
    return target_monday, target_sunday

def test_iso_week_calculation():
    """Test ISO week calculation for various dates"""
    print("=" * 60)
    print("Testing ISO Week Calculation")
    print("=" * 60)
    
    test_cases = [
        (2026, 1, "Week 1 of 2026"),
        (2026, 5, "Week 5 of 2026"),
        (2026, 6, "Week 6 of 2026 (current)"),
        (2025, 52, "Week 52 of 2025"),
    ]
    
    for year, week, description in test_cases:
        monday, sunday = get_iso_week_boundaries(year, week)
        print(f"\n{description}:")
        print(f"  Year: {year}, Week: {week}")
        print(f"  Monday: {monday.strftime('%Y-%m-%d')} ({monday.strftime('%A')})")
        print(f"  Sunday: {sunday.strftime('%Y-%m-%d')} ({sunday.strftime('%A')})")
        
        # Verify it's actually the correct week
        actual_week = monday.isocalendar()[1]
        actual_year = monday.isocalendar()[0]
        if actual_week == week and actual_year == year:
            print(f"  ✓ Verification: Monday is in week {actual_week} of {actual_year}")
        else:
            print(f"  ✗ ERROR: Monday is in week {actual_week} of {actual_year}, expected {week} of {year}")

def test_current_week():
    """Test getting current week"""
    print("\n" + "=" * 60)
    print("Testing Current Week")
    print("=" * 60)
    
    today = datetime.now()
    iso_cal = today.isocalendar()
    year, week, weekday = iso_cal[0], iso_cal[1], iso_cal[2]
    
    print(f"\nToday: {today.strftime('%Y-%m-%d')} ({today.strftime('%A')})")
    print(f"ISO Calendar: Year={year}, Week={week}, Weekday={weekday}")
    
    monday, sunday = get_iso_week_boundaries(year, week)
    print(f"Current week boundaries:")
    print(f"  Monday: {monday.strftime('%Y-%m-%d')}")
    print(f"  Sunday: {sunday.strftime('%Y-%m-%d')}")
    
    # Verify today is within the week
    if monday.date() <= today.date() <= sunday.date():
        print(f"  ✓ Today ({today.strftime('%Y-%m-%d')}) is within the week")
    else:
        print(f"  ✗ ERROR: Today is NOT within the calculated week!")

def test_week_button_labels():
    """Test generating week button labels"""
    print("\n" + "=" * 60)
    print("Testing Week Button Labels (Last 6 Weeks)")
    print("=" * 60)
    
    today = datetime.now()
    
    for i in range(6):
        week_date = today - timedelta(days=i * 7)
        iso_cal = week_date.isocalendar()
        year, week = iso_cal[0], iso_cal[1]
        year_short = str(year)[2:]
        label = f"CW{week} '{year_short}"
        
        monday, sunday = get_iso_week_boundaries(year, week)
        
        status = "CURRENT" if i == 0 else f"-{i} week(s)"
        print(f"\n{label} ({status}):")
        print(f"  {monday.strftime('%Y-%m-%d')} to {sunday.strftime('%Y-%m-%d')}")

def test_mock_data_structure():
    """Test the data structure returned by the API"""
    print("\n" + "=" * 60)
    print("Testing Mock Data Structure")
    print("=" * 60)
    
    # Mock data structure that backend should return
    mock_response = {
        'chart': json.dumps({
            'data': [
                {'type': 'scatter', 'name': 'Min HR'},
                {'type': 'scatter', 'name': 'Max HR'}
            ],
            'layout': {
                'title': 'Test Chart',
                'xaxis': {'title': 'Date'},
                'yaxis': {'title': 'Heart Rate (bpm)'}
            }
        }),
        'stats': {
            'avg_hr': 72,
            'max_hr': 165,
            'min_waking_hr': 58,
            'time_in_z2': 45,
            'time_in_z4_z5': 12
        }
    }
    
    print("\nMock Response Structure:")
    print(f"  - chart: <JSON string of length {len(mock_response['chart'])}>")
    print(f"  - stats: {mock_response['stats']}")
    
    # Test parsing
    try:
        chart_data = json.loads(mock_response['chart'])
        print("\n✓ Chart JSON parses successfully")
        print(f"  - Number of traces: {len(chart_data['data'])}")
        print(f"  - Has layout: {len(chart_data['layout']) > 0}")
    except Exception as e:
        print(f"\n✗ ERROR parsing chart JSON: {e}")
    
    # Test stats access
    try:
        stats = mock_response['stats']
        print("\n✓ Stats accessible:")
        for key, value in stats.items():
            print(f"  - {key}: {value}")
    except Exception as e:
        print(f"\n✗ ERROR accessing stats: {e}")

if __name__ == '__main__':
    print("\n" + "╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "WEEKLY DASHBOARD TEST SUITE" + " " * 20 + "║")
    print("╚" + "═" * 58 + "╝")
    
    test_iso_week_calculation()
    test_current_week()
    test_week_button_labels()
    test_mock_data_structure()
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60 + "\n")
