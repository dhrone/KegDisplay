"""
Centralized logging configuration for KegDisplay

This module handles all logging configuration to ensure consistent behavior
across all parts of the application.
"""

import os
import logging
import sys

# Constants
LOG_FILE = "/var/log/KegDisplay/taggstaps.log"
LOGGER_NAME = "KegDisplay"

# Custom formatter for clean log messages
class CleanFormatter(logging.Formatter):
    """Custom formatter that ensures clean, left-aligned output with proper line endings."""
    def format(self, record):
        # Clean any existing whitespace and handle slow render messages
        record.msg = record.msg.strip()
        # Format the message and ensure proper line endings
        return super().format(record)

def configure_logging(log_level=None):
    """
    Configure the logging system with the specified log level.
    
    Args:
        log_level: The log level as a string ('DEBUG', 'INFO', etc.) or
                  a logging level constant (logging.DEBUG, logging.INFO, etc.)
                  
    Returns:
        The configured logger
    """
    # Create a temporary basic logger to track the configuration process
    temp_logger = logging.getLogger("temp")
    temp_logger.setLevel(logging.DEBUG)
    if not temp_logger.handlers:
        temp_handler = logging.StreamHandler()
        temp_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        temp_logger.addHandler(temp_handler)
    
    temp_logger.error(f"configure_logging called with log_level={log_level} (type: {type(log_level)})")
    
    # Get the logger
    logger = logging.getLogger(LOGGER_NAME)
    
    # Clear any existing handlers to avoid duplicates when reconfigured
    if logger.handlers:
        temp_logger.error(f"Clearing {len(logger.handlers)} existing handlers")
        logger.handlers.clear()
    
    # Set the initial level to DEBUG to capture everything, will be filtered by handlers
    logger.setLevel(logging.DEBUG)
    temp_logger.error(f"Set logger level to DEBUG ({logging.DEBUG})")
    
    # Determine the effective log level
    effective_level = log_level
    
    # If a string is provided, convert it to the corresponding logging level
    if isinstance(effective_level, str):
        temp_logger.error(f"Converting string '{effective_level}' to logging level")
        level_value = getattr(logging, effective_level.upper(), None)
        if level_value is None:
            temp_logger.error(f"Could not convert '{effective_level}' to a valid logging level, using INFO")
            effective_level = logging.INFO
        else:
            effective_level = level_value
            temp_logger.error(f"Converted to {effective_level}")
    # If nothing is provided, default to INFO
    elif effective_level is None:
        temp_logger.error("No log level provided, defaulting to INFO")
        effective_level = logging.INFO
    else:
        temp_logger.error(f"Using provided numeric level: {effective_level}")
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(effective_level)
    temp_logger.error(f"Created console handler with level {effective_level}")
    console_handler.setFormatter(CleanFormatter('%(asctime)s - %(levelname)-8s - %(message)s'))
    logger.addHandler(console_handler)
    
    # Create file handler if possible
    try:
        # Ensure log directory exists
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE)
        # File handler now uses the same level as the console handler
        file_handler.setLevel(effective_level)
        temp_logger.error(f"Created file handler with level {effective_level}")
        file_handler.setFormatter(CleanFormatter('%(asctime)s - %(levelname)-8s - %(message)s'))
        logger.addHandler(file_handler)
    except Exception as e:
        # Log to console if file logging setup fails
        temp_logger.error(f"Could not set up file logging: {e}")
    
    # Cleanup the temporary logger
    temp_logger.handlers.clear()
    
    # Log the configuration
    logger.debug(f"Logging configured with level: {logging.getLevelName(effective_level)}")
    for i, handler in enumerate(logger.handlers):
        handler_level = logging.getLevelName(handler.level)
        logger.debug(f"Handler {i} ({handler.__class__.__name__}) configured with level: {handler_level}")
        
    return logger

def update_log_level(log_level):
    """
    Update the log level of all handlers.
    
    Args:
        log_level: The new log level as a string or logging constant
    """
    # Create a temporary basic logger to trace the process
    temp_logger = logging.getLogger("temp")
    temp_logger.setLevel(logging.DEBUG)
    if not temp_logger.handlers:
        temp_handler = logging.StreamHandler()
        temp_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        temp_logger.addHandler(temp_handler)
    
    temp_logger.error(f"update_log_level called with log_level={log_level} (type: {type(log_level)})")
    
    # Get the logger
    logger = logging.getLogger(LOGGER_NAME)
    
    # Convert string level to logging constant if needed
    if isinstance(log_level, str):
        temp_logger.error(f"Converting string '{log_level}' to logging level")
        level_value = getattr(logging, log_level.upper(), None)
        if level_value is None:
            temp_logger.error(f"Could not convert '{log_level}' to a valid logging level, using INFO")
            log_level = logging.INFO
        else:
            log_level = level_value
            temp_logger.error(f"Converted to {log_level}")
    elif log_level is None:
        temp_logger.error("No log level provided, defaulting to INFO")
        log_level = logging.INFO
    else:
        temp_logger.error(f"Using provided numeric level: {log_level}")
    
    # Update all handlers to the same level
    temp_logger.error(f"Updating {len(logger.handlers)} handlers to level {log_level}")
    for i, handler in enumerate(logger.handlers):
        temp_logger.error(f"Handler {i} ({handler.__class__.__name__}) level before: {handler.level}")
        handler.setLevel(log_level)
        temp_logger.error(f"Handler {i} ({handler.__class__.__name__}) level after: {handler.level}")
    
    # Cleanup the temporary logger
    temp_logger.handlers.clear()
            
    logger.debug(f"All handler log levels updated to: {logging.getLevelName(log_level)}") 