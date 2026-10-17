"""ClassSense One-Click Demo Runner.

1. Runs Alembic database migrations.
2. Pre-populates classsense.db with rich Calculus & Perceptron demo analyses.
3. Automatically launches default browser to http://127.0.0.1:8000.
4. Starts the FastAPI Uvicorn application server.
"""

import asyncio
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn

# Ensure backend root is in sys.path and is current working directory
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
os.chdir(backend_dir)

from seed_demo_data import seed_demo_lectures


def run_migrations():
    print("=" * 70)
    print(" [1/3] Checking Database Schema & Alembic Migrations...")
    print("=" * 70)
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config(str(backend_dir / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
        print("  -> Alembic schema verified at HEAD.")
    except Exception as e:
        print(f"  -> Migration notice: {e}")


def seed_database():
    print("=" * 70)
    print(" [2/3] Seeding Pre-Computed Demo Lectures (Calculus & Perceptron ANN)...")
    print("=" * 70)
    asyncio.run(seed_demo_lectures())
    print("  -> Pre-computed demo lectures verified in classsense.db.")


def open_browser():
    time.sleep(1.5)
    url = "http://127.0.0.1:8000/"
    print("=" * 70)
    print(f" [3/3] Launching Professor Demo Dashboard in Browser: {url}")
    print("=" * 70)
    webbrowser.open(url)


def main():
    print("\n" + "=" * 70)
    print("  CLASSSENSE: INTELLIGENT PEDAGOGY & COGNITIVE FRICTION PLATFORM")
    print("  Prepared for Professor Live Demonstration & Viva Evaluation")
    print("=" * 70 + "\n")

    run_migrations()
    seed_database()

    # Launch browser after server starts
    threading.Thread(target=open_browser, daemon=True).start()

    print("\nStarting Uvicorn HTTP Server on http://127.0.0.1:8000 (Press Ctrl+C to stop)...")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
