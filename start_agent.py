"""
AGCRA One-command startup script.

Starts the FastAPI webhook server + ngrok tunnel, then prints the public URL.
The GitHub webhook on your repo must point to this URL/webhook.

Usage:
    python start_agent.py
"""
import io
import os
import sys
import time
import threading
import subprocess

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

NGROK_TOKEN = os.getenv("NGROK_AUTH_TOKEN", "3EgU3h0RXx3eisxsP9tHL2VebYv_3xbV8eq5pzugHfgZHYVYt")
PORT = int(os.getenv("PORT", "8000"))


def start_server():
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "src.webhook.app:app",
        "--host", "0.0.0.0",
        "--port", str(PORT),
    ])


def main():
    print("=" * 60)
    print("  AGCRA - Autonomous GitHub Code Review Agent")
    print("=" * 60)

    # Start FastAPI in background thread
    print(f"\n[1/3] Starting webhook server on port {PORT}...")
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    time.sleep(2)

    # Start ngrok tunnel
    print("[2/3] Starting ngrok tunnel...")
    from pyngrok import ngrok
    ngrok.set_auth_token(NGROK_TOKEN)
    tunnel = ngrok.connect(PORT)
    public_url = tunnel.public_url

    webhook_url = f"{public_url}/webhook"
    print(f"[3/3] Tunnel active!\n")
    print("=" * 60)
    print(f"  Webhook URL: {webhook_url}")
    print(f"  Health:      {public_url}/health")
    print("=" * 60)
    print("\nGitHub webhook should point to:")
    print(f"  {webhook_url}")
    print("\nPress Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        ngrok.kill()


if __name__ == "__main__":
    main()
