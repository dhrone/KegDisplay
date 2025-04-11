#!/usr/bin/env python3
"""
Test script for the WS0010PigpioDisplay.
This script creates a simple test pattern and displays it on the WS0010 display using the pigpio interface.
"""

import argparse
import time
import sys
import os
import logging

# Add the parent directory to the path so we can import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    from KegDisplay.display.factory import DisplayFactory
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the KegDisplay directory.")
    sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test script for the WS0010PigpioDisplay')
    
    # Display type
    parser.add_argument('--display', type=str, choices=['ws0010', 'ws0010_pigpio'],
                        default='ws0010_pigpio', help='Type of display (default: ws0010_pigpio)')
    
    # Interface type
    parser.add_argument('--interface', type=str, choices=['bitbang', 'spi'],
                        default='bitbang', help='Type of interface (default: bitbang)')
    
    # Bitbang specific pins
    parser.add_argument('--RS', type=int, default=24, help='RS pin for bitbang interface (default: 24)')
    parser.add_argument('--E', type=int, default=25, help='E pin for bitbang interface (default: 25)')
    parser.add_argument('--PINS', type=int, nargs='+', default=[16, 26, 20, 21],
                        help='Data pins for bitbang interface (default: 16 26 20 21)')
    
    # Pulse time
    parser.add_argument('--pulse_time', type=int, default=50, help='Pulse time in microseconds (default: 50)')
    
    # Log level
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        default='DEBUG', help='Set the logging level (default: DEBUG)')
    
    return parser.parse_args()

def create_test_pattern(width, height):
    """Create a test pattern image."""
    image = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(image)
    
    # Draw a border
    draw.rectangle([(0, 0), (width-1, height-1)], outline=1)
    
    # Draw a diagonal line
    draw.line([(0, 0), (width-1, height-1)], fill=1)
    
    # Draw a horizontal line in the middle
    draw.line([(0, height//2), (width-1, height//2)], fill=1)
    
    # Draw a vertical line in the middle
    draw.line([(width//2, 0), (width//2, height-1)], fill=1)
    
    # Draw some text
    try:
        from PIL import ImageFont
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
        draw.text((5, 5), "Test", font=font, fill=1)
    except:
        # If font is not available, just draw a rectangle
        draw.rectangle([(5, 5), (20, 15)], outline=1)
    
    return image

def main():
    """Main function."""
    args = parse_arguments()
    
    # Configure logging based on the specified log level
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("KegDisplay")
    logger.info(f"Log level set to {args.log_level}")
    
    print("Testing display with the following configuration:")
    print(f"Display type: {args.display}")
    print(f"Interface type: {args.interface}")
    print(f"RS pin: {args.RS}")
    print(f"E pin: {args.E}")
    print(f"Data pins: {args.PINS}")
    print(f"Pulse time: {args.pulse_time} microseconds")
    
    # Create display
    try:
        display = DisplayFactory.create_display(
            args.display,
            interface_type=args.interface,
            RS=args.RS,
            E=args.E,
            PINS=args.PINS
        )
    except Exception as e:
        logger.error(f"Error creating display: {e}")
        sys.exit(1)
    
    # Initialize display
    try:
        if not display.initialize():
            logger.error("Failed to initialize display")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error initializing display: {e}")
        sys.exit(1)
    
    logger.info("Display initialized successfully")
    
    # Create test pattern
    try:
        image = create_test_pattern(display.width, display.height)
        logger.info(f"Created test pattern with size {image.size}")
    except Exception as e:
        logger.error(f"Error creating test pattern: {e}")
        sys.exit(1)
    
    # Display test pattern
    try:
        logger.info("Displaying test pattern...")
        display.display(image)
        logger.info("Test pattern displayed successfully")
    except Exception as e:
        logger.error(f"Error displaying test pattern: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Wait for 5 seconds
    logger.info("Waiting for 5 seconds...")
    time.sleep(5)
    
    # Clean up
    try:
        display.cleanup()
        logger.info("Display cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up display: {e}")
    
    logger.info("Test completed successfully")

if __name__ == "__main__":
    main() 