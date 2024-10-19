import multiprocessing
import multiprocessing
from flask import Flask, render_template, jsonify
from app.models import db, RawData, Data15Min, DataHourly  # Fixed import path
import serial
import time
from datetime import datetime, timedelta
import logging
import signal
import sys
from sqlalchemy import func
import os


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='application.log'
)
logger = logging.getLogger(__name__)

# Flask application setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sensor_data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Arduino configuration
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600

def calculate_kw_per_ton(kw, temperature_differential):
    """Calculate kW/Ton metric"""
    try:
        if temperature_differential <= 0:
            return 0
        
        BTU_PER_TON = 12000
        SPECIFIC_HEAT = 1.0
        DENSITY = 8.34
        
        tons = (temperature_differential * SPECIFIC_HEAT * DENSITY) / BTU_PER_TON
        kw_per_ton = kw / tons if tons > 0 else 0
        
        return round(kw_per_ton, 3)
    except Exception as e:
        logger.error(f"Error calculating kW/Ton: {str(e)}")
        return 0

def data_collector(stop_event):
    """Process for collecting data from Arduino"""
    logger.info("Starting data collector process")
    
    while not stop_event.is_set():
        try:
            with serial.Serial(SERIAL_PORT, BAUD_RATE) as ser:
                while not stop_event.is_set():
                    data = ser.readline().decode('utf-8').strip().split(',')
                    
                    if len(data) == 5:
                        kw = float(data[0])
                        inlet_pressure = float(data[1])
                        outlet_pressure = float(data[2])
                        inlet_temp = float(data[3])
                        outlet_temp = float(data[4])
                        
                        pressure_diff = inlet_pressure - outlet_pressure
                        temp_diff = inlet_temp - outlet_temp
                        kw_per_ton = calculate_kw_per_ton(kw, temp_diff)
                        
                        with app.app_context():
                            new_reading = RawData(
                                timestamp=datetime.utcnow(),
                                kw=kw,
                                pressure_differential=pressure_diff,
                                temperature_differential=temp_diff,
                                kw_per_ton=kw_per_ton
                            )
                            db.session.add(new_reading)
                            db.session.commit()
                            logger.info(f'Data saved: kW={kw}, kW/Ton={kw_per_ton}')
                    
                    time.sleep(300)  # 5 minutes
                    
        except Exception as e:
            logger.error(f'Data collector error: {str(e)}')
            time.sleep(60)
            
def data_aggregator(stop_event):
    """Process for aggregating data"""
    logger.info("Starting data aggregator process")
    
    while not stop_event.is_set():
        try:
            with app.app_context():
                # Aggregate to 15-min intervals
                aggregate_to_15min()
                # Aggregate to hourly intervals
                aggregate_to_hourly()
            
            # Sleep for 15 minutes
            for _ in range(15):
                if stop_event.is_set():
                    break
                time.sleep(60)
                
        except Exception as e:
            logger.error(f'Data aggregator error: {str(e)}')
            time.sleep(60)

def aggregate_to_15min():
    """Aggregate raw data to 15-minute intervals"""
    cutoff_time = datetime.utcnow() - timedelta(days=1)
    latest_15min = db.session.query(func.max(Data15Min.timestamp)).scalar()
    
    if latest_15min is None:
        latest_15min = cutoff_time - timedelta(days=7)
    
    # Aggregation query and logic here (same as before)
    # ... (previous aggregation code)

def aggregate_to_hourly():
    """Aggregate 15-minute data to hourly intervals"""
    cutoff_time = datetime.utcnow() - timedelta(days=3)
    latest_hourly = db.session.query(func.max(DataHourly.timestamp)).scalar()
    
    if latest_hourly is None:
        latest_hourly = cutoff_time - timedelta(days=7)
    
    # Aggregation query and logic here (same as before)
    # ... (previous aggregation code)

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/data')
def get_data():
    try:
        # Get recent data (last 24 hours) from raw data
        recent_data = RawData.query.filter(
            RawData.timestamp >= datetime.utcnow() - timedelta(days=1)
        ).order_by(RawData.timestamp.desc()).all()
        
        # Get 15-min data (1-3 days old)
        data_15min = Data15Min.query.filter(
            Data15Min.timestamp >= datetime.utcnow() - timedelta(days=3),
            Data15Min.timestamp < datetime.utcnow() - timedelta(days=1)
        ).order_by(Data15Min.timestamp.desc()).all()
        
        # Get hourly data (older than 3 days)
        data_hourly = DataHourly.query.filter(
            DataHourly.timestamp < datetime.utcnow() - timedelta(days=3)
        ).order_by(DataHourly.timestamp.desc()).all()
        
        return jsonify({
            'success': True,
            'data': {
                'recent': [d.to_dict() for d in recent_data],
                'daily': [d.to_dict() for d in data_15min],
                'hourly': [d.to_dict() for d in data_hourly]
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info("Shutdown signal received")
    stop_event.set()

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    # Create a stop event for graceful shutdown
    stop_event = multiprocessing.Event()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start data collector process
        collector_process = multiprocessing.Process(
            target=data_collector,
            args=(stop_event,)
        )
        collector_process.start()
        
        # Start data aggregator process
        aggregator_process = multiprocessing.Process(
            target=data_aggregator,
            args=(stop_event,)
        )
        aggregator_process.start()
        
        # Start Flask application
        logger.info("Starting Flask application")
        app.run(host='0.0.0.0', port=5001)
        
    except Exception as e:
        logger.error(f"Error in main process: {str(e)}")
    finally:
        # Signal all processes to stop
        stop_event.set()
        
        # Wait for processes to finish
        collector_process.join()
        aggregator_process.join()
        
        logger.info("Application shutdown complete")
