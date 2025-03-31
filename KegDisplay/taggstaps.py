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
        
        # Initialize components
        try:
            config_manager, display, renderer, data_manager = container.create_application_components()
            
            # Update log level based on config
            log_level = config_manager.get_config('log_level')
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
 



