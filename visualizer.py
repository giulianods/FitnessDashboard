"""
Heart Rate Visualization Module
Creates plotly charts for heart rate data
"""
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict
import webbrowser
import os


def create_heart_rate_chart(data: List[Dict], output_file: str = 'heart_rate_chart.html', 
                            max_hr: int = 190, open_browser: bool = True) -> None:
    """
    Create a line chart visualization of heart rate data using plotly
    
    Args:
        data: List of dictionaries with 'timestamp' and 'heart_rate' keys
        output_file: Path to save the HTML chart file
        max_hr: Maximum heart rate for calculating cardio zones (default: 190)
        open_browser: Whether to automatically open the chart in browser (default: True)
    """
    if not data:
        print("No data to plot")
        return
    
    # Extract timestamps and heart rates
    timestamps = [point['timestamp'] for point in data]
    heart_rates = [point['heart_rate'] for point in data]
    
    # Get date for title
    date_str = timestamps[0].strftime('%Y-%m-%d') if timestamps else 'Unknown Date'
    
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
            range=[0, max_hr * 0.90 * 1.1]  # Scale to 10% above the highest zone (Zone 3 upper limit)
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=12, color='#333'),
        height=600,
        margin=dict(l=80, r=80, t=100, b=80)
    )
    
    # Add statistics annotation and display summary
    if heart_rates:
        avg_hr = sum(heart_rates) / len(heart_rates)
        max_hr_data = max(heart_rates)
        min_hr_data = min(heart_rates)
        
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
    
    # Save to HTML file
    fig.write_html(output_file)
    print(f"Chart saved to {output_file}")
    
    # Display summary statistics
    if heart_rates:
        print(f"\nHeart Rate Statistics:")
        print(f"  Average: {avg_hr:.1f} bpm")
        print(f"  Maximum: {max_hr_data} bpm")
        print(f"  Minimum: {min_hr_data} bpm")
        print(f"  Data points: {len(heart_rates)}")
    
    # Open the chart in the default browser
    if open_browser:
        abs_path = os.path.abspath(output_file)
        webbrowser.open('file://' + abs_path)
        print(f"\n✓ Opening chart in browser...")
