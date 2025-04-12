"""
Implementation for the WS0010 display
"""

import logging
from luma.core.interface.parallel import bitbang_6800
from luma.oled.device import ws0010

logger = logging.getLogger("KegDisplay")


class WS0010Display(ws0010):
    """Implementation for the WS0010 display."""
    
    def __init__(self, interface_type='bitbang', pins=None, **kwargs):
        """Initialize the WS0010 display.
        
        Args:
            interface_type: Type of interface ('bitbang' or 'spi')
            pins: Dictionary of pin settings (for bitbang: RS, E, PINS)
            **kwargs: Additional arguments passed to the base class
        """
        try:
            if interface_type == 'bitbang':
                # Extract pin configurations with defaults
                rs_pin = pins.get('RS', 7) if pins else 7
                e_pin = pins.get('E', 8) if pins else 8
                data_pins = pins.get('PINS', [25, 5, 6, 12]) if pins else [25, 5, 6, 12]
                
                # Create the interface
                interface = bitbang_6800(RS=rs_pin, E=e_pin, PINS=data_pins, pulse_time=1e-6 * 5.0)
                logger.debug(f"Initialized bitbang interface with RS={rs_pin}, E={e_pin}, PINS={data_pins}")
            elif interface_type == 'spi':
                from luma.core.interface.serial import spi
                interface = spi()
                logger.debug("Initialized SPI interface")
            else:
                raise ValueError(f"Unsupported interface type: {interface_type}")
            
            # Initialize the base class
            super().__init__(interface, width=100, height=16, **kwargs)
            logger.debug("Initialized WS0010 display")
            
        except Exception as e:
            logger.error(f"Error initializing display: {e}")
            raise

    def display(self, image):
        """Display an image on the screen.
        
        Args:
            image: PIL image to display
        """
        try:
            # Convert to mode '1' (1-bit) if needed
            if image.mode != self.mode:
                image = image.convert(self.mode)
            super().display(image)
        except Exception as e:
            logger.error(f"Error displaying image: {e}")
            raise 