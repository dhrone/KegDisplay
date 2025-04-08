"""
Implementation for the WS0010 display using pigpio
"""

import logging
import time
from luma.oled.device import ws0010
from .bitbang_6800_pigpio import bitbang_6800_pigpio
from .base import DisplayBase

logger = logging.getLogger("KegDisplay")


class WS0010PigpioDisplay(DisplayBase):
    """Implementation for the WS0010 display using pigpio.  Assumes a bitbang interface."""
    
    def __init__(self, pins=None, interface_type='bitbang'):
        """Initialize the WS0010 display.
        
        Args:
            pins: Dictionary of pin settings (for bitbang: RS, E, PINS)
            interface_type: Type of interface (only 'bitbang' is supported for pigpio)
        """
        self.pins = pins or {}
        self.interface_type = interface_type
        self.device = None
        self.interface = None
        self.pulse_time = 2  # Match the PULSE_TIME in bitbang_6800_pigpio

    def initialize(self):
        """Initialize the display interface."""
        try:
            # Extract pin configurations with defaults
            rs_pin = self.pins.get('RS', 7)
            e_pin = self.pins.get('E', 8)
            data_pins = self.pins.get('PINS', [25, 5, 6, 12])
            
            # Create the interface
            self.interface = bitbang_6800_pigpio(
                RS=rs_pin, 
                E=e_pin, 
                PINS=data_pins, 
                pulse_time=self.pulse_time,
                batch=True
            )
            logger.debug(f"Initialized bitbang_6800_pigpio interface with RS={rs_pin}, E={e_pin}, PINS={data_pins}")
            
            # Create the device
            self.device = ws0010(self.interface)
            
            # Ensure the display is properly initialized
            time.sleep(0.5)  # Give the display time to initialize
            
            # Flush the display to ensure it's initialized
            if hasattr(self.interface, 'flush'):
                self.interface.flush()

            # Ensure the display is properly initialized
            time.sleep(0.5)  # Give the display time to initialize
                 
            logger.debug("Initialized WS0010 display")
            return True
        except Exception as e:
            logger.error(f"Error initializing display: {e}")
            return False
            
    def display(self, image):
        """Display an image on the screen.
        
        Args:
            image: PIL image to display
        """
        if self.device:
            try:
                # Convert to mode '1' (1-bit) if needed
                if image.mode != "1":
                    image = image.convert("1")
                
                # Display the image
                self.device.display(image)
                
                # Flush after displaying
                if hasattr(self.interface, 'flush'):
                    self.interface.flush()
                return True
            except Exception as e:
                logger.error(f"Error displaying image: {e}")
                return False
        else:
            logger.error("Display not initialized")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        # No specific cleanup needed for WS0010
        pass
    
    @property
    def width(self):
        """Get the width of the display."""
        return 100 if self.device else 0
    
    @property
    def height(self):
        """Get the height of the display."""
        return 16 if self.device else 0 