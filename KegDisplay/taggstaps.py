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
from pathlib import Path
from collections import deque

from pyAttention.source import database
from tinyDisplay.render.collection import canvas, sequence
from tinyDisplay.render.widget import text
from tinyDisplay.utility import dataset, image2Text
from tinyDisplay.cfg import _tdLoader, load
from tinyDisplay.utility import animate
from luma.core.interface.parallel import bitbang_6800
from luma.core.interface.serial import spi
from luma.oled.device import ws0010, ssd1322

def sigterm_handler(_signo, _stack_frame):
    sys.exit(0)


def start():
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Variables for tracking render frequency
    render_count = 0
    last_render_print_time = time.time()
    render_start_time = time.time()

    # Changing the system encoding should no longer be needed
    #    if sys.stdout.encoding != u'UTF-8':
    #            sys.stdout = codecs.getwriter(u'utf-8')(sys.stdout, u'strict')

    logging.basicConfig(format=u'%(asctime)s:%(levelname)s:%(message)s', filename="/var/log/KegDisplay/taggstaps.log", level=logging.INFO)
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
        
        current_time = time.time()
        returnSet = []

        # Reset counters
        render_start_time = current_time

        for _ in range(math.ceil(count)):
            display.render()
            returnSet.append(display.image.convert("1"))

        # Calculate the average time per render
        duration = time.time() - current_time
        print(f"Rendered {count}:{duration:.2f} {count/duration:.2f} renders/sec")

        return returnSet

    def dict_hash(dictionary):
        # Convert all keys to strings before dumping to JSON
        string_dict = {str(k): v for k, v in dictionary.items()}
        return hash(json.dumps(string_dict, sort_keys=True))

    def updateData(dbSrc, ds):

        while True:
            dbRow = dbSrc.get(0.001)
            if dbRow is not None:
                for key, value in dbRow.items():
                    if key == 'beer':
                        for item in value:
                            if 'idBeer' in item:
                                ds.update("beers", { item['idBeer']: {k: v for k, v in item.items() if k != 'idBeer'}}, merge=True)
                    if key == 'taps':
                        for item in value:
                            if 'idTap' in item:
                                    ds.update("taps", { item['idTap']: item['idBeer']}, merge=True)
            else:
                break
    
    updateData(src, main._dataset)
    beersHash = dict_hash(main._dataset.get('beers'))
    tapsHash = dict_hash(main._dataset.get('taps'))
    main.render()

    # = animate(render, 120, 500, screen, main)
    #a.start()
    database_update_frequency = 2.5 
    render_frequency = 30
    renderBufferSize = render_frequency * 60
    dqImages = deque([])
    
    startTime = time.time()
    try:
        while True:
            updateData(src, main._dataset)

 
            if main._dataset.sys['status'] == 'start' and time.time() - startTime > 4:
                main._dataset.update('sys', {'status': 'running'}, merge=True)
            #a.clear()

            # Check for changed data
            currentBeersHash = dict_hash(main._dataset.get('beers')) 
            currentTapsHash = dict_hash(main._dataset.get('taps'))
            dataChanged = beersHash != currentBeersHash or tapsHash != currentTapsHash
            beersHash = currentBeersHash
            tapssHash = currentTapsHash

            # Generate enough images to fill display for awhile 
            if len(dqImages) == 0:
                dqImages = deque(render(main, renderBufferSize))

            displayStartTime = time.time()
            displayCount = 0
            while len(dqImages) > 0:
                displayStart = time.time()
                screen.display(dqImages.popleft())
                displayCount += 1
                displayDuration = time.time() - displayStart
                if displayDuration < 1/render_frequency:
                    # If display was updated faster than render_frequency, sleep to sync
                    time.sleep( 1/render_frequency - displayDuration) 

                if time.time() - displayStartTime > database_update_frequency:
                    duration = time.time() - displayStartTime
                    print(f"{displayCount/duration:.2f} fps")
                    break

            if dataChanged:
                del dqImages
                dqImages = deque([])


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
