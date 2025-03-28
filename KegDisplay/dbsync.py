import socket
import threading
import json
import sqlite3
import time
import logging
import hashlib
import os
import shutil
from pathlib import Path
from datetime import datetime, UTC

logger = logging.getLogger("KegDisplay")

class DatabaseSync:
    def __init__(self, db_path, broadcast_port=5002, sync_port=5003, test_mode=False):
        """Initialize a DatabaseSync instance
        
        Args:
            db_path: Path to the SQLite database
            broadcast_port: Port for UDP broadcast messages (all instances should use the same port in production)
            sync_port: Port for TCP sync connections (each instance needs a unique port on the same machine)
            test_mode: Whether to operate in test mode (bypassing actual network operations)
        """
        self.db_path = db_path
        self.broadcast_port = broadcast_port
        self.sync_port = sync_port
        self.version = self._get_db_version()
        self.peers = {}  # {ip: (version, last_seen, sync_port)}
        self.lock = threading.Lock()
        self.test_mode = test_mode
        self.test_peers = []  # List of peer instances for test mode
        
        # Store a list of all our local IP addresses
        self.local_ips = self._get_all_local_ips()
        logger.info(f"Identified local IP addresses: {', '.join(self.local_ips)}")
        
        # Setup network sockets
        if not test_mode:
            self._setup_sockets()
            # Discover peers and request full database if needed
            self._initial_peer_discovery()
        
        # Initialize change tracking
        self._init_change_tracking()
        logger.info("Started database change tracking")
        
        # Start background threads
        self.running = True
        if not test_mode:
            self.threads = [
                threading.Thread(target=self._broadcast_listener),
                threading.Thread(target=self._sync_listener),
                threading.Thread(target=self._heartbeat_sender),
                threading.Thread(target=self._cleanup_peers)
            ]
            for thread in self.threads:
                thread.daemon = True
                thread.start()

    def notify_update(self):
        """Notify other instances that a change has been made"""
        # Update our version
        self.version = self._get_db_version()
        
        if self.test_mode:
            # In test mode, directly sync with test peers
            for peer in self.test_peers:
                if peer != self:
                    self._sync_with_peer(peer)
        else:
            # Broadcast our new version to peers
            self._broadcast_version()

    def add_test_peer(self, peer):
        """Add a peer for test mode synchronization"""
        if self.test_mode and peer not in self.test_peers:
            self.test_peers.append(peer)
            peer.test_peers.append(self)

    def _sync_with_peer(self, peer):
        """Synchronize changes with a peer in test mode"""
        try:
            # Get our last known timestamp
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_modified FROM version LIMIT 1")
                last_timestamp = cursor.fetchone()[0]

            # Get changes from peer since our last timestamp
            changes = peer._get_changes_since(last_timestamp)
            
            if changes:
                # Apply the changes to our database
                with sqlite3.connect(self.db_path) as our_conn:
                    our_cursor = our_conn.cursor()
                    
                    # Connect to peer's database
                    with sqlite3.connect(peer.db_path) as peer_conn:
                        peer_cursor = peer_conn.cursor()
                        
                        for table_name, operation, row_id, timestamp, content_hash in changes:
                            try:
                                if operation == 'INSERT':
                                    # Get the row data from peer's database
                                    peer_cursor.execute(f"SELECT * FROM {table_name} WHERE rowid = ?", (row_id,))
                                    row_data = peer_cursor.fetchone()
                                    if row_data:
                                        # Get column names
                                        peer_cursor.execute(f"PRAGMA table_info({table_name})")
                                        columns = [col[1] for col in peer_cursor.fetchall()]
                                        
                                        # Create INSERT statement
                                        placeholders = ','.join(['?' for _ in columns])
                                        our_cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", row_data)
                                
                                elif operation == 'UPDATE':
                                    # Get the row data from peer's database
                                    peer_cursor.execute(f"SELECT * FROM {table_name} WHERE rowid = ?", (row_id,))
                                    row_data = peer_cursor.fetchone()
                                    if row_data:
                                        # Get column names
                                        peer_cursor.execute(f"PRAGMA table_info({table_name})")
                                        columns = [col[1] for col in peer_cursor.fetchall()]
                                        
                                        # Create UPDATE statement
                                        set_clause = ','.join([f"{col}=?" for col in columns])
                                        our_cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE rowid=?", row_data + (row_id,))
                                
                                elif operation == 'DELETE':
                                    our_cursor.execute(f"DELETE FROM {table_name} WHERE rowid=?", (row_id,))
                                
                                # Log the change
                                our_cursor.execute('''
                                    INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                                    VALUES (?, ?, ?, ?, ?)
                                ''', (table_name, operation, row_id, timestamp, content_hash))
                            
                            except sqlite3.Error as e:
                                logger.error(f"Error applying change: {e}")
                                continue
                        
                        # Update version timestamp
                        our_cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
                        our_conn.commit()
                
                # Update our version
                self.version = self._get_db_version()
                
        except Exception as e:
            logger.error(f"Test mode sync error: {e}")

    def _init_change_tracking(self):
        """Initialize the change tracking system"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create change_log table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    row_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                )
            ''')
            
            # Create version table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS version (
                    last_modified TEXT
                )
            ''')
            
            # Initialize version table if empty
            cursor.execute("SELECT COUNT(*) FROM version")
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO version (last_modified) VALUES (?)",
                    (datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),)
                )
            
            conn.commit()

    def _get_table_hash(self, table_name):
        """Calculate a hash of the table's contents"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid")
            rows = cursor.fetchall()
            if not rows:
                return "0"
            return hashlib.md5(str(rows).encode()).hexdigest()

    def _get_db_version(self):
        """Calculate database version based on content and get timestamp"""
        if not os.path.exists(self.db_path):
            return {"hash": "0", "timestamp": "1970-01-01T00:00:00Z"}
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Calculate content-based hash from all tracked tables
            tables = ['beers', 'taps']
            content_hashes = []
            for table in tables:
                content_hashes.append(self._get_table_hash(table))
            content_hash = hashlib.md5(''.join(content_hashes).encode()).hexdigest()
            
            # Get timestamp from version table
            try:
                cursor.execute("SELECT last_modified FROM version LIMIT 1")
                timestamp = cursor.fetchone()[0]
                if not timestamp:
                    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                    cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
                    conn.commit()
            except sqlite3.Error as e:
                logger.error(f"Error accessing version table: {e}")
                timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        return {"hash": content_hash, "timestamp": timestamp}

    def _log_change(self, table_name, operation, row_id):
        """Log a database change"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            content_hash = self._get_table_hash(table_name)
            
            cursor.execute('''
                INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', (table_name, operation, row_id, timestamp, content_hash))
            
            # Update version timestamp
            cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
            conn.commit()

    def _get_changes_since(self, last_timestamp):
        """Get all changes since a given timestamp"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT table_name, operation, row_id, timestamp, content_hash
                FROM change_log
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (last_timestamp,))
            return cursor.fetchall()

    def _apply_changes(self, changes):
        """Apply changes from a changeset"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for table_name, operation, row_id, timestamp, content_hash in changes:
                try:
                    if operation == 'INSERT':
                        # Get the row data from the source database
                        cursor.execute(f"SELECT * FROM {table_name} WHERE rowid = ?", (row_id,))
                        row_data = cursor.fetchone()
                        if row_data:
                            # Get column names
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            # Create INSERT statement
                            placeholders = ','.join(['?' for _ in columns])
                            cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", row_data)
                    
                    elif operation == 'UPDATE':
                        # Get the row data from the source database
                        cursor.execute(f"SELECT * FROM {table_name} WHERE rowid = ?", (row_id,))
                        row_data = cursor.fetchone()
                        if row_data:
                            # Get column names
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            columns = [col[1] for col in cursor.fetchall()]
                            
                            # Create UPDATE statement
                            set_clause = ','.join([f"{col}=?" for col in columns])
                            cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE rowid=?", row_data + (row_id,))
                    
                    elif operation == 'DELETE':
                        cursor.execute(f"DELETE FROM {table_name} WHERE rowid=?", (row_id,))
                    
                    # Log the change
                    cursor.execute('''
                        INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (table_name, operation, row_id, timestamp, content_hash))
                
                except sqlite3.Error as e:
                    logger.error(f"Error applying change: {e}")
                    continue
            
            # Update version timestamp
            cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
            conn.commit()

    def _initial_peer_discovery(self):
        """Discover peers and request a full database if our version is outdated"""
        logger.info("Starting initial peer discovery")
        # Send discovery message
        msg = json.dumps({
            'type': 'discovery',
            'version': self.version,
            'sync_port': self.sync_port  # Include our sync port in the message
        }).encode()
        
        logger.info(f"Broadcasting discovery message on port {self.broadcast_port}")
        self.broadcast_socket.sendto(msg, ('<broadcast>', self.broadcast_port))
        
        # Wait for responses for a short time
        discovery_time = 5  # seconds
        start_time = time.time()
        
        logger.info(f"Waiting {discovery_time} seconds for peer responses...")
        
        while time.time() - start_time < discovery_time:
            try:
                self.broadcast_socket.settimeout(0.5)
                data, addr = self.broadcast_socket.recvfrom(1024)
                msg = json.loads(data.decode())
                
                # Check if the message is from our own IP
                if addr[0] not in self.local_ips:
                    logger.info(f"Received response from peer {addr[0]}")
                    peer_sync_port = msg.get('sync_port', self.sync_port)  # Default to our port if not provided
                    with self.lock:
                        self.peers[addr[0]] = (msg['version'], time.time(), peer_sync_port)
                        logger.info(f"Added peer {addr[0]} with version {msg['version']} (sync port: {peer_sync_port})")
                else:
                    logger.debug(f"Ignoring message from self ({addr[0]})")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Discovery error: {e}")
        
        # Reset socket timeout
        self.broadcast_socket.settimeout(None)
        
        # Find peer with the latest version
        latest_peer = None
        latest_version = self.version
        
        with self.lock:
            logger.info(f"Found {len(self.peers)} peers during discovery")
            for ip, (version, _, _) in self.peers.items():
                # Check if this peer's version is different from ours
                if version.get("hash") != self.version.get("hash"):
                    logger.info(f"Peer {ip} has different version: {version}")
                    if latest_peer is None or self._is_newer_version(version, latest_version):
                        latest_peer = ip
                        latest_version = version
                        logger.info(f"This is now the latest peer")
        
        if latest_peer:
            logger.info(f"Found peer with latest version: {latest_peer}, requesting full database")
            self._request_full_database(latest_peer)
        else:
            logger.info("No peers with newer database version found")

    def _is_newer_version(self, version1, version2):
        """
        Determine if version1 is newer than version2 based on timestamps.
        
        Args:
            version1: Version dict with hash and timestamp from peer
            version2: Version dict with hash and timestamp from local
            
        Returns:
            True if version1 is newer than version2
        """
        # If our current version is empty database, any other version is newer
        if version2.get("hash") == "0":
            return True
            
        # Compare timestamps
        try:
            timestamp1 = datetime.strptime(version1.get("timestamp", "1970-01-01T00:00:00Z"), 
                                         "%Y-%m-%dT%H:%M:%SZ")
            timestamp2 = datetime.strptime(version2.get("timestamp", "1970-01-01T00:00:00Z"), 
                                         "%Y-%m-%dT%H:%M:%SZ")
            return timestamp1 > timestamp2
        except (ValueError, TypeError) as e:
            logger.error(f"Error comparing timestamps: {e}")
            # Fall back to hash comparison if timestamp comparison fails
            return version1.get("hash") != version2.get("hash")

    def _update_db_timestamp(self):
        """Update the timestamp in the version table"""
        if not os.path.exists(self.db_path):
            return
            
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Check if version table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='version'")
                if not cursor.fetchone():
                    # Create version table if it doesn't exist
                    cursor.execute("CREATE TABLE version (last_modified TEXT)")
                    cursor.execute("INSERT INTO version (last_modified) VALUES (?)", (timestamp,))
                else:
                    cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error updating version timestamp: {e}")

    def _request_full_database(self, peer_ip):
        """Request a full copy of the database from a peer"""
        logger.info(f"Requesting full database from peer {peer_ip}")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Get the peer's sync port from our peers dictionary
                peer_sync_port = self.sync_port  # Default
                with self.lock:
                    if peer_ip in self.peers:
                        peer_data = self.peers[peer_ip]
                        if len(peer_data) >= 3:  # Make sure we have the sync port
                            peer_sync_port = peer_data[2]
                
                logger.info(f"Connecting to {peer_ip}:{peer_sync_port}")
                s.connect((peer_ip, peer_sync_port))
                
                s.send(json.dumps({
                    'type': 'full_db_request',
                    'version': self.version,
                    'sync_port': self.sync_port  # Include our sync port
                }).encode())
                logger.info(f"Sent full database request to {peer_ip}")
                
                # Receive response header
                response = json.loads(s.recv(1024).decode())
                logger.info(f"Received response from {peer_ip}: {response['type']}")
                
                if response['type'] == 'full_db_response':
                    # Send acknowledgment
                    s.send(b'ACK')
                    
                    # Prepare temporary file to receive database
                    temp_db_path = f"{self.db_path}.new"
                    
                    # Get the database size
                    db_size = response['db_size']
                    logger.info(f"Expected database size: {db_size} bytes")
                    
                    if db_size > 0:
                        bytes_received = 0
                        
                        with open(temp_db_path, 'wb') as f:
                            # Receive the database file in chunks
                            while bytes_received < db_size:
                                chunk = s.recv(min(8192, db_size - bytes_received))
                                if not chunk:
                                    break
                                bytes_received += len(chunk)
                                f.write(chunk)
                            
                            logger.info(f"Received {bytes_received} bytes of database data")
                        
                        # Backup the old database
                        if os.path.exists(self.db_path):
                            backup_path = f"{self.db_path}.bak"
                            shutil.copy2(self.db_path, backup_path)
                            logger.info(f"Backed up old database to {backup_path}")
                        
                        # Replace the database
                        shutil.move(temp_db_path, self.db_path)
                        logger.info(f"Replaced database with new version")
                        
                        # Update our version
                        self.version = self._get_db_version()
                        logger.info(f"Full database transferred, new version {self.version}")
                    else:
                        logger.info(f"Peer {peer_ip} has an empty database")
                
        except Exception as e:
            logger.error(f"Full database request error: {e}")
    
    def _setup_sockets(self):
        logger.info("Setting up network sockets")
        # Broadcast socket for discovery
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            logger.info(f"Binding broadcast socket to port {self.broadcast_port}")
            self.broadcast_socket.bind(('', self.broadcast_port))
            logger.info(f"Successfully bound broadcast socket to port {self.broadcast_port}")
        except Exception as e:
            logger.error(f"Error binding broadcast socket: {e}")
            raise
        
        # TCP socket for database sync
        self.sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sync_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            logger.info(f"Binding sync socket to port {self.sync_port}")
            self.sync_socket.bind(('', self.sync_port))
            self.sync_socket.listen(5)
            logger.info(f"Successfully bound sync socket to port {self.sync_port}")
        except Exception as e:
            logger.error(f"Error binding sync socket: {e}")
            raise

    def _broadcast_listener(self):
        """Listen for broadcast messages from peers"""
        logger.info(f"Starting broadcast listener on port {self.broadcast_port}")
        while self.running:
            try:
                data, addr = self.broadcast_socket.recvfrom(1024)
                msg = json.loads(data.decode())
                
                # Check if the message is from our own IP
                if addr[0] not in self.local_ips:
                    logger.info(f"Received broadcast from {addr[0]}: {msg['type']}")
                    peer_sync_port = msg.get('sync_port', self.sync_port)  # Default to our port if not provided
                    with self.lock:
                        old_version = None
                        if addr[0] in self.peers:
                            old_version = self.peers[addr[0]][0]
                        
                        # Update peer info including sync port
                        self.peers[addr[0]] = (msg['version'], time.time(), peer_sync_port)
                        
                        if old_version != msg['version']:
                            logger.info(f"Peer {addr[0]} updated version to {msg['version']} (sync port: {peer_sync_port})")
                            
                    if msg['type'] == 'update' and msg['version'] != self.version:
                        logger.info(f"Detected version change from {addr[0]}, requesting sync")
                        self._request_sync(addr[0])
                else:
                    logger.debug(f"Ignoring broadcast from self ({addr[0]})")
                        
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Broadcast listener error: {e}")

    def _sync_listener(self):
        """Listen for sync requests"""
        logger.info(f"Starting sync listener on port {self.sync_port}")
        while self.running:
            try:
                client, addr = self.sync_socket.accept()
                logger.info(f"Accepted sync connection from {addr[0]}")
                threading.Thread(target=self._handle_sync_request, 
                              args=(client, addr)).start()
            except Exception as e:
                logger.error(f"Sync listener error: {e}")

    def _handle_sync_request(self, client, addr):
        """Handle incoming sync requests"""
        try:
            data = client.recv(1024).decode()
            msg = json.loads(data)
            logger.info(f"Received {msg['type']} request from {addr[0]}")
            
            if msg['type'] == 'sync_request':
                # Get changes since the client's last timestamp
                last_timestamp = msg.get('last_timestamp', '1970-01-01T00:00:00Z')
                logger.info(f"Getting changes since {last_timestamp}")
                changes = self._get_changes_since(last_timestamp)
                
                if changes:
                    logger.info(f"Found {len(changes)} changes to send to {addr[0]}")
                    # Send changes to client
                    client.send(json.dumps({
                        'type': 'sync_response',
                        'version': self.version,
                        'has_changes': True
                    }).encode())
                    
                    # Wait for acknowledgment
                    client.recv(1024)
                    logger.info(f"Acknowledgment received from {addr[0]}")
                    
                    # Send the changes
                    client.send(json.dumps(changes).encode())
                    logger.info(f"Sent changes to {addr[0]}")
                    
                    # Wait for acknowledgment
                    client.recv(1024)
                    logger.info(f"Acknowledgment received from {addr[0]}")
                    
                    # Send the full database content
                    with open(self.db_path, 'rb') as f:
                        bytes_sent = 0
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            client.send(chunk)
                            bytes_sent += len(chunk)
                        logger.info(f"Sent full database ({bytes_sent} bytes) to {addr[0]}")
                else:
                    # No changes to send
                    logger.info(f"No changes to send to {addr[0]}")
                    client.send(json.dumps({
                        'type': 'sync_response',
                        'version': self.version,
                        'has_changes': False
                    }).encode())
            
            elif msg['type'] == 'full_db_request':
                # Handle request for full database copy
                if os.path.exists(self.db_path):
                    db_size = os.path.getsize(self.db_path)
                    logger.info(f"Sending full database ({db_size} bytes) to {addr[0]}")
                    
                    # Send response with file size
                    client.send(json.dumps({
                        'type': 'full_db_response',
                        'version': self.version,
                        'db_size': db_size
                    }).encode())
                    
                    # Wait for acknowledgment
                    client.recv(1024)
                    logger.info(f"Acknowledgment received from {addr[0]}")
                    
                    # Send the database file
                    with open(self.db_path, 'rb') as f:
                        bytes_sent = 0
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            client.send(chunk)
                            bytes_sent += len(chunk)
                    
                    logger.info(f"Sent full database to {addr[0]} ({bytes_sent} bytes)")
                else:
                    # Database doesn't exist
                    logger.info(f"Database doesn't exist, sending empty response to {addr[0]}")
                    client.send(json.dumps({
                        'type': 'full_db_response',
                        'version': self.version,
                        'db_size': 0
                    }).encode())
                
        except Exception as e:
            logger.error(f"Sync handler error: {e}")
        finally:
            client.close()
            logger.info(f"Closed connection to {addr[0]}")

    def _request_sync(self, peer_ip):
        """Request database sync from a peer"""
        logger.info(f"Requesting sync from peer {peer_ip}")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Get the peer's sync port from our peers dictionary
                peer_sync_port = self.sync_port  # Default
                with self.lock:
                    if peer_ip in self.peers:
                        peer_data = self.peers[peer_ip]
                        if len(peer_data) >= 3:  # Make sure we have the sync port
                            peer_sync_port = peer_data[2]
                
                logger.info(f"Connecting to {peer_ip}:{peer_sync_port}")
                s.connect((peer_ip, peer_sync_port))
                
                # Get our last known timestamp
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT last_modified FROM version LIMIT 1")
                    last_timestamp = cursor.fetchone()[0]
                    logger.info(f"Our last timestamp: {last_timestamp}")
                
                s.send(json.dumps({
                    'type': 'sync_request',
                    'version': self.version,
                    'last_timestamp': last_timestamp,
                    'sync_port': self.sync_port  # Include our sync port in case the peer needs to contact us back
                }).encode())
                logger.info(f"Sent sync request to {peer_ip}")
                
                # Receive sync response header
                response = json.loads(s.recv(1024).decode())
                logger.info(f"Received response from {peer_ip}: {response['type']}")
                
                if response['type'] == 'sync_response':
                    if response['has_changes']:
                        logger.info(f"Peer {peer_ip} has changes for us")
                        # Send acknowledgment
                        s.send(b'ACK')
                        
                        # Receive the changes
                        changes_data = s.recv(1024 * 1024)  # Adjust buffer size as needed
                        logger.info(f"Received {len(changes_data)} bytes of changes data")
                        changes = json.loads(changes_data.decode())
                        logger.info(f"Received {len(changes)} changes from {peer_ip}")
                        
                        # Send acknowledgment
                        s.send(b'ACK')
                        
                        # Receive full database content
                        temp_db_path = f"{self.db_path}.new"
                        with open(temp_db_path, 'wb') as f:
                            bytes_received = 0
                            while True:
                                chunk = s.recv(8192)
                                if not chunk:
                                    break
                                bytes_received += len(chunk)
                                f.write(chunk)
                            logger.info(f"Received {bytes_received} bytes of database data")
                        
                        # Apply the changes
                        logger.info(f"Applying {len(changes)} changes to our database")
                        self._apply_changes(changes)
                        
                        # Backup the old database
                        if os.path.exists(self.db_path):
                            backup_path = f"{self.db_path}.bak"
                            shutil.copy2(self.db_path, backup_path)
                            logger.info(f"Backed up old database to {backup_path}")
                        
                        # Replace the database
                        shutil.move(temp_db_path, self.db_path)
                        logger.info(f"Replaced database with new version")
                        
                        # Update our version
                        self.version = self._get_db_version()
                        logger.info(f"Database synchronized to version {self.version}")
                    else:
                        logger.info(f"Peer {peer_ip} has no changes for us")
                
        except Exception as e:
            logger.error(f"Sync request error: {e}")

    def _heartbeat_sender(self):
        """Send periodic heartbeat messages"""
        while self.running:
            try:
                msg = json.dumps({
                    'type': 'heartbeat',
                    'version': self.version,
                    'sync_port': self.sync_port  # Include our sync port in heartbeat messages
                }).encode()
                
                self.broadcast_socket.sendto(msg, 
                                          ('<broadcast>', self.broadcast_port))
                time.sleep(5)
            except Exception as e:
                logger.error(f"Heartbeat sender error: {e}")

    def _cleanup_peers(self):
        """Remove peers that haven't been seen recently"""
        while self.running:
            try:
                with self.lock:
                    current_time = time.time()
                    self.peers = {ip: peer_data
                                for ip, peer_data in self.peers.items()
                                if current_time - peer_data[1] < 15}  # peer_data[1] is last_seen timestamp
                time.sleep(5)
            except Exception as e:
                logger.error(f"Peer cleanup error: {e}")

    def _broadcast_version(self):
        """Broadcast the current version to all peers"""
        if not self.test_mode:
            try:
                msg = json.dumps({
                    'type': 'update',
                    'version': self.version,
                    'sync_port': self.sync_port  # Include our sync port in update messages
                }).encode()
                
                # Try to send to each peer individually
                sent_count = 0
                for ip in self.peers:
                    try:
                        logger.info(f"Sending update notification to peer {ip}")
                        self.broadcast_socket.sendto(msg, (ip, self.broadcast_port))
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Error sending to peer {ip}: {e}")
                
                # Also send general broadcast
                try:
                    logger.info("Sending general broadcast update notification")
                    self.broadcast_socket.sendto(msg, ('<broadcast>', self.broadcast_port))
                    logger.info(f"Broadcasted version {self.version} to all peers ({sent_count} direct, 1 broadcast)")
                except Exception as e:
                    logger.error(f"Error sending broadcast: {e}")
                    
                # If we couldn't send to any peers directly, but we have peers, try sync directly
                if sent_count == 0 and len(self.peers) > 0:
                    logger.warning("Could not broadcast to any peers directly. Attempting direct sync...")
                    self._force_sync_with_peers()
                    
            except Exception as e:
                logger.error(f"Broadcast version error: {e}")

    def _force_sync_with_peers(self):
        """Force sync with all known peers when broadcast fails"""
        logger.info("Forcing direct sync with all known peers")
        for ip in self.peers:
            try:
                logger.info(f"Requesting sync from peer {ip}")
                self._request_sync(ip)
            except Exception as e:
                logger.error(f"Error forcing sync with peer {ip}: {e}")

    def add_peer(self, peer_ip):
        """Manually add a peer by IP address"""
        # First check if this is our own IP
        if peer_ip in self.local_ips:
            logger.warning(f"Ignoring attempt to add self as peer: {peer_ip}")
            return
            
        if peer_ip and peer_ip not in self.peers:
            logger.info(f"Manually adding peer: {peer_ip}")
            # Default to standard primary port 5003 for manually added peers
            self.peers[peer_ip] = ({"hash": "unknown", "timestamp": "1970-01-01T00:00:00Z"}, time.time(), 5003)
            
            # Try to sync with this peer
            try:
                logger.info(f"Requesting initial sync from new peer {peer_ip}")
                self._request_full_database(peer_ip)
            except Exception as e:
                logger.error(f"Error syncing with new peer {peer_ip}: {e}")

    def _handle_sync_response(self, client, addr):
        """Handle incoming sync responses"""
        try:
            data = client.recv(1024).decode()
            msg = json.loads(data)
            
            if msg['type'] == 'sync_response':
                if msg['has_changes']:
                    # Send acknowledgment
                    client.send(b'ACK')
                    
                    # Receive changes
                    data = client.recv(1024).decode()
                    changes = json.loads(data)
                    
                    # Send acknowledgment
                    client.send(b'ACK')
                    
                    # Receive full database content
                    temp_db_path = f"{self.db_path}.new"
                    with open(temp_db_path, 'wb') as f:
                        while True:
                            chunk = client.recv(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    # Backup the old database
                    if os.path.exists(self.db_path):
                        backup_path = f"{self.db_path}.bak"
                        shutil.copy2(self.db_path, backup_path)
                        logger.info(f"Backed up old database to {backup_path}")
                    
                    # Replace the database
                    shutil.move(temp_db_path, self.db_path)
                    
                    # Update our version
                    self.version = msg['version']
                    
                    logger.info(f"Received database update from {addr[0]}")
                else:
                    # No changes needed
                    logger.info(f"No changes needed from {addr[0]}")
            
            elif msg['type'] == 'full_db_response':
                if msg['db_size'] > 0:
                    # Send acknowledgment
                    client.send(b'ACK')
                    
                    # Prepare temporary file to receive database
                    temp_db_path = f"{self.db_path}.new"
                    
                    # Get the database size
                    db_size = msg['db_size']
                    bytes_received = 0
                    
                    with open(temp_db_path, 'wb') as f:
                        # Receive the database file in chunks
                        while bytes_received < db_size:
                            chunk = client.recv(min(8192, db_size - bytes_received))
                            if not chunk:
                                break
                            bytes_received += len(chunk)
                            f.write(chunk)
                    
                    # Backup the old database
                    if os.path.exists(self.db_path):
                        backup_path = f"{self.db_path}.bak"
                        shutil.copy2(self.db_path, backup_path)
                        logger.info(f"Backed up old database to {backup_path}")
                    
                    # Replace the database
                    shutil.move(temp_db_path, self.db_path)
                    
                    # Update our version
                    self.version = msg['version']
                    
                    logger.info(f"Received full database from {addr[0]}")
                else:
                    logger.info(f"No database available from {addr[0]}")
                
        except Exception as e:
            logger.error(f"Sync response handler error: {e}")
        finally:
            client.close()

    def _get_local_ip(self):
        """Get the local IP address"""
        try:
            # First try: using a socket connection to external server
            logger.info("Getting local IP address...")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # This doesn't actually establish a connection,
            # but tells the OS to pick an interface that could reach this address
            try:
                s.connect(('8.8.8.8', 80))
                ip = s.getsockname()[0]
                s.close()
                
                if ip != '127.0.0.1' and ip != '127.0.1.1':
                    logger.info(f"Found local IP using external connection method: {ip}")
                    return ip
            except Exception as e:
                logger.error(f"Error getting IP via socket: {e}")
            
            # Second try: using hostname
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                
                if ip != '127.0.0.1' and ip != '127.0.1.1':
                    logger.info(f"Found local IP using hostname method: {ip}")
                    return ip
            except Exception as e:
                logger.error(f"Error getting IP via hostname: {e}")
            
            # Third try: using network interfaces
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    try:
                        addresses = netifaces.ifaddresses(interface)
                        if netifaces.AF_INET in addresses:
                            for address in addresses[netifaces.AF_INET]:
                                if 'addr' in address and address['addr'] != '127.0.0.1' and address['addr'] != '127.0.1.1':
                                    logger.info(f"Found local IP using netifaces method: {address['addr']}")
                                    return address['addr']
                    except Exception as e:
                        logger.error(f"Error checking interface {interface}: {e}")
            except ImportError:
                logger.warning("netifaces module not available, falling back to other methods")
                
                # Fourth try: try various commands
                try:
                    import subprocess
                    
                    # Try ip command
                    try:
                        result = subprocess.check_output(['ip', '-4', 'addr', 'show', 'scope', 'global']).decode('utf-8')
                        for line in result.split('\n'):
                            if 'inet ' in line:
                                ip = line.strip().split()[1].split('/')[0]
                                if ip != '127.0.0.1' and ip != '127.0.1.1':
                                    logger.info(f"Found local IP using ip command: {ip}")
                                    return ip
                    except:
                        pass
                    
                    # Try ifconfig command
                    try:
                        result = subprocess.check_output(['ifconfig']).decode('utf-8')
                        for line in result.split('\n'):
                            if 'inet ' in line and '127.0.0.1' not in line and '127.0.1.1' not in line:
                                parts = line.strip().split()
                                for i, part in enumerate(parts):
                                    if part == 'inet' and i+1 < len(parts):
                                        ip = parts[i+1].split(':')[-1]
                                        logger.info(f"Found local IP using ifconfig command: {ip}")
                                        return ip
                    except:
                        pass
                    
                    # Try hostname -I command (Linux)
                    try:
                        result = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
                        if result:
                            ip = result.split()[0]
                            if ip != '127.0.0.1' and ip != '127.0.1.1':
                                logger.info(f"Found local IP using hostname -I command: {ip}")
                                return ip
                    except:
                        pass
                        
                except Exception as e:
                    logger.error(f"Error using subprocess for network interfaces: {e}")
            
            # Fallback
            logger.warning("Could not find a suitable local IP, falling back to 127.0.0.1")
            return '127.0.0.1'
        except Exception as e:
            logger.error(f"Error getting local IP: {e}")
            return '127.0.0.1'

    def _get_all_local_ips(self):
        """Get a list of all local IP addresses to avoid self-connections"""
        local_ips = ['127.0.0.1', '127.0.1.1']  # Always include localhost
        
        try:
            # Get the "main" IP first
            main_ip = self._get_local_ip()
            if main_ip not in local_ips:
                local_ips.append(main_ip)
                
            # Try to get additional IPs using various methods
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    try:
                        addresses = netifaces.ifaddresses(interface)
                        if netifaces.AF_INET in addresses:
                            for address in addresses[netifaces.AF_INET]:
                                if 'addr' in address and address['addr'] not in local_ips:
                                    local_ips.append(address['addr'])
                    except Exception:
                        pass
            except ImportError:
                # Fallback methods if netifaces is not available
                try:
                    import subprocess
                    try:
                        result = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
                        if result:
                            for ip in result.split():
                                if ip.strip() and ip.strip() not in local_ips:
                                    local_ips.append(ip.strip())
                    except:
                        pass
                        
                    try:
                        result = subprocess.check_output(['ifconfig']).decode('utf-8')
                        for line in result.split('\n'):
                            if 'inet ' in line and '127.0.0.1' not in line and '127.0.1.1' not in line:
                                parts = line.strip().split()
                                for i, part in enumerate(parts):
                                    if part == 'inet' and i+1 < len(parts):
                                        ip = parts[i+1].split(':')[-1]
                                        if ip not in local_ips:
                                            local_ips.append(ip)
                    except:
                        pass
                except Exception:
                    pass
                    
            # Try socket connection to different addresses to find all interfaces
            try:
                for test_addr in ['8.8.8.8', '1.1.1.1', '192.168.1.1']:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        s.connect((test_addr, 80))
                        ip = s.getsockname()[0]
                        if ip not in local_ips:
                            local_ips.append(ip)
                    except:
                        pass
                    finally:
                        s.close()
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error getting all local IPs: {e}")
            
        return local_ips

    def stop(self):
        """Stop the sync service"""
        logger.info("Stopping database sync service")
        self.running = False
        
        if not self.test_mode:
            try:
                # Close broadcast socket safely
                try:
                    logger.info("Closing broadcast socket")
                    self.broadcast_socket.shutdown(socket.SHUT_RDWR)
                    self.broadcast_socket.close()
                    logger.info("Broadcast socket closed")
                except Exception as e:
                    logger.warning(f"Error closing broadcast socket: {e}")
                
                # Close sync socket safely
                try:
                    logger.info("Closing sync socket")
                    self.sync_socket.shutdown(socket.SHUT_RDWR)
                    self.sync_socket.close()
                    logger.info("Sync socket closed")
                except Exception as e:
                    logger.warning(f"Error closing sync socket: {e}")
                
                # Wait for threads to finish
                logger.info("Waiting for threads to complete")
                if hasattr(self, 'threads'):
                    for thread in self.threads:
                        if thread.is_alive():
                            thread.join(1.0)  # Wait up to 1 second for each thread
                
                logger.info("Database sync service stopped")
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

    def _ensure_valid_session(self):
        """Ensure we have a valid tracking session"""
        with self.lock:
            try:
                # Test if session is still valid
                self._get_changes_since('1970-01-01T00:00:00Z')
            except sqlite3.Error:
                # If session is invalid, create a new one
                logger.warning("Session invalid, creating new session")
                self._init_change_tracking() 