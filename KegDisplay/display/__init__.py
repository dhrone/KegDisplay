"""
Display module for KegDisplay.

This module provides display implementations for different display types.
"""

from .ws0010_display import WS0010Display
from .ws0010_pigpio_display import WS0010PigpioDisplay
from .ssd1322_display import SSD1322Display
from .factory import DisplayFactory

# Try to import VirtualDisplay, but don't fail if it's not available
try:
    from .virtual_display import VirtualDisplay
    VIRTUAL_DISPLAY_AVAILABLE = True
except ImportError:
    VIRTUAL_DISPLAY_AVAILABLE = False

__all__ = [
    'WS0010Display',
    'WS0010PigpioDisplay',
    'SSD1322Display',
    'VirtualDisplay',
    'DisplayFactory',
] 