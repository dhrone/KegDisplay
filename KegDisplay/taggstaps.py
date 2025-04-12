# -*- coding: utf-8 -*-
# Copyright (c) 2024 Ron Ritchey
# See License for details

"""
Main module for taggstaps program

.. versionadded:: 0.0.1
"""

import sys
import signal
import os
import argparse

# Import logging configuration first, before any other modules
from .log_config import configure_logging, update_log_level, LOGGER_NAME
import logging

# Import our application class
from .application import Application
from .dependency_container import DependencyContainer

# Set up initial logger with default level (will be updated after parsing args)
logger = configure_logging()

def start():
    """
    Main entry point for the taggstaps program.
    
    This function initializes and runs the KegDisplay application.
    """
    logger.debug("Starting KegDisplay application")
    
    # Move unhandled exception messages to log file
    def handle_uncaught_exceptions(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_uncaught_exceptions
    
    try:
        # Create dependency container
        container = DependencyContainer()
        
        # Initialize components - IMPORTANT: Pass sys.argv to ensure command line args are used
        try:
            # Parse command line arguments
            parser = argparse.ArgumentParser(description='KegDisplay application')
            parser.add_argument('--display', type=str, choices=['ws0010', 'ssd1322', 'virtual'], help='Display type')
            parser.add_argument('--interface', type=str, choices=['bitbang', 'spi', 'pigpio'], help='Interface type')
            parser.add_argument('--RS', type=int, help='RS pin for bitbang interface')
            parser.add_argument('--E', type=int, help='E pin for bitbang interface')
            parser.add_argument('--PINS', type=int, nargs='+', help='Data pins for bitbang interface')
            parser.add_argument('--DC', type=int, default=24, help='DC pin for SPI interface (default: 24)')
            parser.add_argument('--RST', type=int, default=25, help='RST pin for SPI interface (default: 25)')
            parser.add_argument('--tap', type=int, help='Tap number')
            parser.add_argument('--page', type=str, help='Page template file')
            parser.add_argument('--db', type=str, help='Database file')
            parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'], help='Log level')
            
            args = parser.parse_args(sys.argv[1:])
            
            # Convert args to dict for config manager
            config_args = vars(args)
            
            # Initialize components with the parsed arguments
            config_manager, display, renderer, data_manager = container.create_application_components(args=config_args)
            
            # Update log level based on config
            log_level = config_manager.get_config('log_level')
            
            # IMPORTANT: Ensure log level is explicitly set to proper DEBUG constant
            # rather than relying on string conversion which might be failing
            if isinstance(log_level, str) and log_level.upper() == 'DEBUG':
                update_log_level(logging.DEBUG)
            else:
                # For other levels, use the normal mechanism
                if isinstance(log_level, str):
                    log_level = log_level.upper()
                update_log_level(log_level)
                
            logger.debug(f"Log level updated to {log_level} based on command-line arguments")
                
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return 1
            
        # Create and run the application with injected dependencies
        app = Application(renderer, data_manager, config_manager)
        return 0 if app.run() else 1
        
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, exiting")
        return 0
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
        return 1
        

if __name__ == "__main__":
    sys.exit(start())
 



