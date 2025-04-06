#!/usr/bin/env python3
"""
Test program for KegDisplay displays.
This program asks for display configuration, displays a test message, and exits after 5 seconds.
"""

import argparse
import time
import sys
import os

# Add the parent directory to the path so we can import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from KegDisplay.display.factory import DisplayFactory
    from PIL import Image, ImageDraw, ImageFont
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure you're running this script from the KegDisplay directory.")
    sys.exit(1)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test program for KegDisplay displays')
    
    # Display type
    parser.add_argument('--display', type=str, choices=['ws0010', 'ssd1322', 'virtual'],
                        default='ws0010', help='Type of display (default: ws0010)')
    
    # Interface type
    parser.add_argument('--interface', type=str, choices=['bitbang', 'spi'],
                        default='bitbang', help='Type of interface (default: bitbang)')
    
    # Bitbang specific pins
    parser.add_argument('--RS', type=int, default=7, help='RS pin for bitbang interface (default: 7)')
    parser.add_argument('--E', type=int, default=8, help='E pin for bitbang interface (default: 8)')
    parser.add_argument('--PINS', type=int, nargs=4, default=[25, 5, 6, 12],
                        help='Data pins for bitbang interface (default: 25 5 6 12)')
    
    # Virtual display specific
    parser.add_argument('--resolution', type=int, nargs=2, default=[256, 64],
                        help='Resolution for virtual display (default: 256 64)')
    parser.add_argument('--zoom', type=int, default=3, help='Zoom factor for virtual display (default: 3)')
    
    return parser.parse_args()

def create_test_image(width, height):
    """Create a test image with text."""
    # Create a new image with a black background
    image = Image.new('1', (width, height), 0)
    draw = ImageDraw.Draw(image)
    
    # Try to load a font, fall back to default if not available
    try:
        # Try to use a system font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except IOError:
        try:
            # Try another common font location
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 16)
        except IOError:
            # Fall back to default font
            font = ImageFont.load_default()
    
    # Add text to the image
    text = "KegDisplay Test"
    
    # Get text size - handle both older and newer Pillow versions
    try:
        # For newer Pillow versions
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
    except AttributeError:
        try:
            # For older Pillow versions with textsize
            text_width, text_height = draw.textsize(text, font=font)
        except AttributeError:
            # For very old Pillow versions with getsize
            text_width, text_height = font.getsize(text)
    
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    draw.text((x, y), text, fill=1, font=font)
    
    # Add a border
    draw.rectangle([(0, 0), (width-1, height-1)], outline=1)
    
    return image

def main():
    """Main function."""
    args = parse_arguments()
    
    print("Testing display with the following configuration:")
    print(f"Display type: {args.display}")
    print(f"Interface type: {args.interface}")
    
    if args.interface == 'bitbang':
        print(f"RS pin: {args.RS}")
        print(f"E pin: {args.E}")
        print(f"Data pins: {args.PINS}")
    elif args.display == 'virtual':
        print(f"Resolution: {args.resolution}")
        print(f"Zoom: {args.zoom}")
    
    # Create display
    try:
        if args.interface == 'bitbang':
            display = DisplayFactory.create_display(
                args.display,
                interface_type=args.interface,
                RS=args.RS,
                E=args.E,
                PINS=args.PINS
            )
        elif args.display == 'virtual':
            display = DisplayFactory.create_display(
                args.display,
                resolution=tuple(args.resolution),
                zoom=args.zoom
            )
        else:
            display = DisplayFactory.create_display(
                args.display,
                interface_type=args.interface
            )
    except Exception as e:
        print(f"Error creating display: {e}")
        sys.exit(1)
    
    # Initialize display
    try:
        if not display.initialize():
            print("Failed to initialize display")
            sys.exit(1)
    except Exception as e:
        print(f"Error initializing display: {e}")
        sys.exit(1)
    
    print("Display initialized successfully")
    
    # Create test image
    try:
        image = create_test_image(256, 64)
    except Exception as e:
        print(f"Error creating test image: {e}")
        sys.exit(1)
    
    # Display test image
    try:
        print("Displaying test image...")
        display.display(image)
        print("Test image displayed successfully")
    except Exception as e:
        print(f"Error displaying test image: {e}")
        import traceback
        traceback.print_exc()
        print("Continuing with test...")
    
    # Wait for 5 seconds
    print("Waiting for 5 seconds...")
    time.sleep(5)
    
    print("Test completed successfully")

if __name__ == "__main__":
    main() 