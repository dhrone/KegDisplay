from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import sqlite3
import os
import bcrypt
from functools import wraps

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'beer.db')
PASSWD_PATH = os.path.join(BASE_DIR, 'passwd')
print (PASSWD_PATH)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Generate a random secret key
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, username):
        self.id = username

def load_users():
    users = {}
    print ("Loading Users")
    try:
        with open(PASSWD_PATH, 'r') as f:
            for line in f:
                username, password_hash = line.strip().split(':')
                users[username] = password_hash
                print(username)
    except FileNotFoundError:
        pass
    return users

@login_manager.user_loader
def load_user(username):
    users = load_users()
    if username in users:
        return User(username)
    return None

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
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        
        if username in users and bcrypt.checkpw(password.encode('utf-8'), 
                                              users[username].encode('utf-8')):
            user = User(username)
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add_record/<table_name>', methods=['POST'])
@login_required
def add_record(table_name):
    schema = get_table_schema(table_name)
    columns = [col[1] for col in schema]
    values = [request.form.get(col) for col in columns]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    placeholders = ','.join(['?' for _ in columns])
    cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", values)
    conn.commit()
    conn.close()
    
    return redirect(url_for('index', table=table_name))

@app.route('/delete_record/<table_name>/<int:record_id>', methods=['POST'])
@login_required
def delete_record(table_name, record_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table_name} WHERE rowid=?", (record_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index', table=table_name))

@app.route('/update_record/<table_name>/<int:record_id>', methods=['POST'])
@login_required
def update_record(table_name, record_id):
    schema = get_table_schema(table_name)
    columns = [col[1] for col in schema]
    values = [request.form.get(col) for col in columns]
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    set_clause = ','.join([f"{col}=?" for col in columns])
    values.append(record_id)
    cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE rowid=?", values)
    conn.commit()
    conn.close()
    
    return redirect(url_for('index', table=table_name))

if __name__ == '__main__':
    # Enable debug logging
    app.logger.setLevel('DEBUG')
    app.run(host='0.0.0.0', port=5001, debug=True) 
