from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
from collections import defaultdict
import random
import serial
import os
import logging
from logging.handlers import RotatingFileHandler
from contextlib import contextmanager

app = Flask(__name__)
app.debug = False

# Configure logging
if not os.path.exists('logs'):
    os.mkdir('logs')

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
    """Initialize database with tables and default config"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            c.execute('DROP TABLE IF EXISTS metrics')
            c.execute('DROP TABLE IF EXISTS config')
            
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
            
            c.execute('''CREATE TABLE config
                        (id INTEGER PRIMARY KEY,
                         flow_coefficient REAL,
                         interval1_seconds INTEGER,
                         interval2_seconds INTEGER,
                         interval3_seconds INTEGER,
                         retention_interval1 INTEGER,
                         retention_interval2 INTEGER,
                         retention_interval3 INTEGER)''')
            
            c.execute('SELECT * FROM config WHERE id = 1')
            if not c.fetchone():
                c.execute('''INSERT INTO config VALUES 
                            (1, 0.5, 60, 900, 3600, 1, 7, 30)''')
            
            conn.commit()
            app.logger.info('Database initialized successfully')
    except Exception as e:
        app.logger.error(f'Database initialization failed: {str(e)}')
        raise

class Sensor:
    def __init__(self, port="/dev/ttyACM0", baudrate=9600):
        """Initialize serial connection to Arduino"""
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        
    def read(self):
        """Read temperature and pressure values from Arduino"""
        try:
            if self.serial.in_waiting:
                line = self.serial.readline().decode("utf-8").strip()
                if line:
                    try:
                        temp1, temp2, pressure1, pressure2 = map(float, line.split(","))
                        return temp1, temp2, pressure1, pressure2
                    except ValueError:
                        return None, None, None, None
            return None, None, None, None
        except Exception as e:
            raise serial.SerialException(f"Error reading from Arduino: {str(e)}")

    def close(self):
        """Close serial connection"""
        if self.serial and self.serial.is_open:
            self.serial.close()

class DataAggregator:
    def __init__(self, sampling_rate_seconds):
        self.data_points = defaultdict(list)
        current_time = datetime.now()
        self.last_aggregation = {
            'interval1': self._floor_timestamp(current_time, 60),
            'interval2': self._floor_timestamp(current_time, 900),
            'interval3': self._floor_timestamp(current_time, 3600)
        }
        self.sampling_rate = sampling_rate_seconds
        
    def _floor_timestamp(self, dt, interval_seconds):
        timestamp = dt.timestamp()
        return datetime.fromtimestamp(timestamp - (timestamp % interval_seconds))
    
    def add_data_point(self, temp1, temp2, pressure1, pressure2, power, flow_coefficient):
        timestamp = datetime.now()
        
        try:
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
        except Exception as e:
            app.logger.error(f'Error calculating metrics: {str(e)}')
            raise

    def get_aggregated_data(self, interval_name, interval_seconds):
        try:
            current_time = datetime.now()
            current_interval_start = self._floor_timestamp(current_time, interval_seconds)
            
            if current_interval_start <= self.last_aggregation[interval_name]:
                return None
            
            prev_interval_start = current_interval_start - timedelta(seconds=interval_seconds)
            
            interval_points = [
                dp for dp in self.data_points[interval_name]
                if prev_interval_start <= dp['timestamp'] < current_interval_start
            ]
            
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
                
                self.last_aggregation[interval_name] = current_interval_start
                self.data_points[interval_name] = [
                    dp for dp in self.data_points[interval_name]
                    if dp['timestamp'] >= prev_interval_start
                ]
                
                return avg_data
            return None
        except Exception as e:
            app.logger.error(f'Error in data aggregation: {str(e)}')
            raise

def cleanup_old_data():
    """Removes old data based on retention settings"""
    while True:
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT retention_interval1, retention_interval2, retention_interval3 FROM config WHERE id = 1')
                retentions = c.fetchone()
                
                if retentions:
                    for interval, days in zip(['interval1', 'interval2', 'interval3'], retentions):
                        cutoff = datetime.now() - timedelta(days=days)
                        c.execute('DELETE FROM metrics WHERE interval = ? AND timestamp < ?',
                                (interval, cutoff.strftime('%Y-%m-%d %H:%M:%S')))
                    conn.commit()
                    app.logger.info('Old data cleanup completed')
        except Exception as e:
            app.logger.error(f'Error in data cleanup: {str(e)}')
        time.sleep(3600)  # Run cleanup every hour

def collect_data():
    SAMPLING_RATE = 0.1
    sensor = None
    aggregator = None
    reconnect_delay = 1
    max_reconnect_delay = 30
    last_values = None
    
    while True:
        try:
            if sensor is None:
                try:
                    sensor = Sensor()
                    aggregator = DataAggregator(SAMPLING_RATE)
                    app.logger.info('Arduino connection established')
                    reconnect_delay = 1
                except serial.SerialException as e:
                    app.logger.error(f'Failed to connect to Arduino: {str(e)}')
                    time.sleep(min(reconnect_delay, max_reconnect_delay))
                    reconnect_delay *= 2
                    continue

            sensor_data = sensor.read()
            
            if sensor_data[0] is None:
                time.sleep(0.1)
                continue
            
            if sensor_data != last_values:
                temp1, temp2, pressure1, pressure2 = sensor_data
                power = 100 + random.random()
                
                with get_db_connection() as conn:
                    c = conn.cursor()
                    c.execute('''SELECT interval1_seconds, interval2_seconds, interval3_seconds,
                               flow_coefficient 
                               FROM config WHERE id = 1''')
                    config = c.fetchone()
                    
                    if not config:
                        raise Exception("Configuration not found")
                    
                    interval1_seconds, interval2_seconds, interval3_seconds, flow_coefficient = config
                    aggregator.add_data_point(temp1, temp2, pressure1, pressure2, power, flow_coefficient)
                    
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
                
        except serial.SerialException as e:
            app.logger.error(f'Serial communication error: {str(e)}')
            if sensor:
                try:
                    sensor.close()
                except:
                    pass
                sensor = None
            time.sleep(min(reconnect_delay, max_reconnect_delay))
            reconnect_delay *= 2
            
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

@app.route('/config', methods=['GET', 'POST'])
def config():
    if request.method == 'POST':
        try:
            data = request.json
            with get_db_connection() as conn:
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
            return jsonify({"status": "success"})
        except Exception as e:
            app.logger.error(f'Configuration update failed: {str(e)}')
            return jsonify({"status": "error", "message": str(e)}), 400
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM config WHERE id = 1')
            config_data = c.fetchone()
            
            if config_data is None:
                return jsonify({"status": "error", "message": "Configuration not found"}), 404
                
            return render_template('config.html', 
                                 flow_coefficient=config_data[1],
                                 interval1_seconds=config_data[2],
                                 interval2_seconds=config_data[3],
                                 interval3_seconds=config_data[4],
                                 retention_interval1=config_data[5],
                                 retention_interval2=config_data[6],
                                 retention_interval3=config_data[7])
    except Exception as e:
        app.logger.error(f'Configuration retrieval failed: {str(e)}')
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/data/<interval>')
def get_data(interval):
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
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
        app.logger.error(f'Data retrieval failed: {str(e)}')
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/health')
def health_check():
    """Basic health check endpoint for monitoring"""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT 1')
            return jsonify({
                'status': 'ok',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
    except Exception as e:
        app.logger.error(f'Health check failed: {str(e)}')
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500

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
        
        # Start cleanup thread
        cleanup_thread = Thread(target=cleanup_old_data, daemon=True)
        cleanup_thread.start()
        app.logger.info('Cleanup thread started')
    
    # Production server configuration
    app.run(
        host='0.0.0.0',     # Listen on all network interfaces
        port=5001,          # Port number
        debug=False,        # Disable debug mode
        threaded=True,      # Enable threading
        use_reloader=False  # Disable reloader in production
    )