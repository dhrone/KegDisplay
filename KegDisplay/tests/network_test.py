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
        """Initialize the network test
        
        Args:
            role: Either 'primary' or 'secondary'
            other_ips: List of IP addresses of other instances (for primary only)
            broadcast_port: Port for broadcast communication
        """
        self.role = role
        self.other_ips = other_ips or []
        self.broadcast_port = broadcast_port
        
        # Setup logging to file
        self.log_file = setup_file_logging(role)
        
        # Create a temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, f'test_db_{role}.db')
        
        # Base port for sync operations
        self.sync_port = 5003 if role == 'primary' else 5004
        
        # Create initial database
        self._create_initial_db()
        
        # Create database sync instance
        logger.info(f"Creating DatabaseSync instance with broadcast_port={broadcast_port}, sync_port={self.sync_port}, test_mode=False")
        self.instance = DatabaseSync(
            db_path=self.db_path,
            broadcast_port=self.broadcast_port,
            sync_port=self.sync_port,
            test_mode=False  # Use real network operations
        )
        
        logger.info(f"Initialized {role} instance with sync port {self.sync_port}")
        logger.info(f"Database path: {self.db_path}")
        
        # Log network information
        self._log_network_info()
        
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
        import socket
        
        try:
            # Get hostname
            hostname = socket.gethostname()
            logger.info(f"Hostname: {hostname}")
            
            # Get IP addresses
            host_ip = socket.gethostbyname(hostname)
            logger.info(f"Host IP: {host_ip}")
            
            # Get all network interfaces
            logger.info("Network interfaces:")
            for interface, addrs in socket.getaddrinfo(socket.gethostname(), None):
                logger.info(f"  {addrs[0]} - {addrs[4][0]}")
                
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
            logger.info(f"Waiting for secondary instances to connect ({len(self.other_ips)} expected)...")
            
            # Log peers before the test
            self._log_peers()
            
            time.sleep(10)  # Give time for secondary instances to start
            
            # Log peers after wait
            self._log_peers()
            
            # Make a test change
            logger.info("Creating a test change")
            beer_name = self.make_change()
            if not beer_name:
                return False
            
            # Print instructions for secondary
            logger.info("\n=== INSTRUCTIONS FOR SECONDARY INSTANCES ===")
            logger.info(f"Please verify the beer '{beer_name}' has been synchronized")
            logger.info(f"Run with: poetry run python -m KegDisplay.tests.network_test verify --beer-name \"{beer_name}\"")
            logger.info("=======================================\n")
            
            # Give time for changes to propagate and log peers again
            time.sleep(5)
            self._log_peers()
            
            # Wait for verification
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
                for ip, (version, last_seen) in self.instance.peers.items():
                    time_diff = time.time() - last_seen
                    logger.info(f"  {ip}: version={version}, last_seen={time_diff:.1f}s ago")
        except Exception as e:
            logger.error(f"Error logging peers: {e}")
    
    def verify_specific_beer(self, beer_name):
        """Verify a specific beer name has been synchronized"""
        return self.verify_change(beer_name)
    
    def cleanup(self):
        """Clean up resources"""
        try:
            # Stop the database sync instance
            self.instance.stop()
            
            # Don't remove the temp dir yet so we can inspect it
            logger.info(f"Database remains at {self.db_path} for inspection")
            logger.info(f"Remember to clean up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run database sync tests over a real network")
    parser.add_argument("role", choices=["primary", "secondary", "verify"], 
                       help="Role of this instance (primary, secondary, or verify)")
    parser.add_argument("--ip", action="append", dest="ips",
                       help="IP address of other instances (for primary only, can specify multiple)")
    parser.add_argument("--port", type=int, default=5002,
                       help="Broadcast port to use (default: 5002)")
    parser.add_argument("--beer-name", help="Beer name to verify (for verify command)")
    
    args = parser.parse_args()
    
    if args.role == "verify":
        if not args.beer_name:
            logger.error("Must specify --beer-name for verify command")
            sys.exit(1)
            
        test = NetworkTest("secondary", broadcast_port=args.port)
        result = test.verify_specific_beer(args.beer_name)
        sys.exit(0 if result else 1)
    
    elif args.role == "primary":
        test = NetworkTest("primary", args.ips, broadcast_port=args.port)
        result = test.run_primary_test()
        # Keep running to allow inspection
        while True:
            time.sleep(1)
    
    elif args.role == "secondary":
        test = NetworkTest("secondary", broadcast_port=args.port)
        result = test.run_secondary_test()
        # Keep running to allow inspection
        while True:
            time.sleep(1) 