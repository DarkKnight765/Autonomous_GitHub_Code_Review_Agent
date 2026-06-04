"""
E-commerce order management module.

Handles order creation, payment, and fulfillment.
"""
import sqlite3
import subprocess
import hashlib
import os
import pickle


# BAD: hardcoded credentials in source code
DATABASE_URL = "postgresql://admin:SuperSecret123@prod-db.company.com:5432/orders"
PAYMENT_API_KEY = "pk_live_51NxKkLRs9mZqyIxO3AbCdEfGh"
ADMIN_SECRET = "admin_secret_do_not_share"


def get_order(order_id):
    """Fetch order by ID."""
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    # BAD: SQL injection — user input directly in query
    cursor.execute("SELECT * FROM orders WHERE id = '" + order_id + "'")
    result = cursor.fetchone()
    # BAD: connection never closed — resource leak
    return result


def create_order(user_id, items, discount_code):
    """Create a new order."""
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    # BAD: SQL injection via f-string
    cursor.execute(
        f"INSERT INTO orders (user_id, items) VALUES ('{user_id}', '{items}')"
    )
    # BAD: no commit — data never saved
    # BAD: discount_code not validated — could be arbitrary input
    if discount_code:
        cursor.execute(f"SELECT * FROM discounts WHERE code = '{discount_code}'")


def delete_order(order_id):
    """Delete an order."""
    # BAD: shell injection — order_id passed directly to shell command
    subprocess.run(f"rm -rf /orders/{order_id}", shell=True)


def hash_card_number(card_number):
    """Hash a credit card number for storage."""
    # BAD: MD5 is cryptographically broken, never use for sensitive data
    return hashlib.md5(card_number.encode()).hexdigest()


def get_all_orders(user_id):
    """Get all orders for a user with item details."""
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM orders WHERE user_id = '{user_id}'")
    orders = cursor.fetchall()
    result = []
    # BAD: N+1 query — DB call inside a loop
    for order in orders:
        cursor.execute(f"SELECT * FROM items WHERE order_id = '{order[0]}'")
        items = cursor.fetchall()
        result.append({"order": order, "items": items})
    return result


def restore_session(session_data: bytes):
    """Restore a user session from binary data."""
    # BAD: pickle.loads on untrusted data = arbitrary code execution
    return pickle.loads(session_data)


def apply_discount(price, discount_percent):
    """Apply a discount to a price."""
    # BAD: ZeroDivisionError when discount_percent = 100
    return price - (price * discount_percent / (100 - discount_percent))


def export_orders(filename):
    """Export all orders to a file."""
    orders = get_all_orders("admin")
    # BAD: no path validation — directory traversal attack possible
    with open(filename, "w") as f:
        for order in orders:
            # BAD: sensitive data written to file without sanitization
            f.write(str(order) + "\n")
