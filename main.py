#!/usr/bin/env python3
"""
Fitness Dashboard - Main Script
Retrieves yesterday's heart rate data from Garmin and creates a visualization
"""
import sys
import argparse
from datetime import datetime, timedelta
from garmin_client import GarminClient
from visualizer import create_heart_rate_chart


def main():
    """Main function to retrieve and visualize heart rate data"""
    parser = argparse.ArgumentParser(
        description='Retrieve and visualize heart rate data from Garmin Connect'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to config file (default: config.json)'
    )
    parser.add_argument(
        '--output',
        default='heart_rate_chart.html',
        help='Output file for the chart (default: heart_rate_chart.html)'
    )
    parser.add_argument(
        '--date',
        help='Specific date to retrieve data for (YYYY-MM-DD format). Default is yesterday.'
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize Garmin client
        print("Initializing Garmin client...")
        client = GarminClient()
        
        # Load credentials
        print(f"Loading credentials from {args.config}...")
        client.load_credentials(args.config)
        
        # Login to Garmin Connect
        print("Logging in to Garmin Connect...")
        client.login()
        
        # Get heart rate data
        if args.date:
            # Parse specific date
            try:
                target_date = datetime.strptime(args.date, '%Y-%m-%d')
                print(f"Retrieving heart rate data for {args.date}...")
                data = client.get_heart_rate_data(target_date)
            except ValueError:
                print(f"Error: Invalid date format. Please use YYYY-MM-DD")
                sys.exit(1)
        else:
            # Get yesterday's data
            print("Retrieving yesterday's heart rate data...")
            data = client.get_yesterday_heart_rate()
        
        # Check if data was retrieved
        if not data:
            print("No heart rate data found for the specified date.")
            print("This could mean:")
            print("  - No activity was recorded on that date")
            print("  - Your Garmin device was not worn")
            print("  - The data has not synced yet")
            sys.exit(1)
        
        # Create visualization
        print(f"\nCreating heart rate visualization...")
        create_heart_rate_chart(data, args.output)
        
        print(f"\n✓ Success! Heart rate chart has been created.")
        print(f"  Open {args.output} in your browser to view the chart.")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nTo get started:")
        print("  1. Copy config.json.example to config.json")
        print("  2. Edit config.json with your Garmin credentials")
        print("  3. Run this script again")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
