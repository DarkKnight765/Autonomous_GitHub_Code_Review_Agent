"""
Payment processing module — intentionally buggy for demo.
"""
import sqlite3
import subprocess
import hashlib
import requests

# BAD: hardcoded API keys
STRIPE_SECRET_KEY = "sk_live_abc123xyz_hardcoded_secret"
ADMIN_PASSWORD = "password123"


def charge_card(amount, card_number, cvv):
    # BAD: logging sensitive card data
    print(f"Charging card: {card_number}, CVV: {cvv}, Amount: {amount}")

    # BAD: SQL injection
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO charges VALUES ('{card_number}', {amount}, 'pending')"
    )
    # BAD: no commit, no close


def run_report(report_name):
    # BAD: command injection via subprocess
    result = subprocess.run(f"python reports/{report_name}.py", shell=True)
    return result


def get_payment(payment_id):
    # BAD: SQL injection
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM charges WHERE id = " + payment_id)
    return cursor.fetchone()
    # BAD: connection never closed


def hash_card(card_number):
    # BAD: MD5 for sensitive data
    return hashlib.md5(card_number.encode()).hexdigest()


def process_refund(user_id, amount):
    # BAD: no authorization check, anyone can refund anything
    conn = sqlite3.connect("payments.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE charges SET status='refunded' WHERE user_id='{user_id}'")
    conn.commit()
    # BAD: refunds ALL charges for user regardless of amount


def fetch_exchange_rate(currency):
    # BAD: no timeout, no error handling
    r = requests.get(f"https://api.rates.com/convert?currency={currency}")
    return r.json()["rate"]


def calculate_tax(price, tax_rate=None):
    # BAD: ZeroDivisionError if tax_rate is 0
    return price / tax_rate
