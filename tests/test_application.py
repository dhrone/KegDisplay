"""
Tests for the Application class with dependency injection.

These tests demonstrate how dependency injection makes testing easier
by allowing us to use mock objects instead of real dependencies.
"""

import unittest
from unittest.mock import Mock, MagicMock
import time
from PIL import Image

from KegDisplay.application import Application


class TestApplication(unittest.TestCase):
    """Test the Application class."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Create mock dependencies
        self.mock_config_manager = Mock()
        self.mock_display = Mock()
        self.mock_renderer = Mock()
        self.mock_data_manager = Mock()
        
        # Configure mocks with necessary functionality
        self.mock_renderer.check_data_changed = MagicMock(return_value=False)
        self.mock_renderer.render = MagicMock(return_value=Image.new('1', (100, 16)))
        
        # Create application with mock dependencies
        self.app = Application(
            self.mock_config_manager,
            self.mock_display,
            self.mock_renderer,
            self.mock_data_manager
        )
        
    def test_signal_handler(self):
        """Test that the signal handler sets exit_requested."""
        # When
        self.app._sigterm_handler(15, None)
        
        # Then
        self.assertTrue(self.app.exit_requested)
        
    def test_cleanup(self):
        """Test that cleanup calls cleanup on dependencies."""
        # When
        self.app.cleanup()
        
        # Then
        self.mock_data_manager.cleanup.assert_called_once()
        self.mock_display.cleanup.assert_called_once()
        
    def test_run_checks_data_and_updates_display(self):
        """Test that run checks for data updates and updates the display."""
        # Given
        self.app.exit_requested = True  # Exit after first loop
        
        # When
        self.app.run()
        
        # Then
        self.mock_data_manager.update_data.assert_called()
        self.mock_renderer.render.assert_called()
        self.mock_renderer.generate_image_sequence.assert_called()
        
    def test_run_checks_renderer_for_changes(self):
        """Test that run checks the renderer for data changes."""
        # Given
        self.app.exit_requested = True  # Exit after first loop
        self.mock_renderer.check_data_changed = MagicMock(return_value=True)
        
        # When
        self.app.run()
        
        # Then
        self.mock_renderer.check_data_changed.assert_called()
        self.mock_renderer.render.assert_called_with("update")
        self.mock_renderer.generate_image_sequence.assert_called()
        
    def test_run_displays_next_frame(self):
        """Test that run displays the next frame."""
        # Given
        self.app.exit_requested = True  # Exit after first loop
        
        # When
        self.app.run()
        
        # Then
        self.mock_renderer.display_next_frame.assert_called()


if __name__ == '__main__':
    unittest.main() 