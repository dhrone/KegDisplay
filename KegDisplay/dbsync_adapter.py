"""
Compatibility adapter module for legacy DatabaseSync usage.
"""

import logging
from db import SyncedDatabase

logger = logging.getLogger("KegDisplay")

class DatabaseSync(SyncedDatabase):
    """
    Compatibility class that implements the old DatabaseSync interface
    using the new modular SyncedDatabase class.
    
    This class exists to make the transition to the new code easier
    without breaking existing code that uses DatabaseSync.
    """
    
    def __init__(self, db_path, broadcast_port=5002, sync_port=5003, test_mode=False):
        """Initialize a DatabaseSync instance with the same interface as before
        
        Args:
            db_path: Path to the SQLite database
            broadcast_port: Port for UDP broadcast messages
            sync_port: Port for TCP sync connections
            test_mode: Whether to operate in test mode
        """
        super().__init__(db_path, broadcast_port, sync_port, test_mode)
        logger.info("Using new modular database sync system via compatibility adapter")
    
    # All other methods are inherited from SyncedDatabase
    # and maintain the same interface as the original DatabaseSync class 