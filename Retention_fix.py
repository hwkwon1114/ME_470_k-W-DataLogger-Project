from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
from collections import defaultdict
import random
from Sensor import Sensor
import os
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager

app = Flask(__name__)

# Initialize logging
if not os.path.exists('logs'):
    os.makedirs('logs')
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1024000, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Application startup')

@contextmanager
def get_db_connection():
    """Safe database connection context manager"""
    conn = None
    try:
        conn = sqlite3.connect('metrics.db')
        yield conn
    finally:
        if conn:
            conn.close()

def init_db():
    """Initialize database with tables and triggers for data retention"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Drop existing tables to ensure clean schema
            c.execute('DROP TABLE IF EXISTS metrics')
            c.execute('DROP TABLE IF EXISTS config')
            
            # Create metrics table
            c.execute('''CREATE TABLE metrics
                        (timestamp TEXT, 
                         temp1 REAL, 
                         temp2 REAL, 
                         pressure1 REAL,
                         pressure2 REAL,
                         power REAL,
                         kw_ton REAL,
                         cooling_tons REAL,
                         flow_rate REAL,
                         interval TEXT)''')
            
            # Create config table
            c.execute('''CREATE TABLE config
                        (id INTEGER PRIMARY KEY,
                         flow_coefficient REAL,
                         interval1_seconds INTEGER,
                         interval2_seconds INTEGER,
                         interval3_seconds INTEGER,
                         retention_interval1 INTEGER,
                         retention_interval2 INTEGER,
                         retention_interval3 INTEGER)''')
            
            # Insert default config if not exists
            c.execute('SELECT * FROM config WHERE id = 1')
            if not c.fetchone():
                c.execute('''INSERT INTO config VALUES 
                            (1, 0.5, 60, 900, 3600, 1, 7, 30)''')
                
            # Setup retention triggers and indexes
            setup_retention_triggers(c)
            
            conn.commit()
            app.logger.info('Database initialized successfully')
            
    except Exception as e:
        app.logger.error(f'Database initialization failed: {str(e)}')
        raise

def enforce_retention():
    """Enforces data retention policies by removing old data"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Get retention settings
            c.execute('''SELECT retention_interval1, retention_interval2, retention_interval3 
                        FROM config WHERE id = 1''')
            retention_days = c.fetchone()
            
            if not retention_days:
                raise Exception("Configuration not found")
            
            deleted_counts = {}
            current_time = datetime.now()
            
            # Process each interval
            for interval_num, days in enumerate(retention_days, 1):
                interval_name = f'interval{interval_num}'
                cutoff_date = (current_time - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get count before deletion
                c.execute('''SELECT COUNT(*) FROM metrics 
                            WHERE interval = ? AND timestamp < ?''',
                         (interval_name, cutoff_date))
                count_before = c.fetchone()[0]
                
                # Delete old records
                c.execute('''DELETE FROM metrics 
                            WHERE interval = ? AND timestamp < ?''',
                         (interval_name, cutoff_date))
                
                deleted_counts[interval_name] = count_before
            
            conn.commit()
            
            # Optimize database if needed
            if sum(deleted_counts.values()) > 0:
                c.execute('VACUUM')
                app.logger.info(f'Retention enforcement completed: {deleted_counts}')
            
            return deleted_counts
            
    except Exception as e:
        app.logger.error(f'Retention enforcement failed: {str(e)}')
        return None

def setup_retention_triggers(cursor):
    """Sets up database triggers to maintain data retention policies"""
    try:
        # Create index on timestamp and interval columns
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_metrics_timestamp_interval 
                         ON metrics(timestamp, interval)''')
        
        # Create trigger to enforce retention after config updates
        cursor.execute('''DROP TRIGGER IF EXISTS enforce_retention_on_config_update''')
        cursor.execute('''
            CREATE TRIGGER enforce_retention_on_config_update
            AFTER UPDATE ON config
            FOR EACH ROW
            BEGIN
                -- Remove old interval1 data
                DELETE FROM metrics 
                WHERE interval = 'interval1' 
                AND timestamp < datetime('now', '-' || NEW.retention_interval1 || ' days');
                
                -- Remove old interval2 data
                DELETE FROM metrics 
                WHERE interval = 'interval2' 
                AND timestamp < datetime('now', '-' || NEW.retention_interval2 || ' days');
                
                -- Remove old interval3 data
                DELETE FROM metrics 
                WHERE interval = 'interval3' 
                AND timestamp < datetime('now', '-' || NEW.retention_interval3 || ' days');
            END;
        ''')
        
        # Create index for faster deletions
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_metrics_interval_timestamp
                         ON metrics(interval, timestamp)''')
        
        # Create index for faster querying
        cursor.execute('''CREATE INDEX IF NOT EXISTS idx_metrics_timestamp_desc
                         ON metrics(timestamp DESC)''')
        
    except Exception as e:
        app.logger.error(f'Error setting up retention triggers: {str(e)}')
        raise

