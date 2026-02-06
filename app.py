#!/usr/bin/env python3
"""
Fitness Dashboard - Web Application
Interactive web interface for viewing heart rate data with date selection
"""
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from garmin_client import GarminClient
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.utils
import json
import numpy as np
from scipy import stats

app = Flask(__name__)

# Configuration
DEFAULT_MAX_HR = 190  # Default maximum heart rate for cardio zones
WAKING_HOURS_DURATION = 16 * 60  # Duration of waking hours in minutes (6:00-22:00)

def format_time(minutes):
    """Format time in minutes to human-readable hours and minutes string."""
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    else:
        return f"{mins}m"

# Global Garmin client (will be initialized on first request)
garmin_client = None


def get_garmin_client():
    """Get or initialize Garmin client"""
    global garmin_client
    if garmin_client is None:
        garmin_client = GarminClient()
        garmin_client.load_credentials('config.json')
        garmin_client.login()
    return garmin_client


def create_chart_json(data, max_hr=DEFAULT_MAX_HR):
    """
    Create chart JSON for Plotly with main line chart, zone distribution bar chart, and HR histogram
    
    Args:
        data: List of dictionaries with 'timestamp' and 'heart_rate' keys
        max_hr: Maximum heart rate for calculating cardio zones (default: DEFAULT_MAX_HR)
    
    Returns:
        JSON string for Plotly chart
    """
    if not data:
        return None
    
    # Extract timestamps and heart rates
    timestamps = [point['timestamp'].strftime('%Y-%m-%d %H:%M:%S') for point in data]
    heart_rates = [point['heart_rate'] for point in data]
    
    # Get date for title
    date_obj = data[0]['timestamp']
    date_str = date_obj.strftime('%A, %b %d, %Y')  # e.g., "Friday, Jan 24, 2026"
    
    # Garmin HR Zones (Z0-Z5) based on max HR
    # Z0 is below 50%, Z1-Z5 are the training zones
    garmin_zones = {
        'Z0': (0, max_hr * 0.50, 'Rest'),  # Zone 0: <50%
        'Z1': (max_hr * 0.50, max_hr * 0.60, 'Very Light'),  # Zone 1: 50-60%
        'Z2': (max_hr * 0.60, max_hr * 0.70, 'Light'),  # Zone 2: 60-70%
        'Z3': (max_hr * 0.70, max_hr * 0.80, 'Moderate'),  # Zone 3: 70-80%
        'Z4': (max_hr * 0.80, max_hr * 0.90, 'Hard'),  # Zone 4: 80-90%
        'Z5': (max_hr * 0.90, max_hr * 1.00, 'Maximum'),  # Zone 5: 90-100%
    }
    
    # Filter data for waking hours (6:00-22:00)
    waking_hours_data = []
    for point in data:
        hour = point['timestamp'].hour
        if 6 <= hour < 22:
            waking_hours_data.append(point)
    
    waking_hours_hr = [point['heart_rate'] for point in waking_hours_data]
    
    # Calculate zone distribution for waking hours
    zone_distribution = {zone: 0 for zone in garmin_zones.keys()}
    
    for hr in waking_hours_hr:
        for zone_name, (lower, upper, _) in garmin_zones.items():
            if lower <= hr < upper:
                zone_distribution[zone_name] += 1
                break
    
    # Convert counts to time in minutes
    # Calculate time based on proportion of data points in each zone
    # Total waking hours (6:00-22:00) = 16 hours = 960 minutes
    total_waking_points = len(waking_hours_hr)
    
    # Calculate time in minutes for each zone
    zone_times = {}
    for zone, count in zone_distribution.items():
        # Proportional time calculation: (zone_count / total_points) * total_waking_minutes
        if total_waking_points > 0:
            time_minutes = (count / total_waking_points) * WAKING_HOURS_DURATION
            zone_times[zone] = time_minutes
        else:
            zone_times[zone] = 0
    
    # Create subplots: 1 row with main chart on top, 2 charts below
    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.65, 0.35],
        column_widths=[0.5, 0.5],
        subplot_titles=('', 'Zone Distribution (Waking Hours)', 'HR Distribution (Waking Hours)'),
        specs=[[{'colspan': 2}, None],
               [{}, {}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Add heart rate trace (light blue color) to main chart
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=heart_rates,
        mode='lines',
        name='Heart Rate',
        line=dict(color='#4A90E2', width=2),
        fill='tozeroy',
        fillcolor='rgba(74, 144, 226, 0.2)',
        showlegend=False
    ), row=1, col=1)
    
    # Add horizontal zone lines AFTER the trace so they appear on top
    for idx, (zone_name, (lower, upper, desc)) in enumerate(garmin_zones.items()):
        # Skip Z0 (rest zone) from being drawn as it starts at 0
        if zone_name == 'Z0':
            continue
        # Add horizontal line at the lower boundary of each zone (except Z0)
        fig.add_hline(
            y=lower,
            line_dash="solid",  # Solid for better visibility
            line_color='#000000',  # Black for maximum visibility
            line_width=2,  # Thicker line
            annotation_text=f"{zone_name} ({int(lower)}-{int(upper)} bpm)",
            annotation_position="right",
            annotation_font_size=11,
            annotation_font_color='#000000',
            row=1, col=1
        )
    
    # Add horizontal bar chart for zone distribution
    zone_names = list(garmin_zones.keys())
    zone_time_values = [zone_times[z] for z in garmin_zones.keys()]
    zone_labels = [f"{z} - {garmin_zones[z][2]}" for z in garmin_zones.keys()]
    # Updated colors for Z0-Z5: gray for rest, then green->yellow->orange->red->dark red
    zone_colors_bar = ['#A9A9A9', '#90EE90', '#FFD700', '#FFA500', '#FF6347', '#DC143C']
    
    fig.add_trace(go.Bar(
        y=zone_labels,
        x=zone_time_values,
        orientation='h',
        marker=dict(color=zone_colors_bar),
        text=[format_time(t) for t in zone_time_values],
        textposition='auto',
        showlegend=False
    ), row=2, col=1)
    
    # Add histogram for HR distribution during waking hours with lognormal fit
    if waking_hours_hr:
        # Add histogram
        fig.add_trace(go.Histogram(
            x=waking_hours_hr,
            nbinsx=50,  # Increased from 30 for more granularity
            marker=dict(color='#4A90E2', line=dict(color='white', width=1)),
            showlegend=False,
            name='HR Distribution',
            histnorm='probability density'  # Normalize to show density for comparison with fitted curve
        ), row=2, col=2)
        
        # Fit lognormal distribution shifted by resting heart rate
        # Find minimum HR (resting heart rate) to use as the "zero" point
        min_hr = min(waking_hours_hr)
        
        # Shift data so that minimum HR becomes zero
        # Lognormal distributions cannot go below zero, so we shift the data
        hr_shifted = [hr - min_hr for hr in waking_hours_hr]
        
        # Only fit to positive shifted values (should be all values after shift)
        hr_positive_shifted = [hr for hr in hr_shifted if hr > 0]
        if hr_positive_shifted:
            # Fit lognormal distribution to the shifted data
            shape, loc, scale = stats.lognorm.fit(hr_positive_shifted, floc=0)
            
            # Calculate mean and standard deviation of the fitted lognormal distribution
            lognorm_mean = scale * np.exp(shape**2 / 2)
            lognorm_std = scale * np.sqrt((np.exp(shape**2) - 1) * np.exp(shape**2))
            
            # Generate smooth curve for the fitted distribution
            # Create x values in the shifted space
            x_fit_shifted = np.linspace(0, max_hr - min_hr, 200)
            y_fit = stats.lognorm.pdf(x_fit_shifted, shape, loc, scale)
            
            # Shift x values back to original HR scale for display
            x_fit = x_fit_shifted + min_hr
            
            # Add fitted lognormal curve
            fig.add_trace(go.Scatter(
                x=x_fit,
                y=y_fit,
                mode='lines',
                line=dict(color='#FF6347', width=2.5, dash='solid'),
                name='Lognormal Fit',
                showlegend=False
            ), row=2, col=2)
            
            # Add annotation showing mean, standard deviation, and resting HR
            # Display the mean in the original scale (add back the min_hr)
            lognorm_mean_original = lognorm_mean + min_hr
            lognorm_stats_text = f'Resting HR: {min_hr:.0f} bpm<br>μ = {lognorm_mean_original:.1f} bpm<br>σ = {lognorm_std:.1f} bpm'
            fig.add_annotation(
                text=lognorm_stats_text,
                xref='x3',
                yref='y3',
                x=max_hr * 0.75,
                y=max(y_fit) * 0.85,
                showarrow=False,
                font=dict(size=11, color='#FF6347', family='Arial'),
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='#FF6347',
                borderwidth=1.5,
                borderpad=4,
                align='left',
                row=2, col=2
            )
    
    # Calculate statistics
    avg_hr = sum(heart_rates) / len(heart_rates)
    max_hr_data = max(heart_rates)
    min_hr_data = min(heart_rates)
    
    # Update layout
    fig.update_layout(
        title={
            'text': f'Heart Rate Data - {date_str}',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#333'}
        },
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=11, color='#333'),
        height=700,
        margin=dict(l=60, r=60, t=80, b=60)
    )
    
    # Update axes for main chart
    fig.update_xaxes(
        title_text='Time',
        showgrid=True,
        gridcolor='#E0E0E0',
        tickformat='%H:%M',
        row=1, col=1
    )
    fig.update_yaxes(
        title_text='Heart Rate (bpm)',
        showgrid=True,
        gridcolor='#E0E0E0',
        range=[0, max_hr * 0.90 * 1.1],
        row=1, col=1
    )
    
    # Update axes for bar chart
    fig.update_xaxes(
        title_text='Time (minutes)',
        showgrid=True,
        gridcolor='#E0E0E0',
        row=2, col=1
    )
    fig.update_yaxes(
        title_text='',
        row=2, col=1
    )
    
    # Update axes for histogram
    fig.update_xaxes(
        title_text='Heart Rate (bpm)',
        showgrid=True,
        gridcolor='#E0E0E0',
        range=[0, max_hr],  # Show complete interval from 0 to max HR
        row=2, col=2
    )
    fig.update_yaxes(
        title_text='Frequency',
        showgrid=True,
        gridcolor='#E0E0E0',
        row=2, col=2
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), zone_times


