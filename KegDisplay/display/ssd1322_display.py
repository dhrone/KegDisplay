"""
Implementation for the SSD1322 display
"""

import logging
from luma.core.interface.serial import spi
from luma.oled.device import ssd1322
import traceback

logger = logging.getLogger("KegDisplay")


class SSD1322Display(ssd1322):
    """Implementation for the SSD1322 display."""
    
    def __init__(self, interface_type='spi', pins=None):
        """Initialize the SSD1322 display.
        
        Args:
            interface_type: Type of interface ('spi' or 'i2c')
            pins: Dictionary of pin settings (for SPI: DC, RST)
        """
        self.interface_type = interface_type
        self.pins = pins or {}

        logger.info(f"Initializing SSD1322 display with interface type: {self.interface_type} and pins: {self.pins}")
        
        try:
            if self.interface_type == 'spi':
                # Extract pin configurations with defaults
                dc = self.pins.get('DC', 24)
                rst = self.pins.get('RST', 25)
                
                # Create the interface
                interface = spi(device=0, port=0, gpio_DC=dc, gpio_RST=rst)
                logger.debug(f"Initialized SPI interface with DC={dc}, RST={rst}")
            elif self.interface_type == 'i2c':
                from luma.core.interface.serial import i2c
                interface = i2c(port=1, address=0x3C)
                logger.debug("Initialized I2C interface")
            else:
                raise ValueError(f"Unsupported interface type: {self.interface_type}")
            
            # Initialize the parent class
            super().__init__(interface, width=256, height=64)
            logger.debug("Initialized SSD1322 display")
            
        except Exception as e:
            logger.error(f"Error initializing display: {e}")
            raise
            
    def display(self, image):
        """Display an image on the screen.
        
        Args:
            image: PIL image to display
        """
        try:
            # Convert to mode 'L' (8-bit greyscale) if needed
            if image.mode != "L":
                logger.debug(f"Converting image from mode {image.mode} to mode L")
                image = image.convert("L")
            
            # Display the image
            super().display(image)
            logger.debug("Image displayed successfully")
            return True
        except Exception as e:
            logger.error(f"Error displaying image: {e}\n{traceback.format_exc()}")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        # No specific cleanup needed for SSD1322
        pass
    