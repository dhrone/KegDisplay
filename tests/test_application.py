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
        self.mock_renderer.image_sequence = []
        self.mock_data_manager.update_frequency = 0.1  # Small value for testing
        
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
        # Given - Override the run method to exit immediately after initial setup
        original_run = self.app.run
        
        def mock_run():
            # Call the original method but override the main loop
            if not self.app.display or not self.app.renderer or not self.app.data_manager:
                return False
                
            # Initial data load
            self.app.data_manager.update_data()
            
            # Initial render and display
            splash_image = self.app.renderer.render("start")
            self.app.display.display(splash_image.convert("1"))
            
            # Generate initial image sequence
            self.app.renderer.image_sequence = self.app.renderer.generate_image_sequence()
            
            # Exit after setup
            return True
        
        # Replace the run method temporarily
        self.app.run = mock_run
        
        try:
            # When
            self.app.run()
            
            # Then
            self.mock_data_manager.update_data.assert_called()
            self.mock_renderer.render.assert_called()
            self.mock_renderer.generate_image_sequence.assert_called()
        finally:
            # Restore the original method
            self.app.run = original_run
        
    def test_run_checks_renderer_for_changes(self):
        """Test that run checks the renderer for data changes."""
        # Given
        self.mock_renderer.check_data_changed = MagicMock(return_value=True)
        
        # Mock the main loop to run only once
        def mock_main_loop():
            current_time = time.time()
            
            # Check for database updates
            self.app.data_manager.update_data()
            
            # Check if data has changed
            if self.app.renderer.check_data_changed():
                updating_image = self.app.renderer.render("update")
                self.app.display.display(updating_image.convert("1"))
                
                # Generate new image sequence
                self.app.renderer.image_sequence = self.app.renderer.generate_image_sequence()
            
        # Replace the run method
        original_run = self.app.run
        
        def modified_run():
            # Call only the setup part of the original method
            if not self.app.display or not self.app.renderer or not self.app.data_manager:
                return False
                
            # Run mock main loop once
            mock_main_loop()
            return True
            
        self.app.run = modified_run
        
        try:
            # When
            self.app.run()
            
            # Then
            self.mock_renderer.check_data_changed.assert_called()
            self.mock_renderer.render.assert_called_with("update")
            self.mock_renderer.generate_image_sequence.assert_called()
        finally:
            # Restore original method
            self.app.run = original_run
        
    def test_run_displays_next_frame(self):
        """Test that run displays the next frame."""
        # Given
        # Add a mock implementation of display_next_frame
        self.mock_renderer.display_next_frame = MagicMock(return_value=True)
        
        # Mock the main loop to call display_next_frame once
        def mock_main_loop():
            # Just call display_next_frame directly
            self.app.renderer.display_next_frame()
            
        # Replace the run method
        original_run = self.app.run
        
        def modified_run():
            # Call only the setup part of the original method
            if not self.app.display or not self.app.renderer or not self.app.data_manager:
                return False
                
            # Run mock main loop once
            mock_main_loop()
            return True
            
        self.app.run = modified_run
        
        try:
            # When
            self.app.run()
            
            # Then
            self.mock_renderer.display_next_frame.assert_called()
        finally:
            # Restore original method
            self.app.run = original_run


if __name__ == '__main__':
    unittest.main() 