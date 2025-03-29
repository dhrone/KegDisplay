from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
import bcrypt
from functools import wraps
from datetime import datetime, UTC
import logging
import argparse
import sys

# Import the SyncedDatabase
from KegDisplay.db import SyncedDatabase

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'beer.db')
PASSWD_PATH = os.path.join(BASE_DIR, 'passwd')
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')
print(f"Password file path: {PASSWD_PATH}")
print(f"Template directory: {TEMPLATE_DIR}")

# Parse all command line arguments at the beginning
def parse_args():
    parser = argparse.ArgumentParser(description='KegDisplay Web Interface')
    parser.add_argument('--host', default='0.0.0.0', help='Host to listen on')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    parser.add_argument('--broadcast-port', type=int, default=5002, 
                       help='UDP port for synchronization broadcasts (default: 5002)')
    parser.add_argument('--sync-port', type=int, default=5003,
                       help='TCP port for synchronization connections (default: 5003)')
    parser.add_argument('--no-sync', action='store_true',
                       help='Disable database synchronization')
    parser.add_argument('--debug', action='store_true',
                       help='Run Flask in debug mode')
    return parser.parse_args()

# Parse arguments once at module level
args = parse_args()
print(f"Web interface configuration:")
print(f"  Host: {args.host}")
print(f"  Web port: {args.port}")
print(f"  Broadcast port: {args.broadcast_port}")
print(f"  Sync port: {args.sync_port}")
print(f"  Synchronization: {'Disabled' if args.no_sync else 'Enabled'}")
print(f"  Debug mode: {'Enabled' if args.debug else 'Disabled'}")

# Initialize the SyncedDatabase unless disabled
synced_db = None
if not args.no_sync:
    try:
        print(f"Initializing SyncedDatabase with broadcast_port={args.broadcast_port}, sync_port={args.sync_port}")
        synced_db = SyncedDatabase(
            db_path=DB_PATH,
            broadcast_port=args.broadcast_port,
            sync_port=args.sync_port,
            test_mode=False
        )
        logger = logging.getLogger("KegDisplay")
        logger.info("Initialized SyncedDatabase for web interface")
    except OSError as e:
        print(f"Error initializing SyncedDatabase: {e}")
        print("If another instance is already running, use --broadcast-port and --sync-port to set different ports")
        print("or use --no-sync to disable synchronization for this instance.")
        sys.exit(1)

app = Flask(__name__, 
           template_folder=TEMPLATE_DIR)  # Specify the template folder
app.secret_key = os.urandom(24)  # Generate a random secret key
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, username, password_hash=None):
        self.id = username
        self.username = username
        self.password_hash = password_hash

    @staticmethod
    def get(user_id):
        users = load_users()
        if user_id in users:
            return User(user_id, users[user_id])
        return None

def load_users():
    users = {}
    print("Loading Users")
    try:
        with open(PASSWD_PATH, 'r') as f:
            for line in f:
                username, password_hash = line.strip().split(':')
                users[username] = password_hash
                print(f"Found user: {username}")
    except FileNotFoundError:
        print(f"Password file not found at: {PASSWD_PATH}")
    return users

@login_manager.user_loader
def load_user(user_id):
    print(f"Loading user with ID: {user_id}")
    return User.get(user_id)

def get_db_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    conn.close()
    return [table[0] for table in tables]

