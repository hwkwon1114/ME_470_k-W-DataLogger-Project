import pandas as pd
import time
from Sensor import Sensor

idx = 0
sensor = Sensor()

pressures_1 = []
pressures_2 = []
temps_1 = []
temps_2 = []
timestamps = []

while idx < 60:
    temp1, temp2, p1, p2 = sensor.read()
    pressures_1.append(p1)
    pressures_2.append(p2)
    temps_1.append(temp1)
    temps_2.append(temp2)
    timestamps.append(pd.Timestamp.now())
    time.sleep(1)
    idx += 1

pd.DataFrame.from_dict({
    "Timestamps": timestamps,
    "Temperature 1": temps_1,
    "Temperature 2": temps_2,
    "Pressure 1": pressures_1,
    "Pressure 2": pressures_2,
}).to_csv(f"Measurement_data_{timestamps[-1]}.csv")

