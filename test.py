import time
from datetime import datetime
import statistics
from Sensor import Sensor
import threading
import queue
import sys

class SensorDiagnostics:
    def __init__(self, sample_size=100):
        self.sample_size = sample_size
        self.read_times = []
        self.data_queue = queue.Queue()
        self.is_running = True
        self.sensor = None
        
    def measure_read_time(self):
        """Measure single read operation time"""
        try:
            self.sensor = Sensor()
            start_time = time.perf_counter()
            result = self.sensor.read()
            end_time = time.perf_counter()
            self.sensor.close()
            return end_time - start_time, result
        except Exception as e:
            print(f"Error in read time measurement: {e}")
            if self.sensor:
                self.sensor.close()
            return None, None

    def continuous_monitoring(self):
        """Monitor sensor data continuously"""
        try:
            self.sensor = Sensor()
            last_successful_read = time.time()
            missed_readings = 0
            
            print("\nStarting continuous monitoring (Press Ctrl+C to stop)...")
            print("Timestamp               | Temp1  | Temp2  | Press1 | Press2 | Gap(ms)")
            print("-" * 75)
            
            while self.is_running:
                current_time = time.time()
                data = self.sensor.read()
                
                if any(x is not None for x in data):
                    time_gap = (current_time - last_successful_read) * 1000  # Convert to ms
                    self.data_queue.put((datetime.now(), data, time_gap))
                    last_successful_read = current_time
                else:
                    missed_readings += 1
                
                time.sleep(0.001)  # Tiny sleep to prevent CPU overload
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"\nError in monitoring: {e}")
        finally:
            if self.sensor:
                self.sensor.close()
            self.is_running = False

    def display_results(self):
        """Display results from continuous monitoring"""
        try:
            while self.is_running or not self.data_queue.empty():
                try:
                    timestamp, data, gap = self.data_queue.get_nowait()
                    temp1, temp2, pressure1, pressure2 = data
                    print(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
                          f"{temp1:6.2f} | {temp2:6.2f} | "
                          f"{pressure1:6.2f} | {pressure2:6.2f} | "
                          f"{gap:6.1f}")
                except queue.Empty:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            pass

    def run_diagnostics(self):
        """Run comprehensive diagnostics"""
        print("Starting Sensor Diagnostics...")
        print("\n1. Testing individual read times...")
        
        # Test individual read times
        read_times = []
        valid_readings = 0
        for i in range(self.sample_size):
            read_time, data = self.measure_read_time()
            if read_time is not None:
                read_times.append(read_time * 1000)  # Convert to milliseconds
                if any(x is not None for x in data):
                    valid_readings += 1
            time.sleep(0.1)  # Small delay between tests
            
        if read_times:
            print(f"\nRead Time Statistics (ms):")
            print(f"Min: {min(read_times):.2f}")
            print(f"Max: {max(read_times):.2f}")
            print(f"Average: {statistics.mean(read_times):.2f}")
            print(f"Median: {statistics.median(read_times):.2f}")
            print(f"Standard Deviation: {statistics.stdev(read_times):.2f}")
            print(f"Valid Readings: {valid_readings}/{self.sample_size}")
        
        print("\n2. Starting continuous monitoring...")
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.continuous_monitoring)
        monitor_thread.start()
        
        # Start display thread
        display_thread = threading.Thread(target=self.display_results)
        display_thread.start()
        
        try:
            monitor_thread.join()
            display_thread.join()
        except KeyboardInterrupt:
            self.is_running = False
            print("\nDiagnostics stopped by user")

if __name__ == "__main__":
    diagnostics = SensorDiagnostics(sample_size=100)
    diagnostics.run_diagnostics()