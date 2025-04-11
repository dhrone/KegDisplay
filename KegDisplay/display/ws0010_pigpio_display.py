"""
WS0010 display implementation using pigpio interface.
"""

import logging
from luma.oled.device import ws0010
from luma.core.render import canvas
from PIL import Image

from .bitbang_6800_pigpio import bitbang_6800_pigpio

logger = logging.getLogger("KegDisplay")


class WS0010PigpioDisplay(ws0010):
    """
    WS0010 display implementation using pigpio interface.
    
    This class extends the base WS0010 class to use the pigpio interface
    for GPIO control. It provides a more efficient implementation for
    Raspberry Pi systems.
    """
    
    def __init__(self, RS=None, E=None, PINS=None, **kwargs):
        """
        Initialize the display with pigpio interface.
        
        :param RS: Register Select pin
        :param E: Enable pin
        :param PINS: List of data pins
        :param kwargs: Additional arguments passed to the base class.
        """
        try:
            # Initialize the pigpio interface
            interface = bitbang_6800_pigpio(RS=RS, E=E, PINS=PINS)
            
            # Initialize the base class with our interface
            super().__init__(interface)
            
            logger.info("Initialized WS0010 display with pigpio interface")
        except ImportError as e:
            logger.error("Failed to initialize WS0010 display with pigpio interface: %s", e)
            raise
        except Exception as e:
            logger.error("Unexpected error initializing WS0010 display: %s", e)
            raise

    def display(self, image):
        """
        Display an image on the screen.
        
        :param image: PIL Image to display
        """
        try:
            # Convert the image to the correct format for the display
            if image.mode != self.mode:
                image = image.convert(self.mode)
            
            # Display the image
            super().display(image)
        except Exception as e:
            logger.error("Error displaying image: %s", e)
            raise

    def cleanup(self):
        """Clean up resources."""
        try:
            # Clean up the interface
            if hasattr(self, '_interface'):
                self._interface.cleanup()
            logger.info("Cleaned up WS0010 display resources")
        except Exception as e:
            logger.error("Error during cleanup: %s", e)

    @property
    def width(self):
        """Get the width of the display."""
        return 100 if hasattr(self, 'device') and self.device else 0
    
    @property
    def height(self):
        """Get the height of the display."""
        return 16 if hasattr(self, 'device') and self.device else 0 