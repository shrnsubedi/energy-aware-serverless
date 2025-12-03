import math
import re
import networkx as nx
from metrics.queries import (
    REQUEST_PER_SEC_QUERY,
    BYTES_PER_SEC_QUERY,
    LATENCY_QUERY,
    POD_POWER,
    NODE_POWER,
    POD_MEMORY,
    NODE_MEMORY,
    REQUEST_TOTAL,
    REQUEST_SIZE_QUERY,
    RESPONSE_SIZE_QUERY,
)
from metrics.prometheus import PrometheusClient
from dotenv import load_dotenv

load_dotenv()


class MetricsCollector:
    def __init__(self, prom: PrometheusClient):
        self.prom = prom

    # =========== Network

    def _get_workload_request_duration(self, destination_workload):
        result = self.prom.query(LATENCY_QUERY.format(destination=destination_workload))
        node_latencies = {}
        for entry in result:
            node = entry["metric"].get("node")
            try:
                value = float(entry["value"][1])
                if not math.isnan(value):
                    node_latencies[node] = value
            except (ValueError, TypeError):
                continue

        return node_latencies

    def _get_request_size(self, source_workload, destination_workload):
        result = self.prom.query(
            REQUEST_SIZE_QUERY.format(
                source=source_workload, destination=destination_workload
            )
        )
        for entry in result:
            try:
                value = float(entry["value"][1])
                if not math.isnan(value):
                    return value
            except (ValueError, TypeError):
                continue

    def _get_response_size(self, source_workload, destination_workload):
        result = self.prom.query(
            RESPONSE_SIZE_QUERY.format(
                source=source_workload, destination=destination_workload
            )
        )
        for entry in result:
            try:
                value = float(entry["value"][1])
                if not math.isnan(value):
                    return value
            except (ValueError, TypeError):
                continue
        return None

    def get_request_response_sizes(self, source_workload, destination_workload):
        request_size = self._get_request_size(source_workload, destination_workload)
        response_size = self._get_response_size(source_workload, destination_workload)
        try:
            sum = request_size + response_size
            return sum
        except Exception as e:
            print(f"Error calculating request/response size: {e}")
            return None

    def _clean_name(self, workload: str) -> str:
        """
        Converts workload names to a cleaner format by removing the deployment suffix.
        """
        match = re.match(r"(.*)-\d{5}-deployment", workload)
        if match:
            return match.group(1)
        return workload

    def _build_communication_graph(self, workloads):
        G = nx.DiGraph()
        result = self.prom.query(REQUEST_TOTAL)

        # Add all workloads as nodes first (ensures standalone services are included)
        for workload in workloads:
            G.add_node(workload)

        for metric in result:
            src = self._clean_name(metric["metric"].get("source_workload", ""))
            dst = self._clean_name(metric["metric"].get("destination_workload", ""))
            value = float(metric["value"][1])

            if src in workloads and dst in workloads:
                G.add_edge(src, dst, weight=value)

        return G

    def _get_request_bandwidth(self, source_workload, destination_workload):
        result = self.prom.query(
            BYTES_PER_SEC_QUERY.format(
                source=source_workload, destination=destination_workload
            )
        )
        bandwidths = {}
        for entry in result:
            pod = entry["metric"].get("source_pod") or entry["metric"].get("pod")
            try:
                value = float(entry["value"][1])
                if not math.isnan(value):
                    bandwidths[pod] = value
            except (ValueError, TypeError):
                continue
        return bandwidths

    def _get_request_per_sec(self, source_workload, destination_workload):
        result = self.prom.query(
            REQUEST_PER_SEC_QUERY.format(
                source=source_workload, destination=destination_workload
            )
        )
        rps = {}
        for entry in result:
            pod = entry["metric"].get("source_pod") or entry["metric"].get("pod")
            try:
                value = float(entry["value"][1])
                if not math.isnan(value):
                    rps[pod] = value
            except (ValueError, TypeError):
                continue
        return rps

    def _get_per_request_bandwidth(self, source_workload, destination_workload):
        bandwidths = self._get_request_bandwidth(source_workload, destination_workload)
        rps = self._get_request_per_sec(source_workload, destination_workload)

        bpr = {}
        for pod, bps in bandwidths.items():
            requests = rps.get(pod)
            if requests and requests > 0:
                bpr[pod] = (bps / 1024) / requests  # in KB/request
            else:
                bpr[pod] = 0
        return bpr

    # =========== Power

    def _get_node_cpu_util(self, node_name: str) -> float | None:
        """
        Get total normalized CPU utilization (0.0 – 1.0) for a node using Prometheus.
        Assumes 4 cores per node for normalization.
        """
        CORES_PER_NODE = 4.0
        query = NODE_POWER.format(instance_ip=node_name)
        result = self.prom.query(query)
        try:
            if result:
                value = float(result[0]["value"][1])
                if not math.isnan(value):
                    return value / CORES_PER_NODE
        except (ValueError, TypeError, IndexError):
            return None
        return None

    def _get_pod_cpu_util(self, pod_name: str) -> float | None:
        """Query Prometheus for the pod's CPU utilization"""
        result = self.prom.query(POD_POWER.format(app=pod_name))
        for entry in result:
            pod = entry["metric"].get("pod")
            if pod != pod_name:
                continue
            try:
                cpu_util = float(entry["value"][1])
                if not math.isnan(cpu_util):
                    return cpu_util
            except (ValueError, TypeError):
                continue
        return None

    def _get_pod_memory_util(self, pod_name: str) -> float | None:
        """Returns pod memory usage in MiB (approx)."""
        result = self.prom.query(POD_MEMORY.format(app=pod_name))
        for entry in result:
            pod = entry["metric"].get("pod")
            if pod != pod_name:
                continue
            try:
                mem_bytes = float(entry["value"][1])
                return round(mem_bytes / (1024 * 1024), 2)  # Convert to MiB
            except (ValueError, TypeError):
                continue
        return None

    def _get_node_memory_util(self, node_ip: str) -> float | None:
        """Returns normalized memory usage (0.0 – 1.0) for a node."""
        result = self.prom.query(NODE_MEMORY.format(instance_ip=node_ip))
        try:
            if result:
                value = float(result[0]["value"][1])
                if not math.isnan(value):
                    return round(value, 4)
        except (ValueError, TypeError, IndexError):
            return None
        return None

    # =========== Metrics Collection

    def get_power_metrics(self, placement_map: dict, ip_mapping: dict = None) -> dict:
        """
        Returns power-related metrics per node: normalized CPU and power.
        Suitable for scheduler cost computation.
        """
        node_power = {}

        for node, ip in ip_mapping.items():
            cpu_util = self._get_node_cpu_util(ip)
            if cpu_util is None:
                continue
            power = 4.5344 * cpu_util + 2.2857
            node_power[node] = {
                "cpu_util": round(cpu_util, 6),
                "power": round(power, 6),
            }

        return node_power

    # =========== Dashboard Metrics

    def get_power_metrics_dashboard(
        self, placement_map: dict, ip_mapping: dict
    ) -> dict:
        CORES_PER_NODE = 4.0
        pod_metrics = []
        node_metrics = []

        for service, node_dict in placement_map.items():
            for node, pods in node_dict.items():
                for pod in pods:
                    cpu = self._get_pod_cpu_util(pod)
                    mem = self._get_pod_memory_util(pod)
                    if cpu is not None:
                        normalized_cpu = cpu / CORES_PER_NODE
                        power = 4.5344 * normalized_cpu
                        pod_metrics.append(
                            {
                                "pod": pod,
                                "node": node,
                                "cpu_util": round(normalized_cpu, 6),
                                "power": round(power, 6),
                                "memory_mib": mem or 0.0,
                            }
                        )

        for node, ip in ip_mapping.items():
            cpu_util = self._get_node_cpu_util(ip)
            mem_util = self._get_node_memory_util(ip)
            if cpu_util is not None:
                power = 4.5344 * cpu_util + 2.2857
                node_metrics.append(
                    {
                        "node": node,
                        "cpu_util": round(cpu_util, 6),
                        "power": round(power, 6),
                        "memory_util": mem_util or 0.0,  # as fraction
                    }
                )

        return {
            "pod_metrics": pod_metrics,
            "node_metrics": node_metrics,
        }
