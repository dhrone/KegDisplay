#!/usr/bin/env python3
import argparse
import bcrypt
import os
import sys

PASSWD_FILE = 'passwd'

def load_users():
    users = {}
    try:
        with open(PASSWD_FILE, 'r') as f:
            for line in f:
                username, password_hash = line.strip().split(':')
                users[username] = password_hash
    except FileNotFoundError:
        pass
    return users

def save_users(users):
    with open(PASSWD_FILE, 'w') as f:
        for username, password_hash in users.items():
            f.write(f"{username}:{password_hash}\n")

def add_user(username, password):
    users = load_users()
    if username in users:
        print(f"Error: User '{username}' already exists")
        return False
    
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    users[username] = password_hash
    save_users(users)
    print(f"User '{username}' added successfully")
    return True

def delete_user(username):
    users = load_users()
    if username not in users:
        print(f"Error: User '{username}' does not exist")
        return False
    
    del users[username]
    save_users(users)
    print(f"User '{username}' deleted successfully")
    return True

def reset_password(username, new_password):
    users = load_users()
    if username not in users:
        print(f"Error: User '{username}' does not exist")
        return False
    
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(new_password.encode('utf-8'), salt).decode('utf-8')
    users[username] = password_hash
    save_users(users)
    print(f"Password reset successfully for user '{username}'")
    return True

def list_users():
    users = load_users()
    if not users:
        print("No users found")
        return
    
    print("\nRegistered users:")
    for username in sorted(users.keys()):
        print(f"- {username}")

def main():
    parser = argparse.ArgumentParser(description='User management utility for KegDisplay')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add user
    add_parser = subparsers.add_parser('add', help='Add a new user')
    add_parser.add_argument('username', help='Username')
    add_parser.add_argument('password', help='Password')

    # Delete user
    delete_parser = subparsers.add_parser('delete', help='Delete a user')
    delete_parser.add_argument('username', help='Username')

    # Reset password
    reset_parser = subparsers.add_parser('reset', help='Reset user password')
    reset_parser.add_argument('username', help='Username')
    reset_parser.add_argument('new_password', help='New password')

    # List users
    subparsers.add_parser('list', help='List all users')

    args = parser.parse_args()

    if args.command == 'add':
        add_user(args.username, args.password)
    elif args.command == 'delete':
        delete_user(args.username)
    elif args.command == 'reset':
        reset_password(args.username, args.new_password)
    elif args.command == 'list':
        list_users()
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main() 