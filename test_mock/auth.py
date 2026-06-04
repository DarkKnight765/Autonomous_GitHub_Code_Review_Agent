"""
Mock user authentication module.
Intentionally contains bugs, security issues, and performance problems
to test the AGCRA review agent.
"""

import sqlite3
import hashlib


def authenticate_user(username, password):
    # BUG: SQL injection vulnerability
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
    cursor.execute(query)
    result = cursor.fetchone()
    # BUG: connection never closed
    return result


def hash_password(password):
    # SECURITY: MD5 is cryptographically broken
    return hashlib.md5(password.encode()).hexdigest()


def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = []
    # PERFORMANCE: N+1 query pattern
    for row in cursor.fetchall():
        user_id = row[0]
        cursor2 = conn.cursor()
        cursor2.execute("SELECT * FROM permissions WHERE user_id = " + str(user_id))
        perms = cursor2.fetchall()
        users.append({"user": row, "permissions": perms})
    return users


def reset_password(user_id, new_password):
    # BUG: no validation on new_password — empty string allowed
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    hashed = hash_password(new_password)
    cursor.execute(f"UPDATE users SET password = '{hashed}' WHERE id = {user_id}")
    # BUG: missing conn.commit() — changes never saved
    conn.close()


def login_attempts(username):
    # STYLE: magic number with no explanation
    attempts = []
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM login_log WHERE username = ?", (username,))
    for row in cursor.fetchall():
        attempts.append(row)
    if len(attempts) > 5:
        return False
    return True


SECRET_KEY = "hardcoded-secret-key-do-not-use"  # SECURITY: hardcoded secret
API_TOKEN = "ghp_abc123faketoken"               # SECURITY: leaked token
