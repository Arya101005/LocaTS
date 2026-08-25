"""
Vercel Serverless Function — FastAPI Backend
=============================================
Entry point for Vercel's Python serverless runtime.
Vercel auto-discovers this file and maps /api/* routes to it.

The startup event loads Chamoli dataset into memory.
On Vercel's serverless runtime, cold starts re-load each invocation,
so persistence via Supabase is used to avoid full re-computation.
"""

from backend.app.api.main import app

# Vercel expects a WSGI/ASGI app named `app`
# FastAPI is ASGI, which Vercel supports natively
