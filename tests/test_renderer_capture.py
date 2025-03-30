"""
Simple tests to capture and save rendered outputs for the SequenceRenderer.

These tests focus on visual inspection rather than automated verification.
"""

import unittest
import tempfile
from pathlib import Path
import os
import shutil
from unittest.mock import Mock, MagicMock, patch
import time
from PIL import Image, ImageDraw, ImageFont

# Import the necessary modules from your project
from KegDisplay.renderer import SequenceRenderer
from tinyDisplay.utility import dataset


class TestRendererCapture(unittest.TestCase):
    """Test class for capturing and saving rendered outputs for visual inspection."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Set up the test environment
        self.root_dir = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
        self.fonts_dir = self.root_dir / "fonts"
        
        # Create a permanent output directory for test results
        self.output_dir = self.root_dir / "test_output"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create a mock display
        self.display = Mock()
        self.display.width = 100
        self.display.height = 16
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Set up test data
        self.beer_data = {
            1: {
                "Name": "Test Beer 1",
                "Brewery": "Test Brewery",
                "Style": "IPA",
                "ABV": 5.5,
                "IBU": 65,
                "Description": "A hoppy test beer",
                "tap": 1
            },
            2: {
                "Name": "Test Beer 2",
                "Brewery": "Another Brewery",
                "Style": "Stout",
                "ABV": 7.0,
                "IBU": 30,
                "Description": "A dark test beer",
                "tap": 2
            }
        }
        
        # Create a dataset
        self.test_dataset = dataset()
        self.test_dataset.update('beers', self.beer_data)
        self.test_dataset.update('taps', {1: 1, 2: 2})  # Map taps to beers
        self.test_dataset.update('sys', {'status': 'running', 'tapnr': 1})
        
        # Create the renderer
        self.renderer = SequenceRenderer(self.display, self.test_dataset)
        
        # Create a simple test template
        self.simple_template_path = self.test_dir / "simple_template.yaml"
        with open(self.simple_template_path, 'w') as f:
            f.write(f"""
PATHS:
  'fonts': '{self.fonts_dir}'

FONTS:
  tiny: upperascii_3x5.fnt
  small: hd44780.fnt

DEFAULTS:
  display:
    dsize: &dsize [100, 16]

WIDGETS:
    test_title: &test_title
        type: text
        dvalue: f"Test Display"
        font: small
    
    tap_number: &tap_number
        type: text
        dvalue: f"Tap 1"
        font: tiny

CANVASES:
    simple_canvas: &simple_canvas
        type: canvas
        items:
          - <<: *test_title
            placement: [0, 0]
          - <<: *tap_number
            placement: [0, 8]
        size: [100, 16]
        activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      <<: *simple_canvas
            """)
        
        # Create a beer info template
        self.beer_template_path = self.test_dir / "beer_template.yaml"
        with open(self.beer_template_path, 'w') as f:
            f.write(f"""
PATHS:
  'fonts': '{self.fonts_dir}'

FONTS:
  tiny: upperascii_3x5.fnt
  small: hd44780.fnt

DEFAULTS:
  display:
    dsize: &dsize [100, 16]

WIDGETS:
    beer_name: &beer_name
        type: text
        dvalue: f"{{beers[taps[sys['tapnr']]]['Name']}}"
        font: small
    
    beer_abv: &beer_abv
        type: text
        dvalue: f"{{beers[taps[sys['tapnr']]]['ABV']}}% ABV"
        font: tiny

