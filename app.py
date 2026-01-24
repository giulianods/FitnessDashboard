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

app = Flask(__name__)

# Configuration
DEFAULT_MAX_HR = 190  # Default maximum heart rate for cardio zones

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
    date_str = data[0]['timestamp'].strftime('%Y-%m-%d')
    
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
    for hr in waking_hours_hr:
        for zone_name, (lower, upper, _) in garmin_zones.items():
            if lower <= hr < upper:
                zone_distribution[zone_name] += 1
                break
    
    # Convert counts to percentages
    total_waking_points = len(waking_hours_hr)
    zone_percentages = {zone: (count / total_waking_points * 100) if total_waking_points > 0 else 0 
                        for zone, count in zone_distribution.items()}
    
    # Create subplots: 1 row with main chart on top, 2 charts below
    fig = make_subplots(
        rows=2, cols=2,
        row_heights=[0.65, 0.35],
        column_widths=[0.5, 0.5],
        subplot_titles=('Heart Rate Timeline', 'Zone Distribution (Waking Hours)', 'HR Distribution (Waking Hours)'),
        specs=[[{'colspan': 2}, None],
               [{}, {}]],
        vertical_spacing=0.12,
        horizontal_spacing=0.1
    )
    
    # Add cardio zone lines to main chart
    zone_colors = ['#90EE90', '#FFD700', '#FFA500', '#FF6347', '#DC143C', '#8B0000']
    for idx, (zone_name, (lower, upper, desc)) in enumerate(garmin_zones.items()):
        # Add horizontal line at the upper boundary (except for the last zone)
        if idx < len(garmin_zones) - 1:
            fig.add_hline(
                y=upper,
                line_dash="dash",
                line_color='#CCCCCC',
                line_width=1,
                annotation_text=f"{zone_name} ({int(lower)}-{int(upper)} bpm)",
                annotation_position="right",
                annotation_font_size=9,
                annotation_font_color='#666',
                row=1, col=1
            )
        else:
            # For the last zone (open-ended), add annotation at the lower boundary
            fig.add_hline(
                y=lower,
                line_dash="dash",
                line_color='#CCCCCC',
                line_width=1,
                annotation_text=f"{zone_name} (>{int(lower)} bpm)",
                annotation_position="right",
                annotation_font_size=9,
                annotation_font_color='#666',
                row=1, col=1
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
    
    # Add horizontal bar chart for zone distribution
    zone_names = list(garmin_zones.keys())
    zone_pcts = [zone_percentages[z] for z in zone_names]
    zone_labels = [f"{z} - {garmin_zones[z][2]}" for z in zone_names]
    
    fig.add_trace(go.Bar(
        y=zone_labels,
        x=zone_pcts,
        orientation='h',
        marker=dict(color=zone_colors),
        text=[f"{pct:.1f}%" for pct in zone_pcts],
        textposition='auto',
        showlegend=False
    ), row=2, col=1)
    
    # Add histogram for HR distribution during waking hours
    if waking_hours_hr:
        fig.add_trace(go.Histogram(
            x=waking_hours_hr,
            nbinsx=50,  # Increased from 30 for more granularity
            marker=dict(color='#4A90E2', line=dict(color='white', width=1)),
            showlegend=False
        ), row=2, col=2)
    
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
        title_text='Percentage of Time (%)',
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
    
    # Add statistics annotation
    stats_text = (
        f'Average: {avg_hr:.0f} bpm | '
        f'Max: {max_hr_data} bpm | '
        f'Min: {min_hr_data} bpm'
    )
    
    fig.add_annotation(
        text=stats_text,
        xref='paper',
        yref='paper',
        x=0.5,
        y=-0.12,
        showarrow=False,
        font=dict(size=12, color='#666'),
        xanchor='center'
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


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
        chart_json = create_chart_json(data)
        
        # Calculate statistics
        heart_rates = [point['heart_rate'] for point in data]
        stats = {
            'average': round(sum(heart_rates) / len(heart_rates), 1),
            'maximum': max(heart_rates),
            'minimum': min(heart_rates),
            'data_points': len(heart_rates)
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
