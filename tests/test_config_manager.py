"""
Tests for the ConfigManager class.

These tests validate the configuration loading, parsing, and validation functionality.
"""

import unittest
from unittest.mock import patch, mock_open
import os
import tempfile
from pathlib import Path

from KegDisplay.config import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Test the ConfigManager class."""
    
    def setUp(self):
        """Set up the test fixture."""
        self.config_manager = ConfigManager()
        
        # Create temporary files for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.page_file = Path(self.temp_dir.name) / "test_page.yaml"
        self.db_file = Path(self.temp_dir.name) / "test_db.db"
        
        # Create the test files
        self.page_file.write_text("# Test page file")
        self.db_file.write_text("# Test database file")
    
    def tearDown(self):
        """Clean up after the test."""
        self.temp_dir.cleanup()
    
    def test_default_config_values(self):
        """Test that default configuration values are set correctly."""
        config = self.config_manager.get_config()
        
        self.assertEqual(1, config['tap'])
        self.assertEqual('ws0010', config['display'])
        self.assertEqual('bitbang', config['interface'])
        self.assertEqual(7, config['RS'])
        self.assertEqual(8, config['E'])
        self.assertEqual([25, 5, 6, 12], config['PINS'])
        self.assertEqual('KegDisplay/page.yaml', config['page'])
        self.assertEqual('KegDisplay/beer.db', config['db'])
        self.assertEqual('INFO', config['log_level'])
    
    def test_parse_args_updates_config(self):
        """Test that parse_args updates the configuration with provided values."""
        # When
        args = [
            '--log-level', 'DEBUG',
            '--tap', '2',
            '--display', 'ssd1322',
            '--interface', 'spi',
            '--page', str(self.page_file),
            '--db', str(self.db_file)
        ]
        self.config_manager.parse_args(args)
        
        # Then
        config = self.config_manager.get_config()
        self.assertEqual('DEBUG', config['log_level'])
        self.assertEqual(2, config['tap'])
        self.assertEqual('ssd1322', config['display'])
        self.assertEqual('spi', config['interface'])
        self.assertEqual(str(self.page_file), config['page'])
        self.assertEqual(str(self.db_file), config['db'])
    
    def test_parse_args_with_pins(self):
        """Test that parse_args correctly handles pin configurations."""
        # When
        args = [
            '--RS', '10',
            '--E', '11',
            '--PINS', '20', '21', '22', '23'
        ]
        self.config_manager.parse_args(args)
        
        # Then
        config = self.config_manager.get_config()
        self.assertEqual(10, config['RS'])
        self.assertEqual(11, config['E'])
        self.assertEqual([20, 21, 22, 23], config['PINS'])
    
    def test_validate_config_with_valid_files(self):
        """Test that validate_config returns True when files exist."""
        # Given
        self.config_manager.config['page'] = str(self.page_file)
        self.config_manager.config['db'] = str(self.db_file)
        
        # When/Then
        self.assertTrue(self.config_manager.validate_config())
    
    def test_validate_config_with_missing_page_file(self):
        """Test that validate_config returns False when page file is missing."""
        # Given
        self.config_manager.config['page'] = str(Path(self.temp_dir.name) / "nonexistent.yaml")
        self.config_manager.config['db'] = str(self.db_file)
        
        # When/Then
        self.assertFalse(self.config_manager.validate_config())
    
    def test_validate_config_with_missing_db_file(self):
        """Test that validate_config returns False when db file is missing."""
        # Given
        self.config_manager.config['page'] = str(self.page_file)
        self.config_manager.config['db'] = str(Path(self.temp_dir.name) / "nonexistent.db")
        
        # When/Then
        self.assertFalse(self.config_manager.validate_config())
    
    def test_validate_config_with_missing_pin_config(self):
        """Test that validate_config returns False when pins are missing for bitbang interface."""
        # Given
        self.config_manager.config['page'] = str(self.page_file)
        self.config_manager.config['db'] = str(self.db_file)
        self.config_manager.config['interface'] = 'bitbang'
        self.config_manager.config['display'] = 'ws0010'
        self.config_manager.config['RS'] = None
        
        # When/Then
        self.assertFalse(self.config_manager.validate_config())
    
    def test_get_config_returns_all(self):
        """Test that get_config returns the entire config when no key is provided."""
        # When
        config = self.config_manager.get_config()
        
        # Then
        self.assertEqual(9, len(config))  # 9 config items
        self.assertEqual(1, config['tap'])
    
    def test_get_config_returns_specific_key(self):
        """Test that get_config returns a specific config value when a key is provided."""
        # When
        tap_value = self.config_manager.get_config('tap')
        display_value = self.config_manager.get_config('display')
        
        # Then
        self.assertEqual(1, tap_value)
        self.assertEqual('ws0010', display_value)


if __name__ == '__main__':
    unittest.main() 