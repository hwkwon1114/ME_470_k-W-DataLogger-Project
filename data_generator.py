"""Mock data generator"""

import csv
import time
import random


def generate_live_data(csv_file, t):
    """Generate live data and append to data file

    Example usage
    -------------
    generate_live_data('live_data.csv', 5)  # Generates data every 5 seconds
    """
    # Open CSV file in append mode
    with open(csv_file, "a", newline="", encoding="utf8") as file:
        writer = csv.writer(file)

        # Write header if file is empty
        file.seek(0)
        if file.read(1) == "":
            writer.writerow(
                [
                    "Timestamp",
                    "Inlet Temperature",
                    "Inlet Pressure",
                    "Outlet Temperature",
                    "Outlet Pressure",
                ]
            )

        while True:
            writer.writerow(create_row())

            # Flush the file to ensure it's written immediately
            file.flush()

            # Wait for t seconds before generating next data row
            time.sleep(t)


def create_row() -> list[any]:
    """Generate a row of random data"""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    inlet_temp = 20 + 5 * random.random()
    outlet_temp = 10 + 5 * random.random()
    inlet_pressure = 180 + 10 * random.random()
    outlet_pressure = 120 + 10 * random.random()


    return [timestamp, inlet_temp, inlet_pressure, outlet_temp, outlet_pressure]
