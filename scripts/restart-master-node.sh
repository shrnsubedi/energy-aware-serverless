#!/bin/bash

set -e  # Exit on any error


echo "Disabling swap"
sudo swapoff -a
swapon --show

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

# Remove old manifest files
echo "Removing old Kubernetes manifests..."
sudo rm -f /etc/kubernetes/manifests/kube-apiserver.yaml \
           /etc/kubernetes/manifests/kube-controller-manager.yaml \
           /etc/kubernetes/manifests/kube-scheduler.yaml \
           /etc/kubernetes/manifests/etcd.yaml

# Check if Kubernetes is running before resetting
echo "Checking Kubernetes status..."
sudo kubeadm reset -f

# Start kubelet
echo "Starting kubelet..."
sudo systemctl start kubelet

# Reinitialize Kubernetes cluster
echo "Initializing Kubernetes..."
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

# Configure kubectl
echo "Setting up kubectl config..."
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Wait for API server to be ready
echo "Waiting for Kubernetes API server to be ready..."
sleep 10

# Apply Flannel network plugin
echo "Applying Flannel network plugin..."
kubectl apply -f https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

# Knative
echo "Applying Knative...."
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.17.0/serving-crds.yaml

kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.17.0/serving-core.yaml

# istio
echo "Applying Istio..."
kubectl apply -f https://github.com/knative/net-istio/releases/download/knative-v1.17.0/istio.yaml
kubectl apply -f https://github.com/knative/net-istio/releases/download/knative-v1.17.0/net-istio.yaml
kubectl --namespace istio-system get service istio-ingressgateway

echo "Patching NoDNS"

kubectl patch configmap/config-domain \
      --namespace knative-serving \
      --type merge \
      --patch '{"data":{"example.com":""}}'

echo "Installing Prometheus for metrics"
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.25/samples/addons/prometheus.yaml

kubectl patch svc prometheus -n istio-system -p '{"spec": {"type": "NodePort"}}'

echo "Installing Grafana for metrics"

kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.25/samples/addons/grafana.yaml

kubectl patch svc grafana -n istio-system -p '{"spec": {"type": "NodePort"}}'

echo "Installing Kiali for metrics"
kubectl apply -f https://raw.githubusercontent.com/istio/istio/release-1.26/samples/addons/kiali.yaml

kubectl patch svc kiali -n istio-system -p '{"spec": {"type": "NodePort"}}'


echo "Patching Istio-sidecar injection"
kubectl label namespace default istio-injection=enabled

echo "Enabling PVC and SchedulerName in Knative"
kubectl patch --namespace knative-serving configmap/config-features \
 --type merge \
 --patch '{"data":{"kubernetes.podspec-schedulername": "enabled"}}'

kubectl patch --namespace knative-serving configmap/config-features \
 --type merge \
 --patch '{"data":{"kubernetes.podspec-persistent-volume-claim": "enabled", "kubernetes.podspec-persistent-volume-write": "enabled"}}'

# Generate worker join command
echo "Generating worker node join command..."
kubeadm token create --print-join-command > /tmp/kubeadm_join.sh
echo "Run this on worker nodes:sudo $(cat /tmp/kubeadm_join.sh)"


echo "Kubernetes restarted successfully!"
