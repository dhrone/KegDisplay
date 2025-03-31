# -*- coding: utf-8 -*-
# Copyright (c) 2024 Ron Ritchey
# See License for details

"""
Main module for taggstaps program

.. versionadded:: 0.0.1
"""

import sys
import logging
import signal
import os

# Configure logging
LOG_FILE = "/var/log/KegDisplay/taggstaps.log"
LOGGER_NAME = "KegDisplay"

# Set up logger
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)

# Create handlers if they don't exist already
if not logger.handlers:
    # Create a clean formatter
    class CleanFormatter(logging.Formatter):
        """Custom formatter that ensures clean, left-aligned output with proper line endings in raw mode."""
        def format(self, record):
            # Clean any existing whitespace and handle slow render messages
            record.msg = record.msg.strip()
            # Format the message and ensure proper line endings
            return super().format(record)
            
    # Create file handler
    try:
        # Ensure log directory exists
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        file_handler.setFormatter(CleanFormatter('%(asctime)s - %(levelname)-8s - %(message)s'))
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logging: {e}")
    
    # Create console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(CleanFormatter('%(asctime)s - %(levelname)-8s - %(message)s'))
    logger.addHandler(stream_handler)
    
# Import our application class
from .application import Application
from .dependency_container import DependencyContainer


def start():
    """
    Main entry point for the taggstaps program.
    
    This function initializes and runs the KegDisplay application.
    """
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
        
        # Initialize components
        try:
            config_manager, display, renderer, data_manager = container.create_application_components()
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
 



