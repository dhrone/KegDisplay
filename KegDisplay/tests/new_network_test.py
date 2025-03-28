import unittest
import os
import shutil
import tempfile
import time
import sqlite3
import sys
import hashlib
import argparse
import logging
import random
import json
import socket
import threading
import signal
from datetime import datetime, UTC

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import SyncedDatabase

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("NewNetworkTest")

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
    """Run database sync tests over a real network using the modular SyncedDatabase"""
    
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
        """Initialize the database sync system using the modular SyncedDatabase"""
        logger.info(f"Creating SyncedDatabase instance with broadcast_port={self.broadcast_port}, sync_port={self.sync_port}, test_mode=False")
        
        try:
            # Create the SyncedDatabase instance
            self.instance = SyncedDatabase(
                db_path=self.db_path,
                broadcast_port=self.broadcast_port,
                sync_port=self.sync_port,
                test_mode=False  # Use real network operations
            )
            
            logger.info(f"Initialized {self.role} instance with sync port {self.sync_port}")
            logger.info(f"Database path: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing SyncedDatabase: {e}")
            raise
    
    def _create_initial_db(self):
        """Create an initial database with some test data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beers (
                idBeer INTEGER PRIMARY KEY,
                Name tinytext NOT NULL,
                ABV float,
                IBU float,
                Color float,
                OriginalGravity float,
                FinalGravity float,
                Description TEXT,
                Brewed datetime,
                Kegged datetime,
                Tapped datetime,
                Notes TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS taps (
                idTap INTEGER PRIMARY KEY,
                idBeer INTEGER
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
            
            # Use SyncedDatabase's methods to add a beer which automatically logs changes
            beer_id = self.instance.add_beer(
                name=beer_name,
                abv=abv,
                description=f'Test beer {beer_name}'
            )
            
            logger.info(f"Added beer '{beer_name}' with ID {beer_id}")
            
            # Log version information from change_tracker
            version = self.instance.change_tracker.get_db_version()
            logger.info(f"Current database version: {version}")
                
            return beer_name
            
        except Exception as e:
            logger.error(f"Error making change: {e}")
            return False
    
    def run_primary_test(self):
        """Run the test as the primary instance"""
        try:
            logger.info("=== STARTING PRIMARY TEST SEQUENCE WITH MODULAR DATABASE ===")
            
            # Log peers before the test
            self._log_peers()
            
            logger.info(f"Waiting for secondary instances to connect ({len(self.other_ips)} expected)...")
            time.sleep(10)  # Give time for secondary instances to start
            
            # Log peers after wait
            self._log_peers()
            
            # Make the test change using the dedicated method
            logger.info("Creating a test change")
            beer_name = self.make_change()
            
            if not beer_name:
                logger.error("Failed to make change")
                return False
                
            logger.info(f"Created test beer: {beer_name}")
            
            # Give time for changes to propagate and log peers again
            time.sleep(5)
            self._log_peers()
            
            logger.info(f"Test completed successfully. Log file: {self.log_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error in primary test: {e}")
            return False
        finally:
            self.cleanup()
    
    def run_secondary_test(self):
        """Run the test as a secondary instance"""
        try:
            logger.info("=== STARTING SECONDARY TEST SEQUENCE WITH MODULAR DATABASE ===")
            logger.info("Waiting for changes from primary instance...")
            
            # Log initial database state
            self._log_database_state()
            
            # Track initial beers by ID
            initial_beers = self.instance.get_all_beers()
            initial_beer_ids = {beer['idBeer'] for beer in initial_beers}
            logger.info(f"Initial beer count: {len(initial_beer_ids)}")
            logger.info(f"Initial beer IDs: {initial_beer_ids}")
            
            # Log peers
            self._log_peers()
            
            # Wait and periodically check for changes
            start_time = time.time()
            check_interval = 5  # seconds - checking more frequently
            max_wait_time = 120  # seconds
            
            while time.time() - start_time < max_wait_time:
                # Log peers
                self._log_peers()
                
                # Check for new beers by comparing IDs
                current_beers = self.instance.get_all_beers()
                current_beer_ids = {beer['idBeer'] for beer in current_beers}
                
                # Find new beer IDs by set difference
                new_beer_ids = current_beer_ids - initial_beer_ids
                
                if new_beer_ids:
                    logger.info(f"✅ DETECTED CHANGE: Found {len(new_beer_ids)} new beers")
                    logger.info(f"New beer IDs: {new_beer_ids}")
                    
                    # Log the details of new beers
                    for beer in current_beers:
                        if beer['idBeer'] in new_beer_ids:
                            logger.info(f"New beer detected: ID={beer['idBeer']}, Name='{beer['Name']}', ABV={beer['ABV']}")
                    
                    # Log full database state after change
                    self._log_database_state()
                    
                    logger.info("Test completed successfully - detected changes from primary")
                    logger.info(f"Log file: {self.log_file}")
                    return True
                
                time.sleep(check_interval)
                logger.info(f"Still waiting for changes... ({int(time.time() - start_time)}s elapsed)")
            
            logger.info("⚠️ Test listening period complete without detecting changes.")
            logger.info("Either no changes were made by the primary or sync failed.")
            self._check_network_connectivity()
            logger.info(f"Log file: {self.log_file}")
            return False
            
        except Exception as e:
            logger.error(f"Error in secondary test: {e}")
            return False
        finally:
            self.cleanup()
    
    def _log_database_state(self):
        """Log the current state of the database using the SyncedDatabase API"""
        try:
            # Log version
            version = self.instance.change_tracker.get_db_version()
            logger.info(f"Database version: {version}")
            
            # Log beers using the SyncedDatabase API
            beers = self.instance.get_all_beers()
            logger.info(f"Beer count: {len(beers)}")
            
            # Log most recent beers (up to 3)
            if beers:
                logger.info("Most recent beers:")
                for beer in beers[-3:]:
                    logger.info(f"  {beer['idBeer']}: {beer['Name']} (ABV: {beer['ABV']})")
            
            # Log taps
            taps = self.instance.get_all_taps()
            logger.info(f"Tap count: {len(taps)}")
            if taps:
                logger.info("Current taps:")
                for tap in taps:
                    logger.info(f"  Tap {tap['idTap']}: Beer ID {tap['idBeer']} ({tap.get('BeerName', 'None')})")
            
            # Log recent changes from the change log table
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM change_log ORDER BY id DESC LIMIT 5")
                changes = cursor.fetchall()
                if changes:
                    logger.info("Recent change log entries:")
                    for change in changes:
                        logger.info(f"  {change}")
                
        except Exception as e:
            logger.error(f"Error logging database state: {e}")
    
    def _log_peers(self):
        """Log information about the connected peers"""
        try:
            # In SyncedDatabase, peers are in synchronizer
            if hasattr(self.instance, 'synchronizer'):
                with self.instance.synchronizer.lock:
                    peer_count = len(self.instance.synchronizer.peers)
                    logger.info(f"Connected peers: {peer_count}")
                    
                    for ip, peer_data in self.instance.synchronizer.peers.items():
                        version, last_seen, sync_port = peer_data
                        time_diff = time.time() - last_seen
                        logger.info(f"  Peer {ip}:{sync_port}, Last seen: {time_diff:.1f}s ago, Version: {version}")
            else:
                logger.info("No synchronizer available - possibly in test mode")
                
        except Exception as e:
            logger.error(f"Error logging peers: {e}")
    
    def _check_network_connectivity(self):
        """Perform network connectivity checks to help debug syncing issues"""
        logger.info("Checking network connectivity...")
        
        # Check if we can reach the other IPs
        for ip in self.other_ips:
            try:
                logger.info(f"Testing connection to {ip}...")
                # Try to connect to the sync port
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                result = s.connect_ex((ip, self.sync_port))
                if result == 0:
                    logger.info(f"✅ Connection to {ip}:{self.sync_port} successful")
                else:
                    logger.error(f"❌ Connection to {ip}:{self.sync_port} failed: {result}")
                s.close()
                
                # Try to ping the host
                try:
                    import subprocess
                    ping_cmd = ['ping', '-c', '1', '-W', '2', ip]
                    result = subprocess.run(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    if result.returncode == 0:
                        logger.info(f"✅ Ping to {ip} successful")
                    else:
                        logger.error(f"❌ Ping to {ip} failed: {result.returncode}")
                except Exception as e:
                    logger.error(f"Error running ping test: {e}")
                
            except Exception as e:
                logger.error(f"Error testing connection to {ip}: {e}")
    
    def _add_manual_peers(self):
        """Manually add peers from other_ips list"""
        if not self.other_ips:
            logger.info("No manual peers to add")
            return
            
        logger.info(f"Manually adding {len(self.other_ips)} peers")
        for ip in self.other_ips:
            logger.info(f"Adding peer: {ip}")
            self.instance.add_peer(ip)
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        
        try:
            # Stop the SyncedDatabase instance
            if self.instance:
                logger.info("Stopping SyncedDatabase instance")
                self.instance.stop()
                self.instance = None
                logger.info("SyncedDatabase instance stopped")
            
            # Clean up temporary directory
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                logger.info(f"Removing temporary directory: {self.temp_dir}")
                shutil.rmtree(self.temp_dir)
                logger.info("Temporary directory removed")
            
            # Restore original signal handlers
            signal.signal(signal.SIGINT, self.original_sigint)
            signal.signal(signal.SIGTERM, self.original_sigterm)
            
            logger.info("Cleanup complete")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Parse command line arguments and run the test"""
    parser = argparse.ArgumentParser(description='Network test for database sync')
    parser.add_argument('role', choices=['primary', 'secondary'], 
                        help='Role for this instance (primary or secondary)')
    parser.add_argument('--peers', '-p', type=str, help='Comma-separated list of peer IP addresses')
    parser.add_argument('--port', '-P', type=int, default=5002, help='Broadcast port (default: 5002)')
    
    args = parser.parse_args()
    
    # Parse peer IPs
    peers = []
    if args.peers:
        peers = [ip.strip() for ip in args.peers.split(',') if ip.strip()]
    
    # Create and run the test
    test = NetworkTest(args.role, peers, args.port)
    
    try:
        if args.role == 'primary':
            test.run_primary_test()
        else:
            test.run_secondary_test()
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        test.cleanup()

if __name__ == '__main__':
    main() 