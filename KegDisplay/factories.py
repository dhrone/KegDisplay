"""
Factory interfaces and implementations for KegDisplay.

This module contains abstract interfaces for component factories
and their concrete implementations.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from tinyDisplay.utility import dataset
from .display import DisplayFactory, DisplayBase
from .renderer import SequenceRenderer
from .data_manager import DataManager

logger = logging.getLogger("KegDisplay")


class DisplayFactoryInterface(ABC):
    """Interface for display factories."""
    
    @abstractmethod
    def create_display(self, config: Dict[str, Any]) -> DisplayBase:
        """Create a display based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            A configured display instance
            
        Raises:
            Exception: If display creation fails
        """
        pass


class RendererFactoryInterface(ABC):
    """Interface for renderer factories."""
    
    @abstractmethod
    def create_renderer(self, display: DisplayBase, dataset_obj: Any, config: Dict[str, Any]) -> SequenceRenderer:
        """Create a renderer based on configuration.
        
        Args:
            display: Display instance
            dataset_obj: Dataset instance
            config: Configuration dictionary
            
        Returns:
            A configured renderer instance
            
        Raises:
            Exception: If renderer creation fails
        """
        pass


class DataManagerFactoryInterface(ABC):
    """Interface for data manager factories."""
    
    @abstractmethod
    def create_data_manager(self, db_path: str, renderer: SequenceRenderer) -> DataManager:
        """Create a data manager.
        
        Args:
            db_path: Path to the database file
            renderer: Renderer instance
            
        Returns:
            A configured data manager instance
            
        Raises:
            Exception: If data manager creation fails
        """
        pass


class DatasetFactoryInterface(ABC):
    """Interface for dataset factories."""
    
    @abstractmethod
    def create_dataset(self, config: Dict[str, Any]) -> Any:
        """Create a dataset based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            A configured dataset instance
        """
        pass


# Concrete implementations

class DefaultDisplayFactory(DisplayFactoryInterface):
    """Default implementation of the display factory."""
    
    def create_display(self, config: Dict[str, Any]) -> DisplayBase:
        """Create a display based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            A configured display instance
            
        Raises:
            Exception: If display creation fails
        """
        display = DisplayFactory.create_display(
            config['display'],
            interface_type=config['interface'],
            RS=config['RS'],
            E=config['E'],
            PINS=config['PINS']
        )
        
        if not display.initialize():
            raise Exception(f"Failed to initialize {config['display']} display")
            
        logger.info(f"Initialized {config['display']} display")
        return display


class DefaultRendererFactory(RendererFactoryInterface):
    """Default implementation of the renderer factory."""
    
    def create_renderer(self, display: DisplayBase, dataset_obj: Any, config: Dict[str, Any]) -> SequenceRenderer:
        """Create a renderer based on configuration.
        
        Args:
            display: Display instance
            dataset_obj: Dataset instance
            config: Configuration dictionary
            
        Returns:
            A configured renderer instance
            
        Raises:
            Exception: If renderer creation fails
        """
        # Create the renderer with the provided dataset object
        renderer = SequenceRenderer(display, dataset_obj)
        
        # Load the page template - this will reuse the dataset
        if not renderer.load_page(config['page']):
            raise Exception(f"Failed to load page template: {config['page']}")
            
        # Verify dataset integrity after loading the page
        if not renderer.verify_dataset_integrity():
            logger.warning("Dataset integrity check failed after loading page template")
            logger.warning("This may cause display issues - the dataset is not properly shared")
            
        return renderer


class DefaultDataManagerFactory(DataManagerFactoryInterface):
    """Default implementation of the data manager factory."""
    
    def create_data_manager(self, db_path: str, renderer: SequenceRenderer) -> DataManager:
        """Create a data manager based on configuration.
        
        Args:
            db_path: Path to the database file
            renderer: Renderer instance
            
        Returns:
            A configured data manager instance
            
        Raises:
            Exception: If data manager creation fails
        """
        data_manager = DataManager(db_path, renderer)
        if not data_manager.initialize():
            raise Exception(f"Failed to initialize database connection for {db_path}")
        return data_manager


class DefaultDatasetFactory(DatasetFactoryInterface):
    """Default implementation of the dataset factory."""
    
    def create_dataset(self, config: Dict[str, Any]) -> Any:
        """Create a dataset based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            A configured dataset instance
        """
        ds = dataset()
        ds.add("sys", {"tapnr": config['tap'], "status": "start"})
        ds.add("beers", {})
        ds.add("taps", {})
        return ds 