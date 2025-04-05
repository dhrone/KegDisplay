"""
Performance profiling script for KegDisplay.

This script will run KegDisplay with the virtual display and measure the
time spent in different parts of the code to identify potential bottlenecks.
"""

import sys
import time
import cProfile
import pstats
import io
from pstats import SortKey
import logging
import os

# Add parent directory to path to import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import KegDisplay modules
from KegDisplay.display.virtual_display import VirtualDisplay
from KegDisplay.renderer import SequenceRenderer
from KegDisplay.data_manager import DataManager
from KegDisplay.config.config_manager import ConfigManager
from KegDisplay.application import Application

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('PerformanceTest')

def run_with_profiling(fps=60, duration=30):
    """Run KegDisplay with profiling enabled for a specified duration.
    
    Args:
        fps: Target frames per second
        duration: Duration to run the test in seconds
    """
    logger.info(f"Starting performance test with target {fps} FPS for {duration} seconds")
    
    # Set up display and components
    display = VirtualDisplay(resolution=(256, 64), zoom=3)
    display.initialize()
    
    # Create an initial dataset
    dataset = {
        'sys': {
            'tapnr': 1,
            'target_fps': fps,
            'debug': True,
            'status': 'start'
        },
        'beers': {
            1: {
                'Name': 'Test Beer',
                'ABV': 5.0,
                'Description': 'This is a test beer for performance profiling.'
            }
        },
        'taps': {
            1: 1  # Tap 1 maps to beer ID 1
        }
    }
    
    # Create configuration
    config = ConfigManager()
    # Override config values for testing
    config.config = {
        'display': 'virtual',
        'fps': fps,
        'splash_time': 1,
        'debug': True,
        'page': 'KegDisplay/page.yaml'  # Use default page
    }
    
    # Create renderer
    renderer = SequenceRenderer(display, dataset)
    
    # Load page and prepare the renderer
    renderer.load_page(config.get_config('page'))
    
    # Create data manager (minimal functionality for test)
    data_manager = DataManager(renderer)
    
    # Create application
    app = Application(renderer, data_manager, config)
    
    # Set up profiling
    pr = cProfile.Profile()
    pr.enable()
    
    # Start time
    start_time = time.time()
    
    # Run application for specified duration
    logger.info("Starting application loop")
    app.running = True
    
    # Run the initialization phase
    logger.info("Initializing application...")
    
    # Prepare for render and measure timing
    sequence_start = time.time()
    renderer.image_sequence = renderer.generate_image_sequence()
    sequence_time = time.time() - sequence_start
    logger.info(f"Image sequence generation took {sequence_time:.3f}s for {len(renderer.image_sequence)} frames")
    
    renderer.sequence_index = 0
    renderer.last_frame_time = time.time()
    
    # Main loop for specified duration
    frame_count = 0
    display_times = []
    
    while time.time() - start_time < duration and app.running:
        try:
            # Record time spent in display_next_frame
            display_start = time.time()
            result = renderer.display_next_frame()
            if result:
                frame_time = time.time() - display_start
                display_times.append(frame_time)
                frame_count += 1
            
            # Short sleep to prevent CPU overload
            time.sleep(0.001)
            
        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received")
            break
    
    # Collect final statistics
    end_time = time.time()
    total_runtime = end_time - start_time
    actual_fps = frame_count / total_runtime if total_runtime > 0 else 0
    
    # Disable profiling
    pr.disable()
    
    # Display stats
    logger.info(f"Test complete: {frame_count} frames in {total_runtime:.2f}s")
    logger.info(f"Average FPS: {actual_fps:.2f}")
    
    if display_times:
        avg_display_time = sum(display_times) / len(display_times)
        min_display_time = min(display_times)
        max_display_time = max(display_times)
        logger.info(f"Display time stats (seconds):")
        logger.info(f"  Average: {avg_display_time*1000:.2f}ms")
        logger.info(f"  Minimum: {min_display_time*1000:.2f}ms")
        logger.info(f"  Maximum: {max_display_time*1000:.2f}ms")
    
    # Print profiling results
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(30)  # Print top 30 functions by cumulative time
    logger.info("Profiling Results:\n" + s.getvalue())
    
    # Cleanup
    display.cleanup()
    logger.info("Performance test complete")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Profile KegDisplay performance')
    parser.add_argument('--fps', type=int, default=60, help='Target frames per second')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    args = parser.parse_args()
    
    run_with_profiling(fps=args.fps, duration=args.duration) 