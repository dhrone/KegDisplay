"""
Test script for the virtual display implementation.
Demonstrates the display with a bouncing ball animation.
"""

import time
from PIL import Image, ImageDraw
import numpy as np
import argparse
from ..display.virtual_display import VirtualDisplay


def create_bouncing_ball_frames(width=256, height=64, num_frames=500, ball_radius=8):
    """Create a sequence of frames showing a bouncing ball.
    
    Args:
        width: Width of each frame
        height: Height of each frame
        num_frames: Number of frames to generate
        ball_radius: Radius of the ball in pixels
        
    Returns:
        List of PIL Images
    """
    frames = []
    
    # Initial position and velocity
    x = width // 2
    y = height // 2
    dx = 3
    dy = 3
    
    for _ in range(num_frames):
        # Create a new frame
        frame = Image.new('1', (width, height), 0)
        draw = ImageDraw.Draw(frame)
        
        # Draw the ball
        draw.ellipse(
            [x - ball_radius, y - ball_radius, x + ball_radius, y + ball_radius],
            fill=1
        )
        
        # Update position
        x += dx
        y += dy
        
        # Bounce off walls
        if x - ball_radius <= 0 or x + ball_radius >= width:
            dx = -dx
        if y - ball_radius <= 0 or y + ball_radius >= height:
            dy = -dy
            
        frames.append(frame)
    
    return frames


def test_virtual_display():
    """Test the virtual display with a bouncing ball animation."""
    # Parse command line arguments if running directly
    parser = argparse.ArgumentParser(description='Test the virtual display with a bouncing ball animation')
    parser.add_argument('--fps', type=int, default=30, help='Target frames per second')
    parser.add_argument('--zoom', type=int, default=3, help='Zoom factor for better visibility')
    args = parser.parse_args()
    
    # Create virtual display with zoom factor for better visibility
    vd = VirtualDisplay(resolution=(256, 64), zoom=args.zoom)
    
    # Initialize the display
    if not vd.initialize():
        print("Failed to initialize virtual display")
        return
        
    try:
        # Generate frames
        print("Generating frames...")
        frames = create_bouncing_ball_frames()
        
        # Target frame time for specified FPS
        target_frame_time = 1.0 / args.fps
        
        # Display frames
        print(f"Starting animation at {args.fps} FPS...")
        start_time = time.time()
        next_frame_time = start_time
        
        for i, frame in enumerate(frames):
            # Calculate how long to wait
            current_time = time.time()
            if next_frame_time > current_time:
                time.sleep(next_frame_time - current_time)
            
            # Display the frame
            frame_start = time.time()
            vd.display(frame)
            
            # Calculate next frame time
            next_frame_time = frame_start + target_frame_time
            
            # Print progress every 100 frames
            if (i + 1) % 100 == 0:
                elapsed = time.time() - start_time
                fps = (i + 1) / elapsed
                print(f"Frame {i + 1}/500, Current FPS: {fps:.2f}")
                
        total_time = time.time() - start_time
        print(f"\nAnimation complete!")
        print(f"Total time: {total_time:.2f} seconds")
        print(f"Average FPS: {500/total_time:.2f}")
        
    finally:
        # Clean up
        vd.cleanup()


if __name__ == "__main__":
    test_virtual_display() 