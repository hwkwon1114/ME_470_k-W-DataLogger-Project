class Config:
    # Flask configuration
    SECRET_KEY = 'your-secret-key-here'  # Change this in production
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'sqlite:///instance/sensor_data.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Data collection settings
    COLLECTION_INTERVAL = 300  # 5 minutes in seconds
    AGGREGATION_INTERVAL = 900  # 15 minutes in seconds
    
    # Retention periods
    RAW_DATA_RETENTION = 1  # days
    FIFTEEN_MIN_RETENTION = 3  # days
    
    # Sensor calculation constants
    BTU_PER_TON = 12000
    SPECIFIC_HEAT = 1.0  # BTU/lb°F
    DENSITY = 8.34  # lb/gallon
    FLOW_RATE = 100  # GPM