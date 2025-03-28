#!/bin/bash

# Script to start the KegDisplay web interface with database synchronization
# This should be run on the primary server only

echo "Starting KegDisplay Web Interface with Database Synchronization"
echo "--------------------------------------------------------"

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

# Start the web interface
echo "Starting web interface..."
poetry run python -m KegDisplay.webinterface --port 8080

exit 0 