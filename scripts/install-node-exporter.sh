#!/bin/bash

# Download and extract Node Exporter
wget https://github.com/prometheus/node_exporter/releases/download/v1.9.0/node_exporter-1.9.0.linux-arm64.tar.gz
tar xvfz node_exporter-1.9.0.linux-arm64.tar.gz
sudo mv node_exporter-1.9.0.linux-arm64/node_exporter /usr/local/bin/
sudo chmod +x /usr/local/bin/node_exporter

# Clean up
rm -rf node_exporter-1.9.0.linux-arm64
rm node_exporter-1.9.0.linux-arm64.tar.gz
echo "Node Exporter installed successfully!"

# Create a systemd service file
echo "Creating systemd service file..."

cat <<EOF | sudo tee /etc/systemd/system/node_exporter.service
[Unit]
Description=Prometheus Node Exporter
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/node_exporter
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable and start Node Exporter
echo "Starting Node Exporter service..."
sudo systemctl daemon-reload
sudo systemctl enable node_exporter
sudo systemctl start node_exporter

# Check service status
sudo systemctl status node_exporter --no-pager

# Confirm it's running
echo "Testing Node Exporter..."
curl -s http://localhost:9100/metrics | head -n 10

echo "Node Exporter setup completed successfully!"
