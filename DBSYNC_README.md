# KegDisplay Database Synchronization

This document explains how to set up database synchronization between multiple KegDisplay instances.

## Overview

KegDisplay can run on multiple systems, with changes made to the database in one system (the primary) automatically propagated to other systems (clients). The synchronization happens through these components:

1. **Primary Server**: Runs the web interface and notifies clients of changes
2. **Client Servers**: Receive database updates from the primary server
3. **Database Sync Service**: Handles the actual synchronization on all servers

## Installation

### Prerequisites

- Poetry must be installed on all systems
- All systems must be on the same network with ports 5002 and 5003 accessible

### Automatic Setup with Installer Script

Run the setup script on each system:

```bash
sudo ./setup_dbsync.sh
```

The script will ask if this is the primary server or a client:
- For the primary server (with web interface), answer 'y'
- For client servers, answer 'n' and provide the IP address of the primary server

### Manual Setup

1. **Primary Server** (with web interface):

   Edit `/etc/systemd/system/dbsync_service.service` to use:
   ```
   ExecStart=/usr/bin/poetry run python -m KegDisplay.dbsync_service --mode primary
   ```

   Then enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dbsync_service
   sudo systemctl start dbsync_service
   ```

2. **Client Servers**:

   Edit `/etc/systemd/system/dbsync_service.service` to use:
   ```
   Environment="PRIMARY_IP=192.168.1.100"  # Replace with actual primary IP
   ExecStart=/usr/bin/poetry run python -m KegDisplay.dbsync_service --mode client --primary-ip ${PRIMARY_IP}
   ```

   Then enable and start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable dbsync_service
   sudo systemctl start dbsync_service
   ```

## Alternative: Manual Scripts

Instead of using systemd services, you can use the provided scripts:

1. **For the web interface** (primary server only):
   ```bash
   ./start_webinterface.sh
   ```

2. **For the database sync service**:
   
   On the primary server:
   ```bash
   ./start_dbsync.sh --primary
   ```
   
   On client servers:
   ```bash
   ./start_dbsync.sh --server 192.168.1.100  # Replace with primary server IP
   ```

## Troubleshooting

### Logs

- Web interface logs: `/var/log/KegDisplay/webinterface.log`
- Database sync logs: `/var/log/KegDisplay/dbsync.log`
- Systemd service logs: `journalctl -u dbsync_service`

### Common Issues

1. **Connection problems**:
   - Ensure ports 5002 and 5003 are open in your firewall
   - Verify client servers can reach the primary server IP

2. **Database sync not working**:
   - Check logs for any errors
   - Try restarting the services
   - Verify the correct primary server IP is configured

3. **Poetry not found**:
   - Make sure Poetry is installed and in the PATH
   - Check if the service file uses the correct path to Poetry

## How It Works

1. The web interface on the primary server detects database changes
2. Changes are logged in the `change_log` table
3. The SyncedDatabase component notifies other instances
4. Client instances receive the update and apply changes to their local database
5. The main KegDisplay application reads from the local database and automatically sees the changes 