import os
import requests
import time


class RequestGenerator:
    def __init__(self, url: str):
        self.url: str = url

    def send_request(self, headers=None, data=None, files=None):
        start_time: float = time.time()
        response = requests.post(self.url, headers=headers, data=data, files=files)
        duration = time.time() - start_time
        return response.status_code, duration
