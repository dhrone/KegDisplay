# Network Test for DatabaseSync

This script allows you to test the DatabaseSync functionality over a real network between multiple machines.

## Requirements

- Two or more computers on the same network
- Each computer must have KegDisplay installed
- Ports 5002 (broadcast) and 5003/5004 (sync) must be open in firewalls
- Optional: For network diagnostics, install: `pip install netifaces`

## Usage

The test runs in a primary-secondary model:
- One machine acts as the primary and makes changes
- One or more machines act as secondaries and receive changes

### Running the Primary Instance

On the primary machine:

```bash
# Start the primary instance
poetry run python -m KegDisplay.tests.network_test primary

# Optionally specify IPs of secondary instances (not required but helpful for logging)
poetry run python -m KegDisplay.tests.network_test primary --ip 192.168.1.101 --ip 192.168.1.102
```

The primary will:
1. Create a temporary database with test data
2. Start a DatabaseSync instance with real network mode
3. Make a change to the database (adding a random beer)
4. Display the name of the beer for verification on secondary instances

### Running Secondary Instances

On each secondary machine:

```bash
# Start the secondary instance (uses UDP broadcast discovery)
poetry run python -m KegDisplay.tests.network_test secondary

# If broadcast discovery doesn't work, specify the primary IP directly:
poetry run python -m KegDisplay.tests.network_test secondary --primary-ip 192.168.1.100
```

The secondary will:
1. Create a temporary database with initial test data
2. Start a DatabaseSync instance with real network mode
3. Wait for changes from the primary instance
4. Keep running to receive updates

### Verifying Changes

After the primary makes a change, you can verify if the change was received on a secondary:

```bash
# Use the beer name displayed by the primary
poetry run python -m KegDisplay.tests.network_test verify --beer-name "New Beer 123"

# If broadcast discovery isn't working, specify the primary IP:
poetry run python -m KegDisplay.tests.network_test verify --beer-name "New Beer 123" --primary-ip 192.168.1.100
```

The verify command will:
1. Check if the specified beer exists in the secondary's database
2. Display a success or failure message

## Network Diagnostics

If the secondary cannot connect to the primary, the test script now includes enhanced diagnostics:

1. **Automatic IP detection**: Tries to identify all local network interfaces
2. **Connectivity checking**: Performs multiple tests to diagnose network issues
3. **Firewall diagnosis**: Checks firewall settings that might block communications
4. **Broadcast testing**: Verifies that UDP broadcasts are being sent correctly

When connectivity issues are detected, the script will:
1. Display warning messages with troubleshooting suggestions
2. Show network interface details to help identify the correct IP addresses
3. Log detailed diagnostic information to the log file

### Troubleshooting Network Issues

If the secondary can't discover the primary:

1. Check the log file for detailed diagnostics
2. Use the `--primary-ip` option to directly specify the primary's IP address:
   ```bash
   poetry run python -m KegDisplay.tests.network_test secondary --primary-ip 192.168.1.100
   ```
3. Verify that UDP port 5002 and TCP ports 5003/5004 are open in firewalls
4. Ensure both machines are on the same network/subnet

## Custom Configuration

You can customize the broadcast port if needed:

```bash
# Use a custom port (must be the same on all instances)
poetry run python -m KegDisplay.tests.network_test primary --port 5010

# Secondary must use the same port
poetry run python -m KegDisplay.tests.network_test secondary --port 5010
```

## Logging

The test script includes detailed logging to help diagnose network issues:

### Console Logging
All major events are logged to the console, including:
- Network setup and configuration
- Peer discovery
- Database changes
- Synchronization events

### File Logging
In addition to console output, each instance creates a detailed log file:
- Log files are named `network_test_[role]_[timestamp].log`
- Log files include DEBUG level messages from the DatabaseSync component
- Both the application layer (test script) and the DatabaseSync layer are logged
- At the end of the test, the log file path is displayed

### Viewing Logs
When running tests across multiple machines, you can view the logs to understand what's happening:
1. Watch the console output for high-level events
2. Check the log files for detailed networking information
3. Compare logs between primary and secondary to trace synchronization issues

The log files are extremely useful when troubleshooting failed synchronization, as they show:
- Network interface information
- Peer discovery process
- Database state before and after changes
- All broadcast and sync operations
- Timestamps for all operations

## Troubleshooting

- Ensure all machines are on the same network
- Check firewall settings to allow the required ports
- Verify that all instances use the same broadcast port
- Make sure no other applications are using the specified ports
- Look for error messages in the console output
- Check the log files for detailed diagnostic information 