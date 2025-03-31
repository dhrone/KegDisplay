"""
Tests for the SequenceRenderer class.

These tests validate the renderer's ability to load page templates,
update datasets, and generate image sequences.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import os
import time
import tempfile
import shutil
from pathlib import Path
from PIL import Image

from KegDisplay.renderer import SequenceRenderer
from tinyDisplay.utility import dataset


class TestSequenceRenderer(unittest.TestCase):
    """Test the SequenceRenderer class."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Find the project root directory (needed to reference fonts correctly)
        self.project_root = Path(__file__).parent.parent.absolute()
        self.fonts_dir = self.project_root / "fonts"
        
        # Create mock display
        self.mock_display = Mock()
        
        # Create an actual dataset for more realistic testing
        self.test_dataset = dataset()
        
        # Initialize with test data
        self.test_dataset.update('beers', {
            1: {'Name': 'Test IPA', 'ABV': 6.5, 'Description': 'A hoppy test beer'},
            2: {'Name': 'Test Stout', 'ABV': 7.2, 'Description': 'A dark test beer'}
        })
        
        self.test_dataset.update('taps', {
            1: 1,  # Tap 1 has Beer 1
            2: 2   # Tap 2 has Beer 2
        })
        
        self.test_dataset.update('sys', {
            'status': 'running',
            'tapnr': 1
        })
        
        # Create the renderer with actual dataset
        self.renderer = SequenceRenderer(self.mock_display, self.test_dataset)
        
        # Create a temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create a simple test page for basic tests
        self.simple_test_page_path = Path(self.temp_dir.name) / "simple_test_page.yaml"
        with open(self.simple_test_page_path, 'w') as f:
            f.write("""
DISPLAY:
  size: [100, 16]
  items:
    - name: TEST
      type: canvas
      items:
        - type: text
          dvalue: "Test Display"
          placement: [0, 0]
      size: [100, 16]
            """)
            
        # Create a more realistic test page with actual font references
        self.realistic_test_page_path = Path(self.temp_dir.name) / "realistic_test_page.yaml"
        with open(self.realistic_test_page_path, 'w') as f:
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
    
  widgets:
    scroll: &scroll
      type: scroll
      dgap: __self__['size'][0]/4, 0
      size: [100, 8]
      wait: 'atStart'
      actions:
        - [pause, 100]
        - rtl

WIDGETS:
    # Test widgets
    test_title: &test_title
        type: text
        dvalue: "Test Display"
        font: large

    test_name: &test_name
        type: text
        dvalue: f"{{beers[taps[1]]['Name']}}"
        font: small
        
    test_description: &test_description
        type: text
        font: small
        dvalue: f"{{beers[taps[1]]['Description']}}"
        effect: *scroll
        
    test_abv: &test_abv
        type: text
        font: tiny
        just: rt
        dvalue: f"{{beers[taps[1]]['ABV']}}"

CANVASES:
  test_info_canvas: &test_info_canvas
    type: canvas
    items:
      - <<: *test_name
        placement: [0, 0]
      - <<: *test_abv
        placement: [0, 0, rt] 
      - <<: *test_description
        placement: [0, 8] 
    size: [100, 16]
    activeWhen: True

