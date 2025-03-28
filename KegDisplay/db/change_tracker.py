"""
Change tracking module for KegDisplay.
Handles tracking and recording database changes.
"""

import sqlite3
import logging
import hashlib
import os
from datetime import datetime, UTC

logger = logging.getLogger("KegDisplay")

class ChangeTracker:
    """
    Handles change tracking for the KegDisplay system.
    Manages the change_log and version tables, tracks changes,
    and provides utilities for managing database versions.
    """
    
    def __init__(self, db_manager):
        """Initialize the change tracker
        
        Args:
            db_manager: DatabaseManager instance
        """
        self.db_manager = db_manager
        self.initialize_tracking()
    
    def initialize_tracking(self):
        """Initialize the change tracking system"""
        with sqlite3.connect(self.db_manager.db_path) as conn:
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
            logger.info("Change tracking tables initialized")
    
    def ensure_valid_session(self):
        """Ensure we have a valid tracking session"""
        try:
            # Test if session is still valid
            self.get_changes_since('1970-01-01T00:00:00Z')
        except sqlite3.Error:
            # If session is invalid, create a new one
            logger.warning("Session invalid, creating new session")
            self.initialize_tracking()
    
    def log_change(self, table_name, operation, row_id):
        """Log a database change
        
        Args:
            table_name: Name of the table being changed
            operation: Operation type (INSERT, UPDATE, DELETE)
            row_id: ID of the row being changed
        """
        self.ensure_valid_session()
        
        with sqlite3.connect(self.db_manager.db_path) as conn:
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
            
            logger.debug(f"Logged {operation} operation on {table_name} for row {row_id}")
    
    def get_changes_since(self, last_timestamp, batch_size=1000):
        """Get all changes since a given timestamp
        
        Args:
            last_timestamp: Timestamp to get changes since
            batch_size: Size of batches to fetch (to avoid memory issues)
            
        Returns:
            changes: List of changes since the timestamp
        """
        changes = []
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT table_name, operation, row_id, timestamp, content_hash
                FROM change_log
                WHERE timestamp > ?
                ORDER BY timestamp
            ''', (last_timestamp,))
            
            # Use fetchmany to avoid memory issues with large result sets
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                changes.extend(batch)
                
                # Optional safety check for extremely large result sets
                if len(changes) > 100000:  # Arbitrary large threshold
                    logger.warning(f"Extremely large change set detected ({len(changes)} records). Consider implementing change log pruning.")
            
        return changes
    
    def apply_changes(self, changes):
        """Apply changes from a changeset
        
        Args:
            changes: List of changes to apply
            
        Returns:
            success: True if all changes applied successfully, False otherwise
        """
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            last_timestamp = None
            
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
                    
                    last_timestamp = timestamp
                
                except sqlite3.Error as e:
                    logger.error(f"Error applying change: {e}")
                    continue
            
            # Update version timestamp
            if last_timestamp:
                cursor.execute("UPDATE version SET last_modified = ?", (last_timestamp,))
            
            conn.commit()
            logger.info(f"Applied {len(changes)} changes to database")
            
            return True
    
    def get_db_version(self):
        """Calculate database version based on content and get timestamp
        
        Returns:
            version: Dictionary with hash and timestamp
        """
        if not os.path.exists(self.db_manager.db_path):
            return {"hash": "0", "timestamp": "1970-01-01T00:00:00Z"}
        
        with sqlite3.connect(self.db_manager.db_path) as conn:
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
    
    def _get_table_hash(self, table_name):
        """Calculate a hash of the table's contents
        
        Args:
            table_name: Name of the table to hash
            
        Returns:
            hash: MD5 hash of the table's contents
        """
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"SELECT * FROM {table_name} ORDER BY rowid")
                rows = cursor.fetchall()
                if not rows:
                    return "0"
                return hashlib.md5(str(rows).encode()).hexdigest()
            except sqlite3.Error as e:
                logger.error(f"Error calculating hash for {table_name}: {e}")
                return "0"
    
    def prune_change_log(self, days_to_keep=30):
        """Prune old entries from the change log
        
        Args:
            days_to_keep: Number of days of changes to keep
            
        Returns:
            count: Number of records deleted
        """
        cutoff_date = (datetime.now(UTC) - datetime.timedelta(days=days_to_keep)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        with sqlite3.connect(self.db_manager.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM change_log WHERE timestamp < ?", (cutoff_date,))
            deleted_count = cursor.rowcount
            conn.commit()
        
        logger.info(f"Pruned {deleted_count} old entries from change_log")
        return deleted_count
    
    def is_newer_version(self, version1, version2):
        """Determine if version1 is newer than version2 based on timestamps
        
        Args:
            version1: Version dict with hash and timestamp
            version2: Version dict with hash and timestamp
            
        Returns:
            is_newer: True if version1 is newer than version2
        """
        # If version2 is empty database, any other version is newer
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