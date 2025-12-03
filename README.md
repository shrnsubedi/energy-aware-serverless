# edge-energy

The collection of tools, plugins, and utilities for "Energy-Aware Latency Optimization for Scheduling Serverless Workload in Edge Computing Environment"

**Contents**
- **`descheduler/`** — Contains installation YAML for descheduler.
- **`pyOptimizer/`** — Application code for the Heuristic Service module. The `/metrics` subdirectory contains the Metrics Collector module and `/optimizer` contains the Scoring Engine.
- **`frameworkPlugins/`** — The custom plugin code used for the Kubernetes Scheduling Framework. It needs to be recompiled by placing the plugins under the `/pkg/` in the framework code.
- **`scripts/`** — Scripts to install node-exporter, and restart master and worker nodes.
- **`test kit/`** — Locust load-testing scripts and assets used to perform the experiments.
- **`workload/`** — Serverless workloads described in the work including Dockerfiles and Knative YAMLs for deployment on the Raspberry Pi cluster.