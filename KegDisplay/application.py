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
    
    def __init__(self, config_manager, display, renderer, data_manager):
        """Initialize the application with injected dependencies.
        
        Args:
            config_manager: Configuration manager instance
            display: Display instance
            renderer: Renderer instance
            data_manager: Data manager instance
        """
        self.exit_requested = False
        self.config_manager = config_manager
        self.display = display
        self.renderer = renderer
        self.data_manager = data_manager
        
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