# FitnessDashboard

A Python application that connects to your Garmin account, retrieves heart rate data, and creates beautiful interactive visualizations using Plotly. Now features an interactive web interface!

## Features

- 🚴 **Aerobic Base Dashboard** - Explainable weekly 0–100 scoring for low-intensity volume, frequency, durability, efficiency, and recovery
- 🗓️ **Daily Aerobic Calendar** - Year-to-date calendar colored by the transparent daily aerobic guide
- 🔐 Secure authentication with Garmin Connect
- 📊 Interactive heart rate line charts with Plotly
- 🌐 **Web Interface** - Interactive date picker to view any day's data
- 📅 Retrieves heart rate data for any selected date
- 🎯 Real-time chart updates when selecting different dates
- 📈 Displays statistics (average, max, min heart rate)
- 💙 Beautiful light blue color scheme with cardio zones
- 📍 Cardio zone overlays based on maximum heart rate

## Prerequisites

- Python 3.7 or higher
- A Garmin Connect account
- Heart rate data recorded on your Garmin device

## Installation

1. Clone the repository:
```bash
git clone https://github.com/giulianods/FitnessDashboard.git
cd FitnessDashboard
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create configuration file:
```bash
cp config.json.example config.json
```

4. Edit `config.json` with your Garmin credentials:
```json
{
    "email": "your_garmin_email@example.com",
    "password": "your_garmin_password"
}
```

**Note:** Make sure `config.json` is never committed to version control (it's already in `.gitignore`).

## Usage

### Web Application (Recommended)

Launch the interactive web interface:

```bash
python app.py
```

Then open your browser and navigate to:
```
http://localhost:5000
```

The Aerobic Base dashboard is the first view. Its first refresh imports the selected
range from Garmin in bounded chunks and caches source and derived data in SQLite.
Use the settings panel to inspect the active values; customize targets, eligible
activities, HR zones, LT1, deload weeks, and thresholds in the `aerobic_base`
section shown in `config.json.example`.

### Persistent server and daily Garmin sync

For an always-on installation, serve the Flask application with Gunicorn instead
of the development server:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/gunicorn --workers 2 --threads 2 --timeout 120 \
  --bind 127.0.0.1:5000 wsgi:app
```

`127.0.0.1` is appropriate behind a reverse proxy. Binding to `0.0.0.0:5000`
exposes the dashboard to the network; the application does not provide login
authentication, so use a firewall or an authenticated reverse proxy.

An editable systemd unit is provided at
`deploy/fitness-dashboard.service.example`. Replace its user, group, and absolute
paths, copy it to `/etc/systemd/system/fitness-dashboard.service`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fitness-dashboard
curl http://127.0.0.1:5000/healthz
```

The daily updater is independent of the web process:

```bash
.venv/bin/python sync_aerobic_data.py
```

It backfills unchecked activity dates needed for the current-year calendar,
imports any missing 35-day recovery baseline, force-refreshes the latest three
days, warms the legacy HR/HRV caches, and recalculates the current dashboards.
Runs are idempotent and protected by `data/aerobic_sync.lock` so overlapping cron
jobs cannot run concurrently.

To install the example cron schedule, edit the absolute paths in
`deploy/fitness-dashboard.cron.example` and add it with `crontab -e`. It runs at
04:15 in the Europe/Bucharest timezone and writes output to `data/sync.log`:

```cron
SHELL=/bin/bash
CRON_TZ=Europe/Bucharest
15 4 * * * cd /absolute/path/to/FitnessDashboard && /absolute/path/to/FitnessDashboard/.venv/bin/python sync_aerobic_data.py >> data/sync.log 2>&1
```

Useful sync options:

```bash
.venv/bin/python sync_aerobic_data.py --recent-days 5
.venv/bin/python sync_aerobic_data.py --no-backfill
```

**Features:**
- 📅 Interactive date picker to select any date
- 🔄 Real-time chart updates
- 📊 Statistics cards showing avg/max/min heart rate
- 🎨 Beautiful, modern UI with gradient design
- 📱 Responsive layout that works on all devices
- ⚡ Quick access buttons for "Yesterday" and "Today"

### Command Line Interface

#### Basic Usage (Yesterday's Data)

Retrieve and visualize yesterday's heart rate data:

```bash
python main.py
```

This will create `heart_rate_chart.html` in the current directory.

### Custom Date

Retrieve data for a specific date:

```bash
python main.py --date 2024-01-20
```

### Custom Output File

Specify a custom output file:

```bash
python main.py --output my_heart_rate.html
```

### All Options

```bash
python main.py --config config.json --output chart.html --date 2024-01-20
```

## Command Line Options

- `--config`: Path to config file (default: `config.json`)
- `--output`: Output file for the chart (default: `heart_rate_chart.html`)
- `--date`: Specific date to retrieve data for in YYYY-MM-DD format (default: yesterday)

## Output

The application generates an interactive HTML chart with:
- Line plot of heart rate throughout the day
- Hover tooltips showing time and heart rate values
- Statistics summary (average, maximum, minimum)
- Filled area under the curve for better visualization
- Professional styling with grid lines and proper labels

## Project Structure

```
FitnessDashboard/
├── main.py              # Main script to run the application
├── garmin_client.py     # Garmin Connect API client
├── visualizer.py        # Plotly visualization module
├── requirements.txt     # Python dependencies
├── config.json.example  # Example configuration file
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## Dependencies

- `garminconnect` - Python library for Garmin Connect API
- `plotly` - Interactive graphing library
- `pandas` - Data manipulation library
- `python-dotenv` - Environment variable management

## Troubleshooting

### No data found
- Ensure your Garmin device was worn on the specified date
- Check that your device has synced with Garmin Connect
- Verify that heart rate monitoring was enabled

### Login failed
- Double-check your credentials in `config.json`
- Ensure your Garmin Connect account is active
- Check if you need to accept new terms of service on Garmin Connect website

### Import errors
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Verify you're using Python 3.7 or higher

## Security Notes

- Never commit `config.json` with your actual credentials
- The `.gitignore` file is configured to exclude sensitive files
- Consider using environment variables for production deployments

## License

MIT License - Feel free to use and modify for your own fitness tracking needs!

## Contributing

Contributions are welcome! Feel free to submit issues or pull requests.

## Acknowledgments

- Built with [garminconnect](https://github.com/cyberjunky/python-garminconnect)
- Visualizations powered by [Plotly](https://plotly.com/python/)
