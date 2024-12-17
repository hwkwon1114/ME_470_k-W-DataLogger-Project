import serial
from typing import Optional, Tuple
from serial.tools import list_ports
import time

class Sensor:
    def __init__(self, port: str = "/dev/ttyACM0", baudrate: int = 9600):
        """Initialize sensor matching Arduino's baud rate"""
        self.serial = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=0.1,  # Short timeout for responsiveness
            write_timeout=0,  # Non-blocking writes
            parity=serial.PARITY_NONE,
            bytesize=serial.EIGHTBITS,
            xonxoff=False,  # Disable software flow control
            rtscts=False    # Disable hardware flow control
        )
        time.sleep(2)  # Allow Arduino to reset
        self.serial.reset_input_buffer()
        self.serial.reset_output_buffer()

    def read(self) -> Tuple[Optional[float], ...]:
        """Efficient reading of sensor values"""
        try:
            if self.serial.in_waiting:
                line = self.serial.readline().decode('ascii').strip()
                if line:
                    return tuple(map(float, line.split(',')))
        except (ValueError, UnicodeDecodeError) as e:
            self.serial.reset_input_buffer()
        except serial.SerialException as e:
            self.serial.reset_input_buffer()
            print(f"Serial error: {e}")
        return (None,) * 5

    def close(self) -> None:
        """Clean up serial connection"""
        if hasattr(self, 'serial') and self.serial.is_open:
            self.serial.close()

    @staticmethod
    def find_arduino_port() -> Optional[str]:
        """Auto-detect Arduino port"""
        for port in list_ports.comports():
            if 'Arduino' in port.description or 'ACM' in port.device:
                return port.device
        return None