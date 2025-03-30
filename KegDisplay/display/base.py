"""
Base class for display implementations
"""

from abc import ABC, abstractmethod


class DisplayBase(ABC):
    """Base class for all display implementations.
    
    This abstract class defines the interface that all display types must implement.
    """
    
    @abstractmethod
    def initialize(self):
        """Initialize the display."""
        pass
    
    @abstractmethod
    def display(self, image):
        """Display an image on the display.
        
        Args:
            image: The PIL image to display
        """
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources used by the display."""
        pass
    
    @property
    @abstractmethod
    def width(self):
        """Get the width of the display in pixels."""
        pass
    
    @property
    @abstractmethod
    def height(self):
        """Get the height of the display in pixels."""
        pass 