class DataAggregator:
    def __init__(self, sampling_rate_seconds):
        self.data_points = defaultdict(list)
        # Initialize with current time floored to nearest interval
        current_time = datetime.now()
        self.last_aggregation = {
            'interval1': self._floor_timestamp(current_time, 60),
            'interval2': self._floor_timestamp(current_time, 900),
            'interval3': self._floor_timestamp(current_time, 3600)
        }
        self.sampling_rate = sampling_rate_seconds
    
    def _floor_timestamp(self, dt, interval_seconds):
        """Floor a datetime to the nearest interval"""
        timestamp = dt.timestamp()
        return datetime.fromtimestamp(timestamp - (timestamp % interval_seconds))
    
    def add_data_point(self, temp1, temp2, pressure1, pressure2, power, flow_coefficient):
        timestamp = datetime.now()
        
        # Calculate metrics
        diff_pressure = abs(pressure1 - pressure2)
        flow_rate = flow_coefficient * (diff_pressure ** 0.5)
        temp_diff = abs(temp1 - temp2)
        cooling_tons = (flow_rate * temp_diff * 8.33 * 60) / 12000
        kw_ton = power / cooling_tons if cooling_tons > 0 else 0
        
        metrics = {
            'timestamp': timestamp,
            'temp1': temp1,
            'temp2': temp2,
            'pressure1': pressure1,
            'pressure2': pressure2,
            'power': power,
            'kw_ton': kw_ton,
            'cooling_tons': cooling_tons,
            'flow_rate': flow_rate
        }
        
        for interval in ['interval1', 'interval2', 'interval3']:
            self.data_points[interval].append(metrics)
    
    def get_aggregated_data(self, interval_name, interval_seconds):
        current_time = datetime.now()
        current_interval_start = self._floor_timestamp(current_time, interval_seconds)
        
        # Only aggregate if we've moved to a new interval
        if current_interval_start <= self.last_aggregation[interval_name]:
            return None
        
        # Get previous interval's start and end times
        prev_interval_start = current_interval_start - timedelta(seconds=interval_seconds)
        
        # Get data points from the previous interval
        interval_points = [
            dp for dp in self.data_points[interval_name]
            if prev_interval_start <= dp['timestamp'] < current_interval_start
        ]
        
        # If we have any points in the interval, aggregate them
        if interval_points:
            avg_data = {
                'temp1': sum(dp['temp1'] for dp in interval_points) / len(interval_points),
                'temp2': sum(dp['temp2'] for dp in interval_points) / len(interval_points),
                'pressure1': sum(dp['pressure1'] for dp in interval_points) / len(interval_points),
                'pressure2': sum(dp['pressure2'] for dp in interval_points) / len(interval_points),
                'power': sum(dp['power'] for dp in interval_points) / len(interval_points),
                'kw_ton': sum(dp['kw_ton'] for dp in interval_points) / len(interval_points),
                'cooling_tons': sum(dp['cooling_tons'] for dp in interval_points) / len(interval_points),
                'flow_rate': sum(dp['flow_rate'] for dp in interval_points) / len(interval_points),
                'timestamp': current_interval_start,
                'num_points': len(interval_points)
            }
            
            # Update last aggregation time
            self.last_aggregation[interval_name] = current_interval_start
            
            # Remove data points older than the current interval
            self.data_points[interval_name] = [
                dp for dp in self.data_points[interval_name]
                if dp['timestamp'] >= prev_interval_start
            ]
            
            print(f"Aggregating {interval_name}: {len(interval_points)} points over {interval_seconds} seconds")
            return avg_data
    
@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        try:
            data = request.json
            conn = sqlite3.connect('metrics.db')
            c = conn.cursor()
            c.execute('''UPDATE config SET 
                         flow_coefficient = ?,
                         interval1_seconds = ?,
                         interval2_seconds = ?,
                         interval3_seconds = ?,
                         retention_interval1 = ?,
                         retention_interval2 = ?,
                         retention_interval3 = ?
                         WHERE id = 1''',
                     (float(data['flow_coefficient']),
                      int(data['interval1_seconds']),
                      int(data['interval2_seconds']),
                      int(data['interval3_seconds']),
                      int(data['retention_interval1']),
                      int(data['retention_interval2']),
                      int(data['retention_interval3'])))
            conn.commit()
            conn.close()
            
            # Explicitly enforce retention after config update
            deleted_counts = enforce_retention()
            if deleted_counts:
                print(f"Config update retention enforcement deleted: {deleted_counts}")
            
            return jsonify({"status": "success", "deleted_counts": deleted_counts})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

