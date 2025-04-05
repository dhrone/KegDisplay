"""
Regression testing tool for KegDisplay performance.

This script compares profiling results between different runs to detect 
performance regressions or improvements.
"""

import argparse
import os
import re
import sys
import logging
from tabulate import tabulate

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger('RegressionTest')

def parse_profile_results(filename):
    """Parse a profile results file to extract key metrics.
    
    Args:
        filename: Path to the profile results file
        
    Returns:
        A dictionary with the parsed metrics
    """
    if not os.path.exists(filename):
        logger.error(f"Profile results file not found: {filename}")
        return None
        
    try:
        with open(filename, 'r') as f:
            content = f.read()
            
        # First, check for the FPS log entry format that appears in terminal output
        fps_match = re.search(r'Final performance: (\d+) frames in (\d+\.\d+)s, FPS: (\d+\.\d+)', content)
        if fps_match:
            frames = int(fps_match.group(1))
            duration = float(fps_match.group(2))
            fps = float(fps_match.group(3))
            logger.debug(f"Found FPS data in log format: {fps} FPS, {frames} frames in {duration}s")
        else:
            # Try alternative format that might be in profiler output
            fps_match = re.search(r'Average FPS: (\d+\.\d+)', content)
            frames_match = re.search(r'Test complete: (\d+) frames in (\d+\.\d+)s', content)
            
            if fps_match and frames_match:
                fps = float(fps_match.group(1))
                frames = int(frames_match.group(1))
                duration = float(frames_match.group(2))
                logger.debug(f"Found FPS data in profiler output: {fps} FPS, {frames} frames in {duration}s")
            else:
                # Last attempt - check for the raw profiler stats header
                calls_match = re.search(r'(\d+) function calls .* in (\d+\.\d+) seconds', content)
                if calls_match and 'frames' in os.path.basename(filename):
                    # If we can extract the frame count from the filename, use that
                    frames_in_name = re.search(r'(\d+)_frames', os.path.basename(filename))
                    if frames_in_name:
                        frames = int(frames_in_name.group(1))
                        duration = float(calls_match.group(2))
                        fps = frames / duration if duration > 0 else 0
                        logger.debug(f"Calculated FPS from profile data: {fps} FPS, {frames} frames in {duration}s")
                    else:
                        logger.error(f"Could not extract frame count from filename: {filename}")
                        # Default to zero values if no FPS information found
                        fps, frames, duration = 0, 0, 0
                else:
                    logger.warning(f"Could not find FPS information in {filename}")
                    # Default to zero values if no FPS information found
                    fps, frames, duration = 0, 0, 0
                
        # Parse the hotspot functions from the cumulative time profile
        functions = []
        in_cumulative_section = False
        found_header = False
        
        for line in content.split('\n'):
            # Detect the start of the cumulative section
            if "Ordered by: cumulative time" in line:
                in_cumulative_section = True
                continue
                
            # Look for the header line after that
            if in_cumulative_section and not found_header and "ncalls" in line and "tottime" in line:
                found_header = True
                continue
                
            # Start collecting function stats after the header
            if in_cumulative_section and found_header:
                # Skip separator lines
                if line.strip() == "" or "..." in line:
                    continue
                    
                # End of stats section
                if "=" in line or "Time Spent" in line:
                    break
                    
                # Try to parse the function entry
                parts = re.split(r'\s+', line.strip(), maxsplit=5)
                if len(parts) >= 6:
                    try:
                        ncalls = parts[0]
                        tottime = float(parts[1])
                        percall_tot = float(parts[2])
                        cumtime = float(parts[3])
                        percall_cum = float(parts[4])
                        function_path = parts[5]
                        
                        # Extract just the function name and module
                        function_match = re.search(r'([^/]+):(\d+)\(([^)]+)\)$', function_path)
                        if function_match:
                            module = function_match.group(1)
                            line_num = function_match.group(2)
                            function = function_match.group(3)
                            
                            functions.append({
                                'ncalls': ncalls,
                                'tottime': tottime,
                                'percall_tot': percall_tot,
                                'cumtime': cumtime,
                                'percall_cum': percall_cum,
                                'module': module,
                                'line': line_num,
                                'function': function,
                                'path': function_path
                            })
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Error parsing line: {line} - {e}")
        
        return {
            'frames': frames,
            'duration': duration,
            'fps': fps,
            'functions': functions
        }
    
    except Exception as e:
        logger.error(f"Error parsing profile results: {e}")
        return None

