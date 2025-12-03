import requests
from requests import Response


class PrometheusClient:
    def __init__(self, url: str):
        self.url: str = url

    def query(self, query):
        try:
            resp: Response = requests.get(
                f"{self.url}/api/v1/query", params={"query": query}
            )
            data = resp.json()
            if data["status"] != "success":
                print("Error in response:", data["error"])
                return None
            return data["data"]["result"]
        except Exception as e:
            raise Exception(f"Exception in Querying Prometheus: {e}")
