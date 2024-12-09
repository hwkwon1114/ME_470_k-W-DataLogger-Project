from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
from collections import defaultdict
from Sensor import Sensor

#Flask app
app = Flask(__name__)
aggregator = None # DataAggregator object

def init_db(): # Initialize the database
    conn = sqlite3.connect('metrics.db')
    c = conn.cursor()

    # Drop existing tables to ensure clean schema
    c.execute('DROP TABLE IF EXISTS metrics') 
    c.execute('DROP TABLE IF EXISTS config')

    # Create metrics table
    c.execute('''CREATE TABLE metrics
    (timestamp TEXT NOT NULL,
    temp1 REAL NOT NULL,
    temp2 REAL NOT NULL,
    pressure1 REAL NOT NULL,
    pressure2 REAL NOT NULL,
    power REAL NOT NULL,
    kw_ton REAL NOT NULL,
    cooling_tons REAL NOT NULL,
    flow_rate REAL NOT NULL,
    interval TEXT NOT NULL)''')

    c.execute('CREATE INDEX idx_timestamp_interval ON metrics(timestamp, interval)') # Index for faster queries

    c.execute('''CREATE TABLE config
    (id INTEGER PRIMARY KEY,
    flow_coefficient REAL NOT NULL CHECK(flow_coefficient > 0),
    interval1_seconds INTEGER NOT NULL CHECK(interval1_seconds > 0),
    interval2_seconds INTEGER NOT NULL CHECK(interval2_seconds > 0),
    interval3_seconds INTEGER NOT NULL CHECK(interval3_seconds > 0),
    retention_interval1 INTEGER NOT NULL CHECK(retention_interval1 > 0),
    retention_interval2 INTEGER NOT NULL CHECK(retention_interval2 > 0),
    retention_interval3 INTEGER NOT NULL CHECK(retention_interval3 > 0))''') # Configuration table

    c.execute('''INSERT INTO config VALUES
    (1, 0.5, 60, 900, 3600, 1, 7, 30)''') # Default configuration

    conn.commit() 
    conn.close()

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
        self.max_points = self._get_max_points()
    
    # Get the maximum number of data points to store
    def _get_max_points(self):
        with sqlite3.connect('metrics.db') as conn:
            c = conn.cursor()
            c.execute('''SELECT 
                retention_interval1, interval1_seconds,
                retention_interval2, interval2_seconds,
                retention_interval3, interval3_seconds 
                FROM config WHERE id = 1''')
            config = c.fetchone()
            
            if not config:
                return {'interval1': 1000, 'interval2': 1000, 'interval3': 1000}
            
            return {
                'interval1': (config[0] * 24 * 3600) // config[1],
                'interval2': (config[2] * 24 * 3600) // config[3],
                'interval3': (config[4] * 24 * 3600) // config[5]
            }
    # Update the maximum number of data points
    def update_max_points(self):
        self.max_points = self._get_max_points()
    
    # Add a new data point
    def add_data_point(self, temp1, temp2, pressure1, pressure2, power, flow_coefficient):
        timestamp = datetime.now()
        
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
            max_points = self.max_points[interval]
            if len(self.data_points[interval]) > max_points:
                self.data_points[interval] = self.data_points[interval][-max_points:]
    
    # Round down the timestamp to the nearest interval
    def _floor_timestamp(self, dt, interval_seconds):
        timestamp = dt.timestamp()
        return datetime.fromtimestamp(timestamp - (timestamp % interval_seconds))
    
    # Get the aggregated data for a given interval
    def get_aggregated_data(self, interval_name, interval_seconds):
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
                'timestamp': current_interval_start
            }
            
            self.last_aggregation[interval_name] = current_interval_start
            
            self.data_points[interval_name] = [
                dp for dp in self.data_points[interval_name]
                if dp['timestamp'] >= prev_interval_start
            ]
            
            return avg_data
