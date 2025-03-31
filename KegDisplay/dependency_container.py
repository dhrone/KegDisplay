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
            dataset_factory: Optional custom dataset factory (kept for backward compatibility)
        """
        self.config_manager = None
        self.display = None
        self.dataset_obj = None  # This field is kept for backward compatibility
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
        
        # Note: Logging level is now handled in the main entry point
        logger.debug("Creating application components")
        
        # Create components
        try:
            # Use the factory interfaces to create components
            display = self.display_factory.create_display(config)
            
            # Create initial dataset values for backward compatibility
            # In the new approach, the renderer will use tinyDisplay's dataset after loading the page
            dataset_obj = self.dataset_factory.create_dataset(config)
            
            # Create renderer with display and initial dataset values
            renderer = self.renderer_factory.create_renderer(display, dataset_obj, config)
            
            # Create data manager
            data_manager = self.data_manager_factory.create_data_manager(config['db'], renderer)
            
            # Store for reuse
            self.config_manager = config_manager
            self.display = display
            self.dataset_obj = dataset_obj  # Keep reference for backward compatibility
            self.renderer = renderer
            self.data_manager = data_manager
            
            logger.debug("All components created successfully")
            
            return config_manager, display, renderer, data_manager
        except Exception as e:
            logger.error(f"Error creating components: {e}")
            raise
            
    def verify_integrity(self):
        """Verify that all components have a consistent view of shared objects.
        
        In the current architecture, the renderer uses tinyDisplay's dataset
        after loading the page template, so this method is mainly kept for
        backward compatibility.
        """
        if not hasattr(self, 'renderer'):
            logger.warning("Cannot verify integrity: Not all components are initialized")
            return False
            
        # Verify that the renderer has a valid dataset
        if not self.renderer.verify_dataset_integrity():
            logger.error("Integrity issue: Renderer's dataset integrity check failed")
            return False
                
        logger.debug("Component integrity verified")
        return True 