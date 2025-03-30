"""
Tests for the DataManager class.

These tests validate database initialization and data update functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import os
import tempfile

from KegDisplay.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    """Test the DataManager class."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Create mock renderer
        self.mock_renderer = Mock()
        self.mock_renderer.update_dataset = MagicMock()
        
        # Create temporary database file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        
        # Use a faster update frequency for testing
        self.update_frequency = 0.1
        
        # Create data manager with mock renderer
        self.data_manager = DataManager(
            self.db_path, 
            self.mock_renderer,
            update_frequency=self.update_frequency
        )
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    @patch('KegDisplay.data_manager.database')
    def test_initialize_creates_database_source(self, mock_database):
        """Test that initialize creates a database source with the correct path."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertTrue(result)
        mock_database.assert_called_once_with(f'sqlite+aiosqlite:///{self.db_path}')
        self.assertEqual(mock_db_instance, self.data_manager.src)
    
    @patch('KegDisplay.data_manager.database')
    def test_initialize_adds_queries(self, mock_database):
        """Test that initialize adds the required queries."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertTrue(result)
        self.assertEqual(2, mock_db_instance.add.call_count)
        # Check beer query
        mock_db_instance.add.assert_any_call(
            "SELECT idBeer, Name, Description, ABV from beers", 
            name='beer', 
            frequency=self.update_frequency
        )
        # Check taps query
        mock_db_instance.add.assert_any_call(
            "SELECT idTap, idBeer from taps", 
            name='taps', 
            frequency=self.update_frequency
        )
    
    @patch('KegDisplay.data_manager.database')
    def test_initialize_handles_exceptions(self, mock_database):
        """Test that initialize handles exceptions gracefully."""
        # Given
        mock_database.side_effect = Exception("Database error")
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertFalse(result)
        self.assertIsNone(self.data_manager.src)
    
    @patch('KegDisplay.data_manager.database')
    def test_update_data_processes_beer_data(self, mock_database):
        """Test that update_data processes beer data correctly."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # Setup mock to return beer data once, then None
        mock_db_instance.get = MagicMock(side_effect=[
            {'beer': {'idBeer': 1, 'Name': 'Test Beer', 'Description': 'A test beer', 'ABV': 5.0}},
            None
        ])
        
        self.data_manager.initialize()
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # The actual implementation passes the beer data directly to update_dataset
        self.mock_renderer.update_dataset.assert_called_once_with(
            "beers",
            {'idBeer': 1, 'Name': 'Test Beer', 'Description': 'A test beer', 'ABV': 5.0},
            merge=True
        )
    
    @patch('KegDisplay.data_manager.database')
    def test_update_data_processes_taps_data(self, mock_database):
        """Test that update_data processes taps data correctly."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # Setup mock to return taps data once, then None
        mock_db_instance.get = MagicMock(side_effect=[
            {'taps': {'idTap': 1, 'idBeer': 2}},
            None
        ])
        
        self.data_manager.initialize()
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # The actual implementation transforms taps data into a different format
        self.mock_renderer.update_dataset.assert_called_once_with(
            "taps",
            {1: 2},  # Key: idTap, Value: idBeer
            merge=True
        )
    
    @patch('KegDisplay.data_manager.database')
    def test_update_data_processes_multiple_beer_items(self, mock_database):
        """Test that update_data processes multiple beer items correctly."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # Setup mock to return multiple beer items, then None
        mock_db_instance.get = MagicMock(side_effect=[
            {'beer': [
                {'idBeer': 1, 'Name': 'Beer 1', 'ABV': 4.5},
                {'idBeer': 2, 'Name': 'Beer 2', 'ABV': 5.5}
            ]},
            None
        ])
        
        self.data_manager.initialize()
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # Check that update_dataset was called twice, once for each beer
        self.assertEqual(2, self.mock_renderer.update_dataset.call_count)
        # The actual implementation transforms the beer items by removing the idBeer from the inner dict
        self.mock_renderer.update_dataset.assert_any_call(
            "beers",
            {1: {'Name': 'Beer 1', 'ABV': 4.5}},  # idBeer becomes the key
            merge=True
        )
        self.mock_renderer.update_dataset.assert_any_call(
            "beers",
            {2: {'Name': 'Beer 2', 'ABV': 5.5}},  # idBeer becomes the key
            merge=True
        )
    
    @patch('KegDisplay.data_manager.database')
    def test_update_data_processes_multiple_tap_items(self, mock_database):
        """Test that update_data processes multiple tap items correctly."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # Setup mock to return multiple tap items, then None
        mock_db_instance.get = MagicMock(side_effect=[
            {'taps': [
                {'idTap': 1, 'idBeer': 101},
                {'idTap': 2, 'idBeer': 102}
            ]},
            None
        ])
        
        self.data_manager.initialize()
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # Check that update_dataset was called twice, once for each tap
        self.assertEqual(2, self.mock_renderer.update_dataset.call_count)
        # The actual implementation transforms tap data to {idTap: idBeer} format
        self.mock_renderer.update_dataset.assert_any_call(
            "taps",
            {1: 101},  # Key: idTap, Value: idBeer
            merge=True
        )
        self.mock_renderer.update_dataset.assert_any_call(
            "taps",
            {2: 102},  # Key: idTap, Value: idBeer
            merge=True
        )
    
    def test_update_data_returns_false_if_src_not_initialized(self):
        """Test that update_data returns False if src is not initialized."""
        # Given
        self.data_manager.src = None
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertFalse(result)
        self.mock_renderer.update_dataset.assert_not_called()
    
    def test_update_data_returns_false_if_renderer_not_initialized(self):
        """Test that update_data returns False if renderer is not initialized."""
        # Given
        self.data_manager.renderer = None
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertFalse(result)
    
    @patch('KegDisplay.data_manager.database')
    def test_update_data_handles_exceptions(self, mock_database):
        """Test that update_data handles exceptions gracefully."""
        # Given
        mock_db_instance = Mock()
        mock_database.return_value = mock_db_instance
        
        # Setup mock to raise an exception
        mock_db_instance.get = MagicMock(side_effect=Exception("Database error"))
        
        self.data_manager.initialize()
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertFalse(result)
        self.mock_renderer.update_dataset.assert_not_called()
    
    def test_cleanup_method_exists(self):
        """Test that the cleanup method exists and can be called."""
        # When/Then - just verify it can be called without errors
        self.data_manager.cleanup()


if __name__ == '__main__':
    unittest.main() 