from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import time
from threading import Thread
import json

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
    last_collection = {
        'interval1': datetime.min,
        'interval2': datetime.min,
        'interval3': datetime.min
    }
    
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
            
            # Sample data (replace with actual sensor readings)
            temp1, temp2 = 30, 25
            pressure1, pressure2 = 2, 0
            power = 3
            
            # Calculate metrics
            diff_pressure = abs(pressure1 - pressure2)
            flow_rate = flow_coefficient * (diff_pressure ** 0.5)
            temp_diff = abs(temp1 - temp2)
            cooling_tons = (flow_rate * temp_diff * 8.33 * 60) / 12000
            kw_ton = power / cooling_tons if cooling_tons > 0 else 0
            
            # Insert data for each interval if enough time has passed
            timestamp_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
            data_tuple = (timestamp_str, temp1, temp2, pressure1, pressure2, 
                         power, kw_ton, cooling_tons, flow_rate)
            
            if (current_time - last_collection['interval1']).total_seconds() >= interval1_seconds:
                c.execute('''INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,'interval1')''', data_tuple)
                last_collection['interval1'] = current_time
                
            if (current_time - last_collection['interval2']).total_seconds() >= interval2_seconds:
                c.execute('''INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,'interval2')''', data_tuple)
                last_collection['interval2'] = current_time
                
            if (current_time - last_collection['interval3']).total_seconds() >= interval3_seconds:
                c.execute('''INSERT INTO metrics VALUES (?,?,?,?,?,?,?,?,?,'interval3')''', data_tuple)
                last_collection['interval3'] = current_time
            
            # Clean up old data based on retention settings
            for i, days in enumerate(retention_days, 1):
                c.execute(f"DELETE FROM metrics WHERE interval = 'interval{i}' AND timestamp < datetime('now', '-' || ? || ' days')", 
                         (days,))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error in data collection: {str(e)}")
        
        time.sleep(1)  # Check every second

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