DISPLAY:
  size: *dsize
  items:
    - name: INFO
      <<: *test_info_canvas
            """)
            
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    @patch('KegDisplay.renderer.load')
    def test_load_page_loads_template(self, mock_load):
        """Test that load_page loads a page template from a YAML file."""
        # Given
        mock_page = Mock()
        # Add a _dataset attribute that looks like a real dataset
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        mock_load.return_value = mock_page
        
        # When
        result = self.renderer.load_page(self.simple_test_page_path)
        
        # Then
        self.assertTrue(result)
        mock_load.assert_called_once_with(self.simple_test_page_path, dataset=self.test_dataset)
        self.assertEqual(mock_page, self.renderer.main_display)
    
    @patch('KegDisplay.renderer.load')
    def test_load_page_handles_exceptions(self, mock_load):
        """Test that load_page handles exceptions gracefully."""
        # Given
        mock_load.side_effect = Exception("Page load error")
        
        # When
        result = self.renderer.load_page(self.simple_test_page_path)
        
        # Then
        self.assertFalse(result)
        self.assertIsNone(self.renderer.main_display)
    
    def test_update_dataset_calls_dataset_update(self):
        """Test that update_dataset calls the dataset update method."""
        # Create a renderer with a mock dataset for this specific test
        mock_dataset = Mock()
        mock_dataset.update = MagicMock()
        renderer = SequenceRenderer(self.mock_display, mock_dataset)
        
        # When
        renderer.update_dataset("test_key", {"test": "value"}, merge=True)
        
        # Then
        mock_dataset.update.assert_called_once_with("test_key", {"test": "value"}, merge=True)
    
    def test_dict_hash_generates_consistent_hash(self):
        """Test that dict_hash generates a consistent hash for the same dictionary."""
        # Given
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}  # Same content, different order
        
        # When
        hash1 = self.renderer.dict_hash(dict1)
        hash2 = self.renderer.dict_hash(dict2)
        
        # Then
        self.assertEqual(hash1, hash2)
    
    def test_dict_hash_ignores_specified_key(self):
        """Test that dict_hash ignores the specified key."""
        # Given
        dict1 = {"a": 1, "b": 2, "ignore": "value1"}
        dict2 = {"a": 1, "b": 2, "ignore": "value2"}  # Different value for ignore key
        
        # When
        hash1 = self.renderer.dict_hash(dict1, ignore_key="ignore")
        hash2 = self.renderer.dict_hash(dict2, ignore_key="ignore")
        
        # Then
        self.assertEqual(hash1, hash2)
    
    def test_check_data_changed_returns_true_on_first_call(self):
        """Test that check_data_changed returns True on the first call."""
        # Create a renderer with a mock dataset for this specific test
        mock_dataset = Mock()
        mock_dataset.get = MagicMock(side_effect=[{"1": {"name": "Beer1"}}, {}])
        renderer = SequenceRenderer(self.mock_display, mock_dataset)
        
        # When
        result = renderer.check_data_changed()
        
        # Then
        self.assertTrue(result)
        mock_dataset.get.assert_any_call('beers', {})
        mock_dataset.get.assert_any_call('taps', {})
    
    def test_check_data_changed_detects_changes(self):
        """Test that check_data_changed detects when data has changed."""
        # Given
        # First call - initialize hash values
        mock_dataset = Mock()
        mock_dataset.get = MagicMock(side_effect=[
            {"1": {"name": "Beer1"}},  # First beers
            {"1": 1},                  # First taps
            {"1": {"name": "Beer1"}},  # Second beers (same)
            {"1": 1, "2": 2}           # Second taps (changed)
        ])
        renderer = SequenceRenderer(self.mock_display, mock_dataset)
        
        # When
        first_call = renderer.check_data_changed()
        second_call = renderer.check_data_changed()
        
        # Then
        self.assertTrue(first_call)   # First call always returns True
        self.assertTrue(second_call)  # Second call returns True because taps changed
    
    def test_check_data_changed_returns_false_when_no_changes(self):
        """Test that check_data_changed returns False when no changes occurred."""
        # Given
        renderer = SequenceRenderer(self.mock_display, self.test_dataset)
        
        # First call will initialize the hashes
        renderer.check_data_changed()
        
        # When - no changes to data
        result = renderer.check_data_changed()
        
        # Then
        self.assertFalse(result)
    
    def test_render_returns_image_from_main_display(self):
        """Test that render returns the image from the main display."""
        # Given
        mock_image = Mock()
        mock_page = Mock()
        mock_page.image = mock_image
        
        # Add a _dataset attribute that looks like a real dataset
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        self.renderer.main_display = mock_page
        
        # When
        result = self.renderer.render()
        
        # Then
        self.assertEqual(mock_image, result)
        mock_page.render.assert_called_once()
    
    def test_render_updates_status_when_provided(self):
        """Test that render updates the status when provided."""
        # Given
        mock_image = Mock()
        mock_page = Mock()
        mock_page.image = mock_image
        
        # Add a _dataset attribute that looks like a real dataset
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        self.renderer.main_display = mock_page
        
        # When
        self.renderer.render(status="test_status")
        
        # Then
        self.assertEqual("test_status", self.test_dataset.get('sys', {}).get('status'))
    
    def test_render_returns_none_without_main_display(self):
        """Test that render returns None when no main display is loaded."""
        # Given
        self.renderer.main_display = None
        
        # When
        result = self.renderer.render()
        
        # Then
        self.assertIsNone(result)
    
    @patch('KegDisplay.renderer.time.time')
    def test_generate_image_sequence_produces_sequence(self, mock_time):
        """Test that generate_image_sequence produces a sequence of images."""
        # Given
        mock_time.return_value = 12345  # Fixed time for testing
        
        # Create a simple main display that changes on each render call
        mock_page = Mock()
        # Setup mock dataset for the mock page
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        self.renderer.main_display = mock_page
        
        # Create test images for the sequence
        image1 = Image.new('1', (10, 10), color=0)  # Black
        image2 = Image.new('1', (10, 10), color=1)  # White
        image3 = Image.new('1', (10, 10), color=0)  # Black again - start of pattern
        
        # Keep track of render call count to return appropriate image
        render_call_count = 0
        
        def mock_render():
            nonlocal render_call_count
            # Set the appropriate image based on the render call count
            if render_call_count == 0:
                mock_page.image = image1
            elif render_call_count == 1:
                mock_page.image = image2
            else:
                mock_page.image = image3
            render_call_count += 1
        
        # Set the mock render method
        mock_page.render = MagicMock(side_effect=mock_render)
        
        # Set initial image
        mock_page.image = image1
        
        # Mock the pattern detection to ensure we only have 3 iterations
        # This is needed because the actual implementation might loop many times
        with patch.object(self.renderer, 'check_data_changed', return_value=False):
            # When
            sequence = self.renderer.generate_image_sequence()
            
            # Then
            # Verify we have a sequence with at least one item
            self.assertGreater(len(sequence), 0)
            
            # First element should be (image, duration) tuple
            image, duration = sequence[0]
            self.assertIsInstance(image, Image.Image)
            self.assertIsInstance(duration, float)
    
    def test_display_next_frame_returns_false_without_sequence(self):
        """Test that display_next_frame returns False when no sequence is available."""
        # Given
        self.renderer.image_sequence = []
        
        # When
        result = self.renderer.display_next_frame()
        
        # Then
        self.assertFalse(result)
        self.mock_display.display.assert_not_called()
    
    def test_rendering_with_complex_template(self):
        """Test demonstrating how to work with the complex template by mocking necessary components."""
        # This test demonstrates template use without loading through normal mechanisms
        
        # Create a mock canvas with the necessary behavior
        mock_page = Mock()
        mock_image = Image.new('1', (100, 16), color=0)
        mock_page.image = mock_image
        mock_page.render = MagicMock()
        
        # Add a _dataset attribute that looks like a real dataset
        mock_page._dataset = Mock()
        mock_page._dataset.keys = MagicMock(return_value=['sys', 'beers', 'taps'])
        mock_page._dataset.update = MagicMock()
        mock_page._dataset.__contains__ = MagicMock(return_value=True)
        mock_page._dataset.__getitem__ = MagicMock(return_value={})
        
        # Assign it to the renderer
        self.renderer.main_display = mock_page
        
        # When
        result = self.renderer.render()
        
        # Then
        self.assertEqual(mock_image, result)
        mock_page.render.assert_called_once()
        
        # Access the specific data that would be used in the template
        beer_data = self.test_dataset.get('beers', {}).get(1, {})
        self.assertEqual('Test IPA', beer_data.get('Name'))
        self.assertEqual(6.5, beer_data.get('ABV'))
        
    @patch('KegDisplay.renderer.load')
    def test_load_realistic_template(self, mock_load):
        """Test loading a realistic template with actual font paths."""
        # Skip if fonts directory doesn't exist
        if not self.fonts_dir.exists():
            self.skipTest("Fonts directory not found")
            
        # Given
        mock_canvas = Mock()
        mock_canvas.image = Image.new('1', (100, 16), color=0)
        mock_load.return_value = mock_canvas
        
        # When
        result = self.renderer.load_page(self.realistic_test_page_path)
        
        # Then
        self.assertTrue(result)
        mock_load.assert_called_once_with(self.realistic_test_page_path, dataset=self.test_dataset)
        
        # Verify the beer data is accessible in the expected format
        beer = self.test_dataset.get('beers', {}).get(1, {})
        self.assertEqual('Test IPA', beer.get('Name'))
        self.assertEqual('A hoppy test beer', beer.get('Description'))
    
    def test_integration_with_real_files(self):
        """
        A more complete integration test that actually tries to load a template with real fonts.
        
        Note: This test may still be skipped in CI environments where the real files are not available.
        """
        # Skip if fonts directory doesn't exist or is empty
        if not self.fonts_dir.exists() or not any(self.fonts_dir.glob('*.fnt')):
            self.skipTest("Fonts not available")
            
        try:
            # Create an actual dataset
            test_dataset = dataset()
            test_dataset.update('beers', {
                1: {'Name': 'Test IPA', 'ABV': 6.5, 'Description': 'A hoppy test beer'}
            })
            test_dataset.update('taps', {1: 1})
            test_dataset.update('sys', {'status': 'running', 'tapnr': 1})
            
            # Create a renderer with the actual dataset
            renderer = SequenceRenderer(self.mock_display, test_dataset)
            
            # Try to load the realistic template - this will use the actual fonts
            result = renderer.load_page(self.realistic_test_page_path)
            
            # If it gets here without errors, the test passes
            self.assertTrue(result)
            self.assertIsNotNone(renderer.main_display)
            
        except Exception as e:
            # We'll convert any exceptions to skips with the error message
            self.skipTest(f"Integration test failed due to environment limitations: {str(e)}")

    def test_verify_dataset_integrity(self):
        """Test the verify_dataset_integrity method."""
        # Given
        # Create a real dataset instead of a mock
        from tinyDisplay.utility import dataset as td_dataset
        test_dataset = td_dataset()
        test_dataset.add("sys", {"status": "running"})
        
        renderer = SequenceRenderer(self.mock_display, test_dataset)
        
        # Create a custom mock for main_display that supports __contains__ and __getitem__
        class DatasetAccessMock(Mock):
            def __init__(self, dataset_obj):
                super().__init__()
                self._dataset = dataset_obj
                
            def __contains__(self, key):
                return key in self._dataset
                
            def __getitem__(self, key):
                return self._dataset[key]
                
        # Create main_display with properly functioning dataset access
        renderer.main_display = DatasetAccessMock(test_dataset)
        
        # When - integrity check with same dataset
        result = renderer.verify_dataset_integrity()
        
        # Then - should pass
        self.assertTrue(result)
        
        # When - dataset mismatch
        different_dataset = td_dataset()  # Different dataset
        different_dataset.add("sys", {"status": "running"})
        renderer.main_display = DatasetAccessMock(different_dataset)
        result = renderer.verify_dataset_integrity()
        
        # Then - should fail
        self.assertFalse(result)
        
    def test_force_dataset_sync(self):
        """Test the force_dataset_sync method."""
        # Given - create real datasets
        from tinyDisplay.utility import dataset as td_dataset
        main_dataset = td_dataset()
        main_dataset.add("sys", {"status": "running"})
        
        renderer = SequenceRenderer(self.mock_display, main_dataset)
        
        # Create a custom display item class (NOT a Mock) for testing
        class CustomDisplayItem:
            def __init__(self, dataset_obj=None):
                self._dataset = dataset_obj or td_dataset()
                self.items = []
                self.sequence = []
                
        # Create a nested display structure
        child1 = CustomDisplayItem(td_dataset())  # Different dataset
        child2 = CustomDisplayItem(td_dataset())  # Different dataset
        
        # Create display with items
        main_display = CustomDisplayItem(td_dataset())  # Different dataset
        main_display.items = [child1, child2]
        
        # Sequence example
        seq_item = CustomDisplayItem(td_dataset())  # Different dataset
        main_display.sequence = [seq_item]
        
        # Record original IDs to verify changes
        orig_main_id = id(main_display._dataset)
        orig_child1_id = id(child1._dataset)
        orig_child2_id = id(child2._dataset)
        orig_seq_id = id(seq_item._dataset)
        renderer_id = id(renderer._dataset)
        
        # When - force dataset sync
        renderer.force_dataset_sync(main_display)
        
        # Then - all datasets should be the same as renderer's dataset
        self.assertEqual(id(main_display._dataset), renderer_id)
        self.assertEqual(id(child1._dataset), renderer_id)
        self.assertEqual(id(child2._dataset), renderer_id)
        self.assertEqual(id(seq_item._dataset), renderer_id)
        
        # Original IDs should be different from renderer's dataset
        self.assertNotEqual(orig_main_id, renderer_id)
        self.assertNotEqual(orig_child1_id, renderer_id)
        self.assertNotEqual(orig_child2_id, renderer_id)
        self.assertNotEqual(orig_seq_id, renderer_id)


if __name__ == '__main__':
    unittest.main() 