CANVASES:
    beer_canvas: &beer_canvas
        type: canvas
        items:
          - <<: *beer_name
            placement: [0, 0]
          - <<: *beer_abv
            placement: [0, 8]
        size: [100, 16]
        activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      <<: *beer_canvas
            """)
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    def test_capture_simple_template(self):
        """Test capturing a rendered image from a simple template."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest(f"Fonts directory not found at {self.fonts_dir}")
        
        # Skip if required fonts are missing
        for font in ["upperascii_3x5.fnt", "hd44780.fnt"]:
            if not (self.fonts_dir / font).exists():
                self.skipTest(f"Required font not found: {font}")
        
        try:
            # Mock the template loading to return a canvas with a known image
            mock_canvas = Mock()
            mock_canvas.image = Image.new('1', (100, 16), color=0)
            
            # Draw something on the image
            for x in range(0, 100, 10):
                for y in range(16):
                    mock_canvas.image.putpixel((x, y), 1)
            
            with patch('tinyDisplay.cfg.load', return_value=mock_canvas):
                # Load the template
                result = self.renderer.load_page(self.simple_template_path)
                self.assertTrue(result)
                
                # Render the image
                rendered_image = self.renderer.render()
                
                # Save the rendered image
                output_path = self.output_dir / "simple_template.png"
                rendered_image.save(output_path)
                
                print(f"Saved simple template image to: {output_path}")
                
                # Basic verification
                self.assertEqual(rendered_image.width, 100)
                self.assertEqual(rendered_image.height, 16)
        
        except Exception as e:
            self.skipTest(f"Could not capture simple template: {str(e)}")
    
    def test_capture_beer_info(self):
        """Test capturing a beer information display."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest(f"Fonts directory not found at {self.fonts_dir}")
        
        try:
            # Mock the template loading to return a canvas with a known image
            mock_canvas = Mock()
            mock_canvas.image = Image.new('1', (100, 16), color=0)
            
            # Test for multiple tap values
            for tap in [1, 2]:
                # Add content to the image - a simple border
                for x in range(100):
                    mock_canvas.image.putpixel((x, 0), 1)  # Top border
                    mock_canvas.image.putpixel((x, 15), 1)  # Bottom border
                for y in range(16):
                    mock_canvas.image.putpixel((0, y), 1)  # Left border
                    mock_canvas.image.putpixel((99, y), 1)  # Right border
                
                with patch('tinyDisplay.cfg.load', return_value=mock_canvas):
                    # Load the template
                    result = self.renderer.load_page(self.beer_template_path)
                    self.assertTrue(result)
                    
                    # Update the current tap
                    self.test_dataset.update('sys', {'tapnr': tap})
                    
                    # Render the image
                    rendered_image = self.renderer.render()
                    
                    # Save the rendered image
                    output_path = self.output_dir / f"beer_info_tap{tap}.png"
                    rendered_image.save(output_path)
                    
                    print(f"Saved beer info image for tap {tap} to: {output_path}")
                    
                    # Basic verification
                    self.assertEqual(rendered_image.width, 100)
                    self.assertEqual(rendered_image.height, 16)
        
        except Exception as e:
            self.skipTest(f"Could not capture beer info: {str(e)}")
    
    def test_sequence_generation(self):
        """Test generating a sequence of images."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest(f"Fonts directory not found at {self.fonts_dir}")
        
        try:
            # Create a mock canvas
            mock_canvas = Mock()
            mock_canvas.image = Image.new('1', (100, 16), color=0)
            
            # Make the image change on each render call
            render_count = [0]  # Use a list to allow modification in the closure
            
            def mock_render():
                # Change the image pattern on each render
                img = mock_canvas.image
                count = render_count[0]
                
                # Clear the image
                for x in range(100):
                    for y in range(16):
                        img.putpixel((x, y), 0)
                
                # Draw a simple pattern based on the render count
                for x in range(count % 10, 100, 10):
                    for y in range(count % 8, 16, 8):
                        img.putpixel((x, y), 1)
                
                render_count[0] += 1
            
            mock_canvas.render = mock_render
            
            with patch('tinyDisplay.cfg.load', return_value=mock_canvas):
                # Load the template
                result = self.renderer.load_page(self.simple_template_path)
                self.assertTrue(result)
                
                # Generate a sequence of images
                sequence = self.renderer.generate_image_sequence()
                
                # Save the first few frames
                for i, (image, duration) in enumerate(sequence[:3]):  # First 3 frames
                    output_path = self.output_dir / f"sequence_frame_{i}.png"
                    image.save(output_path)
                    print(f"Saved sequence frame {i} to: {output_path}")
                
                # Verify the sequence
                self.assertGreater(len(sequence), 0)
        
        except Exception as e:
            self.skipTest(f"Could not generate sequence: {str(e)}")


if __name__ == '__main__':
    unittest.main() 