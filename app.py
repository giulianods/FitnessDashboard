#!/usr/bin/env python3
"""
Fitness Dashboard - Web Application
Interactive web interface for viewing heart rate data with date selection
"""
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
from garmin_client import GarminClient
import plotly.graph_objects as go
import json

app = Flask(__name__)

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


def create_chart_json(data, max_hr=190):
    """
    Create chart JSON for Plotly
    
    Args:
        data: List of dictionaries with 'timestamp' and 'heart_rate' keys
        max_hr: Maximum heart rate for calculating cardio zones (default: 190)
    
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
    
    # Calculate cardio zone boundaries based on max HR
    zones = {
        'Zone -2': (0, max_hr * 0.40),
        'Zone -1': (max_hr * 0.40, max_hr * 0.50),
        'Zone 0': (max_hr * 0.50, max_hr * 0.60),
        'Zone 1': (max_hr * 0.60, max_hr * 0.70),
        'Zone 2': (max_hr * 0.70, max_hr * 0.80),
        'Zone 3': (max_hr * 0.80, max_hr * 0.90),
        'Zone 4': (max_hr * 0.90, max_hr * 1.20),
    }
    
    # Create the plotly figure
    fig = go.Figure()
    
    # Add cardio zone lines
    zone_colors = ['#E8E8E8', '#D0D0D0', '#B8B8B8', '#A0A0A0', '#888888', '#707070', '#585858']
    for idx, (zone_name, (lower, upper)) in enumerate(zones.items()):
        # Add horizontal line at the upper boundary (except for the last zone)
        if idx < len(zones) - 1:
            fig.add_hline(
                y=upper,
                line_dash="dash",
                line_color=zone_colors[idx],
                line_width=1,
                annotation_text=f"{zone_name} ({int(lower)}-{int(upper)} bpm)",
                annotation_position="right",
                annotation_font_size=10,
                annotation_font_color='#666'
            )
        else:
            # For the last zone (open-ended), add annotation at the lower boundary
            fig.add_hline(
                y=lower,
                line_dash="dash",
                line_color=zone_colors[idx],
                line_width=1,
                annotation_text=f"{zone_name} (>{int(lower)} bpm)",
                annotation_position="right",
                annotation_font_size=10,
                annotation_font_color='#666'
            )
    
    # Add heart rate trace (light blue color)
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=heart_rates,
        mode='lines',
        name='Heart Rate',
        line=dict(color='#4A90E2', width=2),
        fill='tozeroy',
        fillcolor='rgba(74, 144, 226, 0.2)'
    ))
    
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
            'font': {'size': 24, 'color': '#333'}
        },
        xaxis_title='Time',
        yaxis_title='Heart Rate (bpm)',
        xaxis=dict(
            showgrid=True,
            gridcolor='#E0E0E0',
            tickformat='%H:%M'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='#E0E0E0',
            range=[0, max_hr * 0.90 * 1.1]  # Scale to 10% above Zone 3 upper limit (90% of max HR)
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=12, color='#333'),
        height=600,
        margin=dict(l=80, r=80, t=100, b=80)
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
        y=-0.15,
        showarrow=False,
        font=dict(size=14, color='#666'),
        xanchor='center'
    )
    
    return json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)


@app.route('/')
def index():
    """Main page with date picker"""
    # Default to yesterday
    default_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    return render_template('index.html', default_date=default_date)


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
    print("Starting Fitness Dashboard Web App...")
    print("Open your browser and navigate to: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
