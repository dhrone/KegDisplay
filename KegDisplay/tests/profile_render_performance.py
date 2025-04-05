"""
Profiler focused specifically on the rendering system performance.

This script isolates the rendering pipeline to measure:
1. Time spent generating the complete image sequence
2. Average render time per screen
3. Rendering speed independent of display/GUI overhead
"""

import sys
import os
import time
import cProfile
import pstats
import io
from pstats import SortKey
import logging
from PIL import Image

# Add parent directory to path to import KegDisplay modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import necessary modules
from KegDisplay.display.virtual_display import VirtualDisplay
from KegDisplay.renderer import SequenceRenderer
from KegDisplay.config.config_manager import ConfigManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('RenderProfiler')

class NullDisplay:
    """A display implementation that doesn't actually show anything.
    
    This allows us to measure pure rendering performance without GUI overhead.
    """
    
    def __init__(self, resolution=(256, 64)):
        self.resolution = resolution
        self._dataset = None
        
    def initialize(self):
        """Initialize the null display."""
        return True
        
    def display(self, image):
        """Pretend to display an image, but do nothing."""
        # Just return success, don't actually display
        return True
        
    def cleanup(self):
        """Clean up resources."""
        pass
    
    @property
    def width(self):
        """Get the width of the display."""
        return self.resolution[0]
    
    @property
    def height(self):
        """Get the height of the display."""
        return self.resolution[1]

def profile_render_performance(display_type='null', iterations=10):
    """Profile the rendering performance without display overhead.
    
    Args:
        display_type: Type of display to use ('null' or 'virtual')
        iterations: Number of times to generate the sequence for better averages
    """
    logger.info(f"Starting render performance test with {display_type} display")
    
    # Create an initial dataset
    dataset = {
        'sys': {
            'tapnr': 1,
            'target_fps': 60,
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
    config.config = {
        'display': display_type,
        'fps': 60,
        'splash_time': 1,
        'debug': True,
        'page': 'KegDisplay/page.yaml'  # Use default page
    }
    
    # Create the appropriate display
    if display_type == 'virtual':
        display = VirtualDisplay(resolution=(256, 64), zoom=2)
    else:
        display = NullDisplay(resolution=(256, 64))
    
    # Initialize the display
    display.initialize()
    
    # Set up profiling
    pr = cProfile.Profile()
    
    try:
        # Create renderer
        renderer = SequenceRenderer(display, dataset)
        
        # Load page and prepare the renderer
        renderer.load_page(config.get_config('page'))
        
        # Performance measurements
        total_render_time = 0
        total_frames = 0
        sequence_sizes = []
        
        logger.info(f"Running {iterations} iterations of sequence generation")
        
        # Run multiple iterations to get better averages
        for i in range(iterations):
            # Start profiling for this iteration
            pr.enable()
            
            # Measure sequence generation time
            start_time = time.time()
            image_sequence = renderer.generate_image_sequence()
            end_time = time.time()
            
            # Stop profiling for this iteration
            pr.disable()
            
            # Calculate metrics
            sequence_time = end_time - start_time
            total_render_time += sequence_time
            frames_count = len(image_sequence)
            total_frames += frames_count
            sequence_sizes.append(frames_count)
            
            # Calculate frames per second
            fps = frames_count / sequence_time if sequence_time > 0 else 0
            
            logger.info(f"Iteration {i+1}: Generated {frames_count} frames in {sequence_time:.3f}s ({fps:.1f} fps)")
            
            # Clear the sequence to avoid memory issues
            image_sequence = None
        
        # Calculate averages
        avg_render_time = total_render_time / iterations
        avg_sequence_size = sum(sequence_sizes) / len(sequence_sizes)
        avg_render_rate = total_frames / total_render_time if total_render_time > 0 else 0
        avg_time_per_frame = (total_render_time / total_frames) * 1000 if total_frames > 0 else 0
        
        logger.info("\nRender Performance Summary:")
        logger.info(f"Average sequence size: {avg_sequence_size:.1f} frames")
        logger.info(f"Average sequence generation time: {avg_render_time:.3f}s")
        logger.info(f"Average render rate: {avg_render_rate:.1f} frames per second")
        logger.info(f"Average time per frame: {avg_time_per_frame:.2f}ms")
        
        # Memory usage for frames
        test_frame = Image.new('1', (256, 64), 0)
        frame_size_bytes = len(test_frame.tobytes())
        estimated_memory = (frame_size_bytes * avg_sequence_size) / (1024 * 1024)  # Convert to MB
        logger.info(f"Estimated memory usage for sequence: {estimated_memory:.2f} MB")
        
        # Generate profiling report
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE)
        ps.print_stats(30)  # Print top 30 functions
        logger.info("\nProfiling Results:\n" + s.getvalue())
        
        # Also save results to file
        results_file = f"render_profile_{display_type}_results.txt"
        with open(results_file, "w") as f:
            ps = pstats.Stats(pr, stream=f).sort_stats(SortKey.CUMULATIVE)
            ps.print_stats(50)
            
            # Also include time spent stats
            f.write("\n\n==== Time Spent ====\n")
            ps = pstats.Stats(pr, stream=f).sort_stats(SortKey.TIME)
            ps.print_stats(50)
            
            # Save summary
            f.write("\n\n==== Performance Summary ====\n")
            f.write(f"Average sequence size: {avg_sequence_size:.1f} frames\n")
            f.write(f"Average sequence generation time: {avg_render_time:.3f}s\n")
            f.write(f"Average render rate: {avg_render_rate:.1f} frames per second\n")
            f.write(f"Average time per frame: {avg_time_per_frame:.2f}ms\n")
            f.write(f"Estimated memory usage for sequence: {estimated_memory:.2f} MB\n")
        
        logger.info(f"Detailed profiling results saved to {results_file}")
    
    finally:
        # Cleanup
        display.cleanup()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Profile the rendering system performance')
    parser.add_argument('--display', choices=['null', 'virtual'], default='null',
                      help='Display type to use (null=no GUI overhead, virtual=with GUI)')
    parser.add_argument('--iterations', type=int, default=10,
                      help='Number of rendering iterations to run')
    
    args = parser.parse_args()
    
    profile_render_performance(display_type=args.display, iterations=args.iterations) 