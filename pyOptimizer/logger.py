import os
import time
import datetime

from config import config as application_config
from metrics.core import MetricsCore
from metrics.k8s import KubernetesManager
from metrics.logger import ExperimentLogger

SERVICE_NAME = os.getenv("SERVICE_NAME", "autocar")
KUBE_CONFIG = os.getenv("KUBE_CONFIG", "~/.kube/config")
LOG_INTERVAL = 5  # seconds
LOG_DURATION = int(os.getenv("LOG_DURATION", 180))  # seconds

config = application_config.get(SERVICE_NAME)
metrics_core = MetricsCore(config=config)
k8s_manager = KubernetesManager(config_file=KUBE_CONFIG)
logger = ExperimentLogger()


def get_node_power_snapshot(placement_map, ip_mapping):
    power = metrics_core.collect_dashboard_power_metrics(placement_map, ip_mapping)
    timestamp = datetime.datetime.now().isoformat()
    node_power_rows = []
    active_nodes = set()
    for node_dict in placement_map.values():
        active_nodes.update(node_dict.keys())

    # Build power row per node
    for row in power["node_metrics"]:
        node = row["node"]
        if node in active_nodes:
            node_power_rows.append(
                {
                    "timestamp": timestamp,
                    "scope": "node",
                    "name": node,
                    "cpu_util": row["cpu_util"],
                    "power": row["power"],
                    "memory_util": row.get("memory_util", 0.0),
                }
            )
        else:
            node_power_rows.append(
                {
                    "timestamp": timestamp,
                    "scope": "node",
                    "name": node,
                    "cpu_util": 0.0,
                    "power": 0.0,
                    "memory_util": 0.0,
                }
            )

    return node_power_rows


def compute_inter_node_traffic(placement_map):
    assoc_graph = config["association_graph"]
    total_traffic = 0
    for (src, dst), meta in assoc_graph.items():
        src_nodes = placement_map.get(src, {})
        dst_nodes = placement_map.get(dst, {})
        for src_node in src_nodes:
            for dst_node in dst_nodes:
                if src_node != dst_node:
                    total_traffic += meta.get("traffic_cost", 0.0)
                    break
    return total_traffic


# Logging loop
end_time = time.time() + LOG_DURATION
while time.time() < end_time:
    placement_map = k8s_manager.get_pod_mapping(services=config["workloads"])
    ip_mapping = k8s_manager.get_internal_ip_mapping()

    node_power_rows = get_node_power_snapshot(placement_map, ip_mapping)
    inter_node_traffic = compute_inter_node_traffic(placement_map)

    meta_row = {
        "timestamp": datetime.datetime.now().isoformat(),
        "scope": "meta",
        "internode_traffic": inter_node_traffic,
    }

    logger.log(node_power_rows, filename="13_energy_log.csv")
    # logger.log([meta_row], filename="meta_log.csv")
    # time.sleep(LOG_INTERVAL)
