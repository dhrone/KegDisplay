"""
Implementation for the WS0010 display using pigpio
"""

import logging
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
        self.pulse_time = 10
        
    def initialize(self):
        """Initialize the display interface."""
        try:
            # Extract pin configurations with defaults
            rs_pin = self.pins.get('RS', 7)
            e_pin = self.pins.get('E', 8)
            data_pins = self.pins.get('PINS', [25, 5, 6, 12])
            
            # Create the interface
            interface = bitbang_6800_pigpio(
                RS=rs_pin, 
                E=e_pin, 
                PINS=data_pins, 
                pulse_time=self.pulse_time,
                batch=True
            )
            logger.debug(f"Initialized bitbang_6800_pigpio interface with RS={rs_pin}, E={e_pin}, PINS={data_pins}")
            
            # Create the device
            self.device = ws0010(interface)

            # Flush the display to ensure it's initialized
            if hasattr(interface, 'flush'):
                interface.flush()
                 
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
                if hasattr(self.device._serial_interface, 'flush'):
                    self.device._serial_interface.flush()
                return True
            except Exception as e:
                logger.error(f"Error displaying image: {e}")
                return False
        else:
            logger.error("Display not initialized")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        if self.device and hasattr(self.device._serial_interface, 'cleanup'):
            self.device._serial_interface.cleanup()
    
    @property
    def width(self):
        """Get the width of the display."""
        return 100 if self.device else 0
    
    @property
    def height(self):
        """Get the height of the display."""
        return 16 if self.device else 0 