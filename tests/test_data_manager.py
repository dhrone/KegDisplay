"""
Tests for the DataManager class.

These tests validate database initialization and data update functionality.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import os
import tempfile
import sqlite3

from KegDisplay.data_manager import DataManager


class TestDataManager(unittest.TestCase):
    """Test the DataManager class."""
    
    def setUp(self):
        """Set up the test fixture."""
        # Create mock renderer
        self.mock_renderer = Mock()
        self.mock_renderer.update_dataset = MagicMock()
        self.mock_renderer._dataset = {
            'sys': {'tapnr': 1},
            'beers': {
                1: {'Name': 'Test Beer', 'ABV': 5.0, 'Description': 'A test beer'},
                2: {'Name': 'Another Beer', 'ABV': 6.0, 'Description': 'Another test beer'}
            }
        }
        
        # Create temporary database file
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test.db")
        
        # Create an empty database file
        with open(self.db_path, 'w') as f:
            f.write('')  # Create empty file
        
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
    
    @patch('sqlite3.connect')
    def test_initialize_creates_database_source(self, mock_connect):
        """Test that initialize creates a database connection with the correct path."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor behavior
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertTrue(result)
        mock_connect.assert_called_once_with(self.db_path)
        self.assertEqual(mock_conn, self.data_manager.conn)
    
    @patch('sqlite3.connect')
    def test_initialize_adds_queries(self, mock_connect):
        """Test that initialize executes the required queries."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to return test data
        mock_cursor.fetchall.return_value = []
        mock_cursor.fetchone.return_value = None
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertTrue(result)
        # Check beer query
        mock_cursor.execute.assert_any_call(
            "SELECT idBeer, Name, Description, ABV FROM beers"
        )
        # Check taps query
        mock_cursor.execute.assert_any_call(
            "SELECT idTap, idBeer FROM taps"
        )
        # Check tap-specific query
        mock_cursor.execute.assert_any_call(
            "SELECT idBeer FROM taps WHERE idTap = ?", (1,)
        )
    
    @patch('sqlite3.connect')
    def test_initialize_handles_exceptions(self, mock_connect):
        """Test that initialize handles exceptions gracefully."""
        # Given
        mock_connect.side_effect = sqlite3.Error("Database error")
        
        # When
        result = self.data_manager.initialize()
        
        # Then
        self.assertFalse(result)
        self.assertIsNone(self.data_manager.conn)
    
    @patch('sqlite3.connect')
    def test_update_data_processes_beer_data(self, mock_connect):
        """Test that update_data processes beer data correctly."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to return beer data
        mock_cursor.fetchone.side_effect = [
            {'idBeer': 1},  # First call for tap query
            {  # Second call for beer query
                'idBeer': 1,
                'Name': 'Test Beer',
                'Description': 'A test beer',
                'ABV': 5.0
            }
        ]
        
        # Initialize the connection
        self.data_manager.conn = mock_conn
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        self.mock_renderer.update_dataset.assert_called_with(
            "beers",
            {1: {'Name': 'Test Beer', 'Description': 'A test beer', 'ABV': 5.0}},
            merge=True
        )
    
    @patch('sqlite3.connect')
    def test_update_data_processes_taps_data(self, mock_connect):
        """Test that update_data processes taps data correctly."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to return tap data
        mock_cursor.fetchone.side_effect = [
            {'idBeer': 2},  # First call for tap query
            {  # Second call for beer query
                'idBeer': 2,
                'Name': 'Another Beer',
                'Description': 'Another test beer',
                'ABV': 6.0
            }
        ]
        
        # Initialize the connection
        self.data_manager.conn = mock_conn
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # First call should be to update taps
        self.mock_renderer.update_dataset.assert_any_call(
            "taps",
            {1: 2},  # Key: idTap, Value: idBeer
            merge=True
        )
        # Last call should be to update beers
        self.mock_renderer.update_dataset.assert_called_with(
            "beers",
            {2: {'Name': 'Another Beer', 'ABV': 6.0, 'Description': 'Another test beer'}},
            merge=True
        )
    
    @patch('sqlite3.connect')
    def test_update_data_processes_multiple_beer_items(self, mock_connect):
        """Test that update_data processes multiple beer items correctly."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to return beer data
        mock_cursor.fetchone.side_effect = [
            {'idBeer': 1},  # First call for tap query
            {  # Second call for beer query
                'idBeer': 1,
                'Name': 'Beer 1',
                'ABV': 4.5,
                'Description': 'Test beer 1'
            }
        ]
        
        # Initialize the connection
        self.data_manager.conn = mock_conn
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        self.mock_renderer.update_dataset.assert_called_with(
            "beers",
            {1: {'Name': 'Beer 1', 'ABV': 4.5, 'Description': 'Test beer 1'}},
            merge=True
        )
    
    @patch('sqlite3.connect')
    def test_update_data_processes_multiple_tap_items(self, mock_connect):
        """Test that update_data processes multiple tap items correctly."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to return tap data
        mock_cursor.fetchone.side_effect = [
            {'idBeer': 101},  # First call for tap query
            {  # Second call for beer query
                'idBeer': 101,
                'Name': 'New Beer',
                'Description': 'A new test beer',
                'ABV': 7.0
            }
        ]
        
        # Initialize the connection
        self.data_manager.conn = mock_conn
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertTrue(result)
        # First call should be to update taps
        self.mock_renderer.update_dataset.assert_any_call(
            "taps",
            {1: 101},  # Key: idTap, Value: idBeer
            merge=True
        )
        # Last call should be to update beers
        self.mock_renderer.update_dataset.assert_called_with(
            "beers",
            {101: {'Name': 'New Beer', 'ABV': 7.0, 'Description': 'A new test beer'}},
            merge=True
        )
    
    def test_update_data_returns_false_if_src_not_initialized(self):
        """Test that update_data returns False if src is not initialized."""
        # Given
        self.data_manager.conn = None
        
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
    
    @patch('sqlite3.connect')
    def test_update_data_handles_exceptions(self, mock_connect):
        """Test that update_data handles exceptions gracefully."""
        # Given
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        
        # Setup mock cursor to raise an exception
        mock_cursor.execute.side_effect = sqlite3.Error("Database error")
        
        # Initialize the connection
        self.data_manager.conn = mock_conn
        
        # When
        result = self.data_manager.update_data()
        
        # Then
        self.assertFalse(result)
    
    def test_cleanup_method_exists(self):
        """Test that the cleanup method exists and can be called."""
        # When
        self.data_manager.cleanup()
        
        # Then
        self.assertIsNone(self.data_manager.conn)


if __name__ == '__main__':
    unittest.main() 