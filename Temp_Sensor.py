import serial
import time
from datetime import datetime

class TemperatureSensor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        
    def read_temperatures(self):
        try:
            if self.serial.in_waiting:
                line = self.serial.readline().decode('utf-8').strip()
                temp1, temp2 = map(float, line.split(','))
                return temp1, temp2
            return None, None
            
        except Exception as e:
            print(f"Error reading temperature: {str(e)}")
            return None, None
    
    def log_temperatures(self, filename="temperature_log.csv"):
        temp1, temp2 = self.read_temperatures()
        if temp1 is not None and temp2 is not None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"Temperature 1: {temp1:.2f}°C")
            print(f"Temperature 2: {temp2:.2f}°C")
            
            # Log to CSV file
            with open(filename, 'a') as f:
                f.write(f"{timestamp},{temp1:.2f},{temp2:.2f}\n")
    
    def close(self):
        self.serial.close()

def main():
    # Create CSV file with headers if it doesn't exist
    filename = "temperature_log.csv"
    try:
        with open(filename, 'x') as f:
            f.write("Timestamp,Temperature1,Temperature2\n")
    except FileExistsError:
        pass

    print("Initializing temperature sensor...")
    sensor = TemperatureSensor()  # Adjust port if needed
    
    print("Starting temperature logging...")
    try:
        while True:
            sensor.log_temperatures(filename)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nStopping temperature logging...")
        sensor.close()

if __name__ == "__main__":
    main()
