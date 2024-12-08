import serial
import time

class Sensor:
    def __init__(self, port="/dev/ttyACM0", baudrate=9600):
        self.serial = serial.Serial(port, baudrate, timeout=0)  # Non-blocking mode

    def read(self):
        """Read temperature, pressure, and power values from the sensor"""
        try:
            line = self.serial.readline().decode("utf-8").strip()
            if line:
                # Parse five values: temp1, temp2, pressure1, pressure2, power
                temp1, temp2, pressure1, pressure2, power = map(float, line.split(","))
                return temp1, temp2, pressure1, pressure2, power
        except ValueError:
            print("Error: Invalid sensor data")
        except Exception as e:
            print(f"Error reading sensors: {str(e)}")
        return None, None, None, None, None

    def close(self):
        self.serial.close()

def test_sensor() -> None:
    sensor = Sensor(port="/dev/ttyACM0", baudrate=9600)
    while True:
        temp1, temp2, p1, p2, power = sensor.read()
        print(f"{temp1=}, {temp2=}, {p1=}, {p2=}, {power=}")
        time.sleep(1)

if __name__ == "__main__":
    test_sensor()