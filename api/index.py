"""
Vercel Serverless Function — FastAPI Backend
=============================================
This file wraps the FastAPI app for Vercel's serverless Python runtime.
Vercel automatically detects this file and serves it as a serverless function.

Route: /api/* (configured in vercel.json rewrites)
"""

import sys
import os

# Add the project root to Python path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.api.main import app

# Vercel expects a WSGI/ASGI app named `app`
# FastAPI is ASGI, which Vercel supports natively
