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
from datetime import datetime

# Add the parent directory to the path so we can import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from KegDisplay.log_config import configure_logging
from KegDisplay.application import Application
from KegDisplay.dependency_container import DependencyContainer

# Configure logging
logger = configure_logging()

def run_profiled_session(duration=300, output_file=None):
    """Run a profiled session of the taggstap program.
    
    Args:
        duration: Duration of the profiling session in seconds
        output_file: Optional file to save profiling results
    """
    # Create a profiler
    profiler = cProfile.Profile()
    
    # Start profiling
    profiler.enable()
    
    try:
        # Create dependency container
        container = DependencyContainer()
        
        # Initialize components
        config_manager, display, renderer, data_manager = container.create_application_components()
        
        # Create and run the application
        app = Application(renderer, data_manager, config_manager)
        
        # Run for specified duration
        start_time = time.time()
        while time.time() - start_time < duration:
            app.run()
            time.sleep(0.1)  # Small sleep to prevent CPU overload
            
    except KeyboardInterrupt:
        logger.info("Profiling session interrupted by user")
    except Exception as e:
        logger.error(f"Error during profiling: {e}")
    finally:
        # Stop profiling
        profiler.disable()
        
        # Create stats object
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        
        # Print top 50 functions by cumulative time
        ps.print_stats(50)
        
        # Save results to file if specified
        if output_file:
            with open(output_file, 'w') as f:
                f.write(s.getvalue())
            logger.info(f"Profiling results saved to {output_file}")
        else:
            # Print to console
            print(s.getvalue())
            
        # Generate timestamp for the output file if not specified
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"taggstap_profile_{timestamp}.txt"
            with open(output_file, 'w') as f:
                f.write(s.getvalue())
            logger.info(f"Profiling results saved to {output_file}")

if __name__ == "__main__":
    # Default to 5 minutes of profiling
    run_profiled_session(duration=300) 