@app.route('/')
def index():
    """Main page with date picker"""
    # Default to yesterday
    default_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template('index.html', default_date=default_date, max_hr=DEFAULT_MAX_HR)


@app.route('/get_heart_rate_data')
def get_heart_rate_data():
    """API endpoint to get heart rate data for a specific date"""
    date_str = request.args.get('date')
    
    if not date_str:
        return jsonify({'error': 'Date parameter is required'}), 400
    
    try:
        # Parse the date
        target_date = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Get Garmin client
        client = get_garmin_client()
        
        # Fetch heart rate data
        data = client.get_heart_rate_data(target_date)
        
        if not data:
            return jsonify({
                'error': f'No heart rate data found for {date_str}',
                'message': 'No activity was recorded on this date or data has not synced yet'
            }), 404
        
        # Create chart JSON
        chart_json, zone_times = create_chart_json(data)
        
        # Calculate statistics
        heart_rates = [point['heart_rate'] for point in data]
        stats = {
            'average': round(sum(heart_rates) / len(heart_rates)),  # Round to integer
            'maximum': max(heart_rates),
            'minimum': min(heart_rates),
            'time_z2': format_time(zone_times['Z2']),  # Z2: 60-70% (Light)
            'time_z4_z5': format_time(zone_times['Z4'] + zone_times['Z5'])  # Z4: 80-90% + Z5: 90-100%
        }
        
        return jsonify({
            'chart': chart_json,
            'stats': stats,
            'date': date_str
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid date format. Please use YYYY-MM-DD'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def create_historical_chart_json(weeks_data, max_hr=DEFAULT_MAX_HR):
    """
    Create chart JSON for historical trends with 4 subplots:
    - Chart A: Daily min/max heart rate over time
    - Chart B: Aggregated time in each zone
    - Chart C: Aggregated heart rate distribution with lognormal fit
    - Chart D: Daily HRV (Heart Rate Variability)
    
    Args:
        weeks_data: Dictionary with dates as keys and dict with 'hr_data' and 'hrv' as values
        max_hr: Maximum heart rate for calculating cardio zones
    
    Returns:
        JSON string for Plotly chart and zone times
    """
    if not weeks_data:
        return None, None
    
    # Garmin HR Zones
    garmin_zones = {
        'Z0': (0, max_hr * 0.50, 'Rest'),
        'Z1': (max_hr * 0.50, max_hr * 0.60, 'Very Light'),
        'Z2': (max_hr * 0.60, max_hr * 0.70, 'Light'),
        'Z3': (max_hr * 0.70, max_hr * 0.80, 'Moderate'),
        'Z4': (max_hr * 0.80, max_hr * 0.90, 'Hard'),
        'Z5': (max_hr * 0.90, max_hr * 1.00, 'Maximum'),
    }
    
    # Prepare data for min/max chart and HRV chart
    dates = []
    daily_mins = []
    daily_maxs = []
    daily_hrvs = []
    
    # Aggregate all heart rates for distribution
    all_waking_hrs = []
    
    # Aggregate zone times
    total_zone_times = {zone: 0 for zone in garmin_zones.keys()}
    
    for date_str in sorted(weeks_data.keys()):
        entry = weeks_data[date_str]
        
        # Handle both old format (list) and new format (dict)
        if isinstance(entry, dict):
            data = entry.get('hr_data', [])
            hrv_value = entry.get('hrv')
        else:
            # Backward compatibility: treat as HR data list
            data = entry
            hrv_value = None
            
        if not data:
            continue
            
        heart_rates = [point['heart_rate'] for point in data]
        dates.append(date_str)
        daily_mins.append(min(heart_rates))
        daily_maxs.append(max(heart_rates))
        
        # Add HRV value if available
        if hrv_value is not None:
            daily_hrvs.append(hrv_value)
        else:
            daily_hrvs.append(None)
        
        # Filter waking hours data (6:00-22:00)
        waking_hours_data = []
        for point in data:
            hour = point['timestamp'].hour
            if 6 <= hour < 22:
                waking_hours_data.append(point)
                all_waking_hrs.append(point['heart_rate'])
        
        # Calculate zone distribution for this day
        waking_hours_hr = [point['heart_rate'] for point in waking_hours_data]
        for hr in waking_hours_hr:
            for zone_name, (lower, upper, _) in garmin_zones.items():
                if lower <= hr < upper:
                    total_zone_times[zone_name] += 1
                    break
    
    # Convert zone counts to time (proportional to total waking hours)
    total_waking_points = sum(total_zone_times.values())
    for zone in total_zone_times:
        if total_waking_points > 0:
            # Each day has 16 hours * 60 minutes = 960 minutes of waking hours
            # Scale by number of days
            time_minutes = (total_zone_times[zone] / total_waking_points) * WAKING_HOURS_DURATION * len(dates)
            total_zone_times[zone] = time_minutes
        else:
            total_zone_times[zone] = 0
    
    # Create subplots - 2x2 grid
    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.5, 0.5],
        column_widths=[0.5, 0.5],
        subplot_titles=(
            'Daily Min/Max Heart Rate',
            'Time in Each Zone',
            'Daily HRV',
            'Heart Rate Distribution'
        ),
        specs=[[{}, {}],
               [{}, {}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Chart A: Daily min/max heart rate (no legend)
    fig.add_trace(go.Scatter(
        x=dates,
        y=daily_mins,
        mode='lines+markers',
        name='Min HR',
        line=dict(color='#4A90E2', width=2),
        marker=dict(size=6),
        showlegend=False
    ), row=1, col=1)
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=daily_maxs,
        mode='lines+markers',
        name='Max HR',
        line=dict(color='#FF6347', width=2),
        marker=dict(size=6),
        showlegend=False
    ), row=1, col=1)
    
    # Chart B: Time in each zone (horizontal bar chart)
    zone_names = list(garmin_zones.keys())
    zone_time_values = [total_zone_times[z] for z in zone_names]
    zone_labels = [f"{z} - {garmin_zones[z][2]}" for z in zone_names]
    # Updated zone colors: Z0=grey, Z1=light blue, Z2=green, Z3=yellow/orange, Z4=red, Z5=dark red
    zone_colors = ['#808080', '#87CEEB', '#00FF00', '#FFA500', '#FF0000', '#8B0000']
    
    fig.add_trace(go.Bar(
        y=zone_labels,
        x=zone_time_values,
        orientation='h',
        marker=dict(color=zone_colors),
        text=[format_time(t) for t in zone_time_values],
        textposition='auto',
        showlegend=False
    ), row=1, col=2)
    
    # Chart D: Daily HRV (positioned at row 2, col 1)
    # Filter out None values for plotting
    hrv_dates = [date for date, hrv in zip(dates, daily_hrvs) if hrv is not None]
    hrv_values = [v for v in daily_hrvs if v is not None]
    
    if hrv_values:
        fig.add_trace(go.Scatter(
            x=hrv_dates,
            y=hrv_values,
            mode='lines+markers',
            name='HRV',
            line=dict(color='#9B59B6', width=2),
            marker=dict(size=6),
            showlegend=False
        ), row=2, col=1)
    
    # Chart C: Heart rate distribution with lognormal fit (positioned at row 2, col 2)
    if all_waking_hrs:
        fig.add_trace(go.Histogram(
            x=all_waking_hrs,
            nbinsx=50,
            marker=dict(color='#4A90E2', line=dict(color='white', width=1)),
            showlegend=False,
            name='HR Distribution',
            histnorm='probability density'
        ), row=2, col=2)
        
        # Fit lognormal distribution
        min_hr = min(all_waking_hrs)
        hr_shifted = [hr - min_hr for hr in all_waking_hrs]
        hr_positive_shifted = [hr for hr in hr_shifted if hr > 0]
        
        if hr_positive_shifted:
            shape, loc, scale = stats.lognorm.fit(hr_positive_shifted, floc=0)
            lognorm_mean = scale * np.exp(shape**2 / 2)
            lognorm_std = scale * np.sqrt((np.exp(shape**2) - 1) * np.exp(shape**2))
            
            x_fit_shifted = np.linspace(0, max_hr - min_hr, 200)
            y_fit = stats.lognorm.pdf(x_fit_shifted, shape, loc, scale)
            x_fit = x_fit_shifted + min_hr
            
            fig.add_trace(go.Scatter(
                x=x_fit,
                y=y_fit,
                mode='lines',
                line=dict(color='#FF6347', width=2.5, dash='solid'),
                name='Lognormal Fit',
                showlegend=False
            ), row=2, col=2)
            
            # Add annotation with stats
            lognorm_mean_original = lognorm_mean + min_hr
            lognorm_stats_text = f'Min Waking HR: {min_hr:.0f} bpm<br>μ = {lognorm_mean_original:.1f} bpm<br>σ = {lognorm_std:.1f} bpm'
            # Chart C is at position (2,2) which corresponds to x4/y4 in plotly
            fig.add_annotation(
                text=lognorm_stats_text,
                xref='x4',  # Chart C: row 2, col 2
                yref='y4',  # Chart C: row 2, col 2
                x=max_hr * 0.75,
                y=max(y_fit) * 0.85,
                showarrow=False,
                font=dict(size=11, color='#FF6347', family='Arial'),
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='#FF6347',
                borderwidth=1.5,
                borderpad=4,
                align='left'
            )
    
    # Update layout
    fig.update_layout(
        title={
            'text': f'Historical Trends - Last {len(dates)} Days',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#333'}
        },
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=11, color='#333'),
        height=700,
        margin=dict(l=60, r=60, t=80, b=60),
        showlegend=False
    )
    
    # Update axes for Chart A (row 1, col 1) - removed Date label
    fig.update_xaxes(title_text='', showgrid=True, gridcolor='#E0E0E0', row=1, col=1)
    fig.update_yaxes(title_text='Heart Rate (bpm)', showgrid=True, gridcolor='#E0E0E0', row=1, col=1)
    
    # Update axes for Chart B (row 1, col 2)
    fig.update_xaxes(title_text='Time', showgrid=True, gridcolor='#E0E0E0', row=1, col=2)
    fig.update_yaxes(title_text='', row=1, col=2)
    
    # Update axes for Chart D - HRV (row 2, col 1) - set range to 0-100
    fig.update_xaxes(title_text='Date', showgrid=True, gridcolor='#E0E0E0', row=2, col=1)
    fig.update_yaxes(title_text='HRV (ms)', showgrid=True, gridcolor='#E0E0E0', range=[0, 100], row=2, col=1)
    
    # Update axes for Chart C - Distribution (row 2, col 2)
    fig.update_xaxes(title_text='Heart Rate (bpm)', showgrid=True, gridcolor='#E0E0E0', range=[0, max_hr], row=2, col=2)
    fig.update_yaxes(title_text='Frequency', showgrid=True, gridcolor='#E0E0E0', row=2, col=2)
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder), total_zone_times


