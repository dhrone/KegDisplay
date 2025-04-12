"""
WS0010 display implementation using pigpio interface.
"""

import logging
from luma.oled.device import ws0010
from luma.core.render import canvas
from PIL import Image
import traceback

from .bitbang_6800_pigpio import bitbang_6800_pigpio

logger = logging.getLogger("KegDisplay")


class WS0010PigpioDisplay(ws0010):
    """
    WS0010 display implementation using pigpio interface.
    
    This class extends the base WS0010 class to use the pigpio interface
    for GPIO control. It provides a more efficient implementation for
    Raspberry Pi systems.
    """
    
    def __init__(self, interface_type='pigpio', pins=None, **kwargs):
        """
        Initialize the display with pigpio interface.
        
        Args:
            interface_type: Type of interface ('pigpio')
            pins: Dictionary of pin settings (RS, E, PINS)
            **kwargs: Additional arguments passed to the base class.
        """
        try:
            # Extract pin configurations
            rs = pins.get('RS', 22)
            e = pins.get('E', 17)
            data_pins = pins.get('PINS', [25, 24, 23, 18])
            
            logger.debug(f"Initializing WS0010 display with RS={rs}, E={e}, PINS={data_pins}")
            
            # Initialize the pigpio interface
            interface = bitbang_6800_pigpio(
                RS=rs,
                E=e,
                PINS=data_pins,
                **kwargs
            )
            
            # Initialize the base class with our interface
            super().__init__(interface, width=100, height=16, **kwargs)
            
            logger.debug("Initialized WS0010 display with pigpio interface")
        except ImportError as e:
            logger.error("Failed to initialize WS0010 display with pigpio interface: %s\n%s", e, traceback.format_exc())
            raise
        except Exception as e:
            logger.error("Unexpected error initializing WS0010 display: %s\n%s", e, traceback.format_exc())
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
            logger.error("Error displaying image: %s\n%s", e, traceback.format_exc())
            raise 