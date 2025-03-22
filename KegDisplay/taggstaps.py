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
LOG_FILE = "/var/log/KegDisplay/taggstaps.log"

def sigterm_handler(_signo, _stack_frame):
    """Handle SIGTERM signal gracefully by exiting the program.

    Args:
        _signo: Signal number
        _stack_frame: Current stack frame
    """
    sys.exit(0)


def start():
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

    # Changing the system encoding should no longer be needed
    #    if sys.stdout.encoding != u'UTF-8':
    #            sys.stdout = codecs.getwriter(u'utf-8')(sys.stdout, u'strict')

    # Update logging configuration to use the command line argument
    logging.basicConfig(
        format=u'%(asctime)s:%(levelname)s:%(message)s',
        filename="/var/log/KegDisplay/taggstaps.log",
        level=getattr(logging, args.log_level)
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger(u'socketIO-client').setLevel(logging.WARNING)

    # Move unhandled exception messages to log file
    def handleuncaughtexceptions(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.error(u"Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        try:
            if len(mc.musicdata) > 0:
                logging.error(u"Status at exception")
                logging.error(unicode(mc.musicdata))
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

    def main_loop(screen, main_display, src):
        """Main program loop handling display updates and data synchronization.

        Args:
            screen: Display device object
            main_display: Main display controller
            src: Data source object
        """
        dq_images = deque([])
        beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
        taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
        
        start_time = display_start_time = time.time()
        display_count = 0

        try:
            while True:
                update_data(src, main_display._dataset)

                if (main_display._dataset.sys['status'] == 'start' and 
                    time.time() - start_time > 4):
                    main_display._dataset.update('sys', {'status': 'running'}, merge=True)

                # Check for changed data
                data_changed = False
                current_beers_hash = dict_hash(main_display._dataset.get('beers'), '__timestamp__')
                current_taps_hash = dict_hash(main_display._dataset.get('taps'), '__timestamp__')
                
                if current_beers_hash != beers_hash:
                    data_changed = True
                    logging.info("Beers changed")
                if current_taps_hash != taps_hash:
                    data_changed = True
                    logging.info("Taps changed")

                beers_hash = current_beers_hash
                taps_hash = current_taps_hash

                if data_changed:
                    logging.info("New data received")
                    dq_images = deque(render(main_display, RENDER_BUFFER_SIZE))
                elif len(dq_images) == 0:
                    dq_images = deque(render(main_display, 2))

                display_count, display_start_time = handle_display_updates(
                    screen, 
                    dq_images, 
                    display_count, 
                    display_start_time
                )

        except KeyboardInterrupt:
            pass

    try:
        main_loop(screen, main, src)
    except KeyboardInterrupt:
        pass

    finally:
        print ("Shutting down threads")
        try:
            #a.stop()
            pass
        except:
            pass
 
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
    while len(dq_images) > 0:
        display_start = time.time()
        screen.display(dq_images.popleft())
        display_count += 1
        display_duration = time.time() - display_start
        
        if display_duration < 1/RENDER_FREQUENCY:
            # If display was updated faster than render_frequency, sleep to sync
            time.sleep(1/RENDER_FREQUENCY - display_duration)

        if time.time() - display_start_time > 10:
            logging.debug(f"Display updates per second: {display_count/(time.time()-display_start_time):.1f}")
            display_count = 0
            display_start_time = time.time()

    return display_count, display_start_time
