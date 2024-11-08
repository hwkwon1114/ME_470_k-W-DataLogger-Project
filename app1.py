from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
from collections import defaultdict
import random
import os
import math

app = Flask(__name__)
# Set to production mode
app.debug = False

def init_db():
    conn = sqlite3.connect('metrics.db')
    c = conn.cursor()
    
    # Drop existing tables to ensure clean schema
    c.execute('DROP TABLE IF EXISTS metrics')
    c.execute('DROP TABLE IF EXISTS config')
    
    # Create metrics table with correct number of columns
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
    
    # Updated config table with interval settings
    c.execute('''CREATE TABLE config
                 (id INTEGER PRIMARY KEY,
                  flow_coefficient REAL,
                  interval1_seconds INTEGER,
                  interval2_seconds INTEGER,
                  interval3_seconds INTEGER,
                  retention_interval1 INTEGER,
                  retention_interval2 INTEGER,
                  retention_interval3 INTEGER)''')
    
    # Insert default config with new interval settings
    c.execute('SELECT * FROM config WHERE id = 1')
    if not c.fetchone():
        c.execute('''INSERT INTO config VALUES 
                     (1, 0.5, 60, 900, 3600, 1, 7, 30)''')  # 60s=1min, 900s=15min, 3600s=1hour
    
    conn.commit()
    conn.close()

class DummyDataGenerator:
    def __init__(self):
        self.time = 0
        self.base_temp1 = 12.0  # Cold water temperature
        self.base_temp2 = 7.0   # Chilled water temperature
        self.base_pressure1 = 30.0  # Input pressure
        self.base_pressure2 = 25.0  # Output pressure
        self.base_power = 100.0     # Base power consumption
        
    def read(self):
        self.time += 0.1
        temp1 = self.base_temp1 + math.sin(self.time * 0.1) + random.uniform(-0.2, 0.2)
        temp2 = self.base_temp2 + math.sin(self.time * 0.1) + random.uniform(-0.2, 0.2)
        pressure1 = self.base_pressure1 + math.sin(self.time * 0.05) * 2 + random.uniform(-0.5, 0.5)
        pressure2 = self.base_pressure2 + math.sin(self.time * 0.05) * 2 + random.uniform(-0.5, 0.5)
        return temp1, temp2, pressure1, pressure2

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

def collect_data():
    SAMPLING_RATE = 0.1
    dummy_sensor = DummyDataGenerator()
    aggregator = DataAggregator(SAMPLING_RATE)
    last_values = None
    
    while True:
        try:
            sensor_data = dummy_sensor.read()
            
            if sensor_data != last_values:
                temp1, temp2, pressure1, pressure2 = sensor_data
                power = 100 + random.uniform(-5, 5)
                
                last_values = sensor_data
                
                conn = sqlite3.connect('metrics.db')
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
                
                conn.commit()
                conn.close()
            
        except Exception as e:
            pass
        
        time.sleep(SAMPLING_RATE)

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
            return jsonify({"status": "success"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400
    
    try:
        conn = sqlite3.connect('metrics.db')
        c = conn.cursor()
        c.execute('SELECT * FROM config WHERE id = 1')
        config_data = c.fetchone()
        conn.close()
        
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
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/data/<interval>')
def get_data(interval):
    try:
        conn = sqlite3.connect('metrics.db')
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
        conn.close()
        
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

if __name__ == '__main__':
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        init_db()
        data_thread = Thread(target=collect_data, daemon=True)
        data_thread.start()
    
    app.run(host='0.0.0.0', port=5001, debug=False)