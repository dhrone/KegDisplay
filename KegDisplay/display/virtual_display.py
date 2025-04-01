"""
Implementation for a virtual display using tkinter.
This display is useful for testing and development on desktop systems.
"""

import logging
import tkinter as tk
from PIL import Image, ImageTk

from .base import DisplayBase

logger = logging.getLogger("KegDisplay")


class VirtualDisplay(DisplayBase):
    """Implementation for a virtual display using tkinter."""
    
    def __init__(self, resolution=(256, 64), zoom=1):
        """Initialize the virtual display.
        
        Args:
            resolution: A 2 tuple of integers that represents the x (horizontal) and y (vertical) resolution of the display
            zoom: An integer that is used to determine how much to scale the display when it is presented
        """
        self.resolution = resolution
        self.zoom = zoom
        self.window = None
        self.canvas = None
        self.photo = None
        
    def initialize(self):
        """Initialize the virtual display window."""
        try:
            # Create the main window
            self.window = tk.Tk()
            self.window.title("Virtual Display")
            
            # Calculate scaled dimensions
            scaled_width = self.resolution[0] * self.zoom
            scaled_height = self.resolution[1] * self.zoom
            
            # Create canvas with the scaled dimensions
            self.canvas = tk.Canvas(
                self.window,
                width=scaled_width,
                height=scaled_height,
                bg='black'  # Black background to match WS0010 display
            )
            self.canvas.pack()
            
            logger.debug("Initialized virtual display window")
            return True
        except Exception as e:
            logger.error(f"Error initializing virtual display: {e}")
            return False
            
    def display(self, image):
        """Display an image on the virtual screen.
        
        Args:
            image: PIL image to display
        """
        if not self.window or not self.canvas:
            logger.error("Virtual display not initialized")
            return False
            
        try:
            # Log the original image details
            logger.debug(f"Original image: mode={image.mode}, size={image.size}")
            
            # For binary images, check the pixel values before conversion
            if image.mode == "1":
                pixels = image.load()
                white_pixels = 0
                for x in range(image.width):
                    for y in range(image.height):
                        if pixels[x, y] == 1:
                            white_pixels += 1
                logger.debug(f"Binary image has {white_pixels} white pixels out of {image.width * image.height} total")
            
            # Convert image to RGB if needed
            if image.mode != "RGB":
                if image.mode == "1":
                    # Convert binary image to RGB with white text on black background
                    rgb_image = Image.new('RGB', image.size, (0, 0, 0))  # Black background
                    pixels = image.load()
                    rgb_pixels = rgb_image.load()
                    
                    # Count the number of white pixels for debugging
                    white_pixels = 0
                    for x in range(image.width):
                        for y in range(image.height):
                            if pixels[x, y] == 1:  # If pixel is "on" in binary image
                                rgb_pixels[x, y] = (255, 255, 255)  # Make it white
                                white_pixels += 1
                    
                    logger.debug(f"Converted binary image: {white_pixels} white pixels out of {image.width * image.height} total")
                    image = rgb_image
                elif image.mode == "RGBA":
                    # Convert RGBA to RGB with black background
                    bg_image = Image.new('RGB', image.size, (0, 0, 0))
                    bg_image.paste(image, mask=image.split()[3])
                    image = bg_image
                else:
                    # Convert other modes to RGB
                    image = image.convert('RGB')
                
            # Resize the image according to zoom
            if self.zoom != 1:
                image = image.resize(
                    (self.resolution[0] * self.zoom, self.resolution[1] * self.zoom),
                    Image.Resampling.NEAREST
                )
                
            # Convert to PhotoImage for tkinter
            self.photo = ImageTk.PhotoImage(image)
            
            # Update the canvas
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            
            # Update the window
            self.window.update()
            return True
        except Exception as e:
            logger.error(f"Error displaying image on virtual display: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources."""
        if self.window:
            self.window.destroy()
            self.window = None
            self.canvas = None
            self.photo = None
    
    @property
    def width(self):
        """Get the width of the display."""
        return self.resolution[0]
    
    @property
    def height(self):
        """Get the height of the display."""
        return self.resolution[1] 