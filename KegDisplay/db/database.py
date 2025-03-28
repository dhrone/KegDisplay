"""
Database management module for KegDisplay.
Handles core database operations for beer and tap management.
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("KegDisplay")

class DatabaseManager:
    """
    Handles core database operations for the KegDisplay system.
    Manages the beer and tap tables and provides CRUD operations.
    """
    
    def __init__(self, db_path):
        """Initialize the database manager
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.initialize_tables()
        
    def initialize_tables(self):
        """Initialize database tables if they don't exist"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create beers table if it doesn't exist
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
            
            # Create taps table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS taps (
                    idTap INTEGER PRIMARY KEY,
                    idBeer INTEGER
                )
            ''')
            
            conn.commit()
            logger.info("Database tables initialized")
    
    def get_connection(self):
        """Get a database connection with proper settings
        
        Returns:
            conn: SQLite database connection
        """
        conn = sqlite3.connect(self.db_path)
        return conn
    
    def query(self, sql, params=(), fetch_all=False, row_factory=None):
        """Execute a query and return results
        
        Args:
            sql: SQL query string
            params: Parameters for the query
            fetch_all: Whether to fetch all results or just one
            row_factory: Optional row factory to use for result rows
            
        Returns:
            Result of the query execution
        """
        with self.get_connection() as conn:
            if row_factory:
                conn.row_factory = row_factory
            cursor = conn.cursor()
            cursor.execute(sql, params)
            
            if sql.strip().upper().startswith(("SELECT", "PRAGMA")):
                if fetch_all:
                    return cursor.fetchall()
                else:
                    return cursor.fetchone()
            else:
                conn.commit()
                return cursor.lastrowid if cursor.lastrowid else cursor.rowcount
    
    # ---- Beer Management Methods ----
    
    def add_beer(self, name, abv=None, ibu=None, color=None, og=None, fg=None, 
                description=None, brewed=None, kegged=None, tapped=None, notes=None):
        """Add a new beer to the database
        
        Args:
            name: Name of the beer (required)
            abv: Alcohol by volume percentage
            ibu: International Bitterness Units
            color: Beer color (SRM)
            og: Original gravity
            fg: Final gravity
            description: Beer description
            brewed: Date brewed (ISO format string or datetime object)
            kegged: Date kegged (ISO format string or datetime object)
            tapped: Date tapped (ISO format string or datetime object)
            notes: Additional notes
            
        Returns:
            id: The ID of the newly added beer
        """
        # Convert datetime objects to strings if needed
        if isinstance(brewed, datetime):
            brewed = brewed.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(kegged, datetime):
            kegged = kegged.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(tapped, datetime):
            tapped = tapped.strftime("%Y-%m-%d %H:%M:%S")
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO beers (
                    Name, ABV, IBU, Color, OriginalGravity, FinalGravity,
                    Description, Brewed, Kegged, Tapped, Notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, abv, ibu, color, og, fg, description, brewed, kegged, tapped, notes))
            
            beer_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Added beer '{name}' with ID {beer_id}")
            return beer_id
    
    def update_beer(self, beer_id, name=None, abv=None, ibu=None, color=None, og=None, fg=None,
                   description=None, brewed=None, kegged=None, tapped=None, notes=None):
        """Update an existing beer in the database
        
        Args:
            beer_id: ID of the beer to update
            Other parameters: Same as add_beer, but all optional
            
        Returns:
            success: True if the beer was updated, False if not found
        """
        # Convert datetime objects to strings if needed
        if isinstance(brewed, datetime):
            brewed = brewed.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(kegged, datetime):
            kegged = kegged.strftime("%Y-%m-%d %H:%M:%S")
        if isinstance(tapped, datetime):
            tapped = tapped.strftime("%Y-%m-%d %H:%M:%S")
        
        # First get the current values
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT Name, ABV, IBU, Color, OriginalGravity, FinalGravity, "
                "Description, Brewed, Kegged, Tapped, Notes FROM beers WHERE idBeer = ?", 
                (beer_id,)
            )
            
            row = cursor.fetchone()
            if not row:
                logger.warning(f"Beer with ID {beer_id} not found for update")
                return False
            
            # Use existing values for any parameters not provided
            current_name, current_abv, current_ibu, current_color = row[0:4]
            current_og, current_fg, current_desc = row[4:7]
            current_brewed, current_kegged, current_tapped, current_notes = row[7:11]
            
            # Update with new values if provided
            update_name = name if name is not None else current_name
            update_abv = abv if abv is not None else current_abv
            update_ibu = ibu if ibu is not None else current_ibu
            update_color = color if color is not None else current_color
            update_og = og if og is not None else current_og
            update_fg = fg if fg is not None else current_fg
            update_desc = description if description is not None else current_desc
            update_brewed = brewed if brewed is not None else current_brewed
            update_kegged = kegged if kegged is not None else current_kegged
            update_tapped = tapped if tapped is not None else current_tapped
            update_notes = notes if notes is not None else current_notes
            
            # Perform the update
            cursor.execute('''
                UPDATE beers SET 
                    Name = ?, ABV = ?, IBU = ?, Color = ?, OriginalGravity = ?, 
                    FinalGravity = ?, Description = ?, Brewed = ?, Kegged = ?, 
                    Tapped = ?, Notes = ?
                WHERE idBeer = ?
            ''', (update_name, update_abv, update_ibu, update_color, update_og, 
                 update_fg, update_desc, update_brewed, update_kegged, update_tapped, 
                 update_notes, beer_id))
            
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Updated beer '{update_name}' with ID {beer_id}")
                return True
            else:
                logger.warning(f"No changes made to beer with ID {beer_id}")
                return False
    
    def delete_beer(self, beer_id):
        """Delete a beer from the database
        
        Args:
            beer_id: ID of the beer to delete
            
        Returns:
            success: True if the beer was deleted, False if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # First check if beer exists
            cursor.execute("SELECT Name FROM beers WHERE idBeer = ?", (beer_id,))
            beer = cursor.fetchone()
            
            if not beer:
                logger.warning(f"Beer with ID {beer_id} not found for deletion")
                return False
            
            beer_name = beer[0]
            
            # Delete the beer
            cursor.execute("DELETE FROM beers WHERE idBeer = ?", (beer_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                logger.info(f"Deleted beer '{beer_name}' with ID {beer_id}")
                return True
            else:
                logger.warning(f"Failed to delete beer with ID {beer_id}")
                return False
    
    def get_beer(self, beer_id):
        """Get a beer by ID
        
        Args:
            beer_id: ID of the beer to retrieve
            
        Returns:
            beer: Dictionary with beer information or None if not found
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM beers WHERE idBeer = ?", 
                (beer_id,)
            )
            
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                return None
    
    def get_all_beers(self):
        """Get all beers from the database
        
        Returns:
            beers: List of dictionaries with beer information
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row  # Return rows as dictionaries
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM beers ORDER BY Name")
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ---- Tap Management Methods ----
    
    def add_tap(self, tap_id=None, beer_id=None):
        """Add a new tap to the database
        
        Args:
            tap_id: Optional tap ID (auto-assigned if not provided)
            beer_id: Optional ID of beer on tap
            
        Returns:
            id: The ID of the newly added tap
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if tap_id is not None:
                # Check if tap with this ID already exists
                cursor.execute("SELECT idTap FROM taps WHERE idTap = ?", (tap_id,))
                if cursor.fetchone():
                    logger.warning(f"Tap with ID {tap_id} already exists")
                    return None
                
                # Insert with specified ID
                cursor.execute(
                    "INSERT INTO taps (idTap, idBeer) VALUES (?, ?)",
                    (tap_id, beer_id)
                )
            else:
                # Let SQLite assign the ID
                cursor.execute(
                    "INSERT INTO taps (idBeer) VALUES (?)",
                    (beer_id,)
                )
            
            tap_id = cursor.lastrowid
            conn.commit()
            
            logger.info(f"Added tap {tap_id}" + (f" with beer {beer_id}" if beer_id else ""))
            return tap_id
    
    def update_tap(self, tap_id, beer_id):
        """Update a tap's beer assignment
        
        Args:
            tap_id: ID of the tap to update
            beer_id: ID of beer to assign (or None to make tap empty)
            
        Returns:
            success: True if updated, False if tap not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if tap exists
            cursor.execute("SELECT idBeer FROM taps WHERE idTap = ?", (tap_id,))
            result = cursor.fetchone()
            
            if not result:
                logger.warning(f"Tap with ID {tap_id} not found for update")
                return False
            
            current_beer = result[0]
            
            # Only update if the beer assignment is actually changing
            if current_beer != beer_id:
                cursor.execute(
                    "UPDATE taps SET idBeer = ? WHERE idTap = ?",
                    (beer_id, tap_id)
                )
                conn.commit()
                
                logger.info(f"Updated tap {tap_id} with beer {beer_id if beer_id else 'None'}")
            else:
                logger.info(f"Tap {tap_id} already has beer {beer_id if beer_id else 'None'}")
            
            return True
    
    def delete_tap(self, tap_id):
        """Delete a tap from the database
        
        Args:
            tap_id: ID of the tap to delete
            
        Returns:
            success: True if deleted, False if not found
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if tap exists
            cursor.execute("SELECT idTap FROM taps WHERE idTap = ?", (tap_id,))
            if not cursor.fetchone():
                logger.warning(f"Tap with ID {tap_id} not found for deletion")
                return False
            
            # Delete the tap
            cursor.execute("DELETE FROM taps WHERE idTap = ?", (tap_id,))
            conn.commit()
            
            logger.info(f"Deleted tap {tap_id}")
            return True
    
    def get_tap(self, tap_id):
        """Get a tap by ID
        
        Args:
            tap_id: ID of the tap to retrieve
            
        Returns:
            tap: Dictionary with tap information or None if not found
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT t.*, b.Name as BeerName FROM taps t "
                "LEFT JOIN beers b ON t.idBeer = b.idBeer "
                "WHERE t.idTap = ?", 
                (tap_id,)
            )
            
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            else:
                return None
    
    def get_all_taps(self):
        """Get all taps with their beer information
        
        Returns:
            taps: List of dictionaries with tap information
        """
        with self.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT t.*, b.Name as BeerName FROM taps t "
                "LEFT JOIN beers b ON t.idBeer = b.idBeer "
                "ORDER BY t.idTap"
            )
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_tap_with_beer(self, beer_id):
        """Find taps that have a specific beer
        
        Args:
            beer_id: ID of the beer to look for
            
        Returns:
            taps: List of tap IDs with this beer
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT idTap FROM taps WHERE idBeer = ? ORDER BY idTap",
                (beer_id,)
            )
            
            return [row[0] for row in cursor.fetchall()] 