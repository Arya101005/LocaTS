#!/usr/bin/env python3
"""
Setup Supabase for LocaTS.

Creates:
  1. A public storage bucket for GeoJSON/JSON data files
  2. PostGIS tables for habitations, shelters, roads, hazard zones
  3. Uploads initial district data if available

Run:
    # With .env file loaded:
    python scripts/setup_supabase.py

    # Or with env vars:
    SUPABASE_URL=https://xxx.supabase.co SUPABASE_KEY=xxx python scripts/setup_supabase.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Load .env if present
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
BUCKET = os.environ.get("SUPABASE_BUCKET", "locats-data")


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Set SUPABASE_URL and SUPABASE_KEY in .env or environment")
        print("  1. Go to https://supabase.com → Create free project")
        print("  2. Copy URL and anon key from Settings → API")
        print("  3. Create .env with those values")
        sys.exit(1)

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"Connected to Supabase: {SUPABASE_URL}")

    # 1. Create storage bucket
    print("\n[1/3] Creating storage bucket...")
    try:
        buckets = client.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        if BUCKET not in bucket_names:
            client.storage.create_bucket(
                BUCKET,
                options={"public": True, "file_size_limit": 50 * 1024 * 1024},
            )
            print(f"  Created bucket: {BUCKET}")
        else:
            print(f"  Bucket exists: {BUCKET}")
    except Exception as e:
        print(f"  Bucket setup: {e}")

    # 2. Create PostGIS tables via SQL (run in Supabase SQL Editor)
    print("\n[2/3] SQL schema (copy-paste into Supabase SQL Editor):")
    SQL_SCHEMA = """
-- LocaTS tables (run this in Supabase SQL Editor → SQL)

-- Hazard zones
CREATE TABLE IF NOT EXISTS hazard_zones (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    hazard_type TEXT NOT NULL,
    severity REAL NOT NULL CHECK (severity >= 0 AND severity <= 1),
    zone_type TEXT DEFAULT 'red',
    center_lat REAL NOT NULL,
    center_lon REAL NOT NULL,
    radius_km REAL DEFAULT 5,
    source TEXT DEFAULT '',
    geom GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hazard_district ON hazard_zones(district);

-- Habitations
CREATE TABLE IF NOT EXISTS habitations (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    population_estimate INTEGER NOT NULL,
    population_confidence REAL DEFAULT 0.8,
    elevation_m REAL,
    block TEXT DEFAULT '',
    social_vulnerability JSONB,
    geom GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hab_district ON habitations(district);

-- Shelters
CREATE TABLE IF NOT EXISTS shelters (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    name TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    bed_capacity INTEGER NOT NULL,
    beds_occupied INTEGER DEFAULT 0,
    healthcare_beds_per_hour REAL DEFAULT 0,
    water_capacity_lpd REAL DEFAULT 0,
    is_accessible BOOLEAN DEFAULT TRUE,
    shelter_type TEXT DEFAULT 'school',
    is_active BOOLEAN DEFAULT TRUE,
    geom GEOMETRY(Point, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_shelter_district ON shelters(district);

-- Road segments
CREATE TABLE IF NOT EXISTS road_segments (
    id TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    from_node TEXT NOT NULL,
    to_node TEXT NOT NULL,
    distance_km REAL NOT NULL,
    travel_time_minutes REAL NOT NULL,
    highway_type TEXT DEFAULT 'tertiary',
    capacity_vehicles_per_hour REAL DEFAULT 50,
    people_throughput_per_hour REAL DEFAULT 400,
    status TEXT DEFAULT 'open',
    damage_factor REAL DEFAULT 1.0,
    geom GEOMETRY(LineString, 4326),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_road_district ON road_segments(district);

-- Relocation orders (audit trail)
CREATE TABLE IF NOT EXISTS relocation_orders (
    order_id TEXT PRIMARY KEY,
    district TEXT NOT NULL,
    result_json JSONB NOT NULL,
    audit_hash TEXT NOT NULL,
    hash_chain_previous TEXT DEFAULT '',
    issued_at TIMESTAMPTZ DEFAULT NOW(),
    issued_by TEXT DEFAULT 'system'
);
"""
    print(SQL_SCHEMA)

    # 3. Upload sample Chamoli data if it exists
    print("\n[3/3] Uploading existing data...")
    sys.path.insert(0, str(Path(__file__).parent.parent))
    try:
        from backend.app.data.cloud_storage import CloudStorage
        cs = CloudStorage()

        # Try to upload the GeoJSON files from frontend/public/data
        data_dir = Path(__file__).parent.parent / "frontend" / "public" / "data"
        if data_dir.exists():
            for geojson_file in data_dir.glob("*.geojson"):
                name = geojson_file.stem
                try:
                    data = json.loads(geojson_file.read_text(encoding="utf-8"))
                    cs.upload_json(f"Chamoli/{name}.json", data)
                    print(f"  Uploaded {name}.json ({len(geojson_file.read_text())} bytes)")
                except Exception as e:
                    print(f"  Skip {name}: {e}")
        else:
            print("  No data files found in frontend/public/data/")
            print("  Run: python scripts/download_real_data.py first")

    except Exception as e:
        print(f"  Upload skipped: {e}")

    print("\nDone! Update .env with your Supabase credentials.")
    print("Backend will read data from Supabase instead of local disk.")


if __name__ == "__main__":
    main()
