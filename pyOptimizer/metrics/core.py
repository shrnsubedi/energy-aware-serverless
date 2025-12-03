import os
from collections import defaultdict

from metrics.metrics import MetricsCollector
from metrics.prometheus import PrometheusClient

PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")

timeout = 10  # Timeout for app readiness check


class MetricsCore:
    def __init__(self, config):
        self.config = config
        self.prom = PrometheusClient(PROM_URL)
        self.collector = MetricsCollector(prom=self.prom)

    def _flatten_pod_node_map(self, grouped_map):
        flat_map = {}
        for service, nodes in grouped_map.items():
            for node, pods in nodes.items():
                for pod in pods:
                    flat_map[pod] = node
        return flat_map

    def _aggregate_metrics_by_node(self, metrics_by_pod, pod_node_map):
        node_metrics = defaultdict(lambda: {"latency": [], "bandwidth": []})
        pod_node_map = self._flatten_pod_node_map(pod_node_map)

        for pod, node in pod_node_map.items():
            if pod in metrics_by_pod.get("latency", {}):
                node_metrics[node]["latency"].append(metrics_by_pod["latency"][pod])
            if pod in metrics_by_pod.get("bandwidth", {}):
                node_metrics[node]["bandwidth"].append(metrics_by_pod["bandwidth"][pod])

        final = {}
        for node, values in node_metrics.items():
            final[node] = {
                "latency": (
                    sum(values["latency"]) / len(values["latency"])
                    if values["latency"]
                    else 0
                ),
                "bandwidth": (
                    sum(values["bandwidth"]) / len(values["bandwidth"])
                    if values["bandwidth"]
                    else 0
                ),
            }
        return final

    # ========== Network Metrics

    def collect_latency_metrics(self, service_name):
        latency_metrics = self.collector._get_workload_request_duration(
            destination_workload=service_name,
        )

        return latency_metrics

    def collect_traffic_metrics(self, source_workload, destination_workload):
        """
        Returns traffic edge metrics for (source->destination):
        - req_rate: requests per second (float)
        - bytes_per_req: total bytes per request (request+response), float
        """
        # req/s per source pod -> sum to get edge rate
        rps_by_pod = self.collector._get_request_per_sec(
            source_workload, destination_workload
        )
        req_rate = sum(rps_by_pod.values()) if rps_by_pod else 0.0

        req_b = (
            self.collector._get_request_size(source_workload, destination_workload)
            or 0.0
        )
        resp_b = (
            self.collector._get_response_size(source_workload, destination_workload)
            or 0.0
        )
        bytes_per_req = req_b + resp_b

        return {"req_rate": req_rate, "bytes_per_req": bytes_per_req}

    def collect_power_metrics(self, placement_map, ip_mapping=None):
        """
        Collect power metrics for the given placement map.
        """
        raw_metrics = self.collector.get_power_metrics(placement_map, ip_mapping)
        return raw_metrics

    # ========== Power Metrics

    def collect_pod_utilization_metrics(self, pod_name: str) -> dict:
        cpu_util = self.collector._get_pod_cpu_util(pod_name)
        mem_util = self.collector._get_pod_memory_util(pod_name)
        return {
            "cpu_util": cpu_util or 0.0,
            "memory_mib": mem_util or 0.0,
        }

    def collect_dashboard_power_metrics(self, placement_map, ip_mapping=None):
        """
        Collect power metrics for the given placement map.
        """
        raw_metrics = self.collector.get_power_metrics_dashboard(
            placement_map, ip_mapping
        )
        return raw_metrics
