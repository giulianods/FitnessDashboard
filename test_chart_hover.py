"""Hover crosshair settings on the historical / monthly Plotly figure."""
import json
from datetime import datetime

from app import create_historical_chart_json


def test_historical_chart_has_vertical_hover_and_trace_labels():
    weeks_data = {
        '2026-01-10': {
            'hr_data': [
                {'timestamp': datetime(2026, 1, 10, 8, 0), 'heart_rate': 60},
                {'timestamp': datetime(2026, 1, 10, 12, 0), 'heart_rate': 140},
            ],
            'hrv': 45.0,
        }
    }
    chart_json, _ = create_historical_chart_json(
        weeks_data, display_days=7, display_start_date='2026-01-10'
    )
    payload = json.loads(chart_json)
    assert payload['layout']['hovermode'] == 'x unified'
    assert payload['layout']['xaxis']['showspikes'] is True
    assert payload['layout']['xaxis']['spikemode'] == 'across'
    hovertemplates = [trace.get('hovertemplate') for trace in payload['data']]
    assert all(hovertemplates), hovertemplates
    assert any('bpm' in (template or '') for template in hovertemplates)
    assert any('ms' in (template or '') for template in hovertemplates)


def test_historical_chart_axes_scale_to_samples():
    """Empty leading days must not leave a blank region; y-axes fit the series."""
    weeks_data = {
        '2025-04-24': {'hr_data': [], 'hrv': None},
        '2025-08-06': {
            'hr_data': [
                {'timestamp': datetime(2025, 8, 6, 8, 0), 'heart_rate': 55},
                {'timestamp': datetime(2025, 8, 6, 12, 0), 'heart_rate': 140},
            ],
            'hrv': 40.0,
        },
        '2026-09-10': {
            'hr_data': [
                {'timestamp': datetime(2026, 9, 10, 8, 0), 'heart_rate': 60},
                {'timestamp': datetime(2026, 9, 10, 12, 0), 'heart_rate': 150},
            ],
            'hrv': 80.0,
        },
    }
    chart_json, _ = create_historical_chart_json(
        weeks_data, display_days=504, display_start_date='2025-04-24'
    )
    payload = json.loads(chart_json)
    axis_range = payload['layout']['xaxis']['range']
    assert str(axis_range[0]).startswith('2025-08-06')
    assert '2026-09-10' in str(axis_range[1])
    min_hr = next(trace for trace in payload['data'] if trace.get('name') == 'Min HR')
    assert min_hr['x'][0] == '2025-04-24'
    assert min_hr['y'][0] is None

    hr_y = payload['layout']['yaxis']['range']
    assert hr_y[0] > 0
    assert hr_y[0] < 55
    assert hr_y[1] > 150

    hrv_y = payload['layout']['yaxis3']['range']
    assert hrv_y != [0, 100]
    assert hrv_y[0] < 40
    assert hrv_y[1] > 80
