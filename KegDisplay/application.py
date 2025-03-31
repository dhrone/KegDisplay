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

# Get the pre-existing logger instead of creating a new one
logger = logging.getLogger("KegDisplay")

class Application:
    """Main application class for KegDisplay."""
    
    def __init__(self, renderer, data_manager, config_manager):
        """Initialize the application with the required components.
        
        Args:
            renderer: The renderer object for display
            data_manager: The data manager for handling beer data
            config_manager: The configuration manager for application settings
        """
        self.renderer = renderer
        self.data_manager = data_manager
        self.config_manager = config_manager
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
        logger.debug("Starting application main loop")
        self.running = True
        splash_time = self.config_manager.get_config('splash_time')
    
        # Initialize display with splash screen
        logger.info("Initializing display with splash screen...")
        splash_image = self.renderer.render('start')
        if splash_image:
            self.renderer.display.display(splash_image)

        # Wait for the splash time to elapse
        current_time = time.time()
        
        # Perform initial data load while showing splash
        logger.info("Loading initial data...")
        update_result = self.data_manager.update_data()

        # Check if data has changed and initialize the check_data_changed hashes
        if not self.renderer.check_data_changed():
            logger.warning("On initial load, no data was received from the database")
        
        # Get current data for diagnostics
        beer_data = self.renderer._dataset.get('beers', {})
        tap_data = self.renderer._dataset.get('taps', {})

        # Check if we have any data to display.  If not, log a warning and set default values
        if len(beer_data) == 0:
            logger.warning("No beers found in database")
            self.renderer.update_dataset("beers", {
                "1": {
                    'Name': 'No Beer Data',
                    'ABV': 0.0,
                    'Description': 'Check the database.  It does not appear to have any beers.'
                }
            }, merge=True)
            
        if len(tap_data) == 0:
            logger.warning("No tap mappings found in database")
            self.renderer.update_dataset("taps", { 1: 1}, merge=True)
        
        # Make sure we have a default tap selected
        if not self.renderer._dataset.get('sys', {}).get('tapnr'):
            # Default to tap 1
            self.renderer.update_dataset('sys', {'tapnr': 1}, merge=True)
        
        # Generate image sequence for the first beer canvas
        self.renderer.image_sequence = self.renderer.generate_image_sequence()
        self.renderer.sequence_index = 0
        self.renderer.last_frame_time = time.time()
        logger.info(f"Generated sequence with {len(self.renderer.image_sequence)} frames")

        # Wait for the splash time to elapse
        while time.time() - current_time < splash_time:
            time.sleep(0.1)

        # Reset last_db_check_time to current time
        last_db_check_time = time.time()

        # Main loop
        logger.info("Starting main loop...")
        frame_count = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for database updates at specified frequency
                if current_time - last_db_check_time >= self.data_manager.update_frequency:
                    logger.debug(f"Checking for database updates (frequency: {self.data_manager.update_frequency}s)")
                    update_result = self.data_manager.update_data()
                    last_db_check_time = current_time
                    logger.debug(f"Database update check completed. Update found: {update_result}")
                    
                    # Check if data has changed
                    data_changed = self.renderer.check_data_changed()
                    logger.debug(f"Data change check result: {data_changed}")
                    
                    if data_changed:
                        logger.debug("Data changed - updating display")
                        
                        # Ensure dataset is synchronized after data change
                        if hasattr(self.renderer, 'force_dataset_sync') and self.renderer.main_display:
                            self.renderer.force_dataset_sync(self.renderer.main_display)
                            logger.debug("Forced dataset sync after data change")
                        
                        # Show updating message
                        updating_image = self.renderer.render("update")
                        self.renderer.display.display(updating_image)
                        
                        # Generate new image sequence
                        self.renderer.image_sequence = self.renderer.generate_image_sequence()
                        self.renderer.sequence_index = 0
                        self.renderer.last_frame_time = current_time
                        logger.info(f"Generated sequence with {len(self.renderer.image_sequence)} frames")
                        
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