def collect_data():
    SAMPLING_RATE = 1  # seconds
    sensor = None
    aggregator = None
    reconnect_delay = 1
    max_reconnect_delay = 30
    last_retention_check = datetime.now()
    RETENTION_CHECK_INTERVAL = timedelta(hours=1)
    last_values = None

    while True:
        try:
            if sensor is None:
                try:
                    sensor = Sensor()
                    aggregator = DataAggregator(SAMPLING_RATE)
                    app.logger.info('Sensor connection established')
                    reconnect_delay = 1
                except Exception as e:
                    app.logger.error(f'Failed to connect to sensor: {str(e)}')
                    time.sleep(min(reconnect_delay, max_reconnect_delay))
                    reconnect_delay *= 2
                    continue

            current_time = datetime.now()
            
            # Check retention period
            if current_time - last_retention_check > RETENTION_CHECK_INTERVAL:
                deleted_counts = enforce_retention()
                if deleted_counts:
                    app.logger.info(f'Retention enforcement deleted: {deleted_counts}')
                last_retention_check = current_time

            # Read sensor data
            sensor_data = sensor.read()
            
            if sensor_data[0] is None:
                time.sleep(0.1)
                continue
            
            if sensor_data != last_values:
                temp1, temp2, pressure1, pressure2 = sensor_data
                power = 100 + random.random()  # TODO: Replace with actual power measurement
                
                with get_db_connection() as conn:
                    c = conn.cursor()
                    
                    # Get configuration
                    c.execute('''SELECT interval1_seconds, interval2_seconds, interval3_seconds,
                               flow_coefficient 
                               FROM config WHERE id = 1''')
                    config = c.fetchone()
                    
                    if not config:
                        raise Exception("Configuration not found")
                    
                    interval1_seconds, interval2_seconds, interval3_seconds, flow_coefficient = config
                    
                    # Process data
                    aggregator.add_data_point(temp1, temp2, pressure1, pressure2, power, flow_coefficient)
                    
                    # Aggregate for each interval
                    intervals = [
                        ('interval1', interval1_seconds),
                        ('interval2', interval2_seconds),
                        ('interval3', interval3_seconds)
                    ]
                    
                    for interval_name, seconds in intervals:
                        avg_data = aggregator.get_aggregated_data(interval_name, seconds)
                        if avg_data:
                            c.execute('''INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?)''',
                                    (avg_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                                     avg_data['temp1'],
                                     avg_data['temp2'],
                                     avg_data['pressure1'],
                                     avg_data['pressure2'],
                                     avg_data['power'],
                                     avg_data['kw_ton'],
                                     avg_data['cooling_tons'],
                                     avg_data['flow_rate'],
                                     interval_name))
                    
                    last_values = sensor_data

        except Exception as e:
            app.logger.error(f'Error in data collection: {str(e)}')
            if sensor:
                try:
                    sensor.close()
                except:
                    pass
                sensor = None
            time.sleep(1)
        
        time.sleep(SAMPLING_RATE)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/data/<interval>')
def get_data(interval):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Get interval settings for display
            c.execute('SELECT interval1_seconds, interval2_seconds, interval3_seconds FROM config WHERE id = 1')
            intervals = c.fetchone()
            
            c.execute('''SELECT timestamp, kw_ton, 
                                ABS(pressure1 - pressure2) as diff_pressure,
                                ABS(temp1 - temp2) as diff_temp,
                                cooling_tons,
                                flow_rate
                        FROM metrics 
                        WHERE interval = ? 
                        ORDER BY timestamp DESC 
                        LIMIT 500''', (interval,))
            
            data = c.fetchall()
            
            if not data:
                return jsonify({
                    'timestamps': [],
                    'kw_ton': [],
                    'diff_pressure': [],
                    'diff_temp': [],
                    'cooling_tons': [],
                    'flow_rate': [],
                    'intervals': intervals
                })
            
            return jsonify({
                'timestamps': [row[0] for row in data],
                'kw_ton': [row[1] for row in data],
                'diff_pressure': [row[2] for row in data],
                'diff_temp': [row[3] for row in data],
                'cooling_tons': [row[4] for row in data],
                'flow_rate': [row[5] for row in data],
                'intervals': intervals
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.errorhandler(404)
def not_found_error(error):
    app.logger.error(f'Page not found: {request.url}')
    return jsonify({"status": "error", "message": "Resource not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Server Error: {str(error)}')
    return jsonify({"status": "error", "message": "Internal server error"}), 500

if __name__ == '__main__':
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        # Initialize database
        init_db()
        
        # Start data collection thread
        data_thread = Thread(target=collect_data, daemon=True)
        data_thread.start()
        app.logger.info('Data collection thread started')
    
    # Production server configuration
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=False,
        threaded=True,
        use_reloader=False
    )