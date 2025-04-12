"""
Factory for creating display instances
"""

import logging
from typing import Dict, Any, Optional
from .ws0010_display import WS0010Display
from .ws0010_pigpio_display import WS0010PigpioDisplay
from .ssd1322_display import SSD1322Display
from .base import DisplayBase
import traceback

# Try to import VirtualDisplay, but don't fail if it's not available
try:
    from .virtual_display import VirtualDisplay
    VIRTUAL_DISPLAY_AVAILABLE = True
except ImportError:
    VIRTUAL_DISPLAY_AVAILABLE = False
    logging.getLogger("KegDisplay").warning("Virtual display not available. This is normal if tkinter is not installed.")

logger = logging.getLogger("KegDisplay")


class DisplayFactory:
    """
    Factory class for creating display instances.
    
    This class provides a centralized way to create display instances
    based on the specified type and interface.
    """
    
    @staticmethod
    def create_display(display_type: str, interface_type: str = 'bitbang', **kwargs) -> Optional[Any]:
        """
        Create a display instance based on the specified type and interface.
        
        :param display_type: Type of display to create (e.g., 'ws0010', 'ssd1322')
        :param interface_type: Interface type (e.g., 'bitbang', 'pigpio', 'spi'). Defaults to 'bitbang'
        :param kwargs: Additional arguments passed to the display constructor
        :return: Display instance or None if creation fails
        """
        try:
            if display_type == 'ws0010':
                if interface_type == 'bitbang':
                    logger.debug("Creating WS0010 display with luma.core bitbang interface")
                    return WS0010Display(**kwargs)
                elif interface_type == 'pigpio':
                    logger.debug("Creating WS0010 display with pigpio interface")
                    return WS0010PigpioDisplay(**kwargs)
                else:
                    logger.error(f"Unsupported interface '{interface_type}' for WS0010 display")
                    return None
            elif display_type == 'ssd1322':
                if interface_type == 'spi':
                    return SSD1322Display(**kwargs)
                else:
                    logger.error(f"Unsupported interface '{interface_type}' for SSD1322 display")
                    return None
            elif display_type == 'virtual':
                if not VIRTUAL_DISPLAY_AVAILABLE:
                    logger.error("Virtual display requested but not available. Install tkinter to use this feature.")
                    raise ValueError("Virtual display is not available. Install tkinter to use this feature.")
                logger.debug("Creating virtual display")
                resolution = kwargs.get('resolution', (256, 64))
                zoom = kwargs.get('zoom', 3)
                return VirtualDisplay(resolution=resolution, zoom=zoom)
            else:
                logger.error(f"Unsupported display type '{display_type}'")
                return None
        except ImportError as e:
            logger.error(f"Failed to create display: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating display: %s\n%s", e, traceback.format_exc())
            return None 