# Configuration page
@app.route('/config', methods=['GET', 'POST'])
def config():
    global aggregator
    # Update the configuration
    if request.method == 'POST':
        try:
            data = request.json # Get the JSON data
            required_fields = [
                'flow_coefficient', 'interval1_seconds', 'interval2_seconds',
                'interval3_seconds', 'retention_interval1', 'retention_interval2',
                'retention_interval3'
            ]
            
            if not all(field in data for field in required_fields):
                return jsonify({"status": "error", "message": "Missing required fields"}), 400
            
            flow_coefficient = float(data['flow_coefficient'])
            interval1_seconds = int(data['interval1_seconds'])
            interval2_seconds = int(data['interval2_seconds'])
            interval3_seconds = int(data['interval3_seconds'])
            retention_interval1 = int(data['retention_interval1'])
            retention_interval2 = int(data['retention_interval2'])
            retention_interval3 = int(data['retention_interval3'])
            
            if flow_coefficient <= 0:
                return jsonify({"status": "error", "message": "Flow coefficient must be positive"}), 400
            if any(x <= 0 for x in [interval1_seconds, interval2_seconds, interval3_seconds]):
                return jsonify({"status": "error", "message": "Intervals must be positive"}), 400
            if any(x <= 0 for x in [retention_interval1, retention_interval2, retention_interval3]):
                return jsonify({"status": "error", "message": "Retention periods must be positive"}), 400
            
            with sqlite3.connect('metrics.db') as conn:
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
                         (flow_coefficient, interval1_seconds, interval2_seconds,
                          interval3_seconds, retention_interval1, retention_interval2,
                          retention_interval3))
                conn.commit()
            
            if aggregator:
                aggregator.update_max_points()
                
            return jsonify({"status": "success"})
            
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    
    # Get the current configuration
    with sqlite3.connect('metrics.db') as conn:
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

def collect_data():
    global aggregator 
    SAMPLING_RATE = 1  # seconds
    sensor = Sensor()
    aggregator = DataAggregator(SAMPLING_RATE)
    
    last_values = None

    while True:
        try:
            sensor_data = sensor.read()
            
            if len(sensor_data) != 5 or None in sensor_data:
                time.sleep(0.1)
                continue
            
            if sensor_data != last_values:
                temp1, temp2, pressure1, pressure2, power = sensor_data
                last_values = sensor_data
                
                with sqlite3.connect('metrics.db') as conn:
                    c = conn.cursor()
                    c.execute('''SELECT interval1_seconds, interval2_seconds, 
                               interval3_seconds, flow_coefficient 
                               FROM config WHERE id = 1''')
                    config = c.fetchone()
                    
                    if not config:
                        raise ValueError("Configuration not found")
                    
                    interval1_seconds, interval2_seconds, interval3_seconds, flow_coefficient = config
                    
                    aggregator.add_data_point(temp1, temp2, pressure1, pressure2, 
                                            power, flow_coefficient)
                    
                    intervals = [
                        ('interval1', interval1_seconds),
                        ('interval2', interval2_seconds),
                        ('interval3', interval3_seconds)
                    ]
                    
                    for interval_name, seconds in intervals:
                        avg_data = aggregator.get_aggregated_data(interval_name, seconds)
                        if avg_data:
                            c.execute('''INSERT INTO metrics VALUES 
                                    (?,?,?,?,?,?,?,?,?,?)''',
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
                            conn.commit()
                
        except Exception:
            try:
                sensor.close()
                time.sleep(1)
                sensor = Sensor()
            except Exception:
                time.sleep(5)
        
        time.sleep(SAMPLING_RATE)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/data/<interval>')
def get_data(interval):
    if interval not in ['interval1', 'interval2', 'interval3']:
        return jsonify({"status": "error", "message": "Invalid interval"}), 400
        
    try:
        with sqlite3.connect('metrics.db') as conn:
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
        return jsonify({"status": "error", "message": str(e)}), 500

def cleanup_old_data():
    while True:
        try:
            with sqlite3.connect('metrics.db') as conn:
                c = conn.cursor()
                
                c.execute('''SELECT retention_interval1, retention_interval2, retention_interval3 
                           FROM config WHERE id = 1''')
                retention_settings = c.fetchone()
                
                if not retention_settings:
                    time.sleep(3600)
                    continue
                
                current_time = datetime.now()
                
                for interval_num, retention_days in enumerate(retention_settings, 1):
                    cutoff_date = current_time - timedelta(days=retention_days)
                    cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
                    
                    c.execute('''DELETE FROM metrics 
                               WHERE interval = ? AND timestamp < ?''', 
                            (f'interval{interval_num}', cutoff_str))
                
                conn.commit()
                
        except Exception:
            pass
        
        time.sleep(3600)

if __name__ == '__main__':
    init_db()
    data_thread = Thread(target=collect_data, daemon=True)
    cleanup_thread = Thread(target=cleanup_old_data, daemon=True)
    
    data_thread.start()
    cleanup_thread.start()
    
    app.run(host='0.0.0.0', port=5001, debug=False)