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
    
    def __init__(self, interface_type='spi', pins=None, **kwargs):
        """Initialize the SSD1322 display.
        
        Args:
            interface_type: Type of interface ('spi' or 'i2c')
            pins: Dictionary of pin settings (for SPI: DC, RST)
            mode: Display mode ('1' for 1-bit or 'rgb' for RGB)
        """

        mode = kwargs.get('mode', '1')
        if mode not in ['1', 'rgb']:
            raise ValueError(f"Invalid mode '{mode}'. Must be either '1' or 'rgb'")
            
        self.interface_type = interface_type
        self.pins = pins or {}
        self.mode = mode

        logger.info(f"Initializing SSD1322 display with interface type: {self.interface_type}, pins: {self.pins}, mode: {self.mode}")
        
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
            super().__init__(interface, width=256, height=64, mode=mode)
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
            # Convert to the correct mode if needed
            if image.mode != self.mode:
                logger.debug(f"Converting image from mode {image.mode} to mode {self.mode}")
                if self.mode == '1':
                    image = image.convert("1")
                else:  # rgb mode
                    image = image.convert("RGB")
            
            # Display the image
            super().display(image)
            return True
        except AssertionError as e:
            logger.error(f"Image mode mismatch: Expected mode {self.mode}, got {image.mode}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logger.error(f"Error displaying image: {e}\n{traceback.format_exc()}")
            return False
            