def compare_results(current, baseline):
    """Compare current results with baseline to identify regressions/improvements.
    
    Args:
        current: Dictionary with current metrics
        baseline: Dictionary with baseline metrics
        
    Returns:
        Dictionary with comparison results
    """
    if not current or not baseline:
        return None
        
    # Compare overall performance
    fps_change = current['fps'] - baseline['fps']
    fps_change_pct = (fps_change / baseline['fps']) * 100 if baseline['fps'] > 0 else 0
    
    # Build a lookup dictionary for baseline functions
    baseline_functions = {f['path']: f for f in baseline['functions']}
    
    # Compare function performance
    function_changes = []
    for current_func in current['functions']:
        path = current_func['path']
        if path in baseline_functions:
            baseline_func = baseline_functions[path]
            cumtime_change = current_func['cumtime'] - baseline_func['cumtime']
            pct_change = (cumtime_change / baseline_func['cumtime']) * 100 if baseline_func['cumtime'] > 0 else 0
            
            function_changes.append({
                'module': current_func['module'],
                'function': current_func['function'],
                'baseline_time': baseline_func['cumtime'],
                'current_time': current_func['cumtime'],
                'change_sec': cumtime_change,
                'change_pct': pct_change
            })
        else:
            # New function not in baseline
            function_changes.append({
                'module': current_func['module'],
                'function': current_func['function'],
                'baseline_time': 0,
                'current_time': current_func['cumtime'],
                'change_sec': current_func['cumtime'],
                'change_pct': 100  # 100% increase since it's new
            })
    
    # Also check for functions in baseline but not in current
    current_paths = {f['path'] for f in current['functions']}
    for path, baseline_func in baseline_functions.items():
        if path not in current_paths:
            function_changes.append({
                'module': baseline_func['module'],
                'function': baseline_func['function'],
                'baseline_time': baseline_func['cumtime'],
                'current_time': 0,
                'change_sec': -baseline_func['cumtime'],
                'change_pct': -100  # 100% decrease since it's gone
            })
    
    # Sort function changes by absolute percentage change
    function_changes.sort(key=lambda x: abs(x['change_pct']), reverse=True)
    
    return {
        'baseline_fps': baseline['fps'],
        'current_fps': current['fps'],
        'fps_change': fps_change,
        'fps_change_pct': fps_change_pct,
        'function_changes': function_changes
    }

def print_report(comparison):
    """Print a report with the comparison results.
    
    Args:
        comparison: The comparison results
    """
    if not comparison:
        logger.error("No comparison results available")
        return
    
    # Overall performance changes
    logger.info("=" * 80)
    logger.info("PERFORMANCE REGRESSION TEST RESULTS")
    logger.info("=" * 80)
    
    # FPS comparison
    fps_status = "🟢 IMPROVED" if comparison['fps_change'] > 0 else "🔴 REGRESSED" if comparison['fps_change'] < 0 else "🟡 UNCHANGED"
    logger.info(f"OVERALL PERFORMANCE: {fps_status}")
    logger.info(f"  Baseline FPS: {comparison['baseline_fps']:.2f}")
    logger.info(f"  Current FPS:  {comparison['current_fps']:.2f}")
    logger.info(f"  Change:       {comparison['fps_change']:.2f} ({comparison['fps_change_pct']:.2f}%)")
    logger.info("")
    
    # Function changes
    logger.info("TOP FUNCTION CHANGES (by absolute percentage):")
    
    # Prepare table data
    table_data = []
    for change in comparison['function_changes'][:10]:  # Show top 10 changes
        status = "🟢" if change['change_sec'] < 0 else "🔴" if change['change_sec'] > 0 else "🟡"
        table_data.append([
            status,
            f"{change['module']}:{change['function']}",
            f"{change['baseline_time']:.6f}s",
            f"{change['current_time']:.6f}s",
            f"{change['change_sec']:.6f}s",
            f"{change['change_pct']:.2f}%"
        ])
    
    # Print the table
    headers = ["Status", "Function", "Baseline", "Current", "Change", "% Change"]
    logger.info(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    # Summary
    improved_count = sum(1 for change in comparison['function_changes'] if change['change_sec'] < 0)
    regressed_count = sum(1 for change in comparison['function_changes'] if change['change_sec'] > 0)
    
    logger.info(f"\nSummary: {improved_count} functions improved, {regressed_count} functions regressed")
    logger.info("=" * 80)
    
    # Final assessment
    if comparison['fps_change'] >= 0:
        logger.info("✅ PASS: No significant performance regression detected")
    else:
        if comparison['fps_change_pct'] < -5:  # More than 5% regression
            logger.info("❌ FAIL: Significant performance regression detected!")
        else:
            logger.info("⚠️ WARNING: Minor performance regression detected")

def main():
    """Main entry point for the regression test."""
    parser = argparse.ArgumentParser(description='Compare KegDisplay performance profiles')
    parser.add_argument('--current', required=True, help='Path to current profile results file')
    parser.add_argument('--compare-with', required=True, help='Path to baseline profile results file to compare against')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Parse the profile results
    current_results = parse_profile_results(args.current)
    baseline_results = parse_profile_results(args.compare_with)
    
    if not current_results or not baseline_results:
        logger.error("Failed to parse profile results")
        return 1
    
    # Compare the results
    comparison = compare_results(current_results, baseline_results)
    
    # Print the comparison report
    print_report(comparison)
    
    # Return exit code based on performance regression
    if comparison and comparison['fps_change'] < 0 and comparison['fps_change_pct'] < -5:
        return 1  # Fail if significant regression
    return 0  # Pass otherwise

if __name__ == "__main__":
    sys.exit(main()) 