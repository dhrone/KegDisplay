"""
Implementation for the SSD1306 display
"""

import logging
from luma.core.interface.serial import i2c, spi
from luma.oled.device import ssd1306

logger = logging.getLogger("KegDisplay")


class SSD1306Display(ssd1306):
    """Implementation for the SSD1306 display."""
    
    def __init__(self, interface_type='i2c', pins=None, **kwargs):
        """Initialize the SSD1306 display.
        
        Args:
            interface_type: Type of interface ('i2c' or 'spi')
            pins: Dictionary of pin settings (for SPI: SCLK, MOSI, DC, RST, CS)
            **kwargs: Additional arguments passed to the base class
        """
        try:
            if interface_type == 'i2c':
                interface = i2c(port=1, address=0x3C)
                logger.debug("Initialized I2C interface")
            elif interface_type == 'spi':
                # Extract pin configurations with defaults
                sclk = pins.get('SCLK', 11) if pins else 11
                mosi = pins.get('MOSI', 10) if pins else 10
                dc = pins.get('DC', 9) if pins else 9
                rst = pins.get('RST', 8) if pins else 8
                cs = pins.get('CS', 7) if pins else 7
                
                # Create the interface
                interface = spi(device=0, port=0, bus_speed_hz=16000000,
                              sclk=sclk, mosi=mosi, dc=dc, rst=rst, cs=cs)
                logger.debug(f"Initialized SPI interface with SCLK={sclk}, MOSI={mosi}, DC={dc}, RST={rst}, CS={cs}")
            else:
                raise ValueError(f"Unsupported interface type: {interface_type}")
            
            # Initialize the base class
            super().__init__(interface, width=128, height=64, **kwargs)
            logger.debug("Initialized SSD1306 display")
            
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

    def cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self, '_interface'):
                self._interface.cleanup()
            logger.debug("Cleaned up SSD1306 display resources")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}") 