"""Mock data generator"""
import csv
import time
import random
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_live_data(csv_file, t):
    """Generate live data and append to data file"""
    logger.info(f"Starting data generation for {csv_file}")
    while True:
        try:
            with open(csv_file, "a", newline="", encoding="utf8") as file:
                writer = csv.writer(file)
                
                if os.stat(csv_file).st_size == 0:
                    logger.info("Writing header to empty file")
                    writer.writerow([
                        "Timestamp",
                        "Inlet Temperature",
                        "Inlet Pressure",
                        "Outlet Temperature",
                        "Outlet Pressure",
                    ])
                
                new_row = create_row()
                writer.writerow(new_row)
                logger.info(f"Wrote row: {new_row}")
                
                file.flush()
            
            time.sleep(t)
        except Exception as e:
            logger.error(f"Error in generate_live_data: {str(e)}")
            time.sleep(t)

def create_row() -> list[any]:
    """Generate a row of random data"""
    # Format timestamp as YYYY-MM-DD HH:MM:SS
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    inlet_temp = round(20 + 5 * random.random(), 2)
    outlet_temp = round(10 + 5 * random.random(), 2)
    inlet_pressure = round(180 + 10 * random.random(), 2)
    outlet_pressure = round(120 + 10 * random.random(), 2)
    return [timestamp, inlet_temp, inlet_pressure, outlet_temp, outlet_pressure]

if __name__ == "__main__":
    generate_live_data("live_data.csv", 5)