# ME_470_k-W/Ton-DataLogger-Project

# kW/Ton Data Logger

A real-time monitoring system for HVAC performance metrics with configurable data collection intervals and interactive visualization.

## Features

- **Real-time Data Collection**
  - Continuous monitoring of temperature, pressure, and power metrics
  - Precise 1-second sampling rate with duplicate prevention
  - Multi-threaded design for concurrent data collection and processing
  - Automated data aggregation and storage

- **Web Interface**
  - **Dashboard Page**
    - Real-time visualization of system metrics
    - Historical data trends display
    - Interactive performance monitoring
    - Support for up to 500 most recent entries per interval
  - **Configuration Page**
    - System parameter adjustment interface
    - Data collection interval settings
    - Retention period configuration
    - Flow rate calibration management

- **Performance Metrics**
  - kW/Ton efficiency calculations
  - Temperature differential monitoring
  - Pressure differential tracking
  - Cooling load computation
  - Flow rate calculations using logarithmic calibration

## System Architecture

- **Sensor Management**
  - Auto-detection of Arduino ports
  - 9600 baud rate serial communication
  - 12800-byte RX/TX buffers
  - Robust error handling

- **Data Processing**
  - Efficient aggregation algorithms
  - Floor timestamp mechanism for precise intervals
  - Defaultdict structure for flexible data management
  - Automatic hourly data cleanup

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

### Configuration Table
```sql
CREATE TABLE config (
    id INTEGER PRIMARY KEY,
    interval1_seconds INTEGER NOT NULL CHECK(interval1_seconds > 0),
    interval2_seconds INTEGER NOT NULL CHECK(interval2_seconds > 0),
    interval3_seconds INTEGER NOT NULL CHECK(interval3_seconds > 0),
    retention_interval1 INTEGER NOT NULL CHECK(retention_interval1 > 0),
    retention_interval2 INTEGER NOT NULL CHECK(retention_interval2 > 0),
    retention_interval3 INTEGER NOT NULL CHECK(retention_interval3 > 0)
)
```

### Calibration Table
```sql
CREATE TABLE calibration_points (
    id INTEGER PRIMARY KEY,
    pressure_diff REAL NOT NULL,
    flow_rate REAL NOT NULL,
    timestamp TEXT NOT NULL
)
```

## Usage

1. Start the application:
```bash
python app.py
```

2. Access the interface:
- Dashboard: `http://localhost:5001`
- Configuration: `http://localhost:5001/config`

## Dependencies
- Flask web framework
- SQLite database
- Python serial library
- Threading support
- Math utilities
