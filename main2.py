import multiprocessing
from flask import Flask, render_template, jsonify
from app.models import db, RawData, Data15Min, DataHourly
import time
from datetime import datetime, timedelta
import logging
import signal
import sys
from sqlalchemy import func
import os
import csv
import random
import traceback
from collections import defaultdict

# Configure logging to both file and console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('application.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Ensure instance folder exists
instance_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance')
if not os.path.exists(instance_path):
    os.makedirs(instance_path)
    logger.info(f"Created instance directory at {instance_path}")

# Flask application setup
app = Flask(__name__,
           template_folder='app/templates',  # Add this line
           static_folder='app/static')       # Add this line
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(instance_path, "sensor_data.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Data file configuration
CSV_FILE = 'live_data.csv'

def calculate_tons(temp_differential):
    """Calculate cooling tons based on temperature differential"""
    BTU_PER_TON = 12000
    SPECIFIC_HEAT = 1.0  # BTU/lb°F
    DENSITY = 8.34  # lb/gallon
    FLOW_RATE = 100  # Assume 100 GPM flow rate
    
    tons = (temp_differential * SPECIFIC_HEAT * DENSITY * FLOW_RATE * 60) / BTU_PER_TON
    return max(0, tons)

def generate_test_data(stop_event):
    """Generate mock sensor data"""
    logger.info(f"Starting data generation for {CSV_FILE}")
    
    try:
        with open(CSV_FILE, "w", newline="", encoding="utf8") as file:
            writer = csv.writer(file)
            writer.writerow([
                "Timestamp",
                "Inlet Temperature",
                "Inlet Pressure",
                "Outlet Temperature",
                "Outlet Pressure",
            ])
    except Exception as e:
        logger.error(f"Error creating CSV file: {str(e)}")
        return

    while not stop_event.is_set():
        try:
            with open(CSV_FILE, "a", newline="", encoding="utf8") as file:
                writer = csv.writer(file)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                inlet_temp = round(20 + 5 * random.random(), 2)
                outlet_temp = round(10 + 5 * random.random(), 2)
                inlet_pressure = round(180 + 10 * random.random(), 2)
                outlet_pressure = round(120 + 10 * random.random(), 2)
                
                new_row = [timestamp, inlet_temp, inlet_pressure, outlet_temp, outlet_pressure]
                writer.writerow(new_row)
                logger.info(f"Generated data: {new_row}")
                
                file.flush()
            
            time.sleep(5)  # Generate data every 5 seconds for testing
            
        except Exception as e:
            logger.error(f"Error in generate_test_data: {str(e)}")
            time.sleep(60)

def calculate_averages(data_points):
    """Calculate averages from a list of data points"""
    if not data_points:
        return None
        
    avg_kw = sum(d['kw'] for d in data_points) / len(data_points)
    avg_pressure = sum(d['pressure_diff'] for d in data_points) / len(data_points)
    avg_temp = sum(d['temp_diff'] for d in data_points) / len(data_points)
    avg_kwt = sum(d['kw_per_ton'] for d in data_points) / len(data_points)
    
    return {
        'kw': avg_kw,
        'pressure_differential': avg_pressure,
        'temperature_differential': avg_temp,
        'kw_per_ton': avg_kwt
    }

def data_collector(stop_event):
    """Process for collecting data from CSV file"""
    logger.info("Starting data collector process")
    last_processed_size = 0
    current_5min_data = []
    last_save_time = None
    
    while not stop_event.is_set():
        try:
            if os.path.exists(CSV_FILE):
                current_size = os.path.getsize(CSV_FILE)
                
                if current_size > last_processed_size:
                    with open(CSV_FILE, 'r') as f:
                        f.seek(last_processed_size)
                        csv_reader = csv.reader(f)
                        
                        for row in csv_reader:
                            if len(row) == 5 and row[0] != "Timestamp":  # Skip header
                                try:
                                    timestamp = row[0]
                                    inlet_temp = float(row[1])
                                    inlet_pressure = float(row[2])
                                    outlet_temp = float(row[3])
                                    outlet_pressure = float(row[4])
                                    
                                    temp_diff = inlet_temp - outlet_temp
                                    pressure_diff = inlet_pressure - outlet_pressure
                                    tons = calculate_tons(temp_diff)
                                    simulated_kw = temp_diff * 1.5
                                    kw_per_ton = simulated_kw / tons if tons > 0 else 0
                                    
                                    current_5min_data.append({
                                        'kw': simulated_kw,
                                        'pressure_diff': pressure_diff,
                                        'temp_diff': temp_diff,
                                        'kw_per_ton': kw_per_ton
                                    })
                                    
                                except Exception as e:
                                    logger.error(f"Error processing row {row}: {str(e)}")
                                    continue
                    
                    last_processed_size = current_size

                # Check if it's time to save 5-minute average
                current_time = datetime.utcnow()
                if last_save_time is None:
                    last_save_time = current_time
                
                time_diff = (current_time - last_save_time).total_seconds()
                if time_diff >= 300:  # 5 minutes = 300 seconds
                    if current_5min_data:
                        averages = calculate_averages(current_5min_data)
                        
                        with app.app_context():
                            new_reading = RawData(
                                timestamp=current_time,
                                kw=averages['kw'],
                                pressure_differential=averages['pressure_differential'],
                                temperature_differential=averages['temperature_differential'],
                                kw_per_ton=averages['kw_per_ton']
                            )
                            db.session.add(new_reading)
                            db.session.commit()
                            logger.info(f'5-minute averages saved: kW={averages["kw"]:.2f}, kW/Ton={averages["kw_per_ton"]:.3f}')
                        
                        # Reset for next 5-minute period
                        current_5min_data = []
                        last_save_time = current_time
            
            time.sleep(5)  # Check for new data every 5 seconds
                    
        except Exception as e:
            logger.error(f'Data collector error: {str(e)}')
            time.sleep(5)

def data_aggregator(stop_event):
    """Process for aggregating data"""
    logger.info("Starting data aggregator process")
    
    while not stop_event.is_set():
        try:
            with app.app_context():
                # Aggregate to 15-min intervals for data older than 1 day
                day_ago = datetime.utcnow() - timedelta(days=1)
                latest_15min = db.session.query(func.max(Data15Min.timestamp)).scalar()
                
                if latest_15min is None:
                    latest_15min = day_ago - timedelta(days=1)
                
                # Get raw data for 15-minute aggregation
                raw_data = RawData.query.filter(
                    RawData.timestamp <= day_ago,
                    RawData.timestamp > latest_15min
                ).all()
                
                # Group by 15-minute intervals
                fifteen_min_groups = defaultdict(list)
                for reading in raw_data:
                    interval = reading.timestamp.replace(
                        minute=(reading.timestamp.minute // 15) * 15,
                        second=0,
                        microsecond=0
                    )
                    fifteen_min_groups[interval].append(reading)
                
                # Create 15-minute aggregations
                for interval, readings in fifteen_min_groups.items():
                    kw_values = [r.kw for r in readings]
                    pressure_values = [r.pressure_differential for r in readings]
                    temp_values = [r.temperature_differential for r in readings]
                    kwt_values = [r.kw_per_ton for r in readings]
                    
                    new_15min = Data15Min(
                        timestamp=interval,
                        kw_avg=sum(kw_values) / len(kw_values),
                        kw_min=min(kw_values),
                        kw_max=max(kw_values),
                        pressure_differential_avg=sum(pressure_values) / len(pressure_values),
                        temperature_differential_avg=sum(temp_values) / len(temp_values),
                        kw_per_ton_avg=sum(kwt_values) / len(kwt_values)
                    )
                    db.session.add(new_15min)
                
                # Delete aggregated raw data
                if raw_data:
                    RawData.query.filter(RawData.timestamp <= day_ago).delete()
                
                # Aggregate to hourly intervals for data older than 3 days
                three_days_ago = datetime.utcnow() - timedelta(days=3)
                latest_hourly = db.session.query(func.max(DataHourly.timestamp)).scalar()
                
                if latest_hourly is None:
                    latest_hourly = three_days_ago - timedelta(days=1)
                
                # Get 15-minute data for hourly aggregation
                data_15min = Data15Min.query.filter(
                    Data15Min.timestamp <= three_days_ago,
                    Data15Min.timestamp > latest_hourly
                ).all()
                
                # Group by hour
                hourly_groups = defaultdict(list)
                for reading in data_15min:
                    interval = reading.timestamp.replace(minute=0, second=0, microsecond=0)
                    hourly_groups[interval].append(reading)
                
                # Create hourly aggregations
                for interval, readings in hourly_groups.items():
                    kw_values = [r.kw_avg for r in readings]
                    pressure_values = [r.pressure_differential_avg for r in readings]
                    temp_values = [r.temperature_differential_avg for r in readings]
                    kwt_values = [r.kw_per_ton_avg for r in readings]
                    
                    new_hourly = DataHourly(
                        timestamp=interval,
                        kw_avg=sum(kw_values) / len(kw_values),
                        kw_min=min(r.kw_min for r in readings),
                        kw_max=max(r.kw_max for r in readings),
                        pressure_differential_avg=sum(pressure_values) / len(pressure_values),
                        temperature_differential_avg=sum(temp_values) / len(temp_values),
                        kw_per_ton_avg=sum(kwt_values) / len(kwt_values)
                    )
                    db.session.add(new_hourly)
                
                # Delete aggregated 15-minute data
                if data_15min:
                    Data15Min.query.filter(Data15Min.timestamp <= three_days_ago).delete()
                
                db.session.commit()
                logger.info('Data aggregation completed')
            
            time.sleep(900)  # Run aggregation every 15 minutes
            
        except Exception as e:
            logger.error(f'Data aggregator error: {str(e)}')
            time.sleep(60)

@app.route('/')
def index():
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Error in index route: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}", 500

@app.route('/api/data')
def get_data():
    try:
        with app.app_context():
            recent_data = RawData.query.filter(
                RawData.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).order_by(RawData.timestamp.desc()).all()
            
            return jsonify({
                'success': True,
                'data': [reading.to_dict() for reading in recent_data]
            })
    except Exception as e:
        logger.error(f"Error in get_data route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/data/15min')
def get_data_15min():
    try:
        with app.app_context():
            data = Data15Min.query.filter(
                Data15Min.timestamp >= datetime.utcnow() - timedelta(days=1)
            ).order_by(Data15Min.timestamp.desc()).all()
            
            if not data:  # If no 15-min data, fall back to raw data
                data = RawData.query.filter(
                    RawData.timestamp >= datetime.utcnow() - timedelta(days=1)
                ).order_by(RawData.timestamp.desc()).all()
                
                return jsonify({
                    'success': True,
                    'data': [reading.to_dict() for reading in data]
                })
            
            return jsonify({
                'success': True,
                'data': [
                    {
                        'timestamp': reading.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'kw': reading.kw_avg,
                        'pressure_differential': reading.pressure_differential_avg,
                        'temperature_differential': reading.temperature_differential_avg,
                        'kw_per_ton': reading.kw_per_ton_avg
                    }
                    for reading in data
                ]
            })
    except Exception as e:
        logger.error(f"Error in get_data_15min route: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/data/hourly')
def get_data_hourly():
    try:
        with app.app_context():
            data = DataHourly.query.filter(
                DataHourly.timestamp >= datetime.utcnow() - timedelta(days=7)
            ).order_by(DataHourly.timestamp.desc()).all()
            
            if not data:  # If no hourly data, fall back to 15-min data
                data = Data15Min.query.filter(
                    Data15Min.timestamp >= datetime.utcnow() - timedelta(days=7)
                ).order_by(Data15Min.timestamp.desc()).all()
                
                return jsonify({
                    'success': True,
                    'data': [
                        {
                            'timestamp': reading.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'kw': reading.kw_avg,
                            'pressure_differential': reading.pressure_differential_avg,
                            'temperature_differential': reading.temperature_differential_avg,
                            'kw_per_ton': reading.kw_per_ton_avg
                        }
                        for reading in data
                    ]
                })
            
            return jsonify({
                'success': True,
                'data': [
                    {
                        'timestamp': reading.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        'kw': reading.kw_avg,
                        'pressure_differential': reading.pressure_differential_avg,
                        'temperature_differential': reading.temperature_differential_avg,
                        'kw_per_ton': reading.kw_per_ton_avg
                    }
                    for reading in data
                ]
            })
    except Exception as e:
        logger.error(f"Error in get_data_hourly route: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    stop_event.set()

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating database tables: {str(e)}")
            logger.error(traceback.format_exc())
            sys.exit(1)
    
    # Create a stop event for graceful shutdown
    stop_event = multiprocessing.Event()
    
    # Initialize process variables
    processes = []
    
    try:
        # Start data generator process
        generator_process = multiprocessing.Process(
            target=generate_test_data,
            args=(stop_event,)
        )
        generator_process.start()
        processes.append(generator_process)
        logger.info("Started data generator process")
        
        # Start data collector process
        collector_process = multiprocessing.Process(
            target=data_collector,
            args=(stop_event,)
        )
        collector_process.start()
        processes.append(collector_process)
        logger.info("Started data collector process")
        
        # Start data aggregator process
        aggregator_process = multiprocessing.Process(
            target=data_aggregator,
            args=(stop_event,)
        )
        aggregator_process.start()
        processes.append(aggregator_process)
        logger.info("Started data aggregator process")
        
        def shutdown_server():
            stop_event.set()
            for process in processes:
                process.join(timeout=5)  # Wait up to 5 seconds for each process
                if process.is_alive():
                    process.terminate()  # Force terminate if still running
            
            # Clean up the CSV file
            try:
                if os.path.exists(CSV_FILE):
                    os.remove(CSV_FILE)
                    logger.info(f"Removed {CSV_FILE}")
            except Exception as e:
                logger.error(f"Error removing CSV file: {str(e)}")
            
            logger.info("Application shutdown complete")
            sys.exit(0)

        # Set up signal handlers
        signal.signal(signal.SIGINT, lambda x, y: shutdown_server())
        signal.signal(signal.SIGTERM, lambda x, y: shutdown_server())
        
        # Start Flask application without debug mode
        logger.info("Starting Flask application")
        app.run(host='0.0.0.0', port=5001, debug=False)
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
        logger.error(traceback.format_exc())
    finally:
        shutdown_server()