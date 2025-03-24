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
RENDER_FREQUENCY = 30
RENDER_BUFFER_SIZE = RENDER_FREQUENCY * 10
SPLASH_SCREEN_TIME = 2
LOG_FILE = "/var/log/KegDisplay/taggstaps.log"
LOGGER_NAME = "KegDisplay"

# First, let's modify the logging setup to force clean output
class CleanFormatter(logging.Formatter):
    """Custom formatter that ensures clean, left-aligned output with proper line endings in raw mode."""
    def format(self, record):
        # Clean any existing whitespace and handle slow render messages
        msg = record.msg.strip()
        if msg.startswith('=== slow render'):
            # Skip slow render messages or handle them differently
            return ''
        record.msg = msg
        # Format the message and ensure proper line endings
        return super().format(record) + '\r\n'

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

# Global flag for FPS display
show_fps = False
exit_requested = False

def setup_raw_input():
    """Set up raw input mode for keyboard detection"""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            # No TTY available
            return None
        old_settings = termios.tcgetattr(fd)
        tty.setraw(fd)
        return old_settings
    except (termios.error, OSError):
        # Handle cases where terminal manipulation isn't possible
        return None

def restore_input(old_settings):
    """Restore normal input mode"""
    if old_settings:
        fd = sys.stdin.fileno()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

