import unittest
import os
import shutil
import tempfile
import time
import sqlite3
import sys
from datetime import datetime, UTC
import hashlib
import argparse
import logging
import random
import json
import socket
import glob
import signal
import threading

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dbsync import DatabaseSync

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NetworkTest")

# Create a file handler for logging
def setup_file_logging(role):
    """Setup file logging"""
    log_file = f"network_test_{role}_{int(time.time())}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)
    logging.getLogger("KegDisplay").addHandler(file_handler)
    logging.getLogger("KegDisplay").setLevel(logging.DEBUG)
    logger.info(f"Logging to file: {log_file}")
    return log_file

class NetworkTest:
    """Run database sync tests over a real network"""
    
    def __init__(self, role, other_ips=None, broadcast_port=5002):
        """Initialize the test instance
        
        Args:
            role: 'primary' or 'secondary'
            other_ips: List of known peer IPs (optional)
            broadcast_port: Port to use for discovery broadcasts
        """
        self.role = role
        self.other_ips = other_ips or []
        self.broadcast_port = broadcast_port
        self.instance = None
        
        # Setup signal handlers for graceful shutdown
        self._setup_signal_handlers()
        
        # Setup logging to file
        self.log_file = setup_file_logging(role)
        
        # Create a temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, f'test_db_{role}.db')
        
        # Base port for sync operations
        self.sync_port = 5003
        
        # Create initial database
        self._create_initial_db()
        
        try:
            # Initialize the database sync system
            self._initialize_db_sync()
            
            # Log network information
            self._log_network_info()
            
            # If we have explicit other_ips, add them directly
            if self.other_ips:
                self._add_manual_peers()
                
        except KeyboardInterrupt:
            logger.info("Initialization interrupted by user")
            self.cleanup()
            sys.exit(0)
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            self.cleanup()
            sys.exit(1)
            
    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown"""
        # Store original handlers to restore them later if needed
        self.original_sigint = signal.getsignal(signal.SIGINT)
        self.original_sigterm = signal.getsignal(signal.SIGTERM)
        
        # Set up handler for graceful shutdown
        def signal_handler(sig, frame):
            logger.info("\nReceived interrupt signal. Cleaning up and shutting down gracefully...")
            self.cleanup()
            logger.info(f"Cleanup complete. Log file: {self.log_file}")
            sys.exit(0)
            
        # Register the signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _initialize_db_sync(self):
        """Initialize the database sync system"""
        # Create database sync instance with timeout for initial peer discovery
        logger.info(f"Creating DatabaseSync instance with broadcast_port={self.broadcast_port}, sync_port={self.sync_port}, test_mode=False")
        
        # Override the default initial peer discovery to use a shorter timeout
        original_discovery = DatabaseSync._initial_peer_discovery
        
        def shorter_discovery(instance):
            """Modified discovery method with shorter timeout and interrupt handling"""
            logger.info("Starting initial peer discovery")
            try:
                logger.info(f"Broadcasting discovery message on port {instance.broadcast_port}")
                message = json.dumps({
                    'version': instance._get_db_version(),
                    'sync_port': instance.sync_port
                }).encode('utf-8')
                instance.broadcast_socket.sendto(message, ('255.255.255.255', instance.broadcast_port))
                
                # Set a shorter timeout for test purposes
                instance.broadcast_socket.settimeout(1.0)
                
                logger.info("Waiting 1 second for peer responses...")
                start_time = time.time()
                while time.time() - start_time < 1.0:
                    try:
                        data, addr = instance.broadcast_socket.recvfrom(1024)
                        ip = addr[0]
                        
                        # Skip messages from ourselves
                        if ip in instance.local_ips:
                            continue
                            
                        # Process peer data (same as original method)
                        try:
                            # Try to parse as JSON (new format with sync_port)
                            peer_data = json.loads(data.decode('utf-8'))
                            peer_version = peer_data['version']
                            peer_sync_port = peer_data.get('sync_port', instance.sync_port)
                            instance.add_peer(ip, peer_version, peer_sync_port)
                        except (json.JSONDecodeError, KeyError):
                            # Fall back to old format (just version string)
                            peer_version = data.decode('utf-8')
                            instance.add_peer(ip, peer_version, instance.sync_port)
                        
                    except socket.timeout:
                        # Expected when no peer responses within timeout
                        break
                    except KeyboardInterrupt:
                        logger.info("Peer discovery interrupted")
                        raise
                    except Exception as e:
                        logger.error(f"Error during peer discovery: {e}")
                
                # Reset socket timeout
                instance.broadcast_socket.settimeout(None)
                
                # Start the regular listener threads - simplified implementation
                if hasattr(instance, 'threads') and instance.threads:
                    for thread in instance.threads:
                        if not thread.is_alive():
                            thread.start()
                
            except KeyboardInterrupt:
                raise
            except Exception as e:
                logger.error(f"Error in initial peer discovery: {e}")
                
        
        # Temporarily replace the discovery method
        DatabaseSync._initial_peer_discovery = shorter_discovery
        
        try:
            # Create the instance with our modified discovery method
            self.instance = DatabaseSync(
                db_path=self.db_path,
                broadcast_port=self.broadcast_port,
                sync_port=self.sync_port,
                test_mode=False  # Use real network operations
            )
            
            logger.info(f"Initialized {self.role} instance with sync port {self.sync_port}")
            logger.info(f"Database path: {self.db_path}")
            
        finally:
            # Restore the original discovery method
            DatabaseSync._initial_peer_discovery = original_discovery
    
    def _create_initial_db(self):
        """Create an initial database with some test data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beers (
                idBeer integer primary key,
                Name tinytext NOT NULL,
                ABV float DEFAULT NULL,
                Description text DEFAULT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taps (
                idTap integer primary key,
                idBeer integer
            )
        ''')
        
        # Add some initial data
        cursor.execute('''
            INSERT INTO beers (Name, ABV, Description) VALUES 
            ('Test Beer 1', 5.0, 'Initial test beer'),
            ('Test Beer 2', 6.0, 'Another test beer')
        ''')
        
        cursor.execute('''
            INSERT INTO taps (idTap, idBeer) VALUES 
            (1, 1),
            (2, 2)
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created initial database at {self.db_path}")
    
    def _log_network_info(self):
        """Log network interface information to help with debugging"""
        try:
            # Get hostname
            hostname = socket.gethostname()
            logger.info(f"Hostname: {hostname}")
            
            # Get IP addresses
            try:
                host_ip = socket.gethostbyname(hostname)
                logger.info(f"Host IP: {host_ip}")
            except Exception as e:
                logger.error(f"Error getting host IP: {e}")
            
            # Get all network interfaces more safely
            logger.info("Network interfaces:")
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    try:
                        addresses = netifaces.ifaddresses(interface)
                        if netifaces.AF_INET in addresses:
                            for address in addresses[netifaces.AF_INET]:
                                logger.info(f"  {interface}: {address['addr']}")
                    except Exception as e:
                        logger.error(f"Error getting info for interface {interface}: {e}")
            except ImportError:
                # Fallback if netifaces is not available
                try:
                    import subprocess
                    # Try to get interfaces using ifconfig command
                    try:
                        result = subprocess.check_output(['ifconfig']).decode('utf-8')
                        logger.info("Network interfaces from ifconfig:")
                        for line in result.split('\n'):
                            if 'inet ' in line:
                                logger.info(f"  {line.strip()}")
                    except:
                        # Try using ip addr command
                        try:
                            result = subprocess.check_output(['ip', 'addr']).decode('utf-8')
                            logger.info("Network interfaces from ip addr:")
                            for line in result.split('\n'):
                                if 'inet ' in line:
                                    logger.info(f"  {line.strip()}")
                        except:
                            logger.error("Could not get network interfaces with subprocess commands")
                except Exception as e:
                    logger.error(f"Error using subprocess for network interfaces: {e}")
                
            # Test local broadcast
            logger.info(f"Testing broadcast on port {self.broadcast_port}...")
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
    
    def make_change(self):
        """Make a change to the database (primary only)"""
        if self.role != 'primary':
            logger.error("Only primary instance should make changes")
            return False
        
        try:
            beer_name = f"New Beer {random.randint(100, 999)}"
            abv = round(random.uniform(4.0, 10.0), 1)
            
            logger.info(f"Making database change: Adding beer '{beer_name}' with ABV {abv}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert the new beer
                cursor.execute('''
                    INSERT INTO beers (Name, ABV, Description)
                    VALUES (?, ?, ?)
                ''', (beer_name, abv, f'Test beer {beer_name}'))
                
                # Get the rowid of the inserted record
                row_id = cursor.lastrowid
                logger.info(f"Inserted new beer with rowid {row_id}")
                
                # Log the change manually to see it in our test logs
                timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                cursor.execute(f"SELECT * FROM beers WHERE rowid = ?", (row_id,))
                row = cursor.fetchone()
                content_hash = hashlib.md5(str(row).encode()).hexdigest()
                
                logger.info(f"Adding to change_log: table=beers, operation=INSERT, row_id={row_id}, timestamp={timestamp}")
                cursor.execute('''
                    INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('beers', 'INSERT', row_id, timestamp, content_hash))
                
                # Update version timestamp
                cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
                
                conn.commit()
            
            # Notify the database sync system of the change
            logger.info("Calling notify_update() to broadcast change to peers")
            self.instance.notify_update()
            
            logger.info(f"Made change: Added beer '{beer_name}' with ABV {abv}")
            
            # Log database version
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_modified FROM version")
                version = cursor.fetchone()[0]
                logger.info(f"Current database version timestamp: {version}")
                
                # Log change log entries
                cursor.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT 5")
                changes = cursor.fetchall()
                logger.info(f"Recent change log entries:")
                for change in changes:
                    logger.info(f"  {change}")
                
            return beer_name
            
        except Exception as e:
            logger.error(f"Error making change: {e}")
            return False
    
    def verify_change(self, beer_name):
        """Verify a change has been received (secondary only)"""
        if self.role != 'secondary':
            logger.error("Only secondary instance should verify changes")
            return False
        
        try:
            # Wait for sync to complete
            logger.info(f"Waiting for sync to complete before verifying change for beer '{beer_name}'")
            time.sleep(5)
            
            # Log database version before checking
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_modified FROM version")
                version = cursor.fetchone()[0]
                logger.info(f"Current database version timestamp: {version}")
                
                # Log all beers in database
                cursor.execute("SELECT rowid, * FROM beers")
                beers = cursor.fetchall()
                logger.info(f"All beers in database:")
                for beer in beers:
                    logger.info(f"  {beer}")
                
                # Log change log entries
                cursor.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT 5")
                changes = cursor.fetchall()
                logger.info(f"Recent change log entries:")
                for change in changes:
                    logger.info(f"  {change}")
                
                # Check for the specific beer
                cursor.execute("SELECT Name, ABV FROM beers WHERE Name = ?", (beer_name,))
                result = cursor.fetchone()
            
            if result:
                logger.info(f"✅ VERIFICATION SUCCESSFUL: Beer '{result[0]}' with ABV {result[1]} found")
                return True
            else:
                logger.error(f"❌ VERIFICATION FAILED: Beer '{beer_name}' not found in database")
                return False
                
        except Exception as e:
            logger.error(f"Error verifying change: {e}")
            return False
    
    def run_primary_test(self):
        """Run the test as the primary instance"""
        try:
            logger.info("=== STARTING PRIMARY TEST SEQUENCE ===")
            
            # Generate the beer name first
            beer_name = f"New Beer {random.randint(100, 999)}"
            abv = round(random.uniform(4.0, 10.0), 1)
            
            # Print instructions for secondary BEFORE making changes
            logger.info("\n=== INSTRUCTIONS FOR SECONDARY INSTANCES ===")
            logger.info("Please start the secondary instance now with:")
            logger.info(f"poetry run python -m KegDisplay.tests.network_test secondary --primary-ip <THIS_MACHINE_IP>")
            logger.info("\nAfter secondary is running, the primary will make a test change.")
            logger.info("You can verify the change was received with:")
            logger.info(f"poetry run python -m KegDisplay.tests.network_test verify --beer-name \"{beer_name}\" --primary-ip <THIS_MACHINE_IP>")
            logger.info("=======================================\n")
            
            # Log peers before the test
            self._log_peers()
            
            
            logger.info(f"Waiting for secondary instances to connect ({len(self.other_ips)} expected)...")
            time.sleep(10)  # Give time for secondary instances to start
            
            # Log peers after wait
            self._log_peers()
            
            # Make the test change with the pre-generated name
            logger.info("Creating a test change")
            self._make_change(beer_name, abv)
            
            # Give time for changes to propagate and log peers again
            time.sleep(5)
            self._log_peers()
            
            # Display reminder of verification command
            logger.info("\n=== VERIFICATION INSTRUCTIONS ===")
            logger.info(f"Verify the change was received with:")
            logger.info(f"poetry run python -m KegDisplay.tests.network_test verify --beer-name \"{beer_name}\" --primary-ip <THIS_MACHINE_IP>")
            logger.info("================================\n")
            
            logger.info("Test complete. Check secondary instances for successful sync.")
            logger.info(f"Log file: {self.log_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error in primary test: {e}")
            return False
        finally:
            self.cleanup()
    
    def run_secondary_test(self):
        """Run the test as a secondary instance"""
        try:
            logger.info("=== STARTING SECONDARY TEST SEQUENCE ===")
            logger.info("Waiting for changes from primary instance...")
            
            # Log initial database state
            self._log_database_state()
            
            # Log peers
            self._log_peers()
            
            # Wait and periodically check for changes
            start_time = time.time()
            check_interval = 10  # seconds
            max_wait_time = 120  # seconds
            
            while time.time() - start_time < max_wait_time:
                # Log database state and peers
                self._log_database_state()
                self._log_peers()
                
                time.sleep(check_interval)
                logger.info(f"Still waiting for changes... ({int(time.time() - start_time)}s elapsed)")
            
            logger.info("Test listening period complete.")
            logger.info(f"Log file: {self.log_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error in secondary test: {e}")
            return False
        finally:
            self.cleanup()
    
    def _log_database_state(self):
        """Log the current state of the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Log version
                cursor.execute("SELECT last_modified FROM version")
                version = cursor.fetchone()
                logger.info(f"Database version timestamp: {version[0] if version else 'Unknown'}")
                
                # Log beer count
                cursor.execute("SELECT COUNT(*) FROM beers")
                count = cursor.fetchone()[0]
                logger.info(f"Beer count: {count}")
                
                # Log most recent beers
                cursor.execute("SELECT rowid, * FROM beers ORDER BY rowid DESC LIMIT 3")
                beers = cursor.fetchall()
                if beers:
                    logger.info("Most recent beers:")
                    for beer in beers:
                        logger.info(f"  {beer}")
                
                # Log change log entries
                cursor.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT 3")
                changes = cursor.fetchall()
                if changes:
                    logger.info("Recent change log entries:")
                    for change in changes:
                        logger.info(f"  {change}")
        except Exception as e:
            logger.error(f"Error logging database state: {e}")
    
    def _log_peers(self):
        """Log information about peers"""
        try:
            peer_count = len(self.instance.peers)
            logger.info(f"Current peer count: {peer_count}")
            
            if peer_count > 0:
                logger.info("Peers:")
                for ip, peer_data in self.instance.peers.items():
                    if len(peer_data) >= 3:
                        version, last_seen, sync_port = peer_data
                        time_diff = time.time() - last_seen
                        logger.info(f"  {ip}: version={version}, sync_port={sync_port}, last_seen={time_diff:.1f}s ago")
                    else:
                        # Handle legacy format just in case
                        version, last_seen = peer_data[0], peer_data[1]
                        time_diff = time.time() - last_seen
                        logger.info(f"  {ip}: version={version}, last_seen={time_diff:.1f}s ago")
        except Exception as e:
            logger.error(f"Error logging peers: {e}")
    
    def verify_specific_beer(self, beer_name):
        """Verify a specific beer name has been synchronized"""
        # First check if we have any peers
        self._check_network_connectivity()
        return self.verify_change(beer_name)
    
    def _check_network_connectivity(self):
        """Check and troubleshoot network connectivity issues"""
        logger.info("Checking network connectivity...")
        
        # Check if we have any peers
        peer_count = len(self.instance.peers)
        logger.info(f"Current peer count: {peer_count}")
        
        if peer_count == 0:
            logger.warning("⚠️ NO PEERS DETECTED - Network connectivity issues detected")
            
            # 1. Try to get local IP addresses
            local_ips = self._get_local_ips()
            logger.info(f"Local IP addresses: {local_ips}")
            
            # 2. Try manual ping to discover potential peers
            self._try_manual_discovery()
            
            # 3. Check firewall status
            self._check_firewall()
            
            # 4. Check if broadcast is working
            self._test_broadcast()
            
            # 5. Provide troubleshooting suggestions
            logger.warning("\n===== TROUBLESHOOTING SUGGESTIONS =====")
            logger.warning("1. Ensure primary instance is running")
            logger.warning("2. Check that both machines are on the same network")
            logger.warning("3. Verify firewall settings allow UDP port 5002 (broadcast) and TCP ports 5003/5004 (sync)")
            logger.warning("4. Try specifying the primary IP directly:")
            for ip in local_ips:
                parts = ip.split('.')
                if len(parts) == 4:
                    network_prefix = '.'.join(parts[0:3])
                    logger.warning(f"   - Check for devices on network {network_prefix}.*")
            logger.warning("=====================================\n")
        else:
            logger.info(f"✅ Connected to {peer_count} peers")
            self._log_peers()

    def _get_local_ips(self):
        """Get a list of all local IP addresses"""
        ips = []
        try:
            # First try: using hostname
            try:
                hostname = socket.gethostname()
                ip = socket.gethostbyname(hostname)
                
                if ip != '127.0.0.1' and ip != '127.0.1.1':
                    logger.info(f"Found local IP using hostname method: {ip}")
                    ips.append(ip)
            except Exception as e:
                logger.error(f"Error getting IP via hostname: {e}")
            
            # Try secondary method
            try:
                import netifaces
                for interface in netifaces.interfaces():
                    try:
                        addresses = netifaces.ifaddresses(interface)
                        if netifaces.AF_INET in addresses:
                            for address in addresses[netifaces.AF_INET]:
                                if 'addr' in address and address['addr'] != '127.0.0.1' and address['addr'] != '127.0.1.1':
                                    ips.append(address['addr'])
                    except:
                        pass
            except ImportError:
                # Fallback if netifaces is not available
                try:
                    import subprocess
                    try:
                        result = subprocess.check_output(['hostname', '-I']).decode('utf-8').strip()
                        if result:
                            ips.extend([ip.strip() for ip in result.split(' ') if ip.strip()])
                    except:
                        pass
                except:
                    pass
        except Exception as e:
            logger.error(f"Error getting local IPs: {e}")
        
        return ips

    def _try_manual_discovery(self):
        """Try to manually discover peers on the network"""
        logger.info("Attempting manual peer discovery...")
        try:
            # Try sending a discovery message again
            msg = json.dumps({
                'type': 'discovery',
                'version': self.instance.version,
                'sync_port': self.instance.sync_port  # Include our sync port
            }).encode()
            
            logger.info(f"Broadcasting discovery message on port {self.instance.broadcast_port}")
            self.instance.broadcast_socket.sendto(msg, ('<broadcast>', self.instance.broadcast_port))
            
            # Wait for responses
            discovery_time = 10  # seconds
            start_time = time.time()
            logger.info(f"Waiting {discovery_time} seconds for peer responses...")
            
            discovered = False
            while time.time() - start_time < discovery_time:
                try:
                    self.instance.broadcast_socket.settimeout(0.5)
                    data, addr = self.instance.broadcast_socket.recvfrom(1024)
                    msg = json.loads(data.decode())
                    
                    # Use the list of local IPs rather than just the main one
                    if addr[0] not in self.instance.local_ips:
                        peer_sync_port = msg.get('sync_port', self.instance.sync_port)
                        logger.info(f"✅ Discovered peer at {addr[0]} with version {msg.get('version', 'unknown')} (sync port: {peer_sync_port})")
                        discovered = True
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Discovery error: {e}")
            
            if not discovered:
                logger.warning("❌ No peers discovered during manual discovery")
            
        except Exception as e:
            logger.error(f"Error during manual discovery: {e}")

    def _check_firewall(self):
        """Check firewall status"""
        logger.info("Checking firewall status...")
        try:
            import subprocess
            
            # Try different commands based on OS
            try:
                # Linux - iptables
                result = subprocess.check_output(['iptables', '-L'], stderr=subprocess.STDOUT).decode('utf-8')
                logger.info("Firewall info (iptables):")
                for line in result.split('\n')[:10]:  # Show first 10 lines
                    if line.strip():
                        logger.info(f"  {line.strip()}")
            except:
                try:
                    # Linux - ufw
                    result = subprocess.check_output(['ufw', 'status'], stderr=subprocess.STDOUT).decode('utf-8')
                    logger.info("Firewall info (ufw):")
                    for line in result.split('\n'):
                        if line.strip():
                            logger.info(f"  {line.strip()}")
                except:
                    logger.info("Could not determine firewall status")
        except Exception as e:
            logger.error(f"Error checking firewall: {e}")

    def _test_broadcast(self):
        """Test if broadcast is working"""
        logger.info("Testing broadcast capability...")
        try:
            # Try sending a broadcast on a different test port
            test_port = self.instance.broadcast_port + 1000  # Use a different port
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Don't bind, just send
            msg = "broadcast_test".encode()
            logger.info(f"Sending test broadcast on port {test_port}")
            
            try:
                test_socket.sendto(msg, ('<broadcast>', test_port))
                logger.info("✅ Test broadcast sent successfully")
            except Exception as e:
                logger.error(f"❌ Error sending test broadcast: {e}")
            
            test_socket.close()
        except Exception as e:
            logger.error(f"Error testing broadcast: {e}")
    
    def cleanup(self):
        """Clean up resources before exit"""
        logger.info("Cleaning up resources...")
        
        # Stop the DatabaseSync instance
        if hasattr(self, 'instance') and self.instance:
            logger.info("Stopping DatabaseSync instance...")
            try:
                # Stop the DatabaseSync instance properly
                self.instance.stop()
                logger.info("DatabaseSync instance stopped")
                
            except Exception as e:
                logger.error(f"Error stopping DatabaseSync instance: {e}")
        
        # Close the database connection
        try:
            if hasattr(self, 'instance') and hasattr(self.instance, 'conn') and self.instance.conn:
                self.instance.conn.close()
                # Set to None to prevent further use
                self.instance.conn = None
                logger.info("Closed database connection")
        except Exception as e:
            logger.error(f"Error closing database connection: {e}")
        
        # Remove temporary directory
        try:
            if hasattr(self, 'temp_dir') and self.temp_dir and os.path.exists(self.temp_dir):
                # On Windows, there might be permission issues with removing temp dir immediately
                try:
                    shutil.rmtree(self.temp_dir)
                    logger.info(f"Removed temporary directory: {self.temp_dir}")
                except Exception as e:
                    logger.warning(f"Could not remove temp directory {self.temp_dir} immediately: {e}")
                    logger.info("It will be cleaned up by the cleanup_temp.py script later")
        except Exception as e:
            logger.error(f"Error removing temporary directory: {e}")
        
        logger.info("Cleanup complete")

    def _add_manual_peers(self):
        """Manually add peers from the provided IP addresses"""
        if self.other_ips:
            logger.info(f"Adding manual peers from command line: {self.other_ips}")
            for ip in self.other_ips:
                logger.info(f"Adding manual peer: {ip}")
                # Use the new add_peer method
                self.instance.add_peer(ip)
                
                # Also try direct connection
                self._try_direct_connection(ip)

    def _try_direct_connection(self, peer_ip):
        """Try to directly connect to a peer"""
        logger.info(f"Attempting direct connection to {peer_ip}")
        try:
            # First try requesting full database
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)  # 5 second timeout
                port = 5003  # Primary uses 5003
                
                logger.info(f"Connecting to {peer_ip}:{port}")
                try:
                    s.connect((peer_ip, port))
                    logger.info(f"✅ Successfully connected to {peer_ip}:{port}")
                    
                    # Try sending a request
                    try:
                        s.send(json.dumps({
                            'type': 'full_db_request',
                            'version': self.instance.version
                        }).encode())
                        logger.info(f"Sent full database request to {peer_ip}")
                        
                        # Wait for response
                        try:
                            response = s.recv(1024).decode()
                            logger.info(f"✅ Received response from {peer_ip}: {response[:100]}")
                            return True
                        except socket.timeout:
                            logger.error(f"Timeout waiting for response from {peer_ip}")
                    except Exception as e:
                        logger.error(f"Error sending request to {peer_ip}: {e}")
                except ConnectionRefusedError:
                    logger.error(f"Connection refused by {peer_ip}:{port}")
                except socket.timeout:
                    logger.error(f"Connection to {peer_ip}:{port} timed out")
                except Exception as e:
                    logger.error(f"Error connecting to {peer_ip}:{port}: {e}")
            
            return False
        except Exception as e:
            logger.error(f"Error in direct connection attempt: {e}")
            return False

    def _make_change(self, beer_name, abv):
        """Make a change to the database with a specific beer name and ABV"""
        if self.role != 'primary':
            logger.error("Only primary instance should make changes")
            return False
        
        try:
            logger.info(f"Making database change: Adding beer '{beer_name}' with ABV {abv}")
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert the new beer
                cursor.execute('''
                    INSERT INTO beers (Name, ABV, Description)
                    VALUES (?, ?, ?)
                ''', (beer_name, abv, f'Test beer {beer_name}'))
                
                # Get the rowid of the inserted record
                row_id = cursor.lastrowid
                logger.info(f"Inserted new beer with rowid {row_id}")
                
                # Log the change manually to see it in our test logs
                timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
                cursor.execute(f"SELECT * FROM beers WHERE rowid = ?", (row_id,))
                row = cursor.fetchone()
                content_hash = hashlib.md5(str(row).encode()).hexdigest()
                
                logger.info(f"Adding to change_log: table=beers, operation=INSERT, row_id={row_id}, timestamp={timestamp}")
                cursor.execute('''
                    INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                    VALUES (?, ?, ?, ?, ?)
                ''', ('beers', 'INSERT', row_id, timestamp, content_hash))
                
                # Update version timestamp
                cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
                
                conn.commit()
            
            # Notify the database sync system of the change
            logger.info("Calling notify_update() to broadcast change to peers")
            self.instance.notify_update()
            
            logger.info(f"Made change: Added beer '{beer_name}' with ABV {abv}")
            
            # Log database version
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT last_modified FROM version")
                version = cursor.fetchone()[0]
                logger.info(f"Current database version timestamp: {version}")
                
                # Log change log entries
                cursor.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT 5")
                changes = cursor.fetchall()
                logger.info(f"Recent change log entries:")
                for change in changes:
                    logger.info(f"  {change}")
                
            return True
            
        except Exception as e:
            logger.error(f"Error making change: {e}")
            return False

    def _run_broadcast_thread(self):
        """Thread for broadcasting the database version periodically"""
        logger.debug("Broadcast thread starting")
        self.broadcast_thread_running = True
        
        try:
            while self.broadcast_thread_running:
                try:
                    # Broadcast the current version and sync port
                    if self.broadcast_socket:
                        with self.db_lock:
                            version = self._get_version()
                        
                        # Include the sync port in the broadcast message
                        message = json.dumps({
                            'version': version,
                            'sync_port': self.sync_port
                        }).encode('utf-8')
                        
                        if self.broadcast_socket:  # Check again in case it was closed during sleep
                            try:
                                self.broadcast_socket.sendto(message, ('255.255.255.255', self.broadcast_port))
                                logger.debug(f"Broadcast version: {version}, sync_port: {self.sync_port}")
                            except (socket.error, OSError) as e:
                                if not self.broadcast_thread_running:  # Ignore errors during shutdown
                                    break
                                logger.error(f"Broadcast error: {e}")
                
                    # Wait before the next broadcast
                    for i in range(5):  # Check for shutdown signal more frequently
                        if not self.broadcast_thread_running:
                            break
                        time.sleep(0.2)
                
                except Exception as e:
                    if not self.broadcast_thread_running:  # Ignore errors during shutdown
                        break
                    logger.error(f"Broadcast error: {e}")
                    time.sleep(1)  # Wait a bit before retrying
        except Exception as e:
            logger.error(f"Broadcast thread error: {e}")
        
        logger.debug("Broadcast thread exiting")

    def _run_listener_thread(self):
        """Thread for listening for broadcasts from peers"""
        logger.debug("Listener thread starting")
        self.listener_thread_running = True
        
        try:
            while self.listener_thread_running:
                try:
                    # Listen for broadcasts
                    if self.listener_socket:
                        try:
                            # Use a timeout to allow thread to check termination flag
                            self.listener_socket.settimeout(0.5)
                            data, addr = self.listener_socket.recvfrom(1024)
                            
                            # Process peer data - handle both old and new format
                            try:
                                # Try to parse as JSON (new format with sync_port)
                                peer_data = json.loads(data.decode('utf-8'))
                                peer_version = peer_data['version']
                                peer_sync_port = peer_data.get('sync_port', self.sync_port)
                                self.add_peer(addr[0], peer_version, peer_sync_port)
                            except (json.JSONDecodeError, KeyError):
                                # Fall back to old format (just version string)
                                peer_version = data.decode('utf-8')
                                self.add_peer(addr[0], peer_version, self.sync_port)
                            
                        except socket.timeout:
                            # This is expected - allows checking the thread_running flag
                            pass
                        except (socket.error, OSError) as e:
                            if not self.listener_thread_running:  # Ignore errors during shutdown
                                break
                            logger.error(f"Broadcast listener error: {e}")
                    else:
                        # No socket available, sleep briefly
                        time.sleep(0.5)
                    
                except Exception as e:
                    if not self.listener_thread_running:  # Ignore errors during shutdown
                        break
                    logger.error(f"Broadcast listener error: {e}")
                    time.sleep(1)  # Wait a bit before retrying
        except Exception as e:
            logger.error(f"Listener thread error: {e}")
        
        logger.debug("Listener thread exiting")

    def _run_sync_server(self):
        """Thread for serving database sync requests"""
        logger.debug("Sync server thread starting")
        self.sync_server_running = True
        
        try:
            while self.sync_server_running:
                try:
                    # Accept connections
                    if self.sync_socket:
                        try:
                            # Set a timeout to allow checking the thread_running flag
                            self.sync_socket.settimeout(0.5)
                            client_socket, addr = self.sync_socket.accept()
                            
                            # Handle client in a new thread
                            threading.Thread(
                                target=self._handle_sync_client,
                                args=(client_socket, addr),
                                daemon=True
                            ).start()
                            
                        except socket.timeout:
                            # This is expected - allows checking the thread_running flag
                            pass
                        except (socket.error, OSError) as e:
                            if not self.sync_server_running:  # Ignore errors during shutdown
                                break
                            logger.error(f"Sync listener error: {e}")
                    else:
                        # No socket available, sleep briefly
                        time.sleep(0.5)
                    
                except Exception as e:
                    if not self.sync_server_running:  # Ignore errors during shutdown
                        break
                    logger.error(f"Sync listener error: {e}")
                    time.sleep(1)  # Wait a bit before retrying
        except Exception as e:
            logger.error(f"Sync server thread error: {e}")
        
        logger.debug("Sync server thread exiting")

def verify_beer_in_database(db_path, beer_name):
    """Standalone function to verify a beer exists in a database
    
    Args:
        db_path: Path to the SQLite database
        beer_name: Name of the beer to verify
        
    Returns:
        True if the beer is found, False otherwise
    """
    logger.info(f"Verifying beer '{beer_name}' in database at {db_path}")
    
    if not os.path.exists(db_path):
        logger.error(f"Database file not found: {db_path}")
        return False
        
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Log database version
            cursor.execute("SELECT last_modified FROM version")
            version = cursor.fetchone()
            logger.info(f"Database version timestamp: {version[0] if version else 'Unknown'}")
            
            # Log all beers in database
            cursor.execute("SELECT rowid, * FROM beers")
            beers = cursor.fetchall()
            logger.info(f"All beers in database:")
            for beer in beers:
                logger.info(f"  {beer}")
            
            # Check for the specific beer
            cursor.execute("SELECT Name, ABV FROM beers WHERE Name = ?", (beer_name,))
            result = cursor.fetchone()
        
        if result:
            logger.info(f"✅ VERIFICATION SUCCESSFUL: Beer '{result[0]}' with ABV {result[1]} found")
            return True
        else:
            logger.error(f"❌ VERIFICATION FAILED: Beer '{beer_name}' not found in database")
            return False
            
    except Exception as e:
        logger.error(f"Error verifying change: {e}")
        return False

def find_secondary_database():
    """Find the most recent secondary database in temporary directories"""
    logger.info("Searching for existing secondary database...")
    
    # Search for databases in /tmp (Linux) and TEMP (Windows) directories
    temp_dirs = ['/tmp', '/var/tmp', tempfile.gettempdir()]
    
    # Search patterns to find test databases
    patterns = ['*/test_db_secondary.db', '*/tmp*/test_db_secondary.db']
    
    all_matches = []
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            for pattern in patterns:
                search_path = os.path.join(temp_dir, pattern)
                matches = glob.glob(search_path, recursive=True)
                all_matches.extend(matches)
    
    # Sort by modification time, newest first
    all_matches.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    if all_matches:
        logger.info(f"Found {len(all_matches)} potential secondary databases")
        logger.info(f"Using the most recently modified: {all_matches[0]}")
        return all_matches[0]
    else:
        logger.error("No secondary database found")
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run database sync tests over a real network")
    parser.add_argument("role", choices=["primary", "secondary", "verify"], 
                       help="Role of this instance (primary, secondary, or verify)")
    parser.add_argument("--ip", action="append", dest="ips",
                       help="IP address of other instances (can specify multiple)")
    parser.add_argument("--port", type=int, default=5002,
                       help="Broadcast port to use (default: 5002)")
    parser.add_argument("--beer-name", help="Beer name to verify (for verify command)")
    parser.add_argument("--primary-ip", help="Directly specify primary IP for secondary instance")
    parser.add_argument("--db-path", help="Directly specify the database path for verification")
    
    args = parser.parse_args()
    
    if args.role == "verify":
        if not args.beer_name:
            logger.error("Must specify --beer-name for verify command")
            sys.exit(1)
        
        # Setup file logging for verify command
        log_file = setup_file_logging("verify")
        
        # Use specified database path or find the most recent secondary database
        db_path = args.db_path
        if not db_path:
            db_path = find_secondary_database()
            
        if not db_path:
            logger.error("No database found for verification. Please specify --db-path or ensure a secondary instance is running")
            sys.exit(1)
            
        # Directly verify beer in database without creating new instance
        result = verify_beer_in_database(db_path, args.beer_name)
        logger.info(f"Verification complete. Log file: {log_file}")
        sys.exit(0 if result else 1)
    
    elif args.role in ["primary", "secondary"]:
        # Set up a test instance
        if args.role == "primary":
            test = NetworkTest("primary", args.ips, broadcast_port=args.port)
            result = test.run_primary_test()
        else:  # secondary
            # For secondary, if primary-ip is specified, add it to ips
            ips = args.ips or []
            if args.primary_ip and args.primary_ip not in ips:
                ips.append(args.primary_ip)
                
            test = NetworkTest("secondary", ips, broadcast_port=args.port)
            result = test.run_secondary_test()
        
        # Note: Signal handlers are now set up in the NetworkTest __init__ method
        
        logger.info(f"Network test running. Press Ctrl+C to stop and clean up resources.")
        
        # Keep running to allow inspection (and catch interrupts)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            # Will be caught by our signal handler
            pass
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            test.cleanup()
            sys.exit(1) 