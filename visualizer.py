"""
Heart Rate Visualization Module
Creates plotly charts for heart rate data
"""
import plotly.graph_objects as go
from datetime import datetime
from typing import List, Dict


def create_heart_rate_chart(data: List[Dict], output_file: str = 'heart_rate_chart.html') -> None:
    """
    Create a line chart visualization of heart rate data using plotly
    
    Args:
        data: List of dictionaries with 'timestamp' and 'heart_rate' keys
        output_file: Path to save the HTML chart file
    """
    if not data:
        print("No data to plot")
        return
    
    # Extract timestamps and heart rates
    timestamps = [point['timestamp'] for point in data]
    heart_rates = [point['heart_rate'] for point in data]
    
    # Get date for title
    date_str = timestamps[0].strftime('%Y-%m-%d') if timestamps else 'Unknown Date'
    
    # Create the plotly figure
    fig = go.Figure()
    
    # Add heart rate trace
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=heart_rates,
        mode='lines',
        name='Heart Rate',
        line=dict(color='#FF6B6B', width=2),
        fill='tozeroy',
        fillcolor='rgba(255, 107, 107, 0.2)'
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
            rangemode='tozero'
        ),
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family='Arial, sans-serif', size=12, color='#333'),
        height=600,
        margin=dict(l=80, r=80, t=100, b=80)
    )
    
    # Add statistics annotation
    if heart_rates:
        avg_hr = sum(heart_rates) / len(heart_rates)
        max_hr = max(heart_rates)
        min_hr = min(heart_rates)
        
        stats_text = (
            f'Average: {avg_hr:.0f} bpm | '
            f'Max: {max_hr} bpm | '
            f'Min: {min_hr} bpm'
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
    
    # Also display summary statistics
    if heart_rates:
        print(f"\nHeart Rate Statistics:")
        print(f"  Average: {avg_hr:.1f} bpm")
        print(f"  Maximum: {max_hr} bpm")
        print(f"  Minimum: {min_hr} bpm")
        print(f"  Data points: {len(heart_rates)}")
