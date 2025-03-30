"""
Data Manager for KegDisplay

Handles database access and updates.
"""

import logging
from pyAttention.source import database

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
        self.src = None
        
    def initialize(self):
        """Initialize the database connection.
        
        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Initialize database source
            self.src = database(f'sqlite+aiosqlite:///{self.db_path}')
            
            # Add queries for beer and tap data
            self.src.add("SELECT idBeer, Name, Description, ABV from beers", name='beer', frequency=self.update_frequency)
            self.src.add("SELECT idTap, idBeer from taps", name='taps', frequency=self.update_frequency)
            
            logger.debug(f"Initialized database source from {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            return False
    
    def update_data(self):
        """Update data from the database source.
        
        Returns:
            bool: True if data was updated, False otherwise
        """
        if not self.src or not self.renderer:
            logger.error("Database source or renderer not initialized")
            return False
            
        try:
            updates_found = False
            
            # Process all pending database updates
            while True:
                db_row = self.src.get(0.001)  # Small timeout to avoid blocking
                if db_row is None:
                    break
                
                for key, value in db_row.items():
                    if key == 'beer':
                        if isinstance(value, dict):
                            self.renderer.update_dataset("beers", value, merge=True)
                            updates_found = True
                        else:
                            for item in value:
                                if 'idBeer' in item:
                                    self.renderer.update_dataset(
                                        "beers",
                                        {item['idBeer']: {k: v for k, v in item.items() if k != 'idBeer'}},
                                        merge=True
                                    )
                                    updates_found = True
                    
                    if key == 'taps':
                        if isinstance(value, dict):
                            self.renderer.update_dataset("taps", {value['idTap']: value['idBeer']}, merge=True)
                            updates_found = True
                        else:
                            for item in value:
                                if 'idTap' in item:
                                    self.renderer.update_dataset("taps", {item['idTap']: item['idBeer']}, merge=True)
                                    updates_found = True
                        
            return updates_found
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        if self.src:
            # Any cleanup needed for database source
            pass 