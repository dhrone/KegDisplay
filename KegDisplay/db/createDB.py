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
    'Description' text DEFAULT NULL,
    'Brewed' datetime DEFAULT NULL,
    'Kegged' datetime DEFAULT NULL,
    'Tapped' datetime DEFAULT NULL,
    'Notes' text DEFAULT NULL
  )
  '''  
)

cur.execute(    
  '''
  CREATE TABLE if not exists taps (
    'idTap' integer primary key,
    'idBeer' integer
  )
  '''  
)

cur.execute(
    '''
    INSERT INTO beers (Name, ABV, Description) VALUES 
      ('Porter', 6.4, 'A standard porter from the land of porters'), 
      ('Golden Ale', 4.5, 'Like sunshine in a bottle.  Enjoy while it lasts')
    '''
)

cur.execute(
    '''
    INSERT INTO taps (idTap, idBeer) VALUES 
      (1, 1),
      (2, 2)
    '''
)




cur.close()
con.close()


