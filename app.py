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
    garmin_zones = {
        'Z0': (max_hr * 0.50, max_hr * 0.60, 'Warm-up'),
        'Z1': (max_hr * 0.60, max_hr * 0.70, 'Easy'),
        'Z2': (max_hr * 0.70, max_hr * 0.80, 'Aerobic'),
        'Z3': (max_hr * 0.80, max_hr * 0.90, 'Threshold'),
        'Z4': (max_hr * 0.90, max_hr * 1.00, 'Maximum'),
        'Z5': (max_hr * 1.00, max_hr * 1.20, 'Peak'),
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
    below_z0_count = 0  # Count for HR below Zone 0 (below 50% max HR)
    
    for hr in waking_hours_hr:
        if hr < max_hr * 0.50:
            below_z0_count += 1
        else:
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
    
    # Calculate time below Z0
    if total_waking_points > 0:
        below_z0_time = (below_z0_count / total_waking_points) * WAKING_HOURS_DURATION
    else:
        below_z0_time = 0
    
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
    
    # Add cardio zone lines to main chart
    zone_colors = ['#90EE90', '#FFD700', '#FFA500', '#FF6347', '#DC143C', '#8B0000']
    
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
        # Add horizontal line at the upper boundary (except for the last zone)
        if idx < len(garmin_zones) - 1:
            fig.add_hline(
                y=upper,
                line_dash="solid",  # Changed to solid for better visibility
                line_color='#000000',  # Black for maximum visibility
                line_width=2,  # Thicker line
                annotation_text=f"{zone_name} ({int(lower)}-{int(upper)} bpm)",
                annotation_position="right",
                annotation_font_size=11,
                annotation_font_color='#000000',
                row=1, col=1
            )
        else:
            # For the last zone (open-ended), add annotation at the lower boundary
            fig.add_hline(
                y=lower,
                line_dash="solid",
                line_color='#000000',
                line_width=2,
                annotation_text=f"{zone_name} (>{int(lower)} bpm)",
                annotation_position="right",
                annotation_font_size=11,
                annotation_font_color='#000000',
                row=1, col=1
            )
    
    # Add horizontal bar chart for zone distribution (with Below Z0)
    zone_names = ['Below Z0'] + list(garmin_zones.keys())
    zone_time_values = [below_z0_time] + [zone_times[z] for z in garmin_zones.keys()]
    zone_labels = ['Below Z0 (<50%)'] + [f"{z} - {garmin_zones[z][2]}" for z in garmin_zones.keys()]
    zone_colors_with_below = ['#B0C4DE'] + zone_colors  # Light steel blue for below Z0
    
    fig.add_trace(go.Bar(
        y=zone_labels,
        x=zone_time_values,
        orientation='h',
        marker=dict(color=zone_colors_with_below),
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
            'time_z2': format_time(zone_times['Z2']),
            'time_z4_z5': format_time(zone_times['Z4'] + zone_times['Z5'])  # Combined Z4 and Z5
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


if __name__ == '__main__':
    import os
    print("Starting Fitness Dashboard Web App...")
    print("Open your browser and navigate to: http://localhost:5000")
    # Only enable debug mode if explicitly set via environment variable
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)
