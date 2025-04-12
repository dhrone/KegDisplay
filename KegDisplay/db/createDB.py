#!/usr/bin/env python3
import os
import sqlite3
import argparse
from pathlib import Path

def create_database(db_path=None):
    """
    Create a new SQLite database with the specified schema and initial data.
    
    Args:
        db_path (str, optional): Path where the database should be created.
                               Defaults to /home/beer/Dev/KegDisplay/KegDisplay/beer.db
    """
    # Set default path if not provided
    if db_path is None:
        db_path = "/home/beer/Dev/KegDisplay/KegDisplay/beer.db"
    
    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    os.makedirs(db_dir, exist_ok=True)
    
    # Connect to the database (this will create it if it doesn't exist)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create beers table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS beers (
            'idBeer' integer primary key,
            'Name' tinytext NOT NULL,
            'ABV' float DEFAULT NULL,
            'IBU' float DEFAULT NULL,
            'Color' float DEFAULT NULL,
            'OriginalGravity' float DEFAULT NULL,
            'FinalGravity' float DEFAULT NULL,
            'Description' text DEFAULT NULL,
            'Brewed' datetime DEFAULT NULL,
            'Kegged' datetime DEFAULT NULL,
            'Tapped' datetime DEFAULT NULL,
            'Notes' text DEFAULT NULL
        )
        ''')
        
        # Create taps table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS taps (
            'idTap' integer primary key,
            'idBeer' integer
        )
        ''')
        
        # Create change_log table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            row_id INTEGER NOT NULL,
            timestamp TEXT NOT NULL,
            content_hash TEXT NOT NULL
        )
        ''')
        
        # Create version table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS version (
            last_modified TEXT
        )
        ''')
        
        # Check if we need to insert initial data
        cursor.execute("SELECT COUNT(*) FROM beers")
        if cursor.fetchone()[0] == 0:
            # Insert initial beer record
            cursor.execute('''
            INSERT INTO beers (Name, ABV, Description)
            VALUES (?, ?, ?)
            ''', ('Sync', 0.0, 'Waiting for first sync from peer'))
            
            # Insert initial tap record
            cursor.execute('''
            INSERT INTO taps (idTap, idBeer)
            VALUES (?, ?)
            ''', (1, 1))
        
        # Commit the changes
        conn.commit()
        print(f"Database created/updated successfully at {db_path}")
        
    except sqlite3.Error as e:
        print(f"Error creating database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Create a new KegDisplay database.')
    parser.add_argument('--db-path', type=str, help='Path where the database should be created')
    args = parser.parse_args()
    
    create_database(args.db_path)

if __name__ == '__main__':
    main()
