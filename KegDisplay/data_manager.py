"""
Data Manager for KegDisplay

Handles database access and updates.
"""

import sqlite3
import logging
import time
import os
from datetime import datetime, UTC

# Use the pre-configured logger
logger = logging.getLogger("KegDisplay")

class DataManager:
    """Manages data access and updates for KegDisplay."""
    
    def __init__(self, db_path, renderer=None, update_frequency=2.5):
        """Initialize the data manager.
        
        Args:
            db_path: Path to the SQLite database
            renderer: SequenceRenderer instance to update
            update_frequency: How often to check for updates (in seconds)
        """
        self.db_path = db_path
        self.renderer = renderer
        self.update_frequency = update_frequency
        self.conn = None
        self.last_check_time = 0
        self.current_tap = None
        self.current_beer_id = None
        
    def initialize(self):
        """Initialize the database connection and load initial data.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Check if database file exists
            if not os.path.exists(self.db_path):
                logger.error(f"Database file does not exist: {os.path.abspath(self.db_path)}")
                return False
                
            # Connect to the database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Use row factory for named access
            
            # Load initial data
            if self.renderer:
                # Get current tap number from renderer
                sys_data = self.renderer._dataset.get('sys', {})
                tapnr = sys_data.get('tapnr', 1)
                
                # Get all beers
                cursor = self.conn.cursor()
                cursor.execute("SELECT idBeer, Name, Description, ABV FROM beers")
                beers = {}
                for row in cursor.fetchall():
                    beers[row['idBeer']] = {  # Keep beer_id as integer
                        'Name': row['Name'],
                        'ABV': row['ABV'],
                        'Description': row['Description']
                    }
                self.renderer.update_dataset("beers", beers, merge=True)
                
                # Get tap assignments
                cursor.execute("SELECT idTap, idBeer FROM taps")
                taps = {}
                for row in cursor.fetchall():
                    taps[row['idTap']] = row['idBeer']
                self.renderer.update_dataset("taps", taps, merge=True)
                
                # Get current beer ID for this tap
                cursor.execute("SELECT idBeer FROM taps WHERE idTap = ?", (tapnr,))
                row = cursor.fetchone()
                if row:
                    self.current_beer_id = row['idBeer']
                    self.current_tap = tapnr
                    logger.info(f"Initialized with tap {tapnr} assigned to beer {self.current_beer_id}")
                else:
                    logger.warning(f"No beer assigned to tap {tapnr}")
            
            logger.debug(f"Initialized database connection from {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return False
            
    def _beer_data_changed(self, beer_id, new_data):
        """Check if beer data has changed from what's in the renderer.
        
        Args:
            beer_id: ID of the beer to check
            new_data: New beer data from database
            
        Returns:
            bool: True if data has changed, False otherwise
        """
        current_data = self.renderer._dataset.get('beers', {}).get(beer_id, {})  # Keep beer_id as integer
        
        # Compare each field
        for field in ['Name', 'ABV', 'Description']:
            if str(current_data.get(field)) != str(new_data.get(field)):
                logger.debug(f"Beer {beer_id} {field} changed: '{current_data.get(field)}' -> '{new_data.get(field)}'")
                return True
                
        return False
            
    def update_data(self):
        """Update data from the database.
        
        Returns:
            bool: True if data was updated, False otherwise
        """
        if not self.conn or not self.renderer:
            logger.error("Database connection or renderer not initialized")
            return False
            
        try:
            current_time = time.time()
            if current_time - self.last_check_time < self.update_frequency:
                return False
                
            self.last_check_time = current_time
            
            # Get current tap number from renderer
            sys_data = self.renderer._dataset.get('sys', {})
            tapnr = sys_data.get('tapnr', 1)
            
            # Get current beer ID for this tap from database
            cursor = self.conn.cursor()
            cursor.execute("SELECT idBeer FROM taps WHERE idTap = ?", (tapnr,))
            row = cursor.fetchone()
            if not row:
                logger.warning(f"No beer assigned to tap {tapnr}")
                return False
                
            new_beer_id = row['idBeer']
            
            # Check if tap assignment changed for current tap
            if new_beer_id != self.current_beer_id:
                self.current_beer_id = new_beer_id
                self.current_tap = tapnr
                
                # Update tap mapping
                current_taps = self.renderer._dataset.get('taps', {})
                current_taps[tapnr] = new_beer_id
                self.renderer.update_dataset("taps", current_taps, merge=True)
                logger.debug(f"Updated tap mapping: tap {tapnr} -> beer {new_beer_id}")
                
                # Get beer data
                cursor.execute(
                    "SELECT idBeer, Name, Description, ABV FROM beers WHERE idBeer = ?",
                    (new_beer_id,)
                )
                beer_row = cursor.fetchone()
                if beer_row:
                    beer_data = {
                        new_beer_id: {  # Keep beer_id as integer
                            'Name': beer_row['Name'],
                            'ABV': beer_row['ABV'],
                            'Description': beer_row['Description']
                        }
                    }
                    self.renderer.update_dataset("beers", beer_data, merge=True)
                    logger.info(f"Updated beer data for tap {tapnr}: {beer_row['Name']}")
                    return True
                    
            # Check if current beer data changed
            if self.current_beer_id:
                cursor.execute(
                    "SELECT idBeer, Name, Description, ABV FROM beers WHERE idBeer = ?",
                    (self.current_beer_id,)
                )
                beer_row = cursor.fetchone()
                if beer_row:
                    new_beer_data = {
                        'Name': beer_row['Name'],
                        'ABV': beer_row['ABV'],
                        'Description': beer_row['Description']
                    }
                    
                    # Only update if data has actually changed
                    if self._beer_data_changed(self.current_beer_id, new_beer_data):
                        beer_data = {
                            self.current_beer_id: new_beer_data  # Keep beer_id as integer
                        }
                        self.renderer.update_dataset("beers", beer_data, merge=True)
                        logger.info(f"Updated beer data for beer {self.current_beer_id}: {beer_row['Name']}")
                        return True
                    
            return False
            
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        if self.conn:
            self.conn.close()
            self.conn = None 