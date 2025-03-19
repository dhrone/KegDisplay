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
import asyncio
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

async def update_data(src, ds):
    """Asynchronously update the dataset with new database information"""
    while True:
        try:
            dbRow = src.get(0.001)  # Not awaited since get() returns the result directly
            if dbRow is not None:
                logging.info(f"Received data from database: {dbRow}")
                beer_updates = {}
                tap_updates = {}
                
                for key, value in dbRow.items():
                    if key == 'beer':
                        for item in value:
                            if 'idBeer' in item:
                                beer_updates[item['idBeer']] = {k: v for k, v in item.items() if k != 'idBeer'}
                    if key == 'taps':
                        for item in value:
                            if 'idTap' in item:
                                tap_updates[item['idTap']] = item['idBeer']
                
                if beer_updates:
                    logging.info(f"Updating beers with: {beer_updates}")
                    ds.update("beers", beer_updates, merge=True)
                if tap_updates:
                    logging.info(f"Updating taps with: {tap_updates}")
                    ds.update("taps", tap_updates, merge=True)
            await asyncio.sleep(0.1)  # Small delay to prevent CPU spinning
        except Exception as e:
            logging.error(f"Error in update_data: {e}")
            logging.error(f"Exception details:", exc_info=True)
            await asyncio.sleep(1)  # Longer delay on error

async def render_loop(device, display, a):
    """Main render loop using asyncio"""
    render_count = 0
    last_print_time = time.time()
    start_time = time.time()
    
    while True:
        try:
            current_time = time.time()
            render_count += 1
            
            if current_time - last_print_time >= 30:
                elapsed = current_time - start_time
                rate = render_count / elapsed
                logging.info(f"Average render rate: {rate:.2f} renders/second over last {elapsed:.1f} seconds")
                
                render_count = 0
                start_time = current_time
                last_print_time = current_time
            
            display.render()
            if not hasattr(display, '_cached_image'):
                display._cached_image = display.image.convert("1")
            device.display(display._cached_image)
            
            await asyncio.sleep(1/30)  # 30 FPS
        except Exception as e:
            logging.error(f"Error in render_loop: {e}")
            await asyncio.sleep(1)

async def main():
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Set up logging with rotation
    log_dir = "/var/log/KegDisplay"
    os.makedirs(log_dir, exist_ok=True)
    
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        f"{log_dir}/taggstaps.log",
        maxBytes=1024*1024,  # 1MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(message)s'))
    
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger('socketIO-client').setLevel(logging.WARNING)

    def handleuncaughtexceptions(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        try:
            if len(mc.musicdata) > 0:
                logging.error("Status at exception")
                logging.error(str(mc.musicdata))
        except NameError:
            pass

        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handleuncaughtexceptions

    dbPath = "KegDisplay/beer.db"
    if not Path(dbPath).exists():
        raise FileNotFoundError(f"Database file {dbPath} missing")
    
    src = database(f'sqlite+aiosqlite:///{dbPath}')
    src.add("SELECT idBeer, Name, Description, ABV from beers", name='beer', frequency=5)
    src.add("SELECT idTap, idBeer from taps", name='taps', frequency=5)

    ds = dataset()
    ds.add("sys", {"tapnr": 1, "status": "start"})
    ds.add("beers", {})
    ds.add("taps", {})

    path = Path(__file__).parent / "page.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Page file {path} missing")
    main_display = load(path, dataset=ds)

    interface = spi()
    screen = ssd1322(serial_interface=interface, mode='1')

    # Create tasks for concurrent operations
    update_task = asyncio.create_task(update_data(src, ds))
    render_task = asyncio.create_task(render_loop(screen, main_display, None))
    
    start_time = time.time()
    try:
        while True:
            if main_display._dataset.sys['status'] == 'start' and time.time() - start_time > 4:
                main_display._dataset.update('sys', {'status': 'running'}, merge=True)
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down...")
        update_task.cancel()
        render_task.cancel()
        try:
            await asyncio.gather(update_task, render_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(main())
