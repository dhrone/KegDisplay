# -*- coding: utf-8 -*-
# Copyright (c) 2024 Ron Ritchey
# See License for details

"""
Main class for taggstaps program

.. versionadded:: 0.0.1
"""

import signal
import logging
import sys
import os
import time
import math
import json
import argparse
from pathlib import Path
from collections import deque
from pprint import pprint
import select
import termios
import tty

from pyAttention.source import database
from tinyDisplay.render.collection import canvas, sequence
from tinyDisplay.render.widget import text
from tinyDisplay.utility import dataset, image2Text
from tinyDisplay.cfg import _tdLoader, load
from tinyDisplay.utility import animate
from luma.core.interface.parallel import bitbang_6800
from luma.core.interface.serial import spi
from luma.oled.device import ws0010, ssd1322

DB_PATH = "KegDisplay/beer.db"
DATABASE_UPDATE_FREQUENCY = 2.5
RENDER_FREQUENCY = 20
SPLASH_SCREEN_TIME = 2
MAX_STATIC_RENDER_TIME = 5
MAX_STATIC_RENDERS = RENDER_FREQUENCY * MAX_STATIC_RENDER_TIME
LOG_FILE = "/var/log/KegDisplay/taggstaps.log"
LOGGER_NAME = "KegDisplay"

# First, let's modify the logging setup to force clean output
class CleanFormatter(logging.Formatter):
    """Custom formatter that ensures clean, left-aligned output with proper line endings in raw mode."""
    def format(self, record):
        # Clean any existing whitespace and handle slow render messages
        record.msg = record.msg.strip()
        # Format the message and ensure proper line endings
        return super().format(record)

# Update the logging setup
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)

# Create handlers
file_handler = logging.FileHandler(LOG_FILE)
stream_handler = logging.StreamHandler()

# Create and set formatter
formatter = CleanFormatter('%(asctime)s - %(levelname)-8s - %(message)s')
file_handler.setFormatter(formatter)  # File handler gets the same formatter but file system will handle line endings
stream_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(stream_handler)


exit_requested = False


def sigterm_handler(_signo, _stack_frame):
    """Handle SIGTERM signal gracefully by exiting the program.

    Args:
        _signo: Signal number
        _stack_frame: Current stack frame
    """
    global exit_requested
    logger.info("SIGTERM received, initiating shutdown")
    exit_requested = True

