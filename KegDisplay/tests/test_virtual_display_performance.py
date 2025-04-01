"""
Test script to measure maximum performance of the virtual display.
Runs without frame rate limiting to determine system capabilities.
"""

import time
from PIL import Image, ImageDraw
import numpy as np
from ..display.virtual_display import VirtualDisplay


def create_test_frames(width=256, height=64, num_frames=1000):
    """Create a sequence of test frames with varying patterns.
    
    Args:
        width: Width of each frame
        height: Height of each frame
        num_frames: Number of frames to generate
        
    Returns:
        List of PIL Images
    """
    frames = []
    
    for frame_num in range(num_frames):
        # Create a new frame
        frame = Image.new('1', (width, height), 0)
        draw = ImageDraw.Draw(frame)
        
        # Draw different patterns based on frame number
        if frame_num % 4 == 0:  # Full screen
            draw.rectangle([0, 0, width-1, height-1], fill=1)
        elif frame_num % 4 == 1:  # Checkerboard
            for x in range(0, width, 8):
                for y in range(0, height, 8):
                    if (x + y) % 16 == 0:
                        draw.rectangle([x, y, x+7, y+7], fill=1)
        elif frame_num % 4 == 2:  # Moving bar
            bar_pos = (frame_num * 2) % width
            draw.rectangle([bar_pos, 0, bar_pos+20, height-1], fill=1)
        else:  # Random pixels
            for _ in range(50):
                x = np.random.randint(0, width)
                y = np.random.randint(0, height)
                draw.point([x, y], fill=1)
                
        frames.append(frame)
    
    return frames


def test_virtual_display_performance():
    """Test the virtual display at maximum performance."""
    # Create virtual display with 2x zoom (reduced for performance)
    vd = VirtualDisplay(resolution=(256, 64), zoom=2)
    
    # Initialize the display
    if not vd.initialize():
        print("Failed to initialize virtual display")
        return
        
    try:
        # Generate frames
        print("Generating test frames...")
        frames = create_test_frames()
        
        # Performance metrics
        display_times = []
        total_start_time = time.time()
        
        print("\nStarting performance test...")
        print("Running at maximum speed (no frame rate limiting)")
        
        for i, frame in enumerate(frames):
            # Display the frame and measure time
            frame_start = time.time()
            vd.display(frame)
            display_time = time.time() - frame_start
            display_times.append(display_time)
            
            # Print progress every 100 frames
            if (i + 1) % 100 == 0:
                elapsed = time.time() - total_start_time
                fps = (i + 1) / elapsed
                avg_display_time = sum(display_times[-100:]) / 100
                print(f"Frame {i + 1}/1000, Current FPS: {fps:.2f}, "
                      f"Avg Display Time: {avg_display_time*1000:.2f}ms")
        
        # Calculate final statistics
        total_time = time.time() - total_start_time
        avg_fps = len(frames) / total_time
        avg_display_time = sum(display_times) / len(display_times)
        max_display_time = max(display_times)
        min_display_time = min(display_times)
        
        print("\nPerformance Test Results:")
        print(f"Total Frames: {len(frames)}")
        print(f"Total Time: {total_time:.2f} seconds")
        print(f"Average FPS: {avg_fps:.2f}")
        print(f"Average Display Time: {avg_display_time*1000:.2f}ms")
        print(f"Min Display Time: {min_display_time*1000:.2f}ms")
        print(f"Max Display Time: {max_display_time*1000:.2f}ms")
        
    finally:
        # Clean up
        vd.cleanup()


if __name__ == "__main__":
    test_virtual_display_performance() 