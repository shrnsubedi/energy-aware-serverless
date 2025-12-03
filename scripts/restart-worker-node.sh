#!/bin/bash

set -e  # Exit on any error

echo "Stopping kubelet..."
sudo systemctl stop kubelet

# Stop running containers
echo "Stopping containers..."
for container in $(sudo ctr containers list -q); do
    sudo ctr containers stop "$container"
done

# Kill any remaining Kubernetes processes
echo "Killing Kubernetes processes..."
sudo pkill -f kube || true  # Ignore errors if no processes are found

# Remove old manifest files (not required for workers, but cleaning up any remnants)
echo "Cleaning up Kubernetes manifests..."
sudo rm -f /etc/kubernetes/manifests/kube-apiserver.yaml \
           /etc/kubernetes/manifests/kube-controller-manager.yaml \
           /etc/kubernetes/manifests/kube-scheduler.yaml \
           /etc/kubernetes/manifests/etcd.yaml || true

# Restart containerd and clear network leftovers
echo "Restarting container runtime..."
sudo systemctl restart containerd
sudo ip link delete cni0 || true
sudo ip link delete flannel.1 || true

# Reset Kubernetes node
echo "Resetting Kubernetes node..."
sudo kubeadm reset -f

# Start kubelet
echo "Starting kubelet..."
sudo systemctl start kubelet

echo "Worker node restart completed! Now manually join the cluster using the kubeadm join command from the master node."
