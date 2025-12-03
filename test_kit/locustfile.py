from locust import HttpUser, task, between
import os
import time

# Shared config
INFERENCE_HOST = "s1-inference.default.example.com"
FLOOD_HOST = "s4-sensorflood.default.example.com"
AUDIO_HOST = "s5-audioprocessor.default.example.com"

IMAGE_PATH = "assets/img.webp"
CSV_PATH = "assets/sensors.csv"
AUDIO_PATH = "assets/sound.wav"


class InferenceUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def send_inference(self):
        try:
            with open(IMAGE_PATH, "rb") as f:
                start = time.time()
                r = self.client.post(
                    "/infer",
                    files={"file": f},
                    headers={"Host": INFERENCE_HOST},
                    name="S1 Inference",
                )
                duration = time.time() - start
                print(f"S1 Inference: {r.status_code} in {duration:.2f}s")
        except Exception as e:
            print(f"S1 Error: {e}")


class SensorFloodUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def send_sensor_data(self):
        try:
            if not os.path.exists(CSV_PATH):
                print(f"File not found: {CSV_PATH}")
                return

            with open(CSV_PATH, "rb") as f:
                start = time.time()
                r = self.client.post(
                    "/upload?batch_size=5000",
                    files={"file": ("sensors.csv", f, "text/csv")},
                    headers={"Host": FLOOD_HOST},
                    timeout=30,
                    name="S4 Flood",
                )
                duration = time.time() - start
                print(f"S4 Flood: {r.status_code} in {duration:.2f}s")
        except Exception as e:
            print(f"S4 Error: {e}")


class AudioProcessorUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def send_audio(self):
        try:
            with open(AUDIO_PATH, "rb") as f:
                start = time.time()
                r = self.client.post(
                    "/audio",
                    files={"file": f},
                    headers={"Host": AUDIO_HOST},
                    name="S5 Audio",
                )
                duration = time.time() - start
                print(f"S5 Audio: {r.status_code} in {duration:.2f}s")
        except Exception as e:
            print(f"S5 Error: {e}")
