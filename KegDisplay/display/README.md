# KegDisplay Display Module

This module provides display implementations for the KegDisplay project. It supports various display types and interfaces.

## Display Types

### WS0010 Display

The WS0010 is a monochrome OLED display that supports both 4-bit and 8-bit parallel interfaces.

#### Implementations

1. **WS0010Display** - Standard implementation using the luma.oled library
2. **WS0010PigpioDisplay** - Enhanced implementation using pigpio for GPIO control with mandatory batch mode for efficient communication

### SSD1322 Display

The SSD1322 is a grayscale OLED display that supports SPI interface.

## Interface Types

### Bitbang 6800

The bitbang_6800 interface implements a 6800-style parallel bus interface. Two implementations are available:

1. **Standard** - Uses RPi.GPIO for GPIO control
2. **Pigpio** - Uses pigpio for enhanced GPIO control with wave generation support

## Usage

To create a display instance, use the DisplayFactory:

```python
from KegDisplay.display import DisplayFactory

# Create a WS0010 display with pigpio interface
display = DisplayFactory.create_display(
    display_type='ws0010_pigpio',
    interface_type='bitbang',
    pins={
        'RS': 17,
        'E': 27,
        'PINS': [22, 23, 24, 25, 8, 7, 12, 16]
    }
)

# Initialize the display
display.initialize()

# Display an image
from PIL import Image
image = Image.new('1', (128, 64))
display.display(image)

# Clean up
display.cleanup()
```

## Configuration

The display factory supports the following parameters:

- `display_type`: Type of display ('ws0010', 'ws0010_pigpio', 'ssd1322')
- `interface_type`: Type of interface ('bitbang', 'spi')
- `pins`: Dictionary of GPIO pin assignments

## Dependencies

- luma.oled
- pigpio (for pigpio implementation)
- PIL (Python Imaging Library) 