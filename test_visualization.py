#!/usr/bin/env python3
"""
Test script to demonstrate the visualization module with sample data
"""
from datetime import datetime, timedelta
from visualizer import create_heart_rate_chart
import random


def generate_sample_data():
    """Generate sample heart rate data for testing"""
    start_time = datetime.now().replace(hour=6, minute=0, second=0, microsecond=0)
    data = []
    
    # Generate heart rate data for a full day (6 AM to 11 PM)
    current_time = start_time
    end_time = start_time.replace(hour=23, minute=0)
    
    # Simulate realistic heart rate patterns
    while current_time <= end_time:
        # Base heart rate around 70 bpm
        base_hr = 70
        
        # Add some variation based on time of day
        hour = current_time.hour
        if 6 <= hour < 9:  # Morning - slightly elevated
            base_hr = 75
        elif 12 <= hour < 13:  # Lunch - elevated
            base_hr = 80
        elif 17 <= hour < 19:  # Evening workout - high
            base_hr = 120
        elif 20 <= hour < 23:  # Evening - settling down
            base_hr = 65
        
        # Add random variation
        hr = base_hr + random.randint(-10, 10)
        hr = max(50, min(180, hr))  # Keep within reasonable bounds
        
        data.append({
            'timestamp': current_time,
            'heart_rate': hr
        })
        
        # Move forward by 5 minutes
        current_time += timedelta(minutes=5)
    
    return data


def main():
    """Test the visualization with sample data"""
    print("Generating sample heart rate data...")
    sample_data = generate_sample_data()
    print(f"Generated {len(sample_data)} data points")
    
    print("\nCreating visualization...")
    create_heart_rate_chart(sample_data, 'test_heart_rate_chart.html')
    
    print("\n✓ Test chart created successfully!")
    print("  Open test_heart_rate_chart.html in your browser to view the chart.")


if __name__ == '__main__':
    main()
