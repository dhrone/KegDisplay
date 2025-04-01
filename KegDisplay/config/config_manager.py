"""
Configuration manager for KegDisplay

Handles loading, parsing, and validating configuration settings.
"""

import logging
import argparse
from pathlib import Path

logger = logging.getLogger("KegDisplay")


class ConfigManager:
    """Configuration manager for KegDisplay."""
    
    def __init__(self):
        """Initialize the configuration manager."""
        self.config = {
            'tap': 1,
            'display': 'ws0010',
            'interface': 'bitbang',
            'RS': 7,
            'E': 8,
            'PINS': [25, 5, 6, 12],
            'page': 'KegDisplay/page.yaml',
            'db': 'KegDisplay/beer.db',
            'log_level': 'INFO',
            'splash_time': 4,
            'resolution': (256, 64),
            'zoom': 3,
            'target_fps': 30,
            'debug': False,
        }
        
    def parse_args(self, args=None):
        """Parse command-line arguments.
        
        Args:
            args: Command-line arguments (if None, uses sys.argv)
            
        Returns:
            dict: Configuration dictionary with parsed values
        """
        parser = argparse.ArgumentParser(description='KegDisplay application')
        parser.add_argument('--log-level', 
                           default='INFO',
                           choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                           type=str.upper,
                           help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')
        parser.add_argument('--tap', 
                           type=int,
                           default=1,
                           help='Specify which tap number this server is displaying data for')
        parser.add_argument('--display',
                           choices=['ws0010', 'ssd1322', 'virtual'],
                           default='ws0010',
                           help='Select which display to use (ws0010, ssd1322, or virtual)')
        parser.add_argument('--RS', 
                           type=int,
                           help='Provide the RS pin if it is needed')
        parser.add_argument('--E', 
                           type=int,
                           help='Provide the E pin if it is needed')
        parser.add_argument('--PINS', 
                           type=int,
                           nargs='+',
                           help='Provide a list of data pins if they are needed')
        parser.add_argument('--interface',
                           choices=['bitbang', 'spi'],
                           default='bitbang',
                           help='Type of interface the display is using (bitbang or spi)')
        parser.add_argument('--page',
                           type=str,
                           default='KegDisplay/page.yaml',
                           help='Path to an alternate page file')
        parser.add_argument('--db',
                           type=str,
                           default='KegDisplay/beer.db',
                           help='Path to an alternate database file')
        parser.add_argument('--splash',
                           type=int,
                           default=4,
                           help='Number of seconds to display the splash screen')
        parser.add_argument('--resolution',
                           type=int,
                           nargs=2,
                           default=[256, 64],
                           help='Resolution for virtual display (width height)')
        parser.add_argument('--zoom',
                           type=int,
                           default=3,
                           help='Zoom factor for virtual display')
        parser.add_argument('--fps',
                           type=int,
                           default=30,
                           help='Target frames per second')
        parser.add_argument('--debug',
                           action='store_true',
                           help='Enable debug mode for performance monitoring')
                           
        parsed_args = parser.parse_args(args)
        
        # Update configuration with parsed arguments
        for key, value in vars(parsed_args).items():
            if value is not None:
                if key == 'resolution':
                    self.config[key] = tuple(value)
                elif key == 'fps':
                    self.config['target_fps'] = value
                else:
                    self.config[key] = value
        
        return self.config
    
    def validate_config(self):
        """Validate the configuration settings.
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        # Check if page file exists
        page_path = Path(self.config['page'])
        if not page_path.exists():
            logger.error(f"Page file {page_path} missing")
            return False
            
        # Check if database file exists
        db_path = Path(self.config['db'])
        if not db_path.exists():
            logger.error(f"Database file {db_path} missing")
            return False
            
        # Validate display-specific settings
        if self.config['interface'] == 'bitbang':
            # Make sure pins are provided for bitbang interface
            if self.config['display'] == 'ws0010' and (
                self.config['RS'] is None or 
                self.config['E'] is None or 
                not self.config['PINS']
            ):
                logger.error("Missing pin configuration for bitbang interface")
                return False
                
        return True
    
    def get_config(self, key=None):
        """Get configuration value(s).
        
        Args:
            key: Specific configuration key to retrieve (if None, returns all)
            
        Returns:
            Configuration value or dictionary of all values
        """
        if key is not None:
            return self.config.get(key)
        return self.config 