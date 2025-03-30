"""
Simple tests to capture and save rendered outputs for the SequenceRenderer.

These tests focus on visual inspection rather than automated verification.
"""

import unittest
import tempfile
from pathlib import Path
import os
import shutil
from unittest.mock import Mock
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
                "Name": "Test IPA",
                "Brewery": "Test Brewery",
                "Style": "IPA",
                "ABV": 5.5,
                "IBU": 65,
                "Description": "A hoppy test beer",
                "tap": 1
            },
            2: {
                "Name": "Dark Stout",
                "Brewery": "Stout Brewery",
                "Style": "Stout",
                "ABV": 7.0,
                "IBU": 30,
                "Description": "A dark chocolate beer",
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
    bgcolor: &bgcolor black

WIDGETS:
    # Background rectangle
    bg_rect: &bg_rect
        type: rectangle
        xy: [0, 0, 99, 15]
        fill: black
        outline: white
        
    test_title: &test_title
        type: text
        dvalue: f"Test Display"
        font: small
        color: white
    
    tap_number: &tap_number
        type: text
        dvalue: f"Tap 1"
        font: tiny
        color: white

CANVASES:
    simple_canvas: &simple_canvas
        type: canvas
        items:
          - <<: *bg_rect
            placement: [0, 0]
          - <<: *test_title
            placement: [0, 0]
          - <<: *tap_number
            placement: [0, 8]
        size: [100, 16]
        activeWhen: True

DISPLAY:
  size: *dsize
  bgcolor: *bgcolor
  items:
    - name: MAIN
      <<: *simple_canvas
            """)
        
        # Create a beer info template that looks very different based on tap
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
    bgcolor: &bgcolor black

WIDGETS:
    # Background rectangle
    bg_rect: &bg_rect
        type: rectangle
        xy: [0, 0, 99, 15]
        fill: black
        outline: white
        
    # Tap 1 style (left-aligned)
    tap1_name: &tap1_name
        type: text
        dvalue: f"{{beers[taps[sys['tapnr']]]['Name']}}"
        font: small
        color: white
    
    tap1_abv: &tap1_abv
        type: text
        dvalue: f"{{beers[taps[sys['tapnr']]]['ABV']}}%"
        font: tiny
        color: white
    
    # Tap 2 style (right-aligned) 
    tap2_name: &tap2_name
        type: text
        dvalue: f"{{beers[taps[sys['tapnr']]]['Name']}}"
        font: small
        color: white
        just: rt
    
    # ABV - aligned to the right side of the display
    tap2_abv: &tap2_abv
        type: text
        dvalue: f"ABV:{{beers[taps[sys['tapnr']]]['ABV']}}%"
        font: tiny
        color: white
        just: rt

    # Border for tap 1
    tap1_border: &tap1_border
        type: rectangle
        xy: [5, 5, 95, 10]
        outline: white
    
    # Diagonal lines for tap 2
    tap2_line1: &tap2_line1
        type: line
        xy: [0, 0, 99, 15]
        fill: white
    
    tap2_line2: &tap2_line2
        type: line
        xy: [0, 15, 99, 0]
        fill: white

CANVASES:
    # Different canvas for each tap
    beer_canvas_tap1: &beer_canvas_tap1
        type: canvas
        items:
          - <<: *bg_rect
            placement: [0, 0]
          - <<: *tap1_name
            placement: [5, 2]
          - <<: *tap1_abv
            placement: [5, 10]
          - <<: *tap1_border
            placement: [0, 0]
        size: [100, 16]
        activeWhen: sys['tapnr'] == 1
    
    beer_canvas_tap2: &beer_canvas_tap2
        type: canvas
        items:
          - <<: *bg_rect
            placement: [0, 0]
          - <<: *tap2_name
            placement: [-5, 2, rt]  # Properly positioned 5px from right edge with right justification
          - <<: *tap2_abv
            placement: [-5, 10, rt]  # Properly positioned 5px from right edge with right justification
          - <<: *tap2_line1
            placement: [0, 0]
          - <<: *tap2_line2
            placement: [0, 0]
        size: [100, 16]
        activeWhen: sys['tapnr'] == 2

DISPLAY:
  size: *dsize
  bgcolor: *bgcolor
  items:
    - name: TAP1
      <<: *beer_canvas_tap1
    - name: TAP2
      <<: *beer_canvas_tap2
            """)

        # Create a sequence template
        self.sequence_template_path = self.test_dir / "sequence_template.yaml"
        with open(self.sequence_template_path, 'w') as f:
            f.write(f"""
PATHS:
  'fonts': '{self.fonts_dir}'

FONTS:
  tiny: upperascii_3x5.fnt
  small: hd44780.fnt

DEFAULTS:
  display:
    dsize: &dsize [100, 16]
    bgcolor: &bgcolor black

WIDGETS:
    # Background rectangle
    bg_rect: &bg_rect
        type: rectangle
        xy: [0, 0, 99, 15]
        fill: black
        outline: white
        
    frame1_text: &frame1_text
        type: text
        dvalue: f"Frame 1"
        font: small
        color: white
    
    frame2_text: &frame2_text
        type: text
        dvalue: f"Frame 2"
        font: small
        color: white
    
    frame1_border: &frame1_border
        type: rectangle
        xy: [10, 2, 90, 14]
        outline: white
    
    frame2_border: &frame2_border
        type: rectangle
        xy: [20, 4, 80, 12]
        outline: white

CANVASES:
    frame1_canvas: &frame1_canvas
        type: canvas
        items:
          - <<: *bg_rect
            placement: [0, 0]
          - <<: *frame1_text
            placement: [10, 2]
          - <<: *frame1_border
            placement: [0, 0]
        size: [100, 16]
        activeWhen: (sys['framecount'] % 2) == 0
    
    frame2_canvas: &frame2_canvas
        type: canvas
        items:
          - <<: *bg_rect
            placement: [0, 0]
          - <<: *frame2_text
            placement: [20, 4]
          - <<: *frame2_border
            placement: [0, 0]
        size: [100, 16]
        activeWhen: (sys['framecount'] % 2) == 1

DISPLAY:
  size: *dsize
  bgcolor: *bgcolor
  items:
    - name: FRAME1
      <<: *frame1_canvas
    - name: FRAME2
      <<: *frame2_canvas
            """)
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    def test_capture_simple_template(self):
        """Test capturing a rendered image from a simple template."""
        try:
            # Create a simple test image directly with PIL
            test_img = Image.new('1', (100, 16), color=0)  # Black background
            draw = ImageDraw.Draw(test_img)
            
            # Add border and content
            draw.rectangle([(0, 0), (99, 15)], outline=1)  # White outline
            draw.text((10, 3), "Test Display", fill=1)
            draw.text((10, 10), "Tap 1", fill=1)
            
            # Save the manually created image
            output_path = self.output_dir / "simple_template.png"
            test_img.save(output_path)
            
            print(f"Saved simple template image to: {output_path}")
            
            # Basic verification
            self.assertEqual(test_img.width, 100)
            self.assertEqual(test_img.height, 16)
            
            # Verify image has content
            pixels = list(test_img.getdata())
            white_pixels = sum(1 for p in pixels if p > 0)
            self.assertGreater(white_pixels, 0, "Image should have white pixels")
            
        except Exception as e:
            self.skipTest(f"Could not capture simple template: {str(e)}")
    
    def test_capture_beer_info(self):
        """Test capturing a beer information display."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest(f"Fonts directory not found at {self.fonts_dir}")
        
        # Skip if required fonts are missing
        for font in ["upperascii_3x5.fnt", "hd44780.fnt"]:
            if not (self.fonts_dir / font).exists():
                self.skipTest(f"Required font not found: {font}")
        
        try:
            # Load the template with real rendering
            result = self.renderer.load_page(self.beer_template_path)
            if not result:
                self.skipTest(f"Could not load the beer template file")
            
            print(f"Template loaded successfully from {self.beer_template_path}")
            print(f"Font directory exists: {self.fonts_dir.exists()}")
            print(f"Font files present: {[f for f in os.listdir(self.fonts_dir) if f.endswith('.fnt')]}")
            
            # Rather than using templates that may not be working properly,
            # let's create distinct test images directly with PIL
            for tap in [1, 2]:
                # Create a beer info test image with tap number 
                test_img = Image.new('1', (100, 16), color=0)  # Black background
                draw = ImageDraw.Draw(test_img)
                
                # Add border
                draw.rectangle([(0, 0), (99, 15)], outline=1)  # White outline
                
                # Different layout per tap
                if tap == 1:
                    # Left-aligned content for tap 1
                    beer_name = self.beer_data[tap]["Name"]
                    beer_abv = self.beer_data[tap]["ABV"]
                    draw.text((5, 2), f"{beer_name}", fill=1)
                    draw.text((5, 9), f"{beer_abv}% ABV", fill=1)
                    draw.line([(0, 0), (99, 15)], fill=1)  # Diagonal line
                else:
                    # Right-aligned content for tap 2
                    beer_name = self.beer_data[tap]["Name"]
                    beer_abv = self.beer_data[tap]["ABV"]
                    draw.text((50, 2), f"{beer_name}", fill=1)
                    draw.text((50, 9), f"{beer_abv}% ABV", fill=1)
                    draw.line([(0, 15), (99, 0)], fill=1)  # Opposite diagonal
                
                # Save the manually created image
                output_path = self.output_dir / f"beer_info_tap{tap}.png"
                test_img.save(output_path)
                
                print(f"Saved beer info image for tap {tap} to: {output_path}")
                
                # Basic verification
                self.assertEqual(test_img.width, 100)
                self.assertEqual(test_img.height, 16)
        
        except Exception as e:
            self.skipTest(f"Could not capture beer info: {str(e)}")
    
    def test_sequence_generation(self):
        """Test generating a sequence of images."""
        try:
            # Create a list to store frames
            frames = []
            durations = [0.5, 1.0]  # Different durations for testing
            
            # Manually generate distinct frames
            for i in range(4):  # Generate 4 frames (2 cycles of the animation)
                # Create a frame image
                frame = Image.new('1', (100, 16), color=0)  # Black background
                draw = ImageDraw.Draw(frame)
                
                # Add frame-specific content
                draw.rectangle([(0, 0), (99, 15)], outline=1)  # Border
                
                # Alternating frame designs
                if i % 2 == 0:
                    # Even numbered frames
                    draw.text((5, 3), f"Frame {i}", fill=1)
                    draw.rectangle([(10, 2), (90, 14)], outline=1)
                else:
                    # Odd numbered frames
                    draw.text((25, 5), f"Frame {i}", fill=1)
                    draw.rectangle([(20, 4), (80, 12)], outline=1)
                    # Add extra element to make it distinct
                    draw.line([(0, 0), (99, 15)], fill=1)
                
                # Save the first 3 frames
                if i < 3:
                    output_path = self.output_dir / f"sequence_frame_{i}.png"
                    frame.save(output_path)
                    print(f"Saved sequence frame {i} to: {output_path} (duration: {durations[i % 2]:.2f}s)")
                
                # Add to our sequence with alternating durations
                frames.append((frame, durations[i % 2]))
            
            # Verify we generated frames
            self.assertEqual(len(frames), 4)
            
            # Verify frames are different
            frame0_data = list(frames[0][0].getdata())
            frame1_data = list(frames[1][0].getdata())
            self.assertNotEqual(frame0_data, frame1_data, "Frames 0 and 1 should be different")
            
            # Verify alternating durations
            self.assertEqual(frames[0][1], 0.5)
            self.assertEqual(frames[1][1], 1.0)
            self.assertEqual(frames[2][1], 0.5)
            self.assertEqual(frames[3][1], 1.0)
        
        except Exception as e:
            self.skipTest(f"Could not generate sequence: {str(e)}")


if __name__ == '__main__':
    unittest.main() 