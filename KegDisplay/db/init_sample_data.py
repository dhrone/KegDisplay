#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Initialize sample data for the KegDisplay system

import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Get the directory where this script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
DB_PATH = os.path.join(BASE_DIR, 'beer.db')

def init_sample_data():
    """Initialize the database with sample data"""
    print(f"Initializing sample data in: {DB_PATH}")
    
    # Make sure the database exists and has the required tables
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS beers (
        idBeer INTEGER PRIMARY KEY,
        Name tinytext NOT NULL,
        ABV float,
        IBU float,
        Color float,
        OriginalGravity float,
        FinalGravity float,
        Description TEXT,
        Brewed datetime,
        Kegged datetime,
        Tapped datetime,
        Notes TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS taps (
        idTap INTEGER PRIMARY KEY,
        idBeer INTEGER
    )
    ''')
    
    # Check if we already have data
    cursor.execute("SELECT COUNT(*) FROM beers")
    beer_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM taps")
    tap_count = cursor.fetchone()[0]
    
    if beer_count > 0 or tap_count > 0:
        print(f"Database already has data: {beer_count} beers, {tap_count} taps")
        choice = input("Do you want to reset the database and add sample data? (y/N): ")
        if choice.lower() != 'y':
            print("Keeping existing data.")
            conn.close()
            return
        
        # Clear existing data
        cursor.execute("DELETE FROM taps")
        cursor.execute("DELETE FROM beers")
        print("Deleted existing data.")

    # Sample beer data
    now = datetime.now()
    
    sample_beers = [
        {
            'Name': 'Hoppy IPA',
            'ABV': 6.8,
            'IBU': 65,
            'Color': 6.2,
            'OriginalGravity': 1.062,
            'FinalGravity': 1.010,
            'Description': 'A classic American IPA with a strong hop presence and citrus notes.',
            'Brewed': (now - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Kegged': (now - timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Tapped': (now - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Notes': 'Dry hopped with Citra and Mosaic.'
        },
        {
            'Name': 'Chocolate Porter',
            'ABV': 5.6,
            'IBU': 28,
            'Color': 34.0,
            'OriginalGravity': 1.056,
            'FinalGravity': 1.014,
            'Description': 'A rich porter with notes of chocolate and coffee.',
            'Brewed': (now - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Kegged': (now - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Tapped': (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Notes': 'Added cocoa nibs during secondary fermentation.'
        },
        {
            'Name': 'Summer Wheat',
            'ABV': 4.2,
            'IBU': 12,
            'Color': 3.8,
            'OriginalGravity': 1.042,
            'FinalGravity': 1.006,
            'Description': 'A light and refreshing wheat beer, perfect for summer.',
            'Brewed': (now - timedelta(days=25)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Kegged': (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Tapped': (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Notes': 'Added orange peel and coriander during the boil.'
        },
        {
            'Name': 'Amber Ale',
            'ABV': 5.4,
            'IBU': 35,
            'Color': 12.0,
            'OriginalGravity': 1.054,
            'FinalGravity': 1.012,
            'Description': 'A balanced amber ale with caramel malt flavors and a moderate hop presence.',
            'Brewed': (now - timedelta(days=45)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Kegged': (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Tapped': None,
            'Notes': 'Used a blend of Cascade and Centennial hops.'
        },
        {
            'Name': 'Belgian Tripel',
            'ABV': 8.5,
            'IBU': 25,
            'Color': 4.5,
            'OriginalGravity': 1.080,
            'FinalGravity': 1.010,
            'Description': 'A strong Belgian-style tripel with notes of fruit and spice.',
            'Brewed': (now - timedelta(days=70)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Kegged': (now - timedelta(days=35)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Tapped': (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'Notes': 'Fermented with Belgian Trappist yeast strain.'
        }
    ]
    
    # Insert beer data
    beer_ids = []
    for beer in sample_beers:
        cursor.execute('''
        INSERT INTO beers (
            Name, ABV, IBU, Color, OriginalGravity, FinalGravity,
            Description, Brewed, Kegged, Tapped, Notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            beer['Name'],
            beer['ABV'],
            beer['IBU'],
            beer['Color'],
            beer['OriginalGravity'],
            beer['FinalGravity'],
            beer['Description'],
            beer['Brewed'],
            beer['Kegged'],
            beer['Tapped'],
            beer['Notes']
        ))
        beer_ids.append(cursor.lastrowid)
    
    # Create some taps and assign beers
    for i in range(1, 4):
        if i <= len(beer_ids):
            cursor.execute("INSERT INTO taps (idTap, idBeer) VALUES (?, ?)", (i, beer_ids[i-1]))
        else:
            cursor.execute("INSERT INTO taps (idTap, idBeer) VALUES (?, NULL)", (i,))
    
    # Create change_log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS change_log (
        id INTEGER PRIMARY KEY,
        table_name TEXT,
        operation TEXT,
        row_id INTEGER,
        timestamp TEXT,
        content_hash TEXT
    )
    ''')
    
    # Create version table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_modified TEXT
    )
    ''')
    
    # Make sure there's an entry in the version table
    cursor.execute('SELECT COUNT(*) FROM version')
    if cursor.fetchone()[0] == 0:
        now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        cursor.execute('INSERT INTO version (id, last_modified) VALUES (1, ?)', (now_str,))
    
    conn.commit()
    conn.close()
    
    print(f"Added {len(sample_beers)} sample beers and 3 taps to the database.")

if __name__ == '__main__':
    init_sample_data() 