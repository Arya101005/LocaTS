"""
Server-Side Rate Limiter
========================
Lightweight in-memory rate limiter keyed on IP address.
Used to protect public endpoints (citizen reports, crowd reports) from abuse.

Usage:
    from backend.app.api.rate_limit import check_rate_limit
    check_rate_limit(request, "citizen_report", max_requests=5, window_seconds=300)

Note: This is NOT safe for multi-instance deployments (each instance has its own
counter). For production, use Redis-backed rate limiting.
"""

from __future__ import annotations
import time
from collections import defaultdict
from typing import Optional

from fastapi import Request, HTTPException


class RateLimiter:
    """Simple sliding-window rate limiter using in-memory dict."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_requests: int, window_seconds: float) -> bool:
        """
        Check if a request is allowed.
        Returns True if allowed, False if rate limited.
        """
        now = time.time()
        cutoff = now - window_seconds

        # Clean old entries
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

        if len(self._windows[key]) >= max_requests:
            return False

        self._windows[key].append(now)
        return True

    def remaining(self, key: str, max_requests: int, window_seconds: float) -> int:
        """Return remaining requests in current window."""
        now = time.time()
        cutoff = now - window_seconds
        current = sum(1 for t in self._windows[key] if t > cutoff)
        return max(0, max_requests - current)


# Singleton
limiter = RateLimiter()


def check_rate_limit(request: Request, endpoint: str, max_requests: int = 5, window_seconds: float = 300) -> None:
    """
    Check rate limit for a request. Raises HTTPException 429 if exceeded.

    Args:
        request: FastAPI request object (for IP extraction)
        endpoint: Logical endpoint name (e.g., "citizen_report")
        max_requests: Max requests allowed in window
        window_seconds: Time window in seconds (default: 5 minutes)
    """
    # Extract client IP (handle proxy headers)
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    key = f"{endpoint}:{client_ip}"

    if not limiter.check(key, max_requests, window_seconds):
        remaining = limiter.remaining(key, max_requests, window_seconds)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {int(window_seconds)} seconds.",
            headers={
                "Retry-After": str(int(window_seconds)),
                "X-RateLimit-Limit": str(max_requests),
                "X-RateLimit-Remaining": str(remaining),
            },
        )
