"""
Renderer module for KegDisplay

Handles generating and sequencing images for display.
"""

import time
import logging
import hashlib
import json
from collections import deque

from tinyDisplay.render.collection import canvas, sequence
from tinyDisplay.render.widget import text
from tinyDisplay.utility import dataset, image2Text
from tinyDisplay.cfg import _tdLoader, load

logger = logging.getLogger("KegDisplay")


class SequenceRenderer:
    """Handles rendering and sequencing of display images."""
    
    def __init__(self, display, dataset_obj=None):
        """Initialize the renderer.
        
        Args:
            display: Display object to render to
            dataset_obj: Optional dataset object to use
        """
        self.display = display
        self._dataset = dataset_obj or dataset()
        self.main_display = None
        self.image_sequence = []
        self.sequence_index = 0
        self.last_frame_time = 0
        
        # Used to track data changes
        self.beers_hash = None
        self.taps_hash = None
        
    def load_page(self, page_path):
        """Load a page template from a YAML file.
        
        Args:
            page_path: Path to the page template file
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.main_display = load(page_path, dataset=self._dataset)
            return True
        except Exception as e:
            logger.error(f"Error loading page: {e}")
            return False
    
    def update_dataset(self, key, value, merge=False):
        """Update the dataset with new values.
        
        Args:
            key: Key to update
            value: Value to set
            merge: Whether to merge with existing data
        """
        self._dataset.update(key, value, merge=merge)
        
    def dict_hash(self, dictionary, ignore_key=None):
        """Generate a hash of a dictionary, optionally ignoring a specific key.

        Args:
            dictionary: Dictionary to hash
            ignore_key: Key to ignore when generating hash

        Returns:
            str: Hash value of the dictionary
        """
        filtered_dict = {k: v for k, v in dictionary.items() if k != ignore_key}
        # Convert all keys to strings before dumping to JSON
        string_dict = {str(k): v for k, v in filtered_dict.items()}
        return hashlib.md5(json.dumps(string_dict, sort_keys=True).encode()).hexdigest()
    
    def check_data_changed(self):
        """Check if the dataset has changed.
        
        Returns:
            bool: True if data has changed, False otherwise
        """
        current_beers_hash = self.dict_hash(self._dataset.get('beers', {}), '__timestamp__')
        current_taps_hash = self.dict_hash(self._dataset.get('taps', {}), '__timestamp__')
        
        # Check if this is the first check or if data has changed
        if self.beers_hash is None or self.taps_hash is None:
            self.beers_hash = current_beers_hash
            self.taps_hash = current_taps_hash
            return True
            
        if current_beers_hash != self.beers_hash or current_taps_hash != self.taps_hash:
            self.beers_hash = current_beers_hash
            self.taps_hash = current_taps_hash
            return True
            
        return False
    
    def render(self, status=None):
        """Render a single frame and return the image.
        
        Args:
            status: Optional status to update in the dataset
            
        Returns:
            PIL.Image: The rendered image
        """
        if status:
            self._dataset.update('sys', {'status': status}, merge=True)
            logger.debug(f"Status changed to '{status}'")
            
        if self.main_display:
            self.main_display.render()
            return self.main_display.image
        
        return None
    
    def generate_image_sequence(self):
        """Generate a sequence of images for animation.
        
        Returns:
            list: List of (image, duration) tuples
        """
        if not self.main_display:
            logger.error("No display loaded")
            return []
            
        # Check if beer data exists
        beers = self._dataset.get('beers', {})
        taps = self._dataset.get('taps', {})
        sys_data = self._dataset.get('sys', {})
        logger.debug(f"Current beer data: {beers}")
        logger.debug(f"Current tap data: {taps}")
        logger.debug(f"Current system data: {sys_data}")
        
        # Make sure we have valid beer data for the current tap
        tapnr = sys_data.get('tapnr', 1)
        if tapnr not in taps or len(beers) == 0 or taps[tapnr] not in beers:
            logger.warning(f"Missing beer data for tap {tapnr}. Adding sample data for display.")
            # Add sample beer data to avoid errors
            beer_id = 1
            self._dataset.update('beers', {
                beer_id: {
                    'Name': 'Sample Beer',
                    'ABV': 5.0,
                    'Description': 'Sample beer description for testing'
                }
            }, merge=True)
            self._dataset.update('taps', {tapnr: beer_id}, merge=True)
        
        # Update status to indicate we're in 'running' mode
        self._dataset.update('sys', {'status': 'running'}, merge=True)
        logger.debug("Set status to 'running' in generate_image_sequence")
        
        # Initialize variables
        image_sequence = []
        raw_frames = []
        min_sequence_length = 100  # Minimum frames to collect
        max_iterations = 2000      # Safety limit
        last_image = None
        static_count = 0
        frame_changes = 0
        
        logger.debug("Starting image sequence generation")
        start_time = time.time()
        
        # Generate frames until we find a repeating pattern
        for i in range(max_iterations):
            # Generate next frame
            self.main_display.render()
            current_image = self.main_display.image.convert("1")
            current_bytes = current_image.tobytes()
            
            # Add to raw frames collection
            raw_frames.append(current_bytes)
            
            # For diagnostic purposes, periodically log image content (every 20 frames)
            if i % 20 == 0:
                logger.debug(f"Frame {i} generated - checking for changes")
            
            # Process the frame
            if last_image is not None:
                last_bytes = last_image.tobytes()
                
                if current_bytes == last_bytes:
                    # Frame hasn't changed
                    static_count += 1
                    # Log long static periods to help diagnose issues
                    if static_count % 20 == 0:
                        logger.debug(f"Static frame count: {static_count}")
                else:
                    # Frame has changed
                    frame_changes += 1
                    if static_count > 0:
                        # Store the previous static frame with its duration
                        image_sequence.append((last_image, static_count / 20.0))  # 20 is render frequency
                        logger.debug(f"Added static frame with duration {static_count / 20.0:.2f}s")
                    static_count = 0
                    # Store the new frame
                    image_sequence.append((current_image, 1 / 20.0))
                    logger.debug(f"Added new frame {len(image_sequence)-1} (frame change #{frame_changes})")
            else:
                # First frame
                image_sequence.append((current_image, 1 / 20.0))
                logger.debug("Added first frame to sequence")
                
            last_image = current_image
            
            # Start checking for loops after collecting enough frames
            if len(raw_frames) > min_sequence_length:
                pattern_length = 10  # Minimum pattern length to check
                
                # Only check when we have enough frames
                if len(raw_frames) >= pattern_length * 2:
                    # Get recent frames and compare with start frames
                    recent_frames = raw_frames[-pattern_length:]
                    start_frames = raw_frames[:pattern_length]
                    
                    # Check for match
                    matches = True
                    for j in range(pattern_length):
                        if recent_frames[j] != start_frames[j]:
                            matches = False
                            break
                    
                    if matches:
                        # Found repeating pattern
                        sequence_length = len(raw_frames) - pattern_length
                        logger.debug(f"Found repeating pattern after {sequence_length} frames")
                        
                        # Add any remaining static frames
                        if static_count > 0:
                            image_sequence.append((last_image, static_count / 20.0))
                            logger.debug(f"Added final static frame with duration {static_count / 20.0:.2f}s")
                            
                        # Trim to one complete cycle
                        final_sequence = image_sequence[:sequence_length]
                        logger.debug(f"Returning sequence with {len(final_sequence)} frames and {frame_changes} frame changes")
                        return final_sequence
        
        # If we reach max iterations without finding a pattern
        logger.warning(f"Reached maximum iterations ({max_iterations}) - using collected frames")
        if static_count > 0:
            image_sequence.append((last_image, static_count / 20.0))
            
        return image_sequence
        
    def display_next_frame(self):
        """Display the next frame in the sequence.
        
        Returns:
            bool: True if frame was displayed, False otherwise
        """
        if not self.image_sequence:
            logger.debug("No image sequence available")
            return False
            
        current_time = time.time()
        current_image, duration = self.image_sequence[self.sequence_index]
        
        # Debug the timing calculations
        time_since_last = current_time - self.last_frame_time
        
        # Only log timing info occasionally to reduce output volume
        if not hasattr(self, '_debug_counter'):
            self._debug_counter = 0
        self._debug_counter = (self._debug_counter + 1) % 100  # Log every 20th frame
        
        if self._debug_counter == 0:
            logger.debug(f"Frame {self.sequence_index}: time since last frame: {time_since_last:.3f}s, duration: {duration:.3f}s")
        
        if time_since_last >= duration:
            # Display the current frame
            self.display.display(current_image)
            self.last_frame_time = current_time
            
            # Advance to next frame
            prev_index = self.sequence_index
            self.sequence_index = (self.sequence_index + 1) % len(self.image_sequence)
            
            logger.debug(f"Advanced from frame {prev_index} to frame {self.sequence_index}/{len(self.image_sequence)-1}")
            return True
            
        return False 