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
            items_processed = 0
            
            # Process all pending database updates
            while True:
                db_row = self.src.get(0.001)  # Small timeout to avoid blocking
                if db_row is None:
                    break
                
                items_processed += 1
                logger.debug(f"Database query returned: {db_row}")
                
                for key, value in db_row.items():
                    if key == 'beer':
                        logger.debug(f"Processing beer data: {value}")
                        if isinstance(value, dict):
                            self.renderer.update_dataset("beers", value, merge=True)
                            updates_found = True
                        else:
                            for item in value:
                                if 'idBeer' in item:
                                    beer_id = item['idBeer']
                                    beer_data = {k: v for k, v in item.items() if k != 'idBeer'}
                                    logger.debug(f"Adding beer {beer_id}: {beer_data}")
                                    self.renderer.update_dataset(
                                        "beers",
                                        {beer_id: beer_data},
                                        merge=True
                                    )
                                    updates_found = True
                    
                    if key == 'taps':
                        logger.debug(f"Processing tap data: {value}")
                        if isinstance(value, dict):
                            self.renderer.update_dataset("taps", {value['idTap']: value['idBeer']}, merge=True)
                            updates_found = True
                        else:
                            for item in value:
                                if 'idTap' in item:
                                    logger.debug(f"Adding tap {item['idTap']} with beer {item['idBeer']}")
                                    self.renderer.update_dataset("taps", {item['idTap']: item['idBeer']}, merge=True)
                                    updates_found = True
                        
            if items_processed == 0:
                logger.debug("No database updates found")
            else:
                logger.debug(f"Processed {items_processed} database updates")
                
            return updates_found
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        if self.src:
            # Any cleanup needed for database source
            pass 