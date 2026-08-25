"""
Vercel Serverless Function — FastAPI Backend
=============================================
Wraps the FastAPI app for Vercel's Python serverless runtime.
Route: /api/* (configured in vercel.json rewrites)
"""

import sys
import os

# Ensure the project root is on the Python path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Also set PYTHONPATH for any subprocess calls
os.environ.setdefault("PYTHONPATH", _project_root)

from backend.app.api.main import app

# Vercel serves ASGI apps natively — FastAPI is ASGI
