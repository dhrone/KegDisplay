"""
Tests for individual text elements in the renderer.

This test renders each text element separately to diagnose positioning issues.
"""

import unittest
import tempfile
import os
from pathlib import Path
import shutil
from PIL import Image, ImageDraw
from unittest.mock import Mock, patch, MagicMock

from KegDisplay.renderer import SequenceRenderer
from tinyDisplay.utility import dataset


class TestRendererTextElements(unittest.TestCase):
    """Test individual text elements in the renderer."""
    
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
        
        # Create a temp directory for output
        self.output_dir = self.test_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        
        # Use the temporary directory for test results
        # Instead of a permanent one
        self.permanent_output_dir = self.output_dir
        
        # Test data
        self.test_beer = {
            'Name': 'Test IPA', 
            'ABV': 6.5, 
            'Description': 'A hoppy test beer'
        }
        
        # Create the dataset
        self.test_dataset = dataset()
        self.test_dataset.update('beers', {1: self.test_beer})
        self.test_dataset.update('taps', {1: 1})
        self.test_dataset.update('sys', {'status': 'running', 'tapnr': 1})
        
        # Create the renderer
        self.renderer = SequenceRenderer(self.mock_display, self.test_dataset)
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    def create_template_with_single_element(self, element_type, value, font, just, placement):
        """Create a template with just a single text element."""
        template_path = self.test_dir / f"{element_type}_template.yaml"
        with open(template_path, 'w') as f:
            f.write(f"""
PATHS:
  'fonts': '{self.fonts_dir}'

FONTS:
  tiny: upperascii_3x5.fnt
  small: hd44780.fnt
  large: Vintl01_10x16.fnt

DEFAULTS:
  display:
    dsize: &dsize [100, 16]

WIDGETS:
    test_element: &test_element
        type: text
        dvalue: f"{value}"
        font: {font}
        just: {just}

CANVASES:
  test_canvas: &test_canvas
    type: canvas
    items:
      - <<: *test_element
        placement: {placement}
    size: [100, 16]
    activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      <<: *test_canvas
            """)
        return template_path
    
    @patch('KegDisplay.renderer.load')
    def render_and_save(self, template_path, element_type, mock_load):
        """Render an image using the template and save it."""
        # Create a mock page object that the renderer can use
        mock_page = Mock()
        mock_image = Image.new('1', (100, 16), color=0)
        mock_page.image = mock_image
        mock_page.render = MagicMock()
        
        # Setup mock dataset for the mock page
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        # Configure the mock to return our mock page
        mock_load.return_value = mock_page
        
        # Load the template
        result = self.renderer.load_page(str(template_path))
        self.assertTrue(result, f"Failed to load template for {element_type}")
        
        # Render the image
        rendered_image = self.renderer.render()
        self.assertIsNotNone(rendered_image, f"Failed to render image for {element_type}")
        
        # Save the original image
        output_path = self.output_dir / f"{element_type}.png"
        rendered_image.save(output_path)
        
        # Create a version with a black background for better visibility
        bg_image = Image.new('RGB', rendered_image.size, color=(0, 0, 0))
        bg_image.paste(rendered_image, (0, 0), rendered_image)
        
        # Save the image with background
        bg_path = self.output_dir / f"{element_type}_with_bg.png"
        bg_image.save(bg_path)
        
        # Create an enlarged version
        large_image = bg_image.resize((400, 64), Image.NEAREST)
        large_path = self.output_dir / f"{element_type}_large.png"
        large_image.save(large_path)
        
        # No need to copy to permanent location since we're now using the temp directory
        # Just log that images were saved
        print(f"Saved {element_type} images to: {self.output_dir}")
        
        return rendered_image
    
    def test_beer_name_element(self):
        """Test rendering just the beer name element."""
        template_path = self.create_template_with_single_element(
            "beer_name", 
            "Test IPA", 
            "small", 
            "lt", 
            "[0, 0]"
        )
        
        image = self.render_and_save(template_path, "beer_name")
        self.assertEqual(image.size, (100, 16))
    
    def test_abv_element(self):
        """Test rendering just the ABV element."""
        # Use rt (right-top) justification and position at the right edge
        template_path = self.create_template_with_single_element(
            "beer_abv", 
            "6.5%", 
            "tiny", 
            "rt", 
            "[99, 0, rt]"  # Position at right edge, right-top justified
        )
        
        image = self.render_and_save(template_path, "beer_abv")
        self.assertEqual(image.size, (100, 16))
    
    def test_description_element(self):
        """Test rendering just the description element."""
        # Use lb (left-bottom) justification and position at the bottom
        template_path = self.create_template_with_single_element(
            "beer_desc", 
            "A hoppy test beer", 
            "tiny", 
            "lb", 
            "[0, 15, lb]"  # Position at bottom, left-bottom justified
        )
        
        image = self.render_and_save(template_path, "beer_desc")
        self.assertEqual(image.size, (100, 16))
    
    def test_rt_justification_variants(self):
        """Test different variants of right-top justification."""
        variants = [
            ("rt_neg5", "rt", "[-5, 0, rt]"),   # 5px inset from right edge
            ("rt_neg10", "rt", "[-10, 0, rt]"), # 10px inset from right edge
            ("rt_0", "rt", "[0, 0, rt]"),       # Aligned at right edge
            ("rt_plain", "rt", "[-5, 0]"),      # Offset but no explicit just in placement
            ("r_plain", "r", "[-5, 8]"),        # Single-char just (may fail)
            ("r_neg10", "r", "[-10, 8]")        # Single-char just with 10px inset
        ]
        
        for name, just, placement in variants:
            template_path = self.create_template_with_single_element(
                f"abv_{name}", 
                "6.5%", 
                "tiny", 
                just, 
                placement
            )
            
            image = self.render_and_save(template_path, f"abv_{name}")
            self.assertEqual(image.size, (100, 16))
    
    def test_lb_justification_variants(self):
        """Test different variants of left-bottom justification."""
        variants = [
            ("lb_15", "lb", "[0, 15, lb]"),
            ("lb_16", "lb", "[0, 16, lb]"),
            ("lb_14", "lb", "[0, 14, lb]"),
            ("lb_plain", "lb", "[0, 16]"),
            ("l_plain", "l", "[0, 8]"),
            ("b_plain", "b", "[50, 16]")
        ]
        
        for name, just, placement in variants:
            template_path = self.create_template_with_single_element(
                f"desc_{name}", 
                "A hoppy test beer", 
                "tiny", 
                just, 
                placement
            )
            
            image = self.render_and_save(template_path, f"desc_{name}")
            self.assertEqual(image.size, (100, 16))
    
    def test_complete_layout(self):
        """Test the complete layout with all elements."""
        template_path = self.test_dir / "complete_template.yaml"
        with open(template_path, 'w') as f:
            f.write(f"""
PATHS:
  'fonts': '{self.fonts_dir}'

FONTS:
  tiny: upperascii_3x5.fnt
  small: hd44780.fnt
  large: Vintl01_10x16.fnt

DEFAULTS:
  display:
    dsize: &dsize [100, 16]

WIDGETS:
    # Beer name - top left aligned
    beer_name: &beer_name
        type: text
        dvalue: f"Test IPA"
        font: small
        just: lt
        
    # ABV - top right aligned
    beer_abv: &beer_abv
        type: text
        dvalue: f"6.5%"
        font: small
        just: rt
        
    # Description - bottom left aligned
    beer_desc: &beer_desc
        type: text
        dvalue: f"A hoppy test beer"
        font: small
        just: lb

CANVASES:
  test_canvas: &test_canvas
    type: canvas
    items:
      - <<: *beer_name
        placement: [0, 0, lt]  # Left-top, no offset
      - <<: *beer_abv
        placement: [-5, 0, rt]  # Right-top, 5px inset from right
      - <<: *beer_desc
        placement: [0, 0, lb]  # Left-bottom, no offset
    size: [100, 16]
    activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: MAIN
      <<: *test_canvas
            """)
        
        # Render and save the image
        image = self.render_and_save(template_path, "complete_layout")
        self.assertEqual(image.size, (100, 16))
        
        # Create a debug image showing expected placements
        debug_img = Image.new('RGB', (100, 16), color=(0, 0, 0))
        draw = ImageDraw.Draw(debug_img)
        
        # Draw boxes where text should be
        # Top left - Beer name at [0, 0, lt] - Origin at left-top, no offset
        draw.rectangle([(0, 0), (50, 8)], outline=(255, 0, 0))
        draw.text((2, 1), "Test IPA", fill=(255, 255, 255))
        
        # Top right - ABV at [-5, 0, rt] - Origin at right-top, 5px inset from right
        draw.rectangle([(70, 0), (99, 8)], outline=(0, 255, 0))
        draw.text((75, 1), "6.5%", fill=(255, 255, 255))
        
        # Bottom left - Description at [0, 0, lb] - Origin at left-bottom, no offset
        draw.rectangle([(0, 8), (99, 15)], outline=(0, 0, 255))
        draw.text((2, 9), "A hoppy test beer", fill=(255, 255, 255))
        
        # Save the debug image
        debug_path = self.output_dir / "debug_layout.png"
        debug_img.save(debug_path)
        
        # Create an enlarged version
        debug_large = debug_img.resize((400, 64), Image.NEAREST)
        debug_large_path = self.output_dir / "debug_layout_large.png"
        debug_large.save(debug_large_path)
        
        # Create HTML to display the results
        self.create_comparison_html()
    
    def create_comparison_html(self):
        """Create an HTML file to display all test results."""
        html_path = self.output_dir / "text_elements_comparison.html"
        
        with open(html_path, 'w') as f:
            f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text Elements Test</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        h1, h2, h3 {{
            color: #333;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }}
        .image-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .image-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .image-item img {{
            max-width: 100%;
            border: 1px solid #ddd;
            margin-bottom: 5px;
        }}
    </style>
</head>
<body>
    <h1>Text Elements Rendering Test</h1>
    
    <div class="section">
        <h2>Beer Name Element</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="beer_name.png" alt="Beer Name">
                <span>Original</span>
            </div>
            <div class="image-item">
                <img src="beer_name_with_bg.png" alt="Beer Name with Background">
                <span>With Background</span>
            </div>
            <div class="image-item">
                <img src="beer_name_large.png" alt="Beer Name Large">
                <span>Enlarged (4x)</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Beer ABV Element</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="beer_abv.png" alt="Beer ABV">
                <span>Original</span>
            </div>
            <div class="image-item">
                <img src="beer_abv_with_bg.png" alt="Beer ABV with Background">
                <span>With Background</span>
            </div>
            <div class="image-item">
                <img src="beer_abv_large.png" alt="Beer ABV Large">
                <span>Enlarged (4x)</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Beer Description Element</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="beer_desc.png" alt="Beer Description">
                <span>Original</span>
            </div>
            <div class="image-item">
                <img src="beer_desc_with_bg.png" alt="Beer Description with Background">
                <span>With Background</span>
            </div>
            <div class="image-item">
                <img src="beer_desc_large.png" alt="Beer Description Large">
                <span>Enlarged (4x)</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Complete Layout</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="complete_layout.png" alt="Complete Layout">
                <span>Original</span>
            </div>
            <div class="image-item">
                <img src="complete_layout_with_bg.png" alt="Complete Layout with Background">
                <span>With Background</span>
            </div>
            <div class="image-item">
                <img src="complete_layout_large.png" alt="Complete Layout Large">
                <span>Enlarged (4x)</span>
            </div>
            <div class="image-item">
                <img src="debug_layout.png" alt="Debug Layout">
                <span>Debug Layout</span>
            </div>
            <div class="image-item">
                <img src="debug_layout_large.png" alt="Debug Layout Large">
                <span>Debug Layout Enlarged (4x)</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Right-Top Justification Variants</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="abv_rt_neg5_with_bg.png" alt="RT -5px">
                <span>RT with -5px offset</span>
            </div>
            <div class="image-item">
                <img src="abv_rt_0_with_bg.png" alt="RT 0px">
                <span>RT with 0px offset</span>
            </div>
            <div class="image-item">
                <img src="abv_rt_neg10_with_bg.png" alt="RT -10px">
                <span>RT with -10px offset</span>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Left-Bottom Justification Variants</h2>
        <div class="image-grid">
            <div class="image-item">
                <img src="desc_lb_0_with_bg.png" alt="LB 0px" onerror="this.src='desc_lb_15_with_bg.png'">
                <span>LB with 0px offset</span>
            </div>
            <div class="image-item">
                <img src="desc_lb_15_with_bg.png" alt="LB 15px">
                <span>LB with 15px offset</span>
            </div>
            <div class="image-item">
                <img src="desc_lb_14_with_bg.png" alt="LB 14px">
                <span>LB with 14px offset</span>
            </div>
        </div>
    </div>
</body>
</html>
""")
            
            print(f"Created comparison HTML at: {html_path}")


if __name__ == '__main__':
    unittest.main() 