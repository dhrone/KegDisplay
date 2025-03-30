"""
Dependency Container for KegDisplay

Manages the creation and configuration of application dependencies.
"""

import logging
from typing import Dict, Any, Tuple, Optional

from .config import ConfigManager
from .factories import (
    DisplayFactoryInterface,
    RendererFactoryInterface,
    DataManagerFactoryInterface,
    DatasetFactoryInterface,
    DefaultDisplayFactory,
    DefaultRendererFactory,
    DefaultDataManagerFactory,
    DefaultDatasetFactory
)

logger = logging.getLogger("KegDisplay")


class DependencyContainer:
    """Container for managing application dependencies."""
    
    def __init__(
        self,
        display_factory: Optional[DisplayFactoryInterface] = None,
        renderer_factory: Optional[RendererFactoryInterface] = None,
        data_manager_factory: Optional[DataManagerFactoryInterface] = None,
        dataset_factory: Optional[DatasetFactoryInterface] = None
    ):
        """Initialize the dependency container with optional factory overrides.
        
        Args:
            display_factory: Optional custom display factory
            renderer_factory: Optional custom renderer factory
            data_manager_factory: Optional custom data manager factory
            dataset_factory: Optional custom dataset factory
        """
        self.config_manager = None
        self.display = None
        self.dataset_obj = None
        self.renderer = None
        self.data_manager = None
        
        # Initialize factories with defaults or provided implementations
        self.display_factory = display_factory or DefaultDisplayFactory()
        self.renderer_factory = renderer_factory or DefaultRendererFactory()
        self.data_manager_factory = data_manager_factory or DefaultDataManagerFactory()
        self.dataset_factory = dataset_factory or DefaultDatasetFactory()
    
    def get_config_manager(self):
        """Get or create the configuration manager.
        
        Returns:
            ConfigManager: The configuration manager instance
        """
        if not self.config_manager:
            self.config_manager = ConfigManager()
        return self.config_manager
    
    def create_application_components(self, args=None):
        """Create the application components.
        
        Args:
            args: Optional command line arguments
            
        Returns:
            A tuple of (config_manager, display, renderer, data_manager)
            
        Raises:
            Exception: If component creation fails
        """
        # Create config manager and load configuration
        config_manager = self.get_config_manager()
        
        if args:
            config_manager.parse_args(args)
            
        if not config_manager.validate_config():
            raise Exception("Invalid configuration")
            
        config = config_manager.get_config()
        
        # Set up logging
        log_level = config['log_level']
        logger.setLevel(getattr(logging, log_level))
        
        # Create components
        try:
            # Use the factory interfaces to create components
            display = self.display_factory.create_display(config)
            dataset_obj = self.dataset_factory.create_dataset(config)
            renderer = self.renderer_factory.create_renderer(display, dataset_obj, config)
            data_manager = self.data_manager_factory.create_data_manager(config['db'], renderer)
            
            # Store for reuse
            self.config_manager = config_manager
            self.display = display
            self.dataset_obj = dataset_obj
            self.renderer = renderer
            self.data_manager = data_manager
            
            # Verify integrity of created components
            self.verify_integrity()
            
            return config_manager, display, renderer, data_manager
        except Exception as e:
            logger.error(f"Error creating components: {e}")
            raise
            
    def verify_integrity(self):
        """Verify that all components have a consistent view of shared objects.
        
        This method verifies that the dataset object is properly shared across 
        all components that need it, preventing synchronization issues.
        """
        if not hasattr(self, 'renderer') or not hasattr(self, 'dataset_obj'):
            logger.warning("Cannot verify integrity: Not all components are initialized")
            return False
            
        # Verify that the renderer uses the same dataset object that was created
        if id(self.renderer._dataset) != id(self.dataset_obj):
            logger.error("Integrity issue: Renderer is not using the dataset object created by the factory")
            logger.error(f"Renderer dataset id: {id(self.renderer._dataset)}, Factory dataset id: {id(self.dataset_obj)}")
            return False
            
        # If the renderer has a display object with a dataset, check that too
        if (hasattr(self.renderer, 'main_display') and 
            self.renderer.main_display is not None and 
            hasattr(self.renderer.main_display, '_dataset')):
            
            if id(self.renderer.main_display._dataset) != id(self.dataset_obj):
                logger.error("Integrity issue: Display is not using the dataset object created by the factory")
                logger.error(f"Display dataset id: {id(self.renderer.main_display._dataset)}, " 
                          f"Factory dataset id: {id(self.dataset_obj)}")
                return False
                
        logger.debug("Component integrity verified: All components are using the same dataset object")
        return True 