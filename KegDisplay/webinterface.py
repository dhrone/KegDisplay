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
    tables = get_db_tables()
    selected_table = request.args.get('table', tables[0] if tables else None)
    
    if selected_table:
        columns, data = get_table_data(selected_table)
        schema = get_table_schema(selected_table)
    else:
        columns, data, schema = [], [], []
    
    return render_template('index.html', 
                         tables=tables, 
                         selected_table=selected_table,
                         columns=columns,
                         schema=schema,
                         data=data)

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

@app.route('/add_record/<table_name>', methods=['POST'])
@login_required
def add_record(table_name):
    try:
        schema = get_table_schema(table_name)
        columns = [col[1] for col in schema]
        values = [request.form.get(col) for col in columns]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in columns])
        cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", values)
        
        # Get the rowid of the inserted record
        row_id = cursor.lastrowid
        
        # Log the change
        log_change(conn, table_name, 'INSERT', row_id)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Record added successfully"})
        
    except sqlite3.IntegrityError as e:
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            return jsonify({
                "error": "This record violates a unique constraint. The value already exists."
            }), 400
        elif "NOT NULL constraint failed" in error_msg:
            column = error_msg.split(".")[-1]
            return jsonify({
                "error": f"The {column} field cannot be empty."
            }), 400
        else:
            return jsonify({
                "error": "This record violates a database constraint."
            }), 400
            
    except Exception as e:
        return jsonify({
            "error": "An unexpected error occurred while adding the record."
        }), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/delete_record/<table_name>/<int:record_id>', methods=['POST'])
@login_required
def delete_record(table_name, record_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Log the change before deleting
    log_change(conn, table_name, 'DELETE', record_id)
    
    cursor.execute(f"DELETE FROM {table_name} WHERE rowid=?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', table=table_name))

@app.route('/update_record/<table_name>/<int:record_id>', methods=['POST'])
@login_required
def update_record(table_name, record_id):
    try:
        schema = get_table_schema(table_name)
        columns = [col[1] for col in schema]
        values = [request.form.get(col) for col in columns]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        set_clause = ','.join([f"{col}=?" for col in columns])
        values.append(record_id)
        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE rowid=?", values)
        
        if cursor.rowcount == 0:
            return jsonify({
                "error": "Record not found or no changes made."
            }), 404
        
        # Log the change
        log_change(conn, table_name, 'UPDATE', record_id)
        
        conn.commit()
        
        return jsonify({
            "success": True,
            "message": "Record updated successfully"
        })
        
    except sqlite3.IntegrityError as e:
        error_msg = str(e)
        if "UNIQUE constraint failed" in error_msg:
            return jsonify({
                "error": "This record violates a unique constraint. The value already exists."
            }), 400
        else:
            return jsonify({
                "error": "This record violates a database constraint."
            }), 400
    
    except Exception as e:
        return jsonify({
            "error": f"An unexpected error occurred while updating the record: {str(e)}"
        }), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

def start():
    """Start the web interface"""
    
    # Make sure all required tables exist
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
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
