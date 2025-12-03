import time
from kubernetes import client, config


class KubernetesManager:
    def __init__(self, namespace="default", config_file=None):
        config.load_kube_config(config_file=config_file)
        self.namespace = namespace
        self.apps = client.AppsV1Api()
        self.core = client.CoreV1Api()

    def get_running_node(self, app_name):
        pods = self.core.list_namespaced_pod(
            namespace=self.namespace, label_selector=f"app={app_name}"
        ).items
        if not pods:
            return None
        return pods[0].spec.node_name

    def get_nodes(self):
        """
        Returns a list of all nodes in the Kubernetes cluster.
        """
        nodes = self.core.list_node().items
        return [node.metadata.name for node in nodes]

    def get_internal_ip_mapping(self):
        nodes = self.core.list_node()
        internal_ips = {}
        for node in nodes.items:
            node_name = node.metadata.name
            for addr in node.status.addresses:
                if addr.type == "InternalIP":
                    internal_ips[node_name] = addr.address
        return internal_ips

    def get_pod_mapping(self, services: list[str]):
        service_pods = {}
        for service in services:
            all_pods = self.core.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"serving.knative.dev/service={service}",
            ).items

            if not all_pods:
                all_pods = self.core.list_namespaced_pod(
                    namespace=self.namespace, label_selector=f"app={service}"
                ).items

            if not all_pods:
                continue

            pods = [pod for pod in all_pods if pod.status.phase == "Running"]

            if service not in service_pods:
                service_pods[service] = {}

            for pod in pods:
                node_name = pod.spec.node_name
                pod_name = pod.metadata.name

                if node_name not in service_pods[service]:
                    service_pods[service][node_name] = []

                service_pods[service][node_name].append(pod_name)
        return service_pods

    def patch_node_affinity(self, deployment_name, namespace, target_node):
        """
        Patch the nodeAffinity of a deployment to place pods on the given node.

        Args:
            deployment_name (str): Name of the deployment to patch
            namespace (str): Namespace where the deployment exists
            target_node (str): The node to place the pod on
        """

        # Define affinity patch
        affinity_patch = {
            "spec": {
                "template": {
                    "spec": {
                        "affinity": {
                            "nodeAffinity": {
                                "requiredDuringSchedulingIgnoredDuringExecution": {
                                    "nodeSelectorTerms": [
                                        {
                                            "matchExpressions": [
                                                {
                                                    "key": "kubernetes.io/hostname",
                                                    "operator": "In",
                                                    "values": [target_node],
                                                }
                                            ]
                                        }
                                    ]
                                }
                            }
                        }
                    }
                }
            }
        }

        # Apply the patch
        response = self.apps.patch_namespaced_deployment(
            name=deployment_name, namespace=namespace, body=affinity_patch
        )

        print(f"Patched deployment '{deployment_name}' to prefer node '{target_node}'")
        return response
