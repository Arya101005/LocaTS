#!/usr/bin/env python3
"""Quick start: launches all LocaTS services"""
import sys, os, subprocess, time
sys.path.insert(0, os.path.dirname(__file__))
os.environ["PYTHONPATH"] = "."

PORTS = {"backend": 8000, "frontend": 3000, "pwa": 3001}
DIR = os.path.dirname(os.path.abspath(__file__))

print("=" * 60)
print("  LocaTS - Starting all services...")
print("=" * 60)

# Start backend
print("  [1/3] Starting backend on port 8000...")
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.app.api.main:app",
     "--host", "127.0.0.1", "--port", "8000", "--log-level", "info"],
    cwd=DIR,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)
print(f"       PID: {backend.pid}")

time.sleep(2)

# Start frontend
print("  [2/3] Starting frontend on port 3000...")
frontend_dir = os.path.join(DIR, "frontend")
frontend = subprocess.Popen(
    ["npx", "vite", "--port", "3000"],
    cwd=frontend_dir,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
)
print(f"       PID: {frontend.pid}")

print("=" * 60)
print("  ALL SERVICES RUNNING")
print("")
print("  Backend API:    http://127.0.0.1:8000")
print("  Swagger Docs:   http://127.0.0.1:8000/docs")
print("  Dashboard:      http://localhost:3000")
print("")
print("  Press Ctrl+C to stop all services")
print("=" * 60)

try:
    backend.wait()
except KeyboardInterrupt:
    print("\nShutting down...")
    backend.terminate()
    frontend.terminate()
