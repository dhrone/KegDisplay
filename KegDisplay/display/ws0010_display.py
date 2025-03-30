"""
Implementation for the WS0010 display
"""

import logging
from luma.core.interface.parallel import bitbang_6800
from luma.oled.device import ws0010

from .base import DisplayBase

logger = logging.getLogger("KegDisplay")


class WS0010Display(DisplayBase):
    """Implementation for the WS0010 display."""
    
    def __init__(self, interface_type='bitbang', pins=None):
        """Initialize the WS0010 display.
        
        Args:
            interface_type: Type of interface ('bitbang' or 'spi')
            pins: Dictionary of pin settings (for bitbang: RS, E, PINS)
        """
        self.interface_type = interface_type
        self.pins = pins or {}
        self.device = None
        
    def initialize(self):
        """Initialize the display interface."""
        try:
            if self.interface_type == 'bitbang':
                # Extract pin configurations with defaults
                rs_pin = self.pins.get('RS', 7)
                e_pin = self.pins.get('E', 8)
                data_pins = self.pins.get('PINS', [25, 5, 6, 12])
                
                # Create the interface
                interface = bitbang_6800(RS=rs_pin, E=e_pin, PINS=data_pins)
                logger.debug(f"Initialized bitbang interface with RS={rs_pin}, E={e_pin}, PINS={data_pins}")
            elif self.interface_type == 'spi':
                from luma.core.interface.serial import spi
                interface = spi()
                logger.debug("Initialized SPI interface")
            else:
                raise ValueError(f"Unsupported interface type: {self.interface_type}")
            
            # Create the device
            self.device = ws0010(interface)
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
                self.device.display(image)
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