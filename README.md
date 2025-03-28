# KegDisplay
Project using tinyDisplay and pyAttention to display beer metadata on small screens for use in a kegerator

## Database Synchronization

The KegDisplay system includes a database synchronization feature that allows multiple instances to keep their databases in sync across a network. This is useful for environments with multiple display screens or control points.

### Configuration

When running multiple instances across a network:

1. **Broadcast Port**: All instances should use the same broadcast port (default: 5002)
   - This allows broadcast messages to be received by all instances
   - Example: `broadcast_port=5002` for all instances

2. **Sync Port**: Each instance on the same machine needs a unique sync port
   - Different machines can use the same sync port number if needed
   - Example: `sync_port=5003` for instance 1, `sync_port=5004` for instance 2, etc.

### Testing

When running in test mode (`test_mode=True`), the system bypasses actual network operations and uses direct peer connections for synchronization. This allows testing the synchronization logic without network requirements.
