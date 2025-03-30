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
from PIL import Image

from KegDisplay.renderer import SequenceRenderer


class TestSequenceRenderer(unittest.TestCase):
    """Test the SequenceRenderer class."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Create mock display
        self.mock_display = Mock()
        
        # Create mock dataset
        self.mock_dataset = Mock()
        self.mock_dataset.get = MagicMock(return_value={})
        self.mock_dataset.update = MagicMock()
        
        # Create the renderer
        self.renderer = SequenceRenderer(self.mock_display, self.mock_dataset)
        
        # Create a temp directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    @patch('KegDisplay.renderer.load')
    def test_load_page_loads_template(self, mock_load):
        """Test that load_page loads a page template from a YAML file."""
        # Given
        mock_page = Mock()
        mock_load.return_value = mock_page
        page_path = os.path.join(self.temp_dir.name, "test_page.yaml")
        
        # When
        result = self.renderer.load_page(page_path)
        
        # Then
        self.assertTrue(result)
        mock_load.assert_called_once_with(page_path, dataset=self.mock_dataset)
        self.assertEqual(mock_page, self.renderer.main_display)
    
    @patch('KegDisplay.renderer.load')
    def test_load_page_handles_exceptions(self, mock_load):
        """Test that load_page handles exceptions gracefully."""
        # Given
        mock_load.side_effect = Exception("Page load error")
        page_path = os.path.join(self.temp_dir.name, "test_page.yaml")
        
        # When
        result = self.renderer.load_page(page_path)
        
        # Then
        self.assertFalse(result)
        self.assertIsNone(self.renderer.main_display)
    
    def test_update_dataset_calls_dataset_update(self):
        """Test that update_dataset calls the dataset update method."""
        # When
        self.renderer.update_dataset("test_key", {"test": "value"}, merge=True)
        
        # Then
        self.mock_dataset.update.assert_called_once_with("test_key", {"test": "value"}, merge=True)
    
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
        # Given
        self.mock_dataset.get = MagicMock(side_effect=[{"1": {"name": "Beer1"}}, {}])
        
        # When
        result = self.renderer.check_data_changed()
        
        # Then
        self.assertTrue(result)
        self.mock_dataset.get.assert_any_call('beers', {})
        self.mock_dataset.get.assert_any_call('taps', {})
    
    def test_check_data_changed_detects_changes(self):
        """Test that check_data_changed detects when data has changed."""
        # Given
        # First call - initialize hash values
        self.mock_dataset.get = MagicMock(side_effect=[
            {"1": {"name": "Beer1"}},  # First beers
            {"1": 1},                  # First taps
            {"1": {"name": "Beer1"}},  # Second beers (same)
            {"1": 1, "2": 2}           # Second taps (changed)
        ])
        
        # When
        first_call = self.renderer.check_data_changed()
        second_call = self.renderer.check_data_changed()
        
        # Then
        self.assertTrue(first_call)   # First call always returns True
        self.assertTrue(second_call)  # Second call returns True because taps changed
    
    def test_check_data_changed_returns_false_when_no_changes(self):
        """Test that check_data_changed returns False when no data has changed."""
        # Given
        # First call - initialize hash values
        self.mock_dataset.get = MagicMock(side_effect=[
            {"1": {"name": "Beer1"}},  # First beers
            {"1": 1},                  # First taps
            {"1": {"name": "Beer1"}},  # Second beers (same)
            {"1": 1}                   # Second taps (same)
        ])
        
        # When
        first_call = self.renderer.check_data_changed()
        second_call = self.renderer.check_data_changed()
        
        # Then
        self.assertTrue(first_call)    # First call always returns True
        self.assertFalse(second_call)  # Second call returns False because nothing changed
    
    def test_render_returns_image_from_main_display(self):
        """Test that render returns the image from the main display."""
        # Given
        mock_image = Mock()
        mock_page = Mock()
        mock_page.image = mock_image
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
        self.renderer.main_display = mock_page
        
        # When
        self.renderer.render(status="test_status")
        
        # Then
        self.mock_dataset.update.assert_called_once_with('sys', {'status': 'test_status'}, merge=True)
    
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


if __name__ == '__main__':
    unittest.main() 