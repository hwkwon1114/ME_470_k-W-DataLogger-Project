from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class RawData(db.Model):
    """5-minute interval raw sensor data"""
    __tablename__ = 'raw_data'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    kw = db.Column(db.Float, nullable=False)
    pressure_differential = db.Column(db.Float, nullable=False)
    temperature_differential = db.Column(db.Float, nullable=False)
    kw_per_ton = db.Column(db.Float, nullable=False)

    def to_dict(self):
        return {
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'kw': round(self.kw, 2),
            'pressure_differential': round(self.pressure_differential, 2),
            'temperature_differential': round(self.temperature_differential, 2),
            'kw_per_ton': round(self.kw_per_ton, 3)
        }

class Data15Min(db.Model):
    """15-minute aggregated data"""
    __tablename__ = 'data_15min'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    kw_avg = db.Column(db.Float, nullable=False)
    kw_min = db.Column(db.Float, nullable=False)
    kw_max = db.Column(db.Float, nullable=False)
    pressure_differential_avg = db.Column(db.Float, nullable=False)
    temperature_differential_avg = db.Column(db.Float, nullable=False)
    kw_per_ton_avg = db.Column(db.Float, nullable=False)

class DataHourly(db.Model):
    """Hourly aggregated data"""
    __tablename__ = 'data_hourly'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    kw_avg = db.Column(db.Float, nullable=False)
    kw_min = db.Column(db.Float, nullable=False)
    kw_max = db.Column(db.Float, nullable=False)
    pressure_differential_avg = db.Column(db.Float, nullable=False)
    temperature_differential_avg = db.Column(db.Float, nullable=False)
    kw_per_ton_avg = db.Column(db.Float, nullable=False)