from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
from collections import defaultdict

app = Flask(__name__)

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

class DataAggregator:
    def __init__(self, sampling_rate_seconds):
        self.data_points = defaultdict(list)
        self.last_aggregation = {
            'interval1': datetime.min,
            'interval2': datetime.min,
            'interval3': datetime.min
        }
        self.sampling_rate = sampling_rate_seconds
    
    def add_data_point(self, temp1, temp2, pressure1, pressure2, power, flow_coefficient):
        # Calculate metrics
        diff_pressure = abs(pressure1 - pressure2)
        flow_rate = flow_coefficient * (diff_pressure ** 0.5)
        temp_diff = abs(temp1 - temp2)
        cooling_tons = (flow_rate * temp_diff * 8.33 * 60) / 12000
        kw_ton = power / cooling_tons if cooling_tons > 0 else 0
        
        timestamp = datetime.now()
        
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
        data_points = self.data_points[interval_name]
        
        # Calculate how many points we expect for this interval
        expected_points = interval_seconds / self.sampling_rate
        
        # Remove old data points beyond the interval window
        cutoff_time = current_time - timedelta(seconds=interval_seconds)
        data_points = [dp for dp in data_points if dp['timestamp'] > cutoff_time]
        self.data_points[interval_name] = data_points
        
        # Check if we have enough data points
        if not data_points or len(data_points) < (expected_points * 0.8):  # Allow 20% tolerance
            return None
        
        # Calculate averages
        avg_data = {
            'temp1': sum(dp['temp1'] for dp in data_points) / len(data_points),
            'temp2': sum(dp['temp2'] for dp in data_points) / len(data_points),
            'pressure1': sum(dp['pressure1'] for dp in data_points) / len(data_points),
            'pressure2': sum(dp['pressure2'] for dp in data_points) / len(data_points),
            'power': sum(dp['power'] for dp in data_points) / len(data_points),
            'kw_ton': sum(dp['kw_ton'] for dp in data_points) / len(data_points),
            'cooling_tons': sum(dp['cooling_tons'] for dp in data_points) / len(data_points),
            'flow_rate': sum(dp['flow_rate'] for dp in data_points) / len(data_points),
            'timestamp': current_time,
            'num_points': len(data_points)
        }
        
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

def collect_data():
    # Configure sampling rate (in seconds)
    SAMPLING_RATE = 5  # Change this value to adjust raw sampling rate
    
    aggregator = DataAggregator(SAMPLING_RATE)
    print(f"Starting data collection with {SAMPLING_RATE} second sampling rate")
    
    while True:
        try:
            conn = sqlite3.connect('metrics.db')
            c = conn.cursor()
            
            # Get current configuration
            c.execute('''SELECT interval1_seconds, interval2_seconds, interval3_seconds,
                               retention_interval1, retention_interval2, retention_interval3,
                               flow_coefficient 
                        FROM config WHERE id = 1''')
            config = c.fetchone()
            
            if not config:
                raise Exception("Configuration not found")
                
            interval1_seconds, interval2_seconds, interval3_seconds = config[0:3]
            retention_days = config[3:6]
            flow_coefficient = config[6]
            
            current_time = datetime.now()
            
            # Sample data
            temp1, temp2 = 30, 25  # TODO: Implement temperature sensor reading
            pressure1, pressure2 = 2, 0  # TODO: Implement pressure sensor reading
            power = 3  # TODO: Implement power meter reading
            
            # Add raw data point for aggregation
            aggregator.add_data_point(temp1, temp2, pressure1, pressure2, power, flow_coefficient)
            
            # Check each interval for aggregation
            intervals = [
                ('interval1', interval1_seconds),
                ('interval2', interval2_seconds),
                ('interval3', interval3_seconds)
            ]
            
            for interval_name, seconds in intervals:
                if (current_time - aggregator.last_aggregation[interval_name]).total_seconds() >= seconds:
                    avg_data = aggregator.get_aggregated_data(interval_name, seconds)
                    
                    if avg_data:
                        print(f"Aggregating {interval_name}: {avg_data['num_points']} points over {seconds} seconds")
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
                        aggregator.last_aggregation[interval_name] = current_time
            
            # Clean up old data
            for i, days in enumerate(retention_days, 1):
                c.execute(f"DELETE FROM metrics WHERE interval = 'interval{i}' AND timestamp < datetime('now', '-' || ? || ' days')", 
                         (days,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error in data collection: {str(e)}")
        
        time.sleep(SAMPLING_RATE)

@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/data/<interval>')
def get_data(interval):
    try:
        conn = sqlite3.connect('metrics.db')
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
    init_db()
    data_thread = Thread(target=collect_data, daemon=True)
    data_thread.start()
    app.run(debug=True)