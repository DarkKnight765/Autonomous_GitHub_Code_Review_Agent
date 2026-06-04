"""
User management module — intentionally buggy for demo purposes.
"""
import sqlite3
import hashlib
import pickle
import os


# BAD: hardcoded credentials
DB_PASSWORD = "admin123"
SECRET_TOKEN = "tok_live_abc123xyz789secret"


def get_user(username):
    # BAD: SQL injection vulnerability
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
    # BAD: connection never closed


def create_user(username, password):
    # BAD: MD5 for password hashing
    hashed = hashlib.md5(password.encode()).hexdigest()
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO users VALUES ('{username}', '{hashed}')")
    # BAD: no commit, no close


def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    # BAD: N+1 — querying inside loop
    result = []
    for user in users:
        cursor.execute(f"SELECT * FROM sessions WHERE user_id = '{user[0]}'")
        sessions = cursor.fetchall()
        result.append({"user": user, "sessions": sessions})
    return result


def load_user_data(data_bytes):
    # BAD: arbitrary code execution via pickle
    return pickle.loads(data_bytes)


def reset_password(username, new_password):
    # BAD: no authentication check before reset
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET password='{new_password}' WHERE username='{username}'")
    conn.commit()


def calculate_score(values):
    # BAD: ZeroDivisionError if empty list
    return sum(values) / len(values)


def export_users(filename):
    users = get_all_users()
    # BAD: no check if file exists — silently overwrites
    with open(filename, "w") as f:
        for user in users:
            f.write(str(user) + "\n")