@app.route('/get_historical_data')
def get_historical_data():
    """API endpoint to get historical heart rate data for multiple weeks"""
    weeks_str = request.args.get('weeks', '4')
    
    try:
        weeks = int(weeks_str)
        if weeks not in [4, 8, 12, 16, 24, 48]:
            return jsonify({'error': 'Invalid weeks parameter. Must be 4, 8, 12, 16, 24, or 48'}), 400
        
        # Get Garmin client
        client = get_garmin_client()
        
        # Fetch data for the last N weeks (excluding today)
        weeks_data = {}
        all_heart_rates = []
        end_date = datetime.now() - timedelta(days=1)  # Exclude today
        start_date = end_date - timedelta(weeks=weeks)
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            try:
                hr_data = client.get_heart_rate_data(current_date)
                hrv_data = client.get_hrv_data(current_date)
                
                if hr_data:
                    weeks_data[date_str] = {
                        'hr_data': hr_data,
                        'hrv': hrv_data
                    }
                    all_heart_rates.extend([point['heart_rate'] for point in hr_data])
            except Exception as e:
                print(f"Warning: Could not fetch data for {date_str}: {e}")
            
            current_date += timedelta(days=1)
        
        if not weeks_data:
            return jsonify({
                'error': f'No heart rate data found for the last {weeks} weeks',
                'message': 'No activity was recorded in this period or data has not synced yet'
            }), 404
        
        # Create historical chart JSON
        chart_json, zone_times = create_historical_chart_json(weeks_data)
        
        # Calculate statistics for the entire period
        stats = {
            'average': round(sum(all_heart_rates) / len(all_heart_rates)),
            'maximum': max(all_heart_rates),
            'minimum': min(all_heart_rates),
            'time_z2': format_time(zone_times['Z2']),
            'time_z4_z5': format_time(zone_times['Z4'] + zone_times['Z5'])
        }
        
        return jsonify({
            'chart': chart_json,
            'stats': stats,
            'weeks': weeks,
            'days_with_data': len(weeks_data)
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid weeks parameter. Must be an integer'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/get_monthly_data')
def get_monthly_data():
    """API endpoint to get historical heart rate data for a specific month"""
    year_str = request.args.get('year')
    month_str = request.args.get('month')
    
    if not year_str or not month_str:
        return jsonify({'error': 'Year and month parameters are required'}), 400
    
    try:
        year = int(year_str)
        month = int(month_str)
        
        if month < 1 or month > 12:
            return jsonify({'error': 'Invalid month. Must be between 1 and 12'}), 400
        
        if year < 2000 or year > 2100:
            return jsonify({'error': 'Invalid year'}), 400
        
        # Get Garmin client
        client = get_garmin_client()
        
        # Calculate first and last day of the month
        start_date = datetime(year, month, 1)
        
        # Calculate last day of month
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)
        
        # Fetch data for all days in the month
        month_data = {}
        all_heart_rates = []
        
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            try:
                hr_data = client.get_heart_rate_data(current_date)
                hrv_data = client.get_hrv_data(current_date)
                
                if hr_data:
                    month_data[date_str] = {
                        'hr_data': hr_data,
                        'hrv': hrv_data
                    }
                    all_heart_rates.extend([point['heart_rate'] for point in hr_data])
            except Exception as e:
                print(f"Warning: Could not fetch data for {date_str}: {e}")
            
            current_date += timedelta(days=1)
        
        if not month_data:
            month_names = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December']
            return jsonify({
                'error': f'No heart rate data found for {month_names[month-1]} {year}',
                'message': 'No activity was recorded in this month or data has not synced yet'
            }), 404
        
        # Create historical chart JSON (reuse the same function)
        chart_json, zone_times = create_historical_chart_json(month_data)
        
        # Calculate statistics for the entire month
        stats = {
            'average': round(sum(all_heart_rates) / len(all_heart_rates)),
            'maximum': max(all_heart_rates),
            'minimum': min(all_heart_rates),
            'time_z2': format_time(zone_times['Z2']),
            'time_z4_z5': format_time(zone_times['Z4'] + zone_times['Z5'])
        }
        
        return jsonify({
            'chart': chart_json,
            'stats': stats,
            'year': year,
            'month': month,
            'days_with_data': len(month_data)
        })
        
    except ValueError:
        return jsonify({'error': 'Invalid year or month parameter'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    import os
    print("Starting Fitness Dashboard Web App...")
    print("Open your browser and navigate to: http://localhost:5000")
    # Only enable debug mode if explicitly set via environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
