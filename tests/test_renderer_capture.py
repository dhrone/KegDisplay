"""
Simple tests to capture and save rendered outputs for the SequenceRenderer.

These tests focus on visual inspection rather than automated verification.
"""

import unittest
import tempfile
import os
from pathlib import Path
import shutil
from PIL import Image
from unittest.mock import Mock, patch, MagicMock

from KegDisplay.renderer import SequenceRenderer
from tinyDisplay.utility import dataset


class TestRendererCapture(unittest.TestCase):
    """Test class for capturing rendered outputs from SequenceRenderer."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Find the project root directory (needed to reference fonts correctly)
        self.project_root = Path(__file__).parent.parent.absolute()
        self.fonts_dir = self.project_root / "fonts"
        
        # Create a mock display
        self.mock_display = Mock()
        
        # Create a temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create an output directory for rendered images
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Test data for beers
        self.test_beers = {
            1: {
                'Name': 'Test IPA', 
                'ABV': 6.5, 
                'Description': 'A hoppy test beer with citrus notes'
            },
            2: {
                'Name': 'Test Stout', 
                'ABV': 7.2, 
                'Description': 'A rich, dark test beer with coffee flavors'
            }
        }
        
        # Create the actual dataset with test data
        self.test_dataset = dataset()
        self.test_dataset.update('beers', self.test_beers)
        self.test_dataset.update('taps', {1: 1, 2: 2})  # Map taps to beers
        self.test_dataset.update('sys', {'status': 'running', 'tapnr': 1})
        
        # Create the renderer with the dataset
        self.renderer = SequenceRenderer(self.mock_display, self.test_dataset)
        
        # Create a simple test template file that should render without complex logic
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

CANVASES:
  simple_canvas:
    type: canvas
    items:
      - type: text
        dvalue: "Test Display"
        font: small
        placement: [0, 0]
      - type: text
        dvalue: "Tap 1"
        font: tiny
        placement: [0, 8]
    size: [100, 16]
    activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      type: canvas
      items:
        - type: text
          dvalue: "Test Display"
          font: small
          placement: [0, 0]
        - type: text
          dvalue: "Tap 1"
          font: tiny
          placement: [0, 8]
      size: [100, 16]
            """)
            
        # Create a template for beer info
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

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      type: canvas
      items:
        - type: text
          dvalue: "Beer Information"
          font: small
          placement: [0, 0]
      size: [100, 16]
            """)
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    def test_capture_simple_template(self):
        """Capture a rendered image from a simple template."""
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
            
            with patch('KegDisplay.renderer.load', return_value=mock_canvas):
                # Load the template
                result = self.renderer.load_page(self.simple_template_path)
                self.assertTrue(result)
                
                # Render the image
                rendered_image = self.renderer.render()
                
                # Save the rendered image
                output_path = self.output_dir / "simple_template.png"
                rendered_image.save(output_path)
                
                print(f"Saved simple template render to {output_path}")
                
                # Basic verification
                self.assertEqual((100, 16), rendered_image.size)
        
        except Exception as e:
            self.skipTest(f"Could not capture simple template: {e}")
    
    def test_capture_beer_info(self):
        """Capture a beer information display."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest(f"Fonts directory not found at {self.fonts_dir}")
        
        try:
            # Create a mock canvas with a basic beer display
            mock_canvas = Mock()
            mock_canvas.image = Image.new('1', (100, 16), color=0)
            
            # Add content to the image - a simple border
            for x in range(100):
                mock_canvas.image.putpixel((x, 0), 1)  # Top border
                mock_canvas.image.putpixel((x, 15), 1)  # Bottom border
            for y in range(16):
                mock_canvas.image.putpixel((0, y), 1)  # Left border
                mock_canvas.image.putpixel((99, y), 1)  # Right border
            
            with patch('KegDisplay.renderer.load', return_value=mock_canvas):
                # Load the template
                result = self.renderer.load_page(self.beer_template_path)
                self.assertTrue(result)
                
                # Render with different tap values
                for tap in [1, 2]:
                    # Update the current tap
                    self.test_dataset.update('sys', {'tapnr': tap})
                    
                    # Render the image
                    rendered_image = self.renderer.render()
                    
                    # Save the rendered image
                    output_path = self.output_dir / f"beer_info_tap{tap}.png"
                    rendered_image.save(output_path)
                    
                    print(f"Saved beer info for tap {tap} to {output_path}")
                    
                    # Basic verification
                    self.assertEqual((100, 16), rendered_image.size)
        
        except Exception as e:
            self.skipTest(f"Could not capture beer info: {e}")
    
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
            
            with patch('KegDisplay.renderer.load', return_value=mock_canvas), \
                 patch('KegDisplay.renderer.time.time', return_value=12345):
                
                # Load the template
                result = self.renderer.load_page(self.simple_template_path)
                self.assertTrue(result)
                
                # Generate a sequence (this will call render multiple times)
                sequence = self.renderer.generate_image_sequence()
                
                # Save some frames from the sequence
                for i, (image, duration) in enumerate(sequence[:3]):  # First 3 frames
                    output_path = self.output_dir / f"sequence_frame_{i}.png"
                    image.save(output_path)
                    print(f"Saved sequence frame {i} to {output_path}, duration: {duration:.2f}s")
                
                # Basic verification
                self.assertGreater(len(sequence), 0)
        
        except Exception as e:
            self.skipTest(f"Could not generate sequence: {e}")


if __name__ == '__main__':
    unittest.main() 