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
from pathlib import Path
from pyAttention.source import database
from tinyDisplay.render.collection import canvas, sequence
from tinyDisplay.render.widget import text
from tinyDisplay.utility import dataset, image2Text
from tinyDisplay.cfg import _tdLoader, load
from tinyDisplay.utility import animate
from luma.core.interface.parallel import bitbang_6800
from luma.oled.device import ws0010

def sigterm_handler(_signo, _stack_frame):
    sys.exit(0)


if __name__ == u'__main__':
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Changing the system encoding should no longer be needed
    #    if sys.stdout.encoding != u'UTF-8':
    #            sys.stdout = codecs.getwriter(u'utf-8')(sys.stdout, u'strict')

    logging.basicConfig(format=u'%(asctime)s:%(levelname)s:%(message)s', filename="taggstaps.log", level=logging.INFO)
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

    src = database('sqlite+aiosqlite:///KegDisplay/beer.db')
    src.add("SELECT idBeer, Name, Description, ABV from beers", name='beer', frequency = 15)
    src.add("SELECT idTap, idBeer from taps", name='taps', frequency = 15)

    ds = dataset()
    ds.add("sys", {"tapnr": 1, "status": "start"})
    ds.add("beers", {})
    ds.add("taps", {})

    path = Path(__file__).parent / "page.yaml"
    print ("Loading: ", path)
    main = load(path, dataset=ds)

    interface = bitbang_6800(RS=7, E=8, PINS=[25,24,23,27])
    screen = ws0010(interface)

    def render(device, display):
        img = display.render()
        device.display(img)

    def updateData(dbSrc, ds):
        while true:
            dbRow = dbSrc.get(wait=0)
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
    
    a = animate(render, 60, 200, screen, main)
    a.start()
    try:
        while True:
            updateData(src, main._dataset)
            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        print ("Shutting down threads")
        exitapp[0] = True
        try:
            a.stop()
        except:
            pass
 
 #print (ds['beers'])
#main.render(force=True)
#print(main)