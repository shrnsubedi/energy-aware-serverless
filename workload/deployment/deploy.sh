#!/bin/bash

echo "Deploying all workloads..."

echo "Deploying S2: ModelDepot (PVC + Service + Gateway)"
kubectl apply -f s2-pv.yaml
kubectl apply -f s2-pvc.yaml
kubectl apply -f s2-deploy.yaml
kubectl apply -f s2-service.yaml
kubectl apply -f s2-gateway.yaml
kubectl apply -f s2-vs.yaml
kubectl apply -f s1-service-v2.yaml
kubectl apply -f round-robin.yaml

for service in s3 s4 s5; do
  echo "Deploying $service..."
  kubectl apply -f ${service}-service.yaml
done

echo "All services deployed."
