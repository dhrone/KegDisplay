"""
Dataset Manager for KegDisplay

Provides centralized dataset management to ensure all components share the same dataset.
"""

import logging
from tinyDisplay.utility import dataset

# Use the pre-configured logger
logger = logging.getLogger("KegDisplay")

class DatasetManager:
    """Manages the central dataset for KegDisplay."""
    
    def __init__(self):
        """Initialize the dataset manager."""
        self._dataset = dataset()
        self._initialized = False
        
    def initialize(self):
        """Initialize the dataset with required containers."""
        if not self._initialized:
            # Initialize with system data
            self._dataset.update('sys', {'status': 'start'})
            
            # Add empty containers for beer and tap data
            self._dataset.update('beers', {})
            self._dataset.update('taps', {})
            
            self._initialized = True
            logger.debug("Dataset initialized with required containers")
            
    @property
    def dataset(self):
        """Get the shared dataset.
        
        Returns:
            The shared dataset object
        """
        if not self._initialized:
            self.initialize()
        return self._dataset
        
    def update(self, key, value, merge=False):
        """Update the dataset with new values.
        
        Args:
            key: Key to update
            value: Value to set
            merge: Whether to merge with existing data
        """
        self._dataset.update(key, value, merge=merge)
        
    def get(self, key, default=None):
        """Get a value from the dataset.
        
        Args:
            key: Key to get
            default: Default value if key not found
            
        Returns:
            The value for the key, or default if not found
        """
        return self._dataset.get(key, default) 