"""
Cache layer for real data. Saves successful OSM/NDMA loads to disk
so subsequent requests don't hit rate-limited APIs.
"""
import json
import os
import time
from pathlib import Path
from typing import Optional

CACHE_DIR = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "data"
CACHE_FILE = CACHE_DIR / "real_data_cache.json"
CACHE_MAX_AGE = 3600 * 24  # 24 hours


def save_cache(data: dict):
    """Save data to disk cache."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data["_cached_at"] = time.time()
        CACHE_FILE.write_text(json.dumps(data, default=str), encoding="utf-8")
        print(f"  [Cache] Saved to {CACHE_FILE}")
    except Exception as e:
        print(f"  [Cache] Save failed: {e}")


def load_cache() -> Optional[dict]:
    """Load data from disk cache if fresh enough."""
    try:
        if not CACHE_FILE.exists():
            return None
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        cached_at = data.get("_cached_at", 0)
        age = time.time() - cached_at
        if age > CACHE_MAX_AGE:
            print(f"  [Cache] Expired ({age/3600:.1f}h old)")
            return None
        print(f"  [Cache] Loaded from cache ({age/60:.0f}min old)")
        return data
    except Exception as e:
        print(f"  [Cache] Load failed: {e}")
        return None
