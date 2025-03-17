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
from pathlib import Path

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
    last_print_time = time.time()
    start_time = time.time()

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
    #interface = bitbang_6800(RS=24, E=25, PINS=[16,26,20,21])
    interface = spi()
    #screen = ws0010(interface)
    screen = ssd1322(serial_interface=interface, mode='1')

    def render(device, display):
        nonlocal render_count, last_print_time, start_time
        
        current_time = time.time()
        render_count += 1
        
        # Every 10 seconds, print the average rate
        if current_time - last_print_time >= 10:
            elapsed = current_time - start_time
            rate = render_count / elapsed
            logging.info(f"Average render rate: {rate:.2f} renders/second over last {elapsed:.1f} seconds")
            
            # Reset counters
            render_count = 0
            start_time = current_time
            last_print_time = current_time
        
        display.render()
        device.display(display.image.convert("1"))
        return 1

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
    main.render()

    a = animate(render, 120, 500, screen, main)
    a.start()
    startTime = time.time()
    try:
        while True:
            updateData(src, main._dataset)
            if main._dataset.sys['status'] == 'start' and time.time() - startTime > 4:
                main._dataset.update('sys', {'status': 'running'}, merge=True)
            a.clear()    

    except KeyboardInterrupt:
        pass

    finally:
        print ("Shutting down threads")
        try:
            a.stop()
        except:
            pass
 
 #print (ds['beers'])
#main.render(force=True)
#print(main)
