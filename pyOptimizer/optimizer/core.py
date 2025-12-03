class HeuristicScheduler:
    def __init__(self, placement_map, nodes, config):
        self.placement_map = placement_map
        self.nodes = nodes
        self.config = config

    # ---------- helpers ----------
    def _node_has_pods(self, node: str) -> bool:
        # true if any service has at least one pod on this node
        return any(
            node in node_pods and node_pods[node]
            for node_pods in self.placement_map.values()
        )

    # ---------- power (Watts) ----------
    def _compute_power(self, node: str, service: str) -> float:
        """Incremental power (W): pod dynamic + activation if node idle."""
        kappa = float(self.config.get("kappa_cpu", 4.5344))  # W per node-fraction
        ncores = float(self.config.get("n_cores", 4.0))
        P_idle = float(self.config.get("P_idle", 2.2857))

        pod_util = float(self.config.get("pod_utilization", {}).get("cpu_util") or 0.0)
        pod_frac = pod_util / ncores
        P_s = kappa * pod_frac
        return P_s if self._node_has_pods(node) else (P_s + P_idle)

    def _get_colocation_ratio(self, dep_service: str, candidate_node: str) -> float:
        dep_nodes = self.placement_map.get(dep_service, {})
        total = sum(len(pods) for pods in dep_nodes.values())
        return 0.0 if total == 0 else len(dep_nodes.get(candidate_node, [])) / total

    # ---------- latency (seconds) ----------
    def _get_effective_latency(self, service: str, node: str) -> float:
        """
        L(node) = base_per-node_latency  +  sum_deps [ req_rate * (1 - coloc_ratio) * delta_L ]
        All seconds (base from Prom ms converted to s).
        """
        base_ms = self.config.get("node_latency", {}).get(node)
        base_s = float(base_ms) / 1000.0 if base_ms is not None else 0.0

        assoc = self.config.get("association_graph", {})  # {(src,dst): meta}
        edges = self.config.get("edge_metrics", {})  # {(src,dst): {"req_rate": rps}}

        total = base_s
        for (src, dst), meta in assoc.items():
            if src != service:
                continue

            lam = float(edges.get((src, dst), {}).get("req_rate", 0.0))  # req/s
            rho = self._get_colocation_ratio(dst, node)  # 0..1

            if "delta_latency_s" in meta:
                delta_L = float(meta["delta_latency_s"])
            else:
                remote_s = float(
                    meta.get("remote_latency_s", meta.get("remote_latency", 10.0))
                )
                coloc_s = float(
                    meta.get("colocated_latency_s", meta.get("colocated_latency", 1.5))
                )
                delta_L = max(0.0, remote_s - coloc_s)

            total += lam * (1.0 - rho) * delta_L

        return total

    # ---------- scoring ----------
    def get_cost_components(self, service: str):
        node_scores, latency_vals, power_vals = {}, [], []
        for node in self.nodes:
            L = self._get_effective_latency(service, node)  # seconds
            P = self._compute_power(node, service)  # Watts
            node_scores[node] = {"latency": L, "power": P}
            latency_vals.append(L)
            power_vals.append(P)
        return node_scores, latency_vals, power_vals

    @staticmethod
    def _normalize(val, vmin, vmax):
        if vmax <= vmin:
            return 0.0
        x = (val - vmin) / (vmax - vmin)
        return 0.0 if x < 0 else 1.0 if x > 1 else x

    def place(self, service: str):
        node_scores, Ls, Ps = self.get_cost_components(service)
        if not node_scores:
            return None, float("inf")

        lmin, lmax = min(Ls), max(Ls)
        pmin, pmax = min(Ps), max(Ps)

        lw = float(self.config.get("latency_weight", 0.7))
        pw = float(self.config.get("power_weight", 0.3))

        best_node, best_score = None, float("inf")
        for node, raw in node_scores.items():
            l_hat = self._normalize(raw["latency"], lmin, lmax)
            p_hat = self._normalize(raw["power"], pmin, pmax)
            score = lw * l_hat + pw * p_hat
            if score < best_score:
                best_node, best_score = node, score
        return best_node, best_score
