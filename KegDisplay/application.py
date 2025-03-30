"""
Main application class for KegDisplay

Ties together all components of the application.
"""

import time
import logging
import signal
import sys
from tinyDisplay.utility import dataset

from .config import ConfigManager
from .display import DisplayFactory
from .renderer import SequenceRenderer
from .data_manager import DataManager

logger = logging.getLogger("KegDisplay")

class Application:
    """Main application class for KegDisplay."""
    
    def __init__(self):
        """Initialize the application."""
        self.exit_requested = False
        self.config_manager = ConfigManager()
        self.display = None
        self.renderer = None
        self.data_manager = None
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._sigterm_handler)
        signal.signal(signal.SIGINT, self._sigterm_handler)
        
    def _sigterm_handler(self, _signo, _stack_frame):
        """Handle termination signals.
        
        Args:
            _signo: Signal number
            _stack_frame: Current stack frame
        """
        logger.info(f"Signal {_signo} received, initiating shutdown")
        self.exit_requested = True
        
    def initialize(self, args=None):
        """Initialize the application.
        
        Args:
            args: Command line arguments to parse
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        # Parse and validate configuration
        self.config_manager.parse_args(args)
        if not self.config_manager.validate_config():
            logger.error("Invalid configuration")
            return False
            
        # Set up logging
        config = self.config_manager.get_config()
        log_level = config['log_level']
        logger.setLevel(getattr(logging, log_level))
        
        # Initialize display
        try:
            self.display = DisplayFactory.create_display(
                config['display'], 
                interface_type=config['interface'], 
                RS=config['RS'],
                E=config['E'],
                PINS=config['PINS']
            )
            
            if not self.display.initialize():
                logger.error("Failed to initialize display")
                return False
                
            logger.info(f"Initialized {config['display']} display")
        except Exception as e:
            logger.error(f"Error creating display: {e}")
            return False
            
        # Initialize dataset
        ds = dataset()
        ds.add("sys", {"tapnr": config['tap'], "status": "start"})
        ds.add("beers", {})
        ds.add("taps", {})
        
        # Initialize renderer
        self.renderer = SequenceRenderer(self.display, ds)
        if not self.renderer.load_page(config['page']):
            logger.error(f"Failed to load page template: {config['page']}")
            return False
            
        # Initialize data manager
        self.data_manager = DataManager(config['db'], self.renderer)
        if not self.data_manager.initialize():
            logger.error(f"Failed to initialize database: {config['db']}")
            return False
            
        return True
    
    def run(self):
        """Run the main application loop."""
        if not self.display or not self.renderer or not self.data_manager:
            logger.error("Application not properly initialized")
            return False
            
        logger.info("Starting KegDisplay application")
        
        # Initial data load
        self.data_manager.update_data()
        
        # Initial render and display
        splash_image = self.renderer.render("start")
        self.display.display(splash_image.convert("1"))
        
        # Generate initial image sequence
        self.renderer.image_sequence = self.renderer.generate_image_sequence()
        self.renderer.sequence_index = 0
        self.renderer.last_frame_time = time.time()
        
        last_db_check_time = 0
        
        # Main loop
        while not self.exit_requested:
            try:
                current_time = time.time()
                
                # Check for database updates at specified frequency
                if current_time - last_db_check_time >= self.data_manager.update_frequency:
                    self.data_manager.update_data()
                    last_db_check_time = current_time
                    
                    # Check if data has changed
                    if self.renderer.check_data_changed():
                        logger.debug("Data changed - updating display")
                        
                        # Show updating message
                        updating_image = self.renderer.render("update")
                        self.display.display(updating_image.convert("1"))
                        
                        # Generate new image sequence
                        self.renderer.image_sequence = self.renderer.generate_image_sequence()
                        self.renderer.sequence_index = 0
                        self.renderer.last_frame_time = current_time
                
                # Display current frame
                self.renderer.display_next_frame()
                
                # Short sleep to prevent CPU overload
                time.sleep(0.01)
                
            except KeyboardInterrupt:
                logger.info("KeyboardInterrupt received, initiating shutdown")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                # Continue running despite errors
        
        # Clean up
        self.cleanup()
        logger.info("Application terminated")
        return True
    
    def cleanup(self):
        """Clean up resources."""
        logger.debug("Cleaning up resources")
        
        if self.data_manager:
            self.data_manager.cleanup()
            
        if self.display:
            self.display.cleanup() 