def start():
    old_settings = None
    try:
        
        # Add argument parsing
        parser = argparse.ArgumentParser(description='KegDisplay application')
        parser.add_argument('--log-level', 
                           default='INFO',
                           choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                           type=str.upper,
                           help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)')

        args = parser.parse_args()

        signal.signal(signal.SIGTERM, sigterm_handler)

        # Variables for tracking render frequency
        render_count = 0
        last_render_print_time = time.time()
        render_start_time = time.time()

        # Update the log level based on command line argument
        logger.setLevel(getattr(logging, args.log_level))

        # Set third-party loggers to their default levels
        logging.getLogger(u'socketIO-client').setLevel(logging.WARNING)

        # Move unhandled exception messages to log file
        def handleuncaughtexceptions(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return

            logger.error(u"Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            try:
                if len(mc.musicdata) > 0:
                    logger.error(u"Status at exception")
                    logger.error(unicode(mc.musicdata))
            except NameError:
                # If this gets called before the music controller is instantiated, ignore it
                pass

            sys.__excepthook__(exc_type, exc_value, exc_traceback)


        sys.excepthook = handleuncaughtexceptions

        dbPath = "KegDisplay/beer.db"
        if Path(dbPath).exists() is False:
            raise FileNotFoundError(f"Database file {dbPath} missing")
        
        src = database(f'sqlite+aiosqlite:///{dbPath}')
        src.add("SELECT idBeer, Name, Description, ABV from beers", name='beer', frequency = 5)
        src.add("SELECT idTap, idBeer from taps", name='taps', frequency = 5)

        ds = dataset()
        ds.add("sys", {"tapnr": 1, "status": "start"})
        ds.add("beers", {})
        ds.add("taps", {})

        path = Path(__file__).parent / "page.yaml"
        if path.exists() is False:
            raise FileNotFoundError(f"Page file {path} missing")
        main = load(path, dataset=ds)

        #interface = bitbang_6800(RS=7, E=8, PINS=[25,24,23,27])
        interface = bitbang_6800(RS=7, E=8, PINS=[25,5,6,12])
        #interface = bitbang_6800(RS=24, E=25, PINS=[16,26,20,21])
        #interface = spi()
        screen = ws0010(interface)
        #screen = ssd1322(serial_interface=interface, mode='1')

        def dict_hash(dictionary, ignore_key=None):
            """Generate a hash of a dictionary, optionally ignoring a specific key.

            Args:
                dictionary (dict): Dictionary to hash
                ignore_key (str, optional): Key to ignore when generating hash

            Returns:
                int: Hash value of the dictionary
            """
            filtered_dict = {k: v for k, v in dictionary.items() if k != ignore_key}
            # Convert all keys to strings before dumping to JSON
            string_dict = {str(k): v for k, v in filtered_dict.items()}
            return hash(json.dumps(string_dict, sort_keys=True))

        def update_data(db_src, ds):
            """Update dataset with latest information from database.

            Args:
                db_src: Database source object
                ds: Dataset object to update
            """
            while True:
                db_row = db_src.get(0.001)
                if db_row is None:
                    break
                
                for key, value in db_row.items():
                    if key == 'beer':
                        if isinstance(value, dict):
                            ds.update("beers", value, merge=True)
                        else:
                            for item in value:
                                if 'idBeer' in item:
                                    ds.update(
                                        "beers",
                                        {item['idBeer']: {k: v for k, v in item.items() if k != 'idBeer'}},
                                        merge=True
                                    )
                    if key == 'taps':
                        if isinstance(value, dict):
                            ds.update("taps", value, merge=True)
                        else:
                            for item in value:
                                if 'idTap' in item:
                                    ds.update("taps", {item['idTap']: item['idBeer']}, merge=True)

        update_data(src, main._dataset)
        beersHash = dict_hash(main._dataset.get('beers'), '__timestamp__')
        tapsHash = dict_hash(main._dataset.get('taps'), '__timestamp__')
        main.render()
        
        startTime = displayStartTime = time.time()
        displayCount = 0

        def generate_complete_image_set(display):
            """Generate all possible unique images for the current data state."""
            # Initialize variables
            global exit_requested                     # Exit requested flag
            image_sequence = []                       # Stores (image, duration) pairs
            raw_frames = []                           # Store raw frame bytes for faster comparison
            min_sequence_length = MAX_STATIC_RENDERS  # Minimum frames to collect before checking for loops
            max_iterations = 2000                     # Safety limit to prevent infinite loops
            last_image = None                         # Previous frame for comparison
            static_count = 0                          # Counter for consecutive identical frames

            start_time = time.time()            
            logger.debug("Starting image sequence generation")
            
            # Main loop to generate frames
            for i in range(max_iterations):
                if exit_requested:
                    image_sequence = []
                    break

                # Generate next frame
                display.render()
                current_image = display.image.convert("1")
                current_bytes = current_image.tobytes()
                
                # Add to our raw frames collection for pattern matching
                raw_frames.append(current_bytes)
                
                # Process the frame
                if last_image is not None:
                    last_bytes = last_image.tobytes()
                    
                    # Check if frame is identical to previous
                    if current_bytes == last_bytes:
                        # Frame hasn't changed
                        static_count += 1
                    else:
                        # Frame has changed
                        if static_count > 0:
                            # Store the previous static frame with its duration
                            image_sequence.append((last_image, static_count / RENDER_FREQUENCY))
                        static_count = 0
                        # Store the new frame
                        image_sequence.append((current_image, 1 / RENDER_FREQUENCY))
                else:
                    # First frame
                    image_sequence.append((current_image, 1 / RENDER_FREQUENCY))
                    
                last_image = current_image
                
                # Start checking for loops after collecting enough frames
                if len(raw_frames) > min_sequence_length:
                    # Check if the recent frames match the beginning of the sequence
                    # We'll look for a pattern of at least 10 frames
                    pattern_length = 10
                    
                    # Only check when we have enough frames to make a meaningful comparison
                    if len(raw_frames) >= pattern_length * 2:
                        # Get the most recent frames
                        recent_frames = raw_frames[-pattern_length:]
                        # Get the same number of frames from the beginning
                        start_frames = raw_frames[:pattern_length]
                        
                        # Check if recent frames match the start frames
                        matches = True
                        for j in range(pattern_length):
                            if recent_frames[j] != start_frames[j]:
                                matches = False
                                break
                        
                        if matches:
                            # We found a match! Now determine the exact sequence length
                            sequence_length = len(raw_frames) - pattern_length
                            logger.debug(f"Found repeating pattern in {time.time()-start_time:.1f} seconds after searching {sequence_length} frames")
                            
                            # Add any remaining static frames
                            if static_count > 0:
                                image_sequence.append((last_image, static_count / RENDER_FREQUENCY))
                            
                            # Trim the sequence to just one complete cycle
                            return image_sequence[:sequence_length]
            
            # If we hit max iterations without finding a pattern
            logger.warning(f"Reached maximum iterations ({max_iterations}) - using collected frames")
            if static_count > 0:
                image_sequence.append((last_image, static_count / RENDER_FREQUENCY))
            return image_sequence

        def main_loop(screen, main_display, src):
            """Main program loop handling display updates and data synchronization."""
            logger.debug("Starting Main Loop")

            global exit_requested
            
            image_sequence = []
            first_time = True
            sequence_index = 0
            last_frame_time = time.time()
            last_db_check_time = 0
            beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
            taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
            
            start_time = display_start_time = time.time()
            display_count = 0

            while not exit_requested:
                try:
                    current_time = time.time()

                    # Check for database updates at specified frequency
                    if current_time - last_db_check_time >= DATABASE_UPDATE_FREQUENCY:
                        update_data(src, main_display._dataset)
                        last_db_check_time = current_time

                        # Check for changed data
                        current_beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
                        current_taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
                        
                        if current_beers_hash != beers_hash or current_taps_hash != taps_hash or first_time:
                            logger.debug("Data changed - updating display")
                            
                            # Render updating canvas
                            if first_time:
                                main_display._dataset.update('sys', {'status': 'start'}, merge=True)
                                first_time = False
                            else:
                                main_display._dataset.update('sys', {'status': 'update'}, merge=True)
                            main_display.render()
                            screen.display(main_display.image.convert("1"))
                            main_display._dataset.update('sys', {'status': 'running'}, merge=True)

                            last_frame_time = current_time
                            display_count += 1
                            
                            # Generate complete sequence in background
                            image_sequence = generate_complete_image_set(main_display)
                            sequence_index = 0  # Start from beginning of new sequence
                            beers_hash = current_beers_hash
                            taps_hash = current_taps_hash

                    # Display current frame
                    if image_sequence:
                        current_image, duration = image_sequence[sequence_index]
                        if current_time - last_frame_time >= duration:
                            screen.display(current_image)
                            last_frame_time = current_time
                            sequence_index = (sequence_index + 1) % len(image_sequence)
                            display_count += 1

                    # Short sleep to prevent CPU overload
                    time.sleep(0.01)

                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    break

        main_loop(screen, main, src)

    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, initiating shutdown")
    except Exception as e:
        # Log any unhandled exceptions
        logger.error("Unhandled exception", exc_info=True)
        raise  # Re-raise the exception after logging
    finally:
        logger.info("Shutting down")
 



