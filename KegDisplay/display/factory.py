"""
Factory for creating display instances
"""

import logging
from .ws0010_display import WS0010Display
from .ssd1322_display import SSD1322Display
from .virtual_display import VirtualDisplay
from .base import DisplayBase

logger = logging.getLogger("KegDisplay")


class DisplayFactory:
    """Factory class for creating display instances."""
    
    @staticmethod
    def create_display(display_type, interface_type='bitbang', **kwargs):
        """Create a display instance based on the specified type.
        
        Args:
            display_type: Type of display ('ws0010', 'ssd1322', or 'virtual')
            interface_type: Type of interface ('bitbang' or 'spi')
            **kwargs: Additional parameters for the display
            
        Returns:
            DisplayBase: An instance of the specified display
            
        Raises:
            ValueError: If the display type is not supported
        """
        pins = {}
        # Extract pin configurations if provided
        if 'RS' in kwargs:
            pins['RS'] = kwargs['RS']
        if 'E' in kwargs:
            pins['E'] = kwargs['E']
        if 'PINS' in kwargs:
            pins['PINS'] = kwargs['PINS']
            
        # Create the appropriate display instance
        if display_type.lower() == 'ws0010':
            logger.debug(f"Creating WS0010 display with {interface_type} interface")
            return WS0010Display(interface_type=interface_type, pins=pins)
        elif display_type.lower() == 'ssd1322':
            logger.debug(f"Creating SSD1322 display with {interface_type} interface")
            return SSD1322Display(interface_type=interface_type, pins=pins)
        elif display_type.lower() == 'virtual':
            logger.debug("Creating virtual display")
            resolution = kwargs.get('resolution', (256, 64))
            zoom = kwargs.get('zoom', 3)
            return VirtualDisplay(resolution=resolution, zoom=zoom)
        else:
            logger.error(f"Unsupported display type: {display_type}")
            raise ValueError(f"Unsupported display type: {display_type}") 