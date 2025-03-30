"""
Implementation for the SSD1322 display
"""

import logging
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322

from .base import DisplayBase

logger = logging.getLogger("KegDisplay")


class SSD1322Display(DisplayBase):
    """Implementation for the SSD1322 display."""
    
    def __init__(self, interface_type='spi', pins=None):
        """Initialize the SSD1322 display.
        
        Args:
            interface_type: Type of interface (typically 'spi')
            pins: Dictionary of pin settings (not typically used for SPI)
        """
        self.interface_type = interface_type
        self.pins = pins or {}
        self.device = None
        
    def initialize(self):
        """Initialize the display interface."""
        try:
            if self.interface_type == 'spi':
                interface = spi()
                logger.debug("Initialized SPI interface for SSD1322")
            else:
                # SSD1322 typically uses SPI, but we'll allow for flexibility
                from luma.core.interface.serial import spi
                interface = spi()
                logger.debug(f"Falling back to SPI interface for unsupported type: {self.interface_type}")
            
            # Create the device
            self.device = ssd1322(serial_interface=interface, mode='1')
            logger.debug("Initialized SSD1322 display")
            return True
        except Exception as e:
            logger.error(f"Error initializing SSD1322 display: {e}")
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
                self.device.display(image)
                return True
            except Exception as e:
                logger.error(f"Error displaying image on SSD1322: {e}")
                return False
        else:
            logger.error("SSD1322 display not initialized")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        # No specific cleanup needed for SSD1322
        pass
    
    @property
    def width(self):
        """Get the width of the display."""
        return 256 if self.device else 0
    
    @property
    def height(self):
        """Get the height of the display."""
        return 64 if self.device else 0 