"""
Implementation of a pigpio-based 6800 style parallel interface for displays.
"""

import logging
import time
import pigpio
from luma.core.interface.parallel import bitbang_6800

logger = logging.getLogger("KegDisplay")

"""
Default amount of time to wait for a pulse to complete if the device the
interface is connected to requires a pin to be 'pulsed' from low to high to
low for it to accept data or a command.  Value is in microseconds.
"""
PULSE_TIME = 2


class bitbang_6800_pigpio(object):
    """
    Implements a 6800 style parallel-bus interface that provides :py:func:`data`
    and :py:func:`command` methods using pigpio for GPIO control. The default pin assignments provided are
    from `Adafruit <https://learn.adafruit.com/drive-a-16x2-lcd-directly-with-a-raspberry-pi/wiring>`_.

    :param gpio: PIGPIO interface
    :param pulse_time: length of time in seconds that the enable line should be
        held high during a data or command transfer
    :type pulse_time: float
    :param RS: The GPIO pin register select (RS) line (low for command, high
        for data). Default: 22
    :type RS: int
    :param E: The GPIO pin to connect the enable (E) line to. Default: 17
    :type E: int
    :param PINS: The GPIO pins that form the data bus (a list of 4 or 8 pins
        depending upon implementation ordered from LSD to MSD). Default: ``[25, 24, 23, 18]``
    :type PINS: list[int]
    """

    def __init__(self, gpio=None, pulse_time=PULSE_TIME, batch=False, **kwargs):
        # Initialize pigpio first
        self._pi = gpio if gpio is not None else pigpio.pi()
        if not self._pi.connected:
            raise RuntimeError("Failed to connect to pigpio daemon")
        
        # Store the batch mode setting
        self._batch = batch

        # Store pulse time
        self._pulse_time = pulse_time

        # Initialize wave cache
        self._wave_cache = []
        self._wave_id = None
        self._saved_waves = {}
        
        # Configure pins
        self._RS = self._configure(kwargs.get("RS", 22))
        self._E = self._configure(kwargs.get("E", 17))
        self._PINS = self._configure(kwargs.get('PINS', [25, 24, 23, 18]))
        
        self._datalines = len(self._PINS)
        assert self._datalines in (4, 8), f'You\'ve provided {len(self._PINS)} pins but a bus must contain either four or eight pins'
        self._bitmode = self._datalines  # Used by device to autoset its own bitmode
        
        self._cmd_mode = 0  # Command mode = Hold low
        self._data_mode = 1  # Data mode = Pull high
        
        logger.debug(f"Initialized bitbang_6800_pigpio with RS={self._RS}, E={self._E}, PINS={self._PINS}, batch={batch}")

    def _configure(self, pin):
        """Configure a pin or list of pins for output."""
        pins = pin if isinstance(pin, list) else [pin] if pin else []
        for p in pins:
            self._pi.set_mode(p, pigpio.OUTPUT)
        return pin

    def command(self, *cmd):
        """
        Sends a command or sequence of commands through the bus.

        If the bus is in 4-bit mode, only the lowest 4 bits of the data
        value will be sent.

        This means that the device needs to send high and low bits separately
        if the device is operating using a 4-bit bus; to send a ``0x32`` in
        4-bit mode the device would use: ``command(0x03, 0x02)``

        :param cmd: A spread of commands.
        :type cmd: int
        """
        self._write(list(cmd), self._cmd_mode)

    def data(self, data):
        """
        Sends a data byte or sequence of data bytes through to the bus.

        If the bus is in 4-bit mode, only the lowest 4 bits of the data
        value will be sent.

        This means that the device needs to send high and low bits separately
        if the device is operating using a 4-bit bus; to send a ``0x32`` in
        4-bit mode the device would use: ``data([0x03, 0x02])``

        :param data: A data sequence.
        :type data: list, bytearray
        """
        self._write(data, self._data_mode)

    def _write(self, data, mode):
        """
        Reimplements _write from the parent class to use pigpio calls instead of gpio.
        
        :param data: an iterable list of values to send to the display
        :type data: list, bytearray, etc.
        :param mode: either high for data or low for command
        """
        
        rs_on = (1 << self._RS) if mode else 0
        rs_off = 0 if mode else (1 << self._RS)


        # For each value in data, create a pulse sequence
        for value in data:
            # Create a list of pulses for this value
            pulses = []
            
            # Set data pins based on the value
            for i in range(self._datalines):
                bit_value = (value >> i) & 0x01
                pin_on = (1 << self._PINS[i]) if bit_value else 0
                pin_off = 0 if bit_value else (1 << self._PINS[i])
 
            pulses.append(pigpio.pulse(pin_on | rs_on | 1 << self._E, pin_off | rs_off, int(self._pulse_time)))
            pulses.append(pigpio.pulse(0, 1 << self._E, int(self._pulse_time)))

        # Insert a pulse to ensure the enable pin is low at the start of the wave
        pulses.insert(0, pigpio.pulse(0, 1 << self._E, 0))

        # If not in batch mode, send the pulse immediately
        if not self._batch:
            try:
                self._pi.wave_add_new()
                self._pi.wave_add_generic(pulses)
                wave_id = self._pi.wave_create()
                self._pi.wave_send_once(wave_id)
                self._pi.wave_delete(wave_id)
            except Exception as e:
                logger.error(f"Error creating or sending wave: {e}")
        else:
            # Add the pulses to the wave cache
            self._wave_cache.extend(pulses)

    def flush(self, save=None, replay=None):
        """
        If there is any content that has been sent to command or data with batch True, 
        send all of it as part of a single wave.
        
        :param save: If save is assigned a value, use the value to store a reference to the wave.
        :type save: str
        :param replay: If replay contains a value and it matches an earlier saved wave, resend that wave.
        :type replay: str
        :note: If save is true, the wave will be saved and can be replayed later using the replay parameter but it will not be sent immediately.
        """
        if replay is not None:
            if replay in self._saved_waves:
                wave_id = self._saved_waves[replay]
                self._pi.wave_send_once(wave_id)
                logger.debug(f"Replayed wave {wave_id} with key '{replay}'")
                return
            else:
                logger.warning(f"No saved wave found with key '{replay}'")
                return
        
        if not self._wave_cache:
            logger.debug("No pulses to flush")
            return
        
        # Create a new wave from the cached pulses
        try:
            self._pi.wave_add_new()
            self._pi.wave_add_generic(self._wave_cache)
            wave_id = self._pi.wave_create()
            
            if save is not None:
                # Store the wave ID for later replay
                self._saved_waves[save] = wave_id
                logger.debug(f"Saved wave {wave_id} with key '{save}'")
            else:
                # Send the wave and then delete it
                self._pi.wave_send_once(wave_id)
                self._pi.wave_delete(wave_id)
                logger.debug(f"Sent and deleted wave {wave_id}")
        except Exception as e:
            logger.error(f"Error creating or sending wave: {e}")
        finally:
            # Clear the wave cache
            self._wave_cache = []

    def cleanup(self):
        """
        Clean up GPIO resources.
        """
        # Delete any saved waves
        for wave_id in self._saved_waves.values():
            try:
                self._pi.wave_delete(wave_id)
            except Exception as e:
                logger.error(f"Error deleting wave {wave_id}: {e}")
        
        # Clear the wave cache
        self._wave_cache = []
        self._saved_waves = {}
        
        # Stop the pigpio interface if we created it
        if self._pi is not None:
            self._pi.stop() 