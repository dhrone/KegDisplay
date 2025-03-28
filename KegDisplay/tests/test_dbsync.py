import unittest
import os
import shutil
import tempfile
import time
import sqlite3
import sys
from datetime import datetime, UTC
import hashlib

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dbsync import DatabaseSync

class TestDatabaseSync(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for test databases
        self.temp_dir = tempfile.mkdtemp()
        self.instances = []
        self.db_paths = []
        
        # Create 5 test database paths
        for i in range(5):
            db_path = os.path.join(self.temp_dir, f'test_db_{i}.db')
            self.db_paths.append(db_path)
            
            # Copy the initial database structure
            self._create_initial_db(db_path)
    
    def tearDown(self):
        # Stop all instances
        for instance in self.instances:
            instance.stop()
        
        # Clean up temporary files
        shutil.rmtree(self.temp_dir)
    
    def _create_initial_db(self, db_path):
        """Create an initial database with some test data"""
        conn = sqlite3.connect(db_path)
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
        
        # Create version table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS version (
                last_modified TEXT
            )
        ''')
        
        cursor.execute('''
            INSERT INTO version (last_modified) VALUES (?)
        ''', (datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),))
        
        conn.commit()
        conn.close()
    
    def _create_instance(self, index, delay=0):
        """Create a DatabaseSync instance with a delay"""
        if delay > 0:
            time.sleep(delay)
        
        instance = DatabaseSync(
            self.db_paths[index],
            broadcast_port=5002 + index,  # Note: Different broadcast ports don't affect test_mode operation
            sync_port=5003 + index,  # Different sync ports would be needed for real networking
            test_mode=True  # Enable test mode to avoid network operations
        )
        self.instances.append(instance)
        
        # Add this instance as a peer to all existing instances
        for other_instance in self.instances[:-1]:
            instance.add_test_peer(other_instance)
        
        return instance
    
    def _make_change(self, instance_index, beer_name, abv):
        """Make a change to the database of a specific instance"""
        instance = self.instances[instance_index]
        
        with sqlite3.connect(instance.db_path) as conn:
            cursor = conn.cursor()
            
            # Insert the new beer
            cursor.execute('''
                INSERT INTO beers (Name, ABV, Description)
                VALUES (?, ?, ?)
            ''', (beer_name, abv, f'Test beer {beer_name}'))
            
            # Get the rowid of the inserted record
            row_id = cursor.lastrowid
            
            # Log the change
            timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            cursor.execute(f"SELECT * FROM beers WHERE rowid = ?", (row_id,))
            row = cursor.fetchone()
            content_hash = hashlib.md5(str(row).encode()).hexdigest()
            
            cursor.execute('''
                INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
                VALUES (?, ?, ?, ?, ?)
            ''', ('beers', 'INSERT', row_id, timestamp, content_hash))
            
            # Update version timestamp
            cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
            
            conn.commit()
        
        # Sync with all peers
        for peer in instance.test_peers:
            peer._sync_with_peer(instance)
        
        # Notify other instances of the update
        instance.notify_update()
    
    def test_basic_sync(self):
        """Test basic scenario where one system has an update and another needs to receive it"""
        # Create two instances
        instance1 = self._create_instance(0)
        instance2 = self._create_instance(1)
        
        # Wait for initial sync
        time.sleep(2)
        
        # Make a change to instance1
        self._make_change(0, "New Beer 1", 7.0)
        
        # Wait for sync
        time.sleep(2)
        
        # Verify the change propagated to instance2
        conn = sqlite3.connect(self.db_paths[1])
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM beers WHERE Name = 'New Beer 1'")
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result, "Change did not propagate to instance2")
    
    def test_delayed_startup(self):
        """Test start up where one system comes up a few seconds later than the others"""
        # Create first four instances immediately
        for i in range(4):
            self._create_instance(i)
        
        # Wait a bit
        time.sleep(2)
        
        # Make a change to instance0
        self._make_change(0, "New Beer 2", 8.0)
        
        # Wait for sync
        time.sleep(2)
        
        # Create the fifth instance with a delay
        instance5 = self._create_instance(4, delay=2)
        
        # Wait for sync
        time.sleep(2)
        
        # Verify the change propagated to the delayed instance
        conn = sqlite3.connect(self.db_paths[4])
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM beers WHERE Name = 'New Beer 2'")
        result = cursor.fetchone()
        conn.close()
        
        self.assertIsNotNone(result, "Change did not propagate to delayed instance")
    
    def test_simultaneous_startup(self):
        """Test start up where all systems come up close to each other"""
        # Create all instances with minimal delay
        for i in range(5):
            self._create_instance(i, delay=0.1)
        
        # Wait for initial sync
        time.sleep(2)
        
        # Make changes to multiple instances
        self._make_change(0, "New Beer 3", 9.0)
        time.sleep(0.5)
        self._make_change(1, "New Beer 4", 10.0)
        
        # Wait for sync
        time.sleep(2)
        
        # Verify changes propagated to all instances
        for i in range(5):
            conn = sqlite3.connect(self.db_paths[i])
            cursor = conn.cursor()
            cursor.execute("SELECT Name FROM beers WHERE Name IN ('New Beer 3', 'New Beer 4')")
            results = cursor.fetchall()
            conn.close()
            
            self.assertEqual(len(results), 2, f"Changes did not propagate to instance {i}")
    
    def test_sync_during_updates(self):
        """Test updates being conducted between systems when a new system comes up"""
        # Create first two instances
        instance1 = self._create_instance(0)
        instance2 = self._create_instance(1)
        
        # Wait for initial sync
        time.sleep(2)
        
        # Start making changes between instances
        self._make_change(0, "New Beer 5", 11.0)
        time.sleep(0.5)
        self._make_change(1, "New Beer 6", 12.0)
        time.sleep(0.5)
        
        # Create third instance while changes are happening
        instance3 = self._create_instance(2, delay=1)
        
        # Wait for sync
        time.sleep(2)
        
        # Verify the new instance received all changes
        conn = sqlite3.connect(self.db_paths[2])
        cursor = conn.cursor()
        cursor.execute("SELECT Name FROM beers WHERE Name IN ('New Beer 5', 'New Beer 6')")
        results = cursor.fetchall()
        conn.close()
        
        self.assertEqual(len(results), 2, "New instance did not receive all changes")

if __name__ == '__main__':
    unittest.main() 