def get_table_schema(table_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    schema = cursor.fetchall()
    conn.close()
    return schema

def get_table_data(table_name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name};")
    data = cursor.fetchall()
    schema = get_table_schema(table_name)
    columns = [col[1] for col in schema]
    conn.close()
    return columns, data

@app.route('/')
@login_required
def index():
    # Redirect to the taps page
    return redirect(url_for('taps'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Entering login route")
    print(f"Template folder: {app.template_folder}")
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        print(f"Login attempt for user: {username}")
        
        users = load_users()
        print(f"Users in passwd file: {users}")  # This will show us what users are loaded
        
        if username in users:
            try:
                stored_hash = users[username]
                print(f"Stored hash for {username}: {stored_hash}")
                print(f"Attempting to verify password")
                result = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
                print(f"Password verification result: {result}")
                
                if result:
                    user = User(username, stored_hash)
                    login_user(user)
                    print(f"Login successful for user: {username}")
                    return redirect(url_for('index'))
                else:
                    print(f"Invalid password for user: {username}")
            except Exception as e:
                print(f"Error during password verification: {str(e)}")
                import traceback
                print(traceback.format_exc())
        else:
            print(f"User not found: {username}")
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/taps')
@login_required
def taps():
    return render_template('taps.html', active_page='taps')

@app.route('/beers')
@login_required
def beers():
    return render_template('beers.html', active_page='beers')

# This function is now used by the web interface to log changes
# The SyncedDatabase handles the synchronization
def log_change(conn, table_name, operation, row_id):
    """Log a database change and trigger synchronization"""
    cursor = conn.cursor()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Calculate content hash for the table
    cursor.execute(f"SELECT * FROM {table_name} WHERE rowid = ?", (row_id,))
    row = cursor.fetchone()
    if row:
        content_hash = str(row)
    else:
        content_hash = "0"
    
    cursor.execute('''
        INSERT INTO change_log (table_name, operation, row_id, timestamp, content_hash)
        VALUES (?, ?, ?, ?, ?)
    ''', (table_name, operation, row_id, timestamp, content_hash))
    
    # Update version timestamp
    cursor.execute("UPDATE version SET last_modified = ?", (timestamp,))
    conn.commit()
    
    # Notify peers about the change if sync is enabled
    if synced_db:
        logger = logging.getLogger("KegDisplay")
        
        if table_name == 'beers':
            logger.info(f"Database change in 'beers': {operation} on row {row_id}")
            synced_db.notify_update()
        
        elif table_name == 'taps':
            logger.info(f"Database change in 'taps': {operation} on row {row_id}")
            synced_db.notify_update()

# --- API Endpoints ---

@app.route('/api/taps', methods=['GET'])
@login_required
def api_get_taps():
    if synced_db:
        taps = synced_db.get_all_taps()
        
        # Get beer details for each tap
        for tap in taps:
            if tap['idBeer']:
                beer = synced_db.get_beer(tap['idBeer'])
                if beer:
                    tap['BeerName'] = beer['Name']
                    tap['ABV'] = beer['ABV']
                    tap['IBU'] = beer['IBU']
                    tap['Description'] = beer['Description']
        
        return jsonify(taps)
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, b.Name as BeerName, b.ABV, b.IBU, b.Description 
            FROM taps t
            LEFT JOIN beers b ON t.idBeer = b.idBeer
            ORDER BY t.idTap
        ''')
        
        taps = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(taps)

@app.route('/api/taps/<int:tap_id>', methods=['GET'])
@login_required
def api_get_tap(tap_id):
    if synced_db:
        tap = synced_db.get_tap(tap_id)
        
        if tap and tap['idBeer']:
            beer = synced_db.get_beer(tap['idBeer'])
            if beer:
                tap['BeerName'] = beer['Name']
                tap['ABV'] = beer['ABV']
                
        if tap:
            return jsonify(tap)
        else:
            return jsonify({"error": "Tap not found"}), 404
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT t.*, b.Name as BeerName, b.ABV 
            FROM taps t
            LEFT JOIN beers b ON t.idBeer = b.idBeer
            WHERE t.idTap = ?
        ''', (tap_id,))
        
        tap = cursor.fetchone()
        conn.close()
        
        if tap:
            return jsonify(dict(tap))
        else:
            return jsonify({"error": "Tap not found"}), 404

@app.route('/api/taps', methods=['POST'])
@login_required
def api_add_tap():
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    tap_number = data.get('tap_number')
    beer_id = data.get('beer_id')
    
    # Validate data
    if not tap_number:
        return jsonify({"error": "Tap number is required"}), 400
    
    # Check if tap already exists
    if synced_db:
        tap = synced_db.get_tap(tap_number)
        if tap:
            return jsonify({"error": f"Tap #{tap_number} already exists"}), 400
            
        # Add the tap
        tap_id = synced_db.add_tap(tap_number, beer_id)
        
        if tap_id:
            return jsonify({"success": True, "tap_id": tap_id}), 201
        else:
            return jsonify({"error": "Failed to create tap"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if tap already exists
        cursor.execute("SELECT idTap FROM taps WHERE idTap = ?", (tap_number,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": f"Tap #{tap_number} already exists"}), 400
        
        # Add the tap
        cursor.execute(
            "INSERT INTO taps (idTap, idBeer) VALUES (?, ?)",
            (tap_number, beer_id)
        )
        
        # Log the change
        log_change(conn, "taps", "INSERT", tap_number)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "tap_id": tap_number}), 201

@app.route('/api/taps/<int:tap_id>', methods=['PUT'])
@login_required
def api_update_tap(tap_id):
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    beer_id = data.get('beer_id')
    
    if synced_db:
        # Check if tap exists
        tap = synced_db.get_tap(tap_id)
        if not tap:
            return jsonify({"error": f"Tap #{tap_id} not found"}), 404
            
        # Update the beer assignment
        if synced_db.update_tap(tap_id, beer_id):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update tap"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if tap exists
        cursor.execute("SELECT idTap FROM taps WHERE idTap = ?", (tap_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": f"Tap #{tap_id} not found"}), 404
        
        # Update the beer assignment
        cursor.execute(
            "UPDATE taps SET idBeer = ? WHERE idTap = ?",
            (beer_id, tap_id)
        )
        log_change(conn, "taps", "UPDATE", tap_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})

@app.route('/api/taps/<int:tap_id>', methods=['DELETE'])
@login_required
def api_delete_tap(tap_id):
    if synced_db:
        # Check if tap exists
        tap = synced_db.get_tap(tap_id)
        if not tap:
            return jsonify({"error": f"Tap #{tap_id} not found"}), 404
            
        # Delete the tap
        if synced_db.delete_tap(tap_id):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to delete tap"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if tap exists
        cursor.execute("SELECT idTap FROM taps WHERE idTap = ?", (tap_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": f"Tap #{tap_id} not found"}), 404
        
        # Delete the tap
        cursor.execute("DELETE FROM taps WHERE idTap = ?", (tap_id,))
        
        # Log the change
        log_change(conn, "taps", "DELETE", tap_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})

@app.route('/api/beers', methods=['GET'])
@login_required
def api_get_beers():
    if synced_db:
        beers = synced_db.get_all_beers()
        return jsonify(beers)
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM beers ORDER BY Name")
        
        beers = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(beers)

@app.route('/api/beers/<int:beer_id>', methods=['GET'])
@login_required
def api_get_beer(beer_id):
    if synced_db:
        beer = synced_db.get_beer(beer_id)
        
        if beer:
            return jsonify(beer)
        else:
            return jsonify({"error": "Beer not found"}), 404
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM beers WHERE idBeer = ?", (beer_id,))
        
        beer = cursor.fetchone()
        conn.close()
        
        if beer:
            return jsonify(dict(beer))
        else:
            return jsonify({"error": "Beer not found"}), 404

@app.route('/api/beers/<int:beer_id>/taps', methods=['GET'])
@login_required
def api_get_beer_taps(beer_id):
    if synced_db:
        taps = synced_db.get_tap_with_beer(beer_id)
        return jsonify(taps)
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT idTap FROM taps WHERE idBeer = ? ORDER BY idTap", (beer_id,))
        
        taps = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(taps)

@app.route('/api/beers', methods=['POST'])
@login_required
def api_add_beer():
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('Name')
    
    # Validate data
    if not name:
        return jsonify({"error": "Beer name is required"}), 400
    
    if synced_db:
        # Add the beer
        beer_data = {
            'name': name,
            'abv': data.get('ABV'),
            'ibu': data.get('IBU'),
            'color': data.get('Color'),
            'og': data.get('OriginalGravity'),  # Use the correct field from frontend
            'fg': data.get('FinalGravity'),     # Use the correct field from frontend
            'description': data.get('Description'),
            'brewed': data.get('Brewed'),
            'kegged': data.get('Kegged'),
            'tapped': data.get('Tapped'),
            'notes': data.get('Notes')
        }
        
        beer_id = synced_db.add_beer(**beer_data)
        
        if beer_id:
            return jsonify({"success": True, "beer_id": beer_id}), 201
        else:
            return jsonify({"error": "Failed to create beer"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Add the beer
        cursor.execute('''
            INSERT INTO beers (
                Name, ABV, IBU, Color, OriginalGravity, FinalGravity,
                Description, Brewed, Kegged, Tapped, Notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            name,
            data.get('ABV'),
            data.get('IBU'),
            data.get('Color'),
            data.get('OriginalGravity'),
            data.get('FinalGravity'),
            data.get('Description'),
            data.get('Brewed'),
            data.get('Kegged'),
            data.get('Tapped'),
            data.get('Notes')
        ))
        
        beer_id = cursor.lastrowid
        
        # Log the change
        log_change(conn, "beers", "INSERT", beer_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "beer_id": beer_id}), 201

@app.route('/api/beers/<int:beer_id>', methods=['PUT'])
@login_required
def api_update_beer(beer_id):
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    name = data.get('Name')
    
    # Validate data
    if not name:
        return jsonify({"error": "Beer name is required"}), 400
    
    if synced_db:
        # Check if beer exists
        beer = synced_db.get_beer(beer_id)
        if not beer:
            return jsonify({"error": "Beer not found"}), 404
            
        # Update the beer
        beer_data = {
            'beer_id': beer_id,
            'name': name,
            'abv': data.get('ABV'),
            'ibu': data.get('IBU'),
            'color': data.get('Color'),
            'og': data.get('OriginalGravity'),  # Use the correct field from frontend
            'fg': data.get('FinalGravity'),     # Use the correct field from frontend
            'description': data.get('Description'),
            'brewed': data.get('Brewed'),
            'kegged': data.get('Kegged'),
            'tapped': data.get('Tapped'),
            'notes': data.get('Notes')
        }
        
        if synced_db.update_beer(**beer_data):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update beer"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if beer exists
        cursor.execute("SELECT idBeer FROM beers WHERE idBeer = ?", (beer_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Beer not found"}), 404
        
        # Update the beer
        cursor.execute('''
            UPDATE beers SET
                Name = ?, ABV = ?, IBU = ?, Color = ?, OriginalGravity = ?, FinalGravity = ?,
                Description = ?, Brewed = ?, Kegged = ?, Tapped = ?, Notes = ?
            WHERE idBeer = ?
        ''', (
            name,
            data.get('ABV'),
            data.get('IBU'),
            data.get('Color'),
            data.get('OriginalGravity'),
            data.get('FinalGravity'),
            data.get('Description'),
            data.get('Brewed'),
            data.get('Kegged'),
            data.get('Tapped'),
            data.get('Notes'),
            beer_id
        ))
        
        # Log the change
        log_change(conn, "beers", "UPDATE", beer_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})

@app.route('/api/beers/<int:beer_id>', methods=['DELETE'])
@login_required
def api_delete_beer(beer_id):
    if synced_db:
        # Check if beer exists
        beer = synced_db.get_beer(beer_id)
        if not beer:
            return jsonify({"error": "Beer not found"}), 404
            
        # Delete the beer (this will also update any taps using this beer)
        if synced_db.delete_beer(beer_id):
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to delete beer"}), 500
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if beer exists
        cursor.execute("SELECT idBeer FROM beers WHERE idBeer = ?", (beer_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({"error": "Beer not found"}), 404
        
        # Check if any taps are using this beer
        cursor.execute("SELECT idTap FROM taps WHERE idBeer = ?", (beer_id,))
        affected_taps = [row[0] for row in cursor.fetchall()]
        
        if affected_taps:
            # Update those taps to remove the beer
            for tap_id in affected_taps:
                cursor.execute("UPDATE taps SET idBeer = NULL WHERE idTap = ?", (tap_id,))
                log_change(conn, "taps", "UPDATE", tap_id)
        
        # Delete the beer
        cursor.execute("DELETE FROM beers WHERE idBeer = ?", (beer_id,))
        
        # Log the change
        log_change(conn, "beers", "DELETE", beer_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})

@app.route('/api/taps/count', methods=['POST'])
@login_required
def api_set_tap_count():
    data = request.json
    
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    count = data.get('count')
    
    if count is None or not isinstance(count, int) or count < 1:
        return jsonify({"error": "Valid tap count is required (must be positive integer)"}), 400
    
    if synced_db:
        # Get current taps
        existing_taps = synced_db.get_all_taps()
        current_count = len(existing_taps)
        
        # If decreasing, delete excess taps
        if count < current_count:
            # Delete taps from highest number to lowest
            for i in range(current_count, count, -1):
                tap_id = i
                synced_db.delete_tap(tap_id)
        
        # If increasing, add new taps
        elif count > current_count:
            # Add new taps with sequential IDs
            for i in range(current_count + 1, count + 1):
                tap_id = i
                synced_db.add_tap(tap_id, None)
        
        return jsonify({"success": True, "tap_count": count})
    else:
        # Fallback if synced_db is not available
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current tap count
        cursor.execute("SELECT COUNT(*) FROM taps")
        current_count = cursor.fetchone()[0]
        
        # If decreasing, delete excess taps
        if count < current_count:
            # Delete taps from highest number to lowest
            for i in range(current_count, count, -1):
                cursor.execute("DELETE FROM taps WHERE idTap = ?", (i,))
                log_change(conn, "taps", "DELETE", i)
        
        # If increasing, add new taps
        elif count > current_count:
            # Add new taps with sequential IDs
            for i in range(current_count + 1, count + 1):
                cursor.execute("INSERT INTO taps (idTap, idBeer) VALUES (?, NULL)", (i,))
                log_change(conn, "taps", "INSERT", i)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "tap_count": count})

def start():
    """Start the web interface"""
    
    # Make sure all required tables exist
    conn = sqlite3.connect(DB_PATH)
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
    
    # Create change_log table if it doesn't exist
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
    
    # Create version table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS version (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        last_modified TEXT
    )
    ''')
    
    # Make sure there's an entry in the version table
    cursor.execute('SELECT COUNT(*) FROM version')
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO version (id, last_modified) VALUES (1, datetime('now'))
        ''')
    
    conn.commit()
    conn.close()
    
    # Start the Flask application
    app.run(host=args.host, port=args.port, debug=args.debug)
    
    # When shutting down, stop the synced_db gracefully
    if synced_db:
        synced_db.stop()

if __name__ == '__main__':
    start() 
