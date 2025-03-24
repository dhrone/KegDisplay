import socket
import threading
import json
import sqlite3
import time
import logging
import hashlib
import os
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("KegDisplay")

class DatabaseSync:
    def __init__(self, db_path, broadcast_port=5000, sync_port=5001):
        self.db_path = db_path
        self.broadcast_port = broadcast_port
        self.sync_port = sync_port
        self.version = self._get_db_version()
        self.peers = {}  # {ip: (version, last_seen)}
        self.lock = threading.Lock()
        
        # Setup network sockets
        self._setup_sockets()
        
        # Start background threads
        self.running = True
        self.threads = [
            threading.Thread(target=self._broadcast_listener),
            threading.Thread(target=self._sync_listener),
            threading.Thread(target=self._heartbeat_sender),
            threading.Thread(target=self._cleanup_peers)
        ]
        for thread in self.threads:
            thread.daemon = True
            thread.start()

    def _setup_sockets(self):
        # Broadcast socket for discovery
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.broadcast_socket.bind(('', self.broadcast_port))
        
        # TCP socket for database sync
        self.sync_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sync_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sync_socket.bind(('', self.sync_port))
        self.sync_socket.listen(5)

    def _get_db_version(self):
        """Calculate database version based on content and last modified time"""
        if not os.path.exists(self.db_path):
            return 0
        
        mtime = os.path.getmtime(self.db_path)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), SUM(ROWID) FROM beers")
            checksum = hashlib.md5(str(cursor.fetchone()).encode()).hexdigest()
        
        return f"{mtime}_{checksum}"

    def _broadcast_listener(self):
        """Listen for broadcast messages from peers"""
        while self.running:
            try:
                data, addr = self.broadcast_socket.recvfrom(1024)
                msg = json.loads(data.decode())
                
                if addr[0] != self._get_local_ip():
                    with self.lock:
                        self.peers[addr[0]] = (msg['version'], time.time())
                        
                    if msg['type'] == 'update' and msg['version'] > self.version:
                        self._request_sync(addr[0])
                        
            except Exception as e:
                logger.error(f"Broadcast listener error: {e}")

    def _sync_listener(self):
        """Listen for sync requests"""
        while self.running:
            try:
                client, addr = self.sync_socket.accept()
                threading.Thread(target=self._handle_sync_request, 
                              args=(client, addr)).start()
            except Exception as e:
                logger.error(f"Sync listener error: {e}")

    def _handle_sync_request(self, client, addr):
        """Handle incoming sync requests"""
        try:
            data = client.recv(1024).decode()
            msg = json.loads(data)
            
            if msg['type'] == 'sync_request':
                # Only respond if we have the latest version
                should_respond = True
                with self.lock:
                    for peer_ip, (peer_version, _) in self.peers.items():
                        if peer_version > self.version:
                            should_respond = False
                            break
                
                if should_respond:
                    with open(self.db_path, 'rb') as f:
                        client.send(json.dumps({
                            'type': 'sync_response',
                            'version': self.version
                        }).encode())
                        
                        # Wait for acknowledgment
                        client.recv(1024)
                        
                        # Send the database file
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            client.send(chunk)
                
        except Exception as e:
            logger.error(f"Sync handler error: {e}")
        finally:
            client.close()

    def _request_sync(self, peer_ip):
        """Request database sync from a peer"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((peer_ip, self.sync_port))
                
                s.send(json.dumps({
                    'type': 'sync_request',
                    'version': self.version
                }).encode())
                
                # Receive sync response header
                response = json.loads(s.recv(1024).decode())
                if response['type'] == 'sync_response':
                    # Send acknowledgment
                    s.send(b'ACK')
                    
                    # Receive and save the database file
                    tmp_path = f"{self.db_path}.tmp"
                    with open(tmp_path, 'wb') as f:
                        while True:
                            chunk = s.recv(8192)
                            if not chunk:
                                break
                            f.write(chunk)
                    
                    # Replace the old database file
                    os.replace(tmp_path, self.db_path)
                    self.version = self._get_db_version()
                    logger.info(f"Database synchronized to version {self.version}")
                    
        except Exception as e:
            logger.error(f"Sync request error: {e}")

    def _heartbeat_sender(self):
        """Send periodic heartbeat messages"""
        while self.running:
            try:
                msg = json.dumps({
                    'type': 'heartbeat',
                    'version': self.version
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
                    self.peers = {ip: (version, last_seen) 
                                for ip, (version, last_seen) in self.peers.items()
                                if current_time - last_seen < 15}
                time.sleep(5)
            except Exception as e:
                logger.error(f"Peer cleanup error: {e}")

    def notify_update(self):
        """Notify peers of a database update"""
        self.version = self._get_db_version()
        try:
            msg = json.dumps({
                'type': 'update',
                'version': self.version
            }).encode()
            
            self.broadcast_socket.sendto(msg, ('<broadcast>', self.broadcast_port))
            logger.info(f"Notified peers of update to version {self.version}")
        except Exception as e:
            logger.error(f"Update notification error: {e}")

    def _get_local_ip(self):
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    def stop(self):
        """Stop the sync service"""
        self.running = False
        self.broadcast_socket.close()
        self.sync_socket.close() 