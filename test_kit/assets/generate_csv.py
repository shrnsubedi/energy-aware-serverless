import csv
import random
from datetime import datetime, timedelta

with open("sensors.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "temperature", "humidity", "pressure", "device_id"])

    base_time = datetime.utcnow()

    for i in range(10000):
        ts = (base_time + timedelta(seconds=i * 5)).isoformat() + "Z"
        temp = round(random.uniform(20.0, 25.0), 1)
        humid = round(random.uniform(40.0, 50.0), 1)
        pressure = round(random.uniform(1010.0, 1020.0), 1)
        device = "node-" + str(random.randint(1, 3))
        writer.writerow([ts, temp, humid, pressure, device])
