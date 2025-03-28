#!/bin/bash

# Script to start the KegDisplay web interface with database synchronization
# This should be run on the primary server only

# Parse command line arguments
WEB_PORT=8080
BROADCAST_PORT=5002
SYNC_PORT=5003
DISABLE_SYNC=0
DEBUG_MODE=0

function show_help {
  echo "Usage: $0 [options]"
  echo "Options:"
  echo "  --web-port PORT      HTTP port for web interface (default: 8080)"
  echo "  --broadcast-port PORT UDP port for sync broadcasting (default: 5002)"
  echo "  --sync-port PORT     TCP port for sync connections (default: 5003)"
  echo "  --no-sync            Disable synchronization (for read-only instances)"
  echo "  --debug              Enable Flask debug mode"
  echo "  --help               Show this help message"
  exit 0
}

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --web-port) WEB_PORT="$2"; shift ;;
    --broadcast-port) BROADCAST_PORT="$2"; shift ;;
    --sync-port) SYNC_PORT="$2"; shift ;;
    --no-sync) DISABLE_SYNC=1 ;;
    --debug) DEBUG_MODE=1 ;;
    --help) show_help ;;
    *) echo "Unknown parameter: $1"; show_help ;;
  esac
  shift
done

echo "Starting KegDisplay Web Interface with Database Synchronization"
echo "--------------------------------------------------------"
echo "Web port: $WEB_PORT"
echo "Broadcast port: $BROADCAST_PORT"
echo "Sync port: $SYNC_PORT"
[ $DISABLE_SYNC -eq 1 ] && echo "Synchronization: DISABLED" || echo "Synchronization: ENABLED"
[ $DEBUG_MODE -eq 1 ] && echo "Debug mode: ENABLED" || echo "Debug mode: DISABLED"

# Check if another instance is already using the broadcast port
if [ $DISABLE_SYNC -eq 0 ] && command -v lsof >/dev/null 2>&1; then
  PORT_IN_USE=$(lsof -i :$BROADCAST_PORT | grep -v "^COMMAND" | wc -l | tr -d ' ')
  if [ "$PORT_IN_USE" -gt 0 ]; then
    echo "WARNING: Port $BROADCAST_PORT is already in use! Another instance may be running."
    echo "Use 'lsof -i :$BROADCAST_PORT' to see what process is using it."
    echo "You can use --broadcast-port to specify a different port or --no-sync to disable synchronization."
    
    read -p "Do you want to continue anyway? (y/n): " CONTINUE
    if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
      echo "Exiting."
      exit 1
    fi
  fi
else
  [ $DISABLE_SYNC -eq 0 ] && echo "Note: 'lsof' command not available, skipping port check."
fi

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
COMMAND_ARGS="--port $WEB_PORT"

if [ $DISABLE_SYNC -eq 0 ]; then
  COMMAND_ARGS="$COMMAND_ARGS --broadcast-port $BROADCAST_PORT --sync-port $SYNC_PORT"
else
  COMMAND_ARGS="$COMMAND_ARGS --no-sync"
fi

if [ $DEBUG_MODE -eq 1 ]; then
  COMMAND_ARGS="$COMMAND_ARGS --debug"
fi

echo "Running: poetry run python -m KegDisplay.webinterface $COMMAND_ARGS"
poetry run python -m KegDisplay.webinterface $COMMAND_ARGS

exit 0 