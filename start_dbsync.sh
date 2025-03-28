#!/bin/bash

# Script to manually start the KegDisplay database sync service
# This can be used as an alternative to the systemd service

echo "Starting KegDisplay Database Sync Service"
echo "---------------------------------------"

# Parse command line arguments
MODE="client"
PRIMARY_IP=""

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --primary|-p) MODE="primary" ;;
        --server|-s) PRIMARY_IP="$2"; shift ;;
        --help|-h) 
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --primary, -p    Run in primary mode (with web interface)"
            echo "  --server, -s IP  Specify primary server IP (for client mode)"
            echo "  --help, -h       Show this help message"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Ensure log directory exists
if [ ! -d "/var/log/KegDisplay" ]; then
  mkdir -p /var/log/KegDisplay
  chmod 755 /var/log/KegDisplay
fi

# Change to the KegDisplay directory
cd "$(dirname "$0")"

# Make sure we have dependencies installed
if [ ! -f "poetry.lock" ]; then
  echo "Running poetry install to ensure dependencies are installed..."
  poetry install
fi

# Start the service
if [ "$MODE" == "primary" ]; then
  echo "Starting in PRIMARY mode..."
  poetry run python -m KegDisplay.dbsync_service --mode primary
else
  if [ -z "$PRIMARY_IP" ]; then
    echo "Starting in CLIENT mode (auto-discovery)..."
    poetry run python -m KegDisplay.dbsync_service --mode client
  else
    echo "Starting in CLIENT mode with primary server $PRIMARY_IP..."
    poetry run python -m KegDisplay.dbsync_service --mode client --primary-ip "$PRIMARY_IP"
  fi
fi

exit 0 