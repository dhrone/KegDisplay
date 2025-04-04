"""
Data Manager for KegDisplay

Handles database access and updates.
"""

import logging
from pyAttention.source import database

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
                db_row_str = str(db_row)
                if len(db_row_str) > 80:
                    db_row_str = db_row_str[:77] + "..."
                # Only log detailed DB rows at trace level (which isn't used by default)
                
                for key, value in db_row.items():
                    if key == 'beer':
                        # Remove redundant logging of beer data processing
                        if isinstance(value, dict):
                            self.renderer.update_dataset("beers", value, merge=True)
                            updates_found = True
                        else:
                            for item in value:
                                if 'idBeer' in item:
                                    beer_id = item['idBeer']
                                    beer_data = {k: v for k, v in item.items() if k != 'idBeer'}
                                    # Only log the first beer to avoid flooding the logs
                                    if beer_id == 1:
                                        beerstr = f"Adding beer {beer_id}: {beer_data}"
                                        beerstr = beerstr[:80]
                                        logger.debug(beerstr)
                                    self.renderer.update_dataset(
                                        "beers",
                                        {beer_id: beer_data},
                                        merge=True
                                    )
                                    updates_found = True
                    
                    if key == 'taps':
                        # Only log significant tap changes
                        if isinstance(value, dict):
                            tap_id = value.get('idTap')
                            beer_id = value.get('idBeer')
                            if tap_id and beer_id:
                                logger.debug(f"Updated tap {tap_id} with beer {beer_id}")
                                self.renderer.update_dataset("taps", {tap_id: beer_id}, merge=True)
                                updates_found = True
                        else:
                            for item in value:
                                if 'idTap' in item:
                                    tap_id = item['idTap']
                                    beer_id = item['idBeer']
                                    logger.debug(f"Updated tap {tap_id} with beer {beer_id}")
                                    self.renderer.update_dataset("taps", {tap_id: beer_id}, merge=True)
                                    updates_found = True
            
            if updates_found:
                logger.debug(f"Processed {items_processed} database updates")
            
            return updates_found
        except Exception as e:
            logger.error(f"Error updating data: {e}")
            return False
            
    def load_all_data(self):
        """Load all data from the database.
        
        This method performs an initial load of data from the database.
        It's a convenience method that just calls update_data().
        
        Returns:
            bool: True if data was loaded, False otherwise
        """
        logger.debug("Loading all data from database")
        return self.update_data()
            
    def cleanup(self):
        """Clean up resources."""
        if self.src:
            # Any cleanup needed for database source
            pass 