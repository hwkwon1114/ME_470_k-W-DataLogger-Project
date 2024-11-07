import serial
import time

class Sensor:
    def __init__(self, port='/dev/ttyUSB0', baudrate=9600):
        self.serial = serial.Serial(port, baudrate, timeout=1)
        time.sleep(2)  # Wait for Arduino to reset
        
    def read(self):
        """Read temperature and pressure values from the sensor"""
        try:
            if self.serial.in_waiting:
                line = self.serial.readline().decode('utf-8').strip()
                # Expecting: temp1,temp2,pressure1,pressure2
                temp1, temp2, pressure1, pressure2 = map(float, line.split(','))
                return temp1, temp2, pressure1, pressure2
            return None, None, None, None
            
        except Exception as e:
            print(f"Error reading sensors: {str(e)}")
            return None, None, None, None
    
    def close(self):
        self.serial.close()