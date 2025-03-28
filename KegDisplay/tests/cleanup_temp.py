#!/usr/bin/env python3
"""
Cleanup script for KegDisplay network test temporary files.
This script locates and removes temporary directories and database files
created during network testing.
"""

import os
import glob
import shutil
import tempfile
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Cleanup")

def find_test_databases():
    """Find all network test database files in temporary directories"""
    # Search in standard temp directories
    temp_dirs = ['/tmp', '/var/tmp', tempfile.gettempdir()]
    
    # Search patterns for test database files
    patterns = [
        '*/test_db_*.db',      # Direct test databases
        '*/tmp*/test_db_*.db', # Nested in tmp subdirectories
        '*test_db_*.db.bak',   # Backup files
        '*test_db_*.db.new'    # New database files
    ]
    
    all_matches = []
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            for pattern in patterns:
                search_path = os.path.join(temp_dir, pattern)
                matches = glob.glob(search_path, recursive=True)
                all_matches.extend(matches)
    
    return all_matches

def find_test_directories():
    """Find directories that appear to be created by network tests"""
    temp_dirs = ['/tmp', '/var/tmp', tempfile.gettempdir()]
    
    # Look for directories that contain test database files
    test_dirs = set()
    
    for temp_dir in temp_dirs:
        if os.path.exists(temp_dir):
            # Find all potential test directories
            for item in os.listdir(temp_dir):
                dir_path = os.path.join(temp_dir, item)
                
                # Only process directories with tmp-like names
                if os.path.isdir(dir_path) and ('tmp' in item.lower() or item.startswith('_')):
                    # Check if it contains our test database files
                    db_files = glob.glob(os.path.join(dir_path, 'test_db_*.db'))
                    if db_files:
                        test_dirs.add(dir_path)
    
    return list(test_dirs)

def find_log_files():
    """Find log files created by network tests"""
    # Look in current directory and parent directories
    patterns = [
        'network_test_*.log',  # Network test logs
    ]
    
    all_matches = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        all_matches.extend(matches)
    
    return all_matches

def cleanup(remove_logs=False, dry_run=False):
    """Clean up all test files and directories"""
    # Find all test files
    db_files = find_test_databases()
    test_dirs = find_test_directories()
    log_files = find_log_files() if remove_logs else []
    
    # Report what we found
    logger.info(f"Found {len(db_files)} test database files")
    logger.info(f"Found {len(test_dirs)} test directories")
    if remove_logs:
        logger.info(f"Found {len(log_files)} log files")
    
    # Remove database files that aren't in test directories
    standalone_db_files = [f for f in db_files if not any(f.startswith(d) for d in test_dirs)]
    for file_path in standalone_db_files:
        logger.info(f"{'Would remove' if dry_run else 'Removing'} file: {file_path}")
        if not dry_run:
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
    
    # Remove test directories
    for dir_path in test_dirs:
        logger.info(f"{'Would remove' if dry_run else 'Removing'} directory: {dir_path}")
        if not dry_run:
            try:
                shutil.rmtree(dir_path)
            except Exception as e:
                logger.error(f"Error removing directory {dir_path}: {e}")
    
    # Remove log files if requested
    if remove_logs:
        for file_path in log_files:
            logger.info(f"{'Would remove' if dry_run else 'Removing'} log file: {file_path}")
            if not dry_run:
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error removing log file {file_path}: {e}")
    
    # Summary
    if dry_run:
        logger.info("Dry run completed. No files were actually removed.")
    else:
        logger.info("Cleanup completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up KegDisplay network test temporary files")
    parser.add_argument("--remove-logs", action="store_true", help="Also remove log files")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without actually removing")
    
    args = parser.parse_args()
    
    cleanup(remove_logs=args.remove_logs, dry_run=args.dry_run) 