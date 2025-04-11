#!/usr/bin/env python3
"""
Profiling script for taggstap program.
This script runs the taggstap program with profiling enabled and collects performance metrics.
"""

import cProfile
import pstats
import io
import time
import logging
import sys
import os
import argparse
import signal
from datetime import datetime

# Add the parent directory to the path so we can import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from KegDisplay.log_config import configure_logging
from KegDisplay.application import Application
from KegDisplay.dependency_container import DependencyContainer

# Configure logging
logger = configure_logging()

# Global flag to track if profiling should stop
profiling_active = True

def signal_handler(sig, frame):
    """Handle signals for graceful shutdown."""
    global profiling_active
    logger.info(f"Received signal {sig}, stopping profiling...")
    profiling_active = False

def parse_arguments():
    """Parse command line arguments similar to taggstaps.py."""
    parser = argparse.ArgumentParser(description='Profile the taggstap program')
    
    # Display type
    parser.add_argument('--display', type=str, choices=['ws0010', 'ssd1322', 'virtual'],
                        default='ws0010', help='Type of display (default: ws0010)')
    
    # Interface type
    parser.add_argument('--interface', type=str, choices=['bitbang', 'spi', 'pigpio'],
                        default='bitbang', help='Type of interface (default: bitbang)')
    
    # Bitbang specific pins
    parser.add_argument('--RS', type=int, default=7, help='RS pin for bitbang interface (default: 7)')
    parser.add_argument('--E', type=int, default=8, help='E pin for bitbang interface (default: 8)')
    parser.add_argument('--PINS', type=int, nargs=4, default=[25, 5, 6, 12],
                        help='Data pins for bitbang interface (default: 25 5 6 12)')
    
    # Tap number
    parser.add_argument('--tap', type=int, default=1, help='Tap number (default: 1)')
    
    # Profiling specific arguments
    parser.add_argument('--duration', type=int, default=300, 
                        help='Duration of profiling in seconds (default: 300)')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for profiling results (default: auto-generated)')
    
    return parser.parse_args()

def run_profiled_session(args):
    """Run a profiled session of the taggstap program.
    
    Args:
        args: Parsed command line arguments
    """
    global profiling_active
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create a profiler
    profiler = cProfile.Profile()
    
    # Start profiling
    profiler.enable()
    
    app = None
    
    try:
        # Create dependency container
        container = DependencyContainer()
        
        # Convert args to list format expected by create_application_components
        cmd_args = []
        if args.display:
            cmd_args.extend(['--display', args.display])
        if args.interface:
            cmd_args.extend(['--interface', args.interface])
        if args.RS:
            cmd_args.extend(['--RS', str(args.RS)])
        if args.E:
            cmd_args.extend(['--E', str(args.E)])
        if args.PINS:
            cmd_args.extend(['--PINS'] + [str(pin) for pin in args.PINS])
        if args.tap:
            cmd_args.extend(['--tap', str(args.tap)])
            
        logger.info(f"Initializing with arguments: {' '.join(cmd_args)}")
        
        # Initialize components with the same arguments as taggstaps
        config_manager, display, renderer, data_manager = container.create_application_components(args=cmd_args)
        
        # Create the application
        app = Application(renderer, data_manager, config_manager)
        
        # Set a timeout for the application run
        # We'll use a custom signal handler to stop the application after the specified duration
        def timeout_handler(signum, frame):
            logger.info(f"Timeout reached ({args.duration} seconds), stopping application...")
            if app:
                app.running = False
        
        # Set up a timer to stop the application after the specified duration
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(args.duration)
        
        # Run the application directly
        logger.info(f"Running application for {args.duration} seconds...")
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Profiling session interrupted by user")
    except Exception as e:
        logger.error(f"Error during profiling: {e}")
    finally:
        # Disable the alarm
        signal.alarm(0)
        
        # Stop profiling
        profiler.disable()
        
        # Clean up application if it was created
        if app:
            logger.info("Cleaning up application...")
            app.cleanup()
        
        # Create stats object
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        
        # Print top 50 functions by cumulative time
        ps.print_stats(50)
        
        # Save results to file if specified
        if args.output:
            output_file = args.output
        else:
            # Generate timestamp for the output file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"taggstap_profile_{timestamp}.txt"
            
        with open(output_file, 'w') as f:
            f.write(s.getvalue())
        logger.info(f"Profiling results saved to {output_file}")

if __name__ == "__main__":
    args = parse_arguments()
    run_profiled_session(args) 