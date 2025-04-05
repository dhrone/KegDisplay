"""
Performance profiler for the full KegDisplay application.

This script launches the full KegDisplay application with profiling enabled,
allowing it to run for a specified duration before collecting performance data.
"""

import sys
import os
import time
import cProfile
import pstats
import io
from pstats import SortKey
import logging
import threading
import signal

# Add parent directory to path to import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the main app entry point
from KegDisplay.taggstaps import start

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('FullAppProfiler')

# Global variables
profiler = None
stop_event = threading.Event()

def signal_handler(sig, frame):
    """Handle signal to stop profiling and finish."""
    logger.info(f"Received signal {sig}, stopping profiler")
    stop_event.set()

def profile_app(duration=30, fps=60, use_virtual=True):
    """Profile the full KegDisplay application for a specified duration.
    
    Args:
        duration: Duration to run the test in seconds
        fps: Target frames per second
        use_virtual: Whether to use the virtual display
    """
    logger.info(f"Starting full application profiler for {duration} seconds (target {fps} FPS)")
    
    # Set up signal handlers for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Prepare command-line arguments for the app
    if use_virtual:
        # Configure with virtual display and specified FPS
        sys.argv = [
            'KegDisplay',
            '--display', 'virtual',
            '--fps', str(fps),
            '--log-level', 'INFO',
            '--debug'  # Enable performance monitoring
        ]
    else:
        # Use default display
        sys.argv = [
            'KegDisplay',
            '--fps', str(fps),
            '--log-level', 'INFO',
            '--debug'  # Enable performance monitoring
        ]
    
    # Create a daemon thread to stop profiling after duration
    def stop_profiling():
        """Wait for duration then stop profiling."""
        logger.info(f"Profiler will run for {duration} seconds")
        time.sleep(duration)
        stop_event.set()
        logger.info("Profiling duration reached")
        
        # Force exit after 5 more seconds if app doesn't exit cleanly
        time.sleep(5)
        logger.warning("Application did not exit cleanly, forcing exit")
        os._exit(1)
    
    timer_thread = threading.Thread(target=stop_profiling, daemon=True)
    timer_thread.start()
    
    # Set up profiling
    global profiler
    profiler = cProfile.Profile()
    profiler.enable()
    
    # Trick to allow the app to check if it's being profiled
    os.environ['KEGDISPLAY_PROFILING'] = 'true'
    
    # A function to periodically check if we should stop
    def check_stop_flag():
        return stop_event.is_set()
    
    # Start the app (this will block until the app exits)
    try:
        # Save the original stdout and stderr
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        
        # Redirect stdout and stderr to avoid cluttering the console
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        
        # Inject check_stop_flag into the KegDisplay.application module
        import KegDisplay.application
        KegDisplay.application.check_profiler_stop = check_stop_flag
        
        # Monkey patch the Application.run method to check for stop_event
        original_run = KegDisplay.application.Application.run
        
        def patched_run(self):
            """Patched run method that checks for stop_event."""
            logger.info("Starting patched application.run()")
            self.running = True
            
            # Run initialization code from the original method
            splash_time = self.config_manager.get_config('splash_time')
            
            # Initialize display with splash screen
            logger.info("Initializing display with splash screen...")
            splash_image = self.renderer.render('start')
            if splash_image:
                self.renderer.display.display(splash_image)
            
            # Perform initial data load while showing splash
            logger.info("Loading initial data...")
            self.data_manager.update_data()
            
            # Generate image sequence for the first beer canvas
            self.renderer.image_sequence = self.renderer.generate_image_sequence()
            self.renderer.sequence_index = 0
            self.renderer.last_frame_time = time.time()
            
            # Reset last_db_check_time to current time
            last_db_check_time = time.time()
            
            # Main loop - runs until stop_event is set
            logger.info("Starting profiled main loop...")
            frame_count = 0
            start_time = time.time()
            
            while self.running and not stop_event.is_set():
                try:
                    current_time = time.time()
                    
                    # Check for database updates at specified frequency
                    if current_time - last_db_check_time >= self.data_manager.update_frequency:
                        self.data_manager.update_data()
                        last_db_check_time = current_time
                        
                        # Check if data has changed
                        data_changed = self.renderer.check_data_changed()
                        if data_changed:
                            # Generate new image sequence
                            self.renderer.image_sequence = self.renderer.generate_image_sequence()
                            self.renderer.sequence_index = 0
                            self.renderer.last_frame_time = current_time
                    
                    # Display current frame and count frames
                    if self.renderer.display_next_frame():
                        frame_count += 1
                    
                    # Short sleep to prevent CPU overload
                    time.sleep(0.001)
                    
                    # Every 100 frames, log performance info
                    if frame_count % 100 == 0:
                        elapsed = time.time() - start_time
                        fps_actual = frame_count / elapsed if elapsed > 0 else 0
                        logger.info(f"Processed {frame_count} frames, current FPS: {fps_actual:.2f}")
                    
                except KeyboardInterrupt:
                    logger.info("KeyboardInterrupt received")
                    break
                except Exception as e:
                    logger.error(f"Error in main loop: {e}")
            
            # Calculate final performance statistics
            elapsed = time.time() - start_time
            fps_actual = frame_count / elapsed if elapsed > 0 else 0
            logger.info(f"Final performance: {frame_count} frames in {elapsed:.2f}s, FPS: {fps_actual:.2f}")
            
            # Clean up resources
            self.cleanup()
            logger.info("Application terminated by profiler")
            return True
        
        # Replace the run method with our patched version
        KegDisplay.application.Application.run = patched_run
        
        # Start the application
        exit_code = start()
        
        # Restore the original run method
        KegDisplay.application.Application.run = original_run
        
        # Restore stdout and stderr
        sys.stdout = orig_stdout
        sys.stderr = orig_stderr
        
        logger.info(f"Application exited with code {exit_code}")
    
    except Exception as e:
        logger.error(f"Error running application: {e}", exc_info=True)
    finally:
        # Disable profiling
        profiler.disable()
        
        # Generate profiling report
        s = io.StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats(SortKey.CUMULATIVE)
        ps.print_stats(30)  # Print top 30 functions by cumulative time
        logger.info("Profiling Results:\n" + s.getvalue())
        
        # Also save results to file
        results_file = "kegdisplay_profile_results.txt"
        with open(results_file, "w") as f:
            ps = pstats.Stats(profiler, stream=f).sort_stats(SortKey.CUMULATIVE)
            ps.print_stats(50)  # More detailed in the file
            
            # Also include time spent stats
            f.write("\n\n==== Time Spent ====\n")
            ps = pstats.Stats(profiler, stream=f).sort_stats(SortKey.TIME)
            ps.print_stats(50)
        
        logger.info(f"Detailed profiling results saved to {results_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Profile the full KegDisplay application')
    parser.add_argument('--fps', type=int, default=60, help='Target frames per second')
    parser.add_argument('--duration', type=int, default=30, help='Test duration in seconds')
    parser.add_argument('--no-virtual', action='store_true', help='Do not use virtual display')
    
    args = parser.parse_args()
    
    profile_app(duration=args.duration, fps=args.fps, use_virtual=not args.no_virtual) 