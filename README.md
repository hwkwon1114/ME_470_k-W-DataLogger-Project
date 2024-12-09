# ME_470_k-W-DataLogger-Project

# HVAC Monitoring System

A real-time monitoring system for HVAC performance metrics with configurable data collection intervals and interactive visualization.

## Features

- **Real-time Data Collection**
  - Continuous monitoring of temperature, pressure, and power metrics
  - Configurable sampling rates at three different intervals
  - Automated data aggregation and storage

- **Interactive Dashboard**
  - Real-time data visualization using Chart.js
  - Customizable X and Y axis metrics
  - Multiple visualization options:
    - Time-series analysis
    - Performance correlation plots
    - System efficiency metrics

- **Configurable Settings**
  - Adjustable flow coefficient
  - Customizable data collection intervals
  - Configurable data retention periods
  - User-friendly configuration interface

- **Performance Metrics**
  - kW/Ton efficiency
  - Temperature differential
  - Pressure differential
  - Cooling load
  - Flow rate calculations

## Usage

1. Start the application:
```bash
python app.py
```

2. Access the dashboard:
- Open a web browser and navigate to `http://localhost:5001`
- View the configuration page at `http://localhost:5001/config`

## Configuration Options

### Data Collection Intervals
- Interval 1: Fast sampling (default: 60 seconds)
- Interval 2: Medium sampling (default: 900 seconds)
- Interval 3: Slow sampling (default: 3600 seconds)

### Data Retention
- Configurable retention periods for each interval
- Automatic data cleanup based on retention settings
- Independent retention policies for different sampling rates

## Database Schema

### Metrics Table
```sql
CREATE TABLE metrics (
    timestamp TEXT NOT NULL,
    temp1 REAL NOT NULL,
    temp2 REAL NOT NULL,
    pressure1 REAL NOT NULL,
    pressure2 REAL NOT NULL,
    power REAL NOT NULL,
    kw_ton REAL NOT NULL,
    cooling_tons REAL NOT NULL,
    flow_rate REAL NOT NULL,
    interval TEXT NOT NULL
)
```

### Config Table
```sql
CREATE TABLE config (
    id INTEGER PRIMARY KEY,
    flow_coefficient REAL NOT NULL,
    interval1_seconds INTEGER NOT NULL,
    interval2_seconds INTEGER NOT NULL,
    interval3_seconds INTEGER NOT NULL,
    retention_interval1 INTEGER NOT NULL,
    retention_interval2 INTEGER NOT NULL,
    retention_interval3 INTEGER NOT NULL
)
```

## API Endpoints

- `/`: Main dashboard
- `/config`: Configuration interface (GET/POST)
- `/data/<interval>`: Data retrieval for specified interval
n
- Flask for web framework
- SQLite for data storage
