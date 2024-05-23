# -*- coding: utf-8 -*-
# Copyright (c) 2024 Ron Ritchey
# See License.rst for details

"""
Create a new database for the KeyDisplay system.

.. versionadded:: 0.0.1
"""

import sqlite3
con = sqlite3.connect('beer.db')
cur = con.cursor()
cur.execute(    
  '''
  CREATE TABLE if not exists beers (
    'idBeer' integer primary key,
    'Name' tinytext NOT NULL,
    'ABV' float DEFAULT NULL,
    'IBU' float DEFAULT NULL,
    'Color' float DEFAULT NULL,
    'OriginalGravity' float DEFAULT NULL,
    'FinalGravity' float DEFAULT NULL,
    'Description' text,
    'Brewed' datetime DEFAULT NULL,
    'Kegged' datetime DEFAULT NULL,
    'Tapped' datetime DEFAULT NULL,
    'Notes' text
  )
  '''  
)

cur.execute(    
  '''
  CREATE TABLE if not exists taps (
    'idTap' integer primary key,
    'idBeer' tinytext NOT NULL
  )
  '''  
)


