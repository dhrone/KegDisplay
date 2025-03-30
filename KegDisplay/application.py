"""
Main application class for KegDisplay

Ties together all components of the application.
"""

import time
import logging
import signal
import sys
import random
from tinyDisplay.utility import dataset

from .config import ConfigManager
from .display import DisplayFactory
from .renderer import SequenceRenderer
from .data_manager import DataManager

logger = logging.getLogger("KegDisplay")

class Application:
    """Main application class for KegDisplay."""
    
    def __init__(self, renderer, data_manager):
        """Initialize the application with the required components.
        
        Args:
            renderer: The renderer object for display
            data_manager: The data manager for handling beer data
        """
        self.renderer = renderer
        self.data_manager = data_manager
        self.running = False
        self.status = 'start'
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def signal_handler(self, sig, frame):
        """Handle signals for graceful shutdown."""
        logger.info(f"Received signal {sig}, shutting down...")
        self.running = False
        
    def cleanup(self):
        """Perform cleanup operations before shutdown."""
        logger.info("Cleaning up before exit")
        self.data_manager.cleanup()
        
    def run(self):
        """Run the main application loop."""
        self.running = True
        
        # Verify dataset integrity to ensure we don't have synchronization issues
        dataset_ok = self.renderer.verify_dataset_integrity()
        if not dataset_ok:
            logger.error("Dataset integrity check failed - dataset is not properly shared between components")
            logger.warning("Continuing with operation, but display may not work correctly")
        else:
            logger.debug("Dataset integrity verified - single dataset instance is properly shared")
        
        # Perform initial data load
        logger.info("Loading initial data...")
        self.data_manager.load_all_data()
        
        # Get current data for diagnostics
        beer_data = self.renderer._dataset.get('beers', {})
        tap_data = self.renderer._dataset.get('taps', {})
        
        logger.debug(f"Loaded {len(beer_data)} beers and {len(tap_data)} tap mappings")
        
        # Make sure we have a default tap selected
        if not self.renderer._dataset.get('sys', {}).get('tapnr'):
            # Default to tap 1
            self.renderer.update_dataset('sys', {'tapnr': 1}, merge=True)
            
        # Initialize display
        logger.info("Initializing display...")
        splash_image = self.renderer.render('start')
        if splash_image:
            self.renderer.display.display(splash_image)
        
        # Generate image sequence
        logger.info("Generating image sequence...")
        self.renderer.update_dataset('sys', {'status': 'update'}, merge=True)
        update_image = self.renderer.render()  # Will use current 'update' status
        if update_image:
            self.renderer.display.display(update_image)
            
        self.renderer.image_sequence = self.renderer.generate_image_sequence()
        logger.info(f"Generated sequence with {len(self.renderer.image_sequence)} frames")
        
        # The renderer sets status to 'running' in generate_image_sequence,
        # but we'll set it again just to be explicit
        self.renderer.update_dataset('sys', {'status': 'running'}, merge=True)
            
        # Main loop
        logger.info("Starting main loop...")
        frame_count = 0
        data_check_interval = 50  # Check for data changes every 50 frames
        
        last_db_check_time = 0
        
        while self.running:
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
                        self.renderer.display.display(updating_image)
                        
                        # Generate new image sequence
                        self.renderer.image_sequence = self.renderer.generate_image_sequence()
                        self.renderer.sequence_index = 0
                        self.renderer.last_frame_time = current_time
                        
                        
                        # Ensure status is set back to running
                        self.renderer.update_dataset('sys', {'status': 'running'}, merge=True)
                        logger.debug("Reset system status to 'running' after data change")
                
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
            
        if self.renderer.display:
            self.renderer.display.cleanup() 