def check_keyboard():
    """Check for keyboard input without blocking"""
    try:
        if not sys.stdin.isatty():
            return None
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1)
            if key == '\x06':  # Ctrl+F
                return 'fps'
            elif key == '\x03':  # Ctrl+C
                return 'exit'
    except (OSError, IOError):
        # Handle cases where input checking fails
        pass
    return None

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
        # Add raw input setup
        old_settings = setup_raw_input()
        
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

        def render(display, count):
            """Render the display for the specified number of frames.

            Args:
                display: Display object to render
                count (int): Number of frames to render

            Returns:
                list: List of rendered images
            """
            current_time = time.time()
            return_set = []

            for _ in range(math.ceil(count)):
                display.render()
                return_set.append(display.image.convert("1"))

            # Calculate the average time per render
            duration = time.time() - current_time
            if count > 10:
                print(f"Rendered {count}:{duration:.2f} {count/duration:.2f} renders/sec")

            return return_set

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
                        for item in value:
                            if 'idBeer' in item:
                                ds.update(
                                    "beers",
                                    {item['idBeer']: {k: v for k, v in item.items() if k != 'idBeer'}},
                                    merge=True
                                )
                    if key == 'taps':
                        for item in value:
                            if 'idTap' in item:
                                ds.update("taps", {item['idTap']: item['idBeer']}, merge=True)

        update_data(src, main._dataset)
        beersHash = dict_hash(main._dataset.get('beers'), '__timestamp__')
        tapsHash = dict_hash(main._dataset.get('taps'), '__timestamp__')
        main.render()

        # = animate(render, 120, 500, screen, main)
        #a.start()
        render_frequency = 30
        renderBufferSize = render_frequency * 10
        dqImages = deque([])
        
        startTime = displayStartTime = time.time()
        displayCount = 0

        def generate_complete_image_set(display):
            """Generate all possible unique images for the current data state."""
            image_sequence = []
            sequence_window = []
            window_size = 20  # Increased window size for better pattern detection
            max_iterations = 400  # Increased for longer sequences
            last_image = None
            static_count = 0
            unchanged_frames = 0
            min_frames = 30  # Minimum frames before considering sequence complete
            max_static_frames = 20  # Maximum consecutive static frames to consider
            
            logger.debug("Starting image sequence generation")
            
            for i in range(max_iterations):
                display.render()
                current_image = display.image.convert("1")
                current_bytes = current_image.tobytes()
                
                if last_image is not None:
                    last_bytes = last_image.tobytes()
                    if current_bytes == last_bytes:
                        static_count += 1
                        unchanged_frames += 1
                        if unchanged_frames >= max_static_frames and len(image_sequence) >= min_frames:
                            # Look back through sequence to find repeating pattern
                            sequence_length = len(image_sequence)
                            for pattern_size in range(10, sequence_length // 2):
                                matches = True
                                for j in range(pattern_size):
                                    if j >= len(image_sequence):
                                        matches = False
                                        break
                                    pattern_frame = image_sequence[j][0].tobytes()
                                    compare_frame = image_sequence[j + pattern_size][0].tobytes()
                                    if pattern_frame != compare_frame:
                                        matches = False
                                        break
                                if matches:
                                    logger.debug(f"Found repeating pattern of {pattern_size} frames")
                                    return image_sequence[:pattern_size]
                    else:
                        if static_count > 0:
                            image_sequence.append((last_image, static_count / RENDER_FREQUENCY))
                        static_count = 0
                        unchanged_frames = 0
                        image_sequence.append((current_image, 1 / RENDER_FREQUENCY))
                        if len(image_sequence) % 10 == 0:
                            logger.debug(f"Captured {len(image_sequence)} frames")
                else:
                    image_sequence.append((current_image, 1 / RENDER_FREQUENCY))
                    logger.debug("First frame captured")
                    
                last_image = current_image
            
            logger.warning(f"Reached maximum iterations ({max_iterations}) - using collected frames")
            if static_count > 0:
                image_sequence.append((last_image, static_count / RENDER_FREQUENCY))
            logger.debug(f"Final sequence length: {len(image_sequence)} frames")
            return image_sequence

        def main_loop(screen, main_display, src):
            """Main program loop handling display updates and data synchronization."""
            global show_fps, exit_requested
            
            image_sequence = []
            sequence_index = 0
            last_frame_time = time.time()
            last_db_check_time = time.time()
            beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
            taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
            
            start_time = display_start_time = time.time()
            display_count = 0

            # Generate initial sequence
            logger.info("Generating initial image sequence")
            image_sequence = generate_complete_image_set(main_display)
            if image_sequence:
                logger.debug(f"Initial sequence generated with {len(image_sequence)} frames")
                screen.display(image_sequence[0][0])

            while not exit_requested:
                try:
                    current_time = time.time()

                    # Check for keyboard input
                    key_event = check_keyboard()
                    if key_event == 'fps':
                        show_fps = not show_fps
                        if not show_fps:
                            print('\r' + ' ' * 80 + '\r', end='', flush=True)
                    elif key_event == 'exit':
                        if show_fps:
                            print('\r' + ' ' * 80 + '\r', end='', flush=True)
                        logger.info("Exit requested via keyboard")
                        break

                    # Check for database updates at specified frequency
                    if current_time - last_db_check_time >= DATABASE_UPDATE_FREQUENCY:
                        update_data(src, main_display._dataset)
                        last_db_check_time = current_time

                        if (main_display._dataset.sys['status'] == 'start' and 
                            current_time - start_time > 4):
                            main_display._dataset.update('sys', {'status': 'running'}, merge=True)

                        # Check for changed data
                        current_beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
                        current_taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
                        
                        if current_beers_hash != beers_hash or current_taps_hash != taps_hash:
                            logger.info("Data changed - updating display")
                            
                            # Immediately render and display first frame
                            main_display.render()
                            screen.display(main_display.image.convert("1"))
                            last_frame_time = current_time
                            display_count += 1
                            
                            # Generate complete sequence in background
                            logger.info("Generating complete image sequence")
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

                            if show_fps:
                                current_fps = display_count/(current_time - display_start_time)
                                print(f"\rCurrent FPS: {current_fps:.1f}", end='', flush=True)

                    # Short sleep to prevent CPU overload
                    time.sleep(0.01)

                except KeyboardInterrupt:
                    logger.info("KeyboardInterrupt received")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error: {e}", exc_info=True)
                    break

            # Cleanup before exit
            if show_fps:
                print('\r' + ' ' * 80 + '\r', end='', flush=True)
            logger.info("Main loop ending")

        main_loop(screen, main, src)

    except KeyboardInterrupt:
        # Clear the line before logging
        clear_line()
        logger.info("KeyboardInterrupt received, initiating shutdown")
    except Exception as e:
        # Log any unhandled exceptions
        logger.error("Unhandled exception", exc_info=True)
        raise  # Re-raise the exception after logging
    finally:
        # Restore terminal settings before final logging
        restore_input(old_settings)
        # Ensure we're at the start of a clean line
        print('\r', end='', flush=True)
        logger.info("Shutting down")
 
 #print (ds['beers'])
#main.render(force=True)
#print(main)

def handle_display_updates(screen, dq_images, display_count, display_start_time):
    """Handle the display updates and timing synchronization.

    Args:
        screen: Display device object
        dq_images (collections.deque): Queue of images to display
        display_count (int): Counter for display updates
        display_start_time (float): Start time for display statistics

    Returns:
        tuple: Updated display_count and display_start_time
    """
    while len(dq_images) > 0 and not exit_requested:  # Changed exit_event.is_set()
        display_start = time.time()
        screen.display(dq_images.popleft())
        display_count += 1
        display_duration = time.time() - display_start
        
        if display_duration < 1/RENDER_FREQUENCY:
            # If display was updated faster than render_frequency, sleep to sync
            time.sleep(1/RENDER_FREQUENCY - display_duration)

        # Show FPS every update when enabled, otherwise only log debug every 10 seconds
        current_fps = display_count/(time.time()-display_start_time)
        if show_fps:
            show_fps_display(current_fps)
        elif time.time() - display_start_time > 10:
            # Clear the line before logging
            clear_line()
            logger.debug(f"Display updates per second: {current_fps:.1f}")
            display_count = 0
            display_start_time = time.time()

    # Clear any remaining FPS display before returning
    if show_fps:
        clear_line()

    return display_count, display_start_time

def show_fps_display(fps):
    """Helper function for FPS display that handles raw mode."""
    print(f"\rCurrent FPS: {fps:.1f}\r", end='', flush=True)

def clear_line():
    """Helper function to clear the current line in raw mode."""
    print('\r' + ' ' * 80 + '\r', end='', flush=True)
