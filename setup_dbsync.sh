#!/bin/bash

# Script to set up the KegDisplay database synchronization service
# This script should be run on each system that needs database synchronization

echo "KegDisplay Database Synchronization Setup"
echo "----------------------------------------"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (use sudo)"
  exit 1
fi

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
  echo "Poetry is not installed. Installing Poetry..."
  curl -sSL https://install.python-poetry.org | python3 -
  # Add to PATH for this session
  export PATH="$HOME/.local/bin:$PATH"
  
  # Check if installation was successful
  if ! command -v poetry &> /dev/null; then
    echo "Failed to install Poetry. Please install it manually and run this script again."
    echo "Visit https://python-poetry.org/docs/#installation for installation instructions."
    exit 1
  fi
fi

echo "Using Poetry: $(which poetry)"

# Determine the mode (primary or client)
MODE=""
PRIMARY_IP=""

read -p "Is this the primary server with the web interface? (y/n): " answer
if [[ "$answer" == "y" || "$answer" == "Y" ]]; then
  MODE="primary"
  echo "Setting up as PRIMARY server (with web interface)"
else
  MODE="client"
  echo "Setting up as CLIENT server"
  read -p "Enter the IP address of the primary server: " PRIMARY_IP
  if [ -z "$PRIMARY_IP" ]; then
    echo "You must specify the primary server IP address."
    exit 1
  fi
  echo "Primary server IP: $PRIMARY_IP"
fi

# Ensure the log directory exists
echo "Creating log directory..."
mkdir -p /var/log/KegDisplay
chmod 755 /var/log/KegDisplay

# Copy the service file
echo "Installing systemd service file..."
cp dbsync_service.service /etc/systemd/system/

# Modify the service file based on the mode
if [ "$MODE" == "primary" ]; then
  # Configure for primary mode
  sed -i 's|^ExecStart=.*|ExecStart=/usr/bin/poetry run python -m KegDisplay.dbsync_service --mode primary|' /etc/systemd/system/dbsync_service.service
else
  # Configure for client mode with primary IP
  sed -i "s|^#Environment=\"PRIMARY_IP=.*\"|Environment=\"PRIMARY_IP=$PRIMARY_IP\"|" /etc/systemd/system/dbsync_service.service
  sed -i 's|^ExecStart=.*|ExecStart=/usr/bin/poetry run python -m KegDisplay.dbsync_service --mode client --primary-ip ${PRIMARY_IP}|' /etc/systemd/system/dbsync_service.service
fi

# Check if a poetry.lock file exists in the working directory
if [ ! -f "/opt/KegDisplay/poetry.lock" ]; then
  echo "Installing poetry dependencies..."
  cd /opt/KegDisplay
  poetry install
  if [ $? -ne 0 ]; then
    echo "Failed to install Poetry dependencies. Please check your Poetry configuration."
    exit 1
  fi
fi

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable and start the service
echo "Enabling and starting the service..."
systemctl enable dbsync_service
systemctl start dbsync_service

echo "Database synchronization service setup complete!"
echo "Check status with: systemctl status dbsync_service"
echo "View logs with: journalctl -u dbsync_service"

exit 0 