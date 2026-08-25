"""
Supabase Cloud Storage backend for LocaTS.

Replaces local disk caching. All downloaded hazard, road, population,
and shelter data is stored in Supabase Storage and streamed back on
subsequent runs. No local disk consumed.

Environment variables (set in .env):
    SUPABASE_URL       — your Supabase project URL
    SUPABASE_KEY       — your Supabase anon/service key
    SUPABASE_BUCKET    — storage bucket name (default: "locats-data")

Usage:
    from backend.app.data.cloud_storage import CloudStorage
    cs = CloudStorage()
    cs.upload_json("chamoli/hazard_zones.json", data)
    data = cs.download_json("chamoli/hazard_zones.json")
"""

from __future__ import annotations

import io
import json
import logging
import os
from typing import Optional

from supabase import create_client, Client

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "locats-data"


class CloudStorage:
    """
    Thin wrapper around Supabase Storage for zero-disk geospatial data.

    All data lives in a single bucket organized by district:
        {bucket}/{district}/{dataset}.json

    Falls back gracefully if Supabase is not configured.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        bucket: Optional[str] = None,
    ):
        self.url = url or os.environ.get("SUPABASE_URL", "")
        self.key = key or os.environ.get("SUPABASE_KEY", "")
        self.bucket = bucket or os.environ.get("SUPABASE_BUCKET", DEFAULT_BUCKET)
        self._client: Optional[Client] = None
        self._connected = False

    @property
    def client(self) -> Optional[Client]:
        if self._client is None and self.url and self.key:
            try:
                self._client = create_client(self.url, self.key)
                self._connected = True
            except Exception as e:
                logger.warning(f"Supabase connection failed: {e}")
                self._connected = False
        return self._client

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def upload_json(self, path: str, data: dict | list, overwrite: bool = True) -> bool:
        """Upload JSON data to Supabase Storage."""
        if not self.is_configured:
            logger.debug(f"Supabase not configured, skipping upload: {path}")
            return False

        try:
            content = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            buf = io.BytesIO(content)

            # Ensure bucket exists
            self._ensure_bucket()

            # Upload (upsert to overwrite)
            self.client.storage.from_(self.bucket).upload(
                path=path,
                file=buf,
                file_options={"content-type": "application/json", "upsert": str(overwrite).lower()},
            )
            logger.info(f"  Uploaded {path} ({len(content)} bytes) to Supabase")
            return True

        except Exception as e:
            logger.warning(f"  Upload failed for {path}: {e}")
            return False

    def upload_geojson(self, path: str, geojson: dict, overwrite: bool = True) -> bool:
        """Upload GeoJSON FeatureCollection to Supabase Storage."""
        return self.upload_json(path, geojson, overwrite)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------
    def download_json(self, path: str) -> Optional[dict | list]:
        """Download and parse JSON from Supabase Storage."""
        if not self.is_configured:
            return None

        try:
            res = self.client.storage.from_(self.bucket).download(path)
            return json.loads(res)
        except Exception as e:
            logger.debug(f"  Download failed for {path}: {e}")
            return None

    def exists(self, path: str) -> bool:
        """Check if a file exists in Supabase Storage."""
        if not self.is_configured:
            return False
        try:
            self.client.storage.from_(self.bucket).list(path.rsplit("/", 1)[0])
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # District-level convenience methods
    # ------------------------------------------------------------------
    def upload_district_data(self, district: str, dataset: str, data: dict | list) -> bool:
        """Upload data for a specific district and dataset."""
        path = f"{district}/{dataset}.json"
        return self.upload_json(path, data)

    def download_district_data(self, district: str, dataset: str) -> Optional[dict | list]:
        """Download data for a specific district and dataset."""
        path = f"{district}/{dataset}.json"
        return self.download_json(path)

    def upload_full_graph(self, district: str, graph_data: dict) -> bool:
        """Upload a serialized CapacityGraph for a district."""
        return self.upload_district_data(district, "capacity_graph", graph_data)

    def download_full_graph(self, district: str) -> Optional[dict]:
        """Download a serialized CapacityGraph for a district."""
        return self.download_district_data(district, "capacity_graph")

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _ensure_bucket(self):
        """Create the storage bucket if it doesn't exist."""
        try:
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            if self.bucket not in bucket_names:
                self.client.storage.create_bucket(
                    self.bucket,
                    options={"public": True, "file_size_limit": 50 * 1024 * 1024},
                )
                logger.info(f"  Created Supabase bucket: {self.bucket}")
        except Exception as e:
            logger.debug(f"  Bucket check/create skipped: {e}")

    # ------------------------------------------------------------------
    # Memory fallback (when Supabase is not configured)
    # ------------------------------------------------------------------
    _memory_store: dict[str, bytes] = {}

    def upload_json_memory(self, path: str, data: dict | list) -> bool:
        """Store JSON in memory (fallback when no Supabase)."""
        content = json.dumps(data, ensure_ascii=False).encode("utf-8")
        CloudStorage._memory_store[path] = content
        logger.info(f"  Stored {path} ({len(content)} bytes) in memory")
        return True

    def download_json_memory(self, path: str) -> Optional[dict | list]:
        """Load JSON from memory fallback."""
        content = CloudStorage._memory_store.get(path)
        if content:
            return json.loads(content)
        return None
