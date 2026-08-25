#!/usr/bin/env python3
"""Quick start: launches LocaTS backend on http://127.0.0.1:8000"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("PYTHONPATH", ".")

import uvicorn
from backend.app.api.main import app

print("=" * 60)
print("  LocaTS is starting...")
print("  Backend:  http://127.0.0.1:8000")
print("  API Docs: http://127.0.0.1:8000/docs")
print("  Dashboard: cd frontend && npm run dev (http://localhost:3000)")
print("=" * 60)

uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
