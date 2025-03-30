"""
Dependency Container for KegDisplay

Manages the creation and configuration of application dependencies.
"""

import logging
from tinyDisplay.utility import dataset

from .config import ConfigManager
from .display import DisplayFactory 
from .renderer import SequenceRenderer
from .data_manager import DataManager

logger = logging.getLogger("KegDisplay")


class DependencyContainer:
    """Container for managing application dependencies."""
    
    def __init__(self):
        """Initialize the dependency container."""
        self.config_manager = None
        self.display = None
        self.dataset_obj = None
        self.renderer = None
        self.data_manager = None
        
    def get_config_manager(self):
        """Get or create the configuration manager.
        
        Returns:
            ConfigManager: The configuration manager instance
        """
        if not self.config_manager:
            self.config_manager = ConfigManager()
        return self.config_manager
    
    def create_display(self, config):
        """Create a display instance based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            DisplayBase: The display instance
            
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
    
    def create_dataset(self, config):
        """Create a dataset based on configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            dataset: The dataset instance
        """
        ds = dataset()
        ds.add("sys", {"tapnr": config['tap'], "status": "start"})
        ds.add("beers", {})
        ds.add("taps", {})
        return ds
    
    def create_renderer(self, display, dataset_obj, config):
        """Create a renderer based on configuration.
        
        Args:
            display: Display instance
            dataset_obj: Dataset instance
            config: Configuration dictionary
            
        Returns:
            SequenceRenderer: The renderer instance
            
        Raises:
            Exception: If renderer creation fails
        """
        renderer = SequenceRenderer(display, dataset_obj)
        if not renderer.load_page(config['page']):
            raise Exception(f"Failed to load page template: {config['page']}")
        return renderer
    
    def create_data_manager(self, db_path, renderer):
        """Create a data manager.
        
        Args:
            db_path: Path to the database file
            renderer: Renderer instance
            
        Returns:
            DataManager: The data manager instance
            
        Raises:
            Exception: If data manager creation fails
        """
        data_manager = DataManager(db_path, renderer)
        if not data_manager.initialize():
            raise Exception(f"Failed to initialize database: {db_path}")
        return data_manager
    
    def create_application_components(self, args=None):
        """Create all application components.
        
        Args:
            args: Command line arguments to parse
            
        Returns:
            tuple: (config_manager, display, renderer, data_manager)
            
        Raises:
            Exception: If component creation fails
        """
        # Get configuration
        config_manager = self.get_config_manager()
        config_manager.parse_args(args)
        if not config_manager.validate_config():
            raise Exception("Invalid configuration")
            
        config = config_manager.get_config()
        
        # Set up logging
        log_level = config['log_level']
        logger.setLevel(getattr(logging, log_level))
        
        # Create components
        try:
            display = self.create_display(config)
            dataset_obj = self.create_dataset(config)
            renderer = self.create_renderer(display, dataset_obj, config)
            data_manager = self.create_data_manager(config['db'], renderer)
            
            # Store for reuse
            self.config_manager = config_manager
            self.display = display
            self.dataset_obj = dataset_obj
            self.renderer = renderer
            self.data_manager = data_manager
            
            return config_manager, display, renderer, data_manager
        except Exception as e:
            logger.error(f"Error creating components: {e}")
            raise 