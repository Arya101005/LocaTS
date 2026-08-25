"""
NDMA/Bhuvan/NDEM hazard zone ingestion.

Downloads and parses hazard layers from ramSeraph/india_natural_disasters:
- Flood inundation polygons (NDEM/Bhuvan)
- Landslide hazard zones (NDEM, GSI, Bhuvan)
- Seismic zone data

All data is CC0 1.0 licensed, attributed to datameet and government sources.

Usage:
    from backend.app.data.ingestion.ndma_ingester import NDMAIngester
    ingester = NDMAIngester(district="Chamoli")
    hazard_zones = ingester.fetch_hazard_zones()
"""

from __future__ import annotations

import io
import json
import logging
import math
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

import httpx
from shapely.geometry import shape, Point, mapping
from shapely.ops import unary_union

logger = logging.getLogger(__name__)

# GitHub release URLs for ramSeraph/india_natural_disasters
RAMSERAPH_RELEASES = {
    "floods": "https://github.com/ramSeraph/india_natural_disasters/releases/download/floods",
    "landslides": "https://github.com/ramSeraph/india_natural_disasters/releases/download/landslides",
    "earthquakes": "https://github.com/ramSeraph/india_natural_disasters/releases/download/earthquakes",
}

# NDEM hazard zone files (GeoJSONL, 7z compressed)
NDEM_FILES = {
    "flood_inundation": "NDEM_Flood_Inundation.geojsonl.7z",
    "landslide_hazard": "NDEM_Landslide_Hazard.geojsonl.7z",
    "landslide_points": "NDEM_Landslides.geojsonl.7z",
    "bhuvan_landslides": "Bhuvan_Landslides.geojsonl.7z",
    "gsi_landslide_inventory": "GSI_Landslide_Inventory.geojsonl.7z",
}

# india-geodata flood inventory (GeoJSON, not compressed)
INDIA_GEODATA_URL = (
    "https://github.com/yashveeeeeeer/india-geodata/releases/download/"
    "environment%2Fflood-inventory/INDIA_FLOOD_INVENTORY_V3.geojson"
)

# District bounding boxes
DISTRICT_BBOXES: dict[str, dict] = {
    "Chamoli": {"bbox": (30.05, 79.05, 30.95, 79.95), "state": "Uttarakhand"},
    "Almora": {"bbox": (29.45, 79.15, 29.95, 79.75), "state": "Uttarakhand"},
    "Pithoragarh": {"bbox": (29.70, 80.05, 30.50, 81.00), "state": "Uttarakhand"},
    "Uttarkashi": {"bbox": (30.40, 78.10, 31.15, 79.10), "state": "Uttarakhand"},
    "Rudraprayag": {"bbox": (30.20, 78.75, 30.65, 79.25), "state": "Uttarakhand"},
    "Dehradun": {"bbox": (30.05, 77.80, 30.65, 78.55), "state": "Uttarakhand"},
}


class NDMAIngester:
    """Downloads and parses NDMA/Bhuvan/NDEM hazard zone data."""

    def __init__(self, district: str = "Chamoli", cache_dir: Optional[str] = None):
        self.district = district
        info = DISTRICT_BBOXES.get(district, DISTRICT_BBOXES["Chamoli"])
        self.bbox = info["bbox"]
        self.state = info["state"]
        # Use cloud storage instead of local disk
        from backend.app.data.cloud_storage import CloudStorage
        self.cloud = CloudStorage()
        # Temp dir only for decompression (deleted after upload)
        self.cache_dir = Path(tempfile.gettempdir()) / "locats_hazard_tmp"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=120, follow_redirects=True)

    def close(self):
        self.client.close()

    # ------------------------------------------------------------------
    # Flood inundation zones
    # ------------------------------------------------------------------
    def fetch_flood_inundation(self, bbox_filter: bool = True) -> list[dict]:
        """
        Fetch flood inundation polygons from NDEM.

        Returns list of dicts with keys: id, severity, zone_type, center, radius_km, geom_wkt
        """
        logger.info("Fetching NDEM flood inundation data...")
        features = self._fetch_geojsonl(
            "floods", NDEM_FILES["flood_inundation"]
        )
        if not features:
            logger.warning("No flood inundation data available, trying india-geodata flood inventory")
            features = self._fetch_flood_inventory(bbox_filter)

        if bbox_filter and features:
            features = self._filter_by_bbox(features)

        zones = []
        for i, feat in enumerate(features):
            geom = self._extract_geometry(feat)
            if geom is None:
                continue

            centroid = geom.centroid
            # Compute bounding radius
            bounds = geom.bounds  # (minx, miny, maxx, maxy)
            radius_deg = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 2
            radius_km = radius_deg * 111.0  # rough conversion

            props = feat.get("properties", {})
            severity = self._extract_severity(props, "flood")

            zones.append({
                "id": f"ndma-flood-{i:04d}",
                "hazard_type": "flood",
                "severity": severity,
                "zone_type": "red" if severity >= 0.7 else ("orange" if severity >= 0.4 else "yellow"),
                "center_lat": centroid.y,
                "center_lon": centroid.x,
                "radius_km": round(radius_km, 1),
                "geom_wkt": geom.wkt[:500] if geom else None,
                "source": "NDEM/Bhuvan",
                "properties": {k: str(v)[:100] for k, v in props.items() if v is not None},
            })

        logger.info(f"  Parsed {len(zones)} flood inundation zones")
        return zones

    def _fetch_flood_inventory(self, bbox_filter: bool = True) -> list[dict]:
        """Fetch from India Flood Inventory v3.0 (HydroSense Lab, IIT Delhi).
        
        Stores in Supabase cloud, not local disk.
        """
        # Try cloud cache first
        cloud_data = self.cloud.download_district_data(self.district, "flood_inventory")
        if cloud_data:
            features = cloud_data.get("features", cloud_data) if isinstance(cloud_data, dict) else cloud_data
            if isinstance(features, list):
                logger.info(f"  Loaded {len(features)} flood inventory events from cloud")
                return features

        # Download from source
        logger.info("  Downloading India Flood Inventory v3.0...")
        try:
            resp = self.client.get(INDIA_GEODATA_URL)
            resp.raise_for_status()
            data = resp.json()
            features = data.get("features", [])
            logger.info(f"  Downloaded {len(features)} flood inventory events")

            # Upload to cloud for next time
            self.cloud.upload_district_data(self.district, "flood_inventory", data)

            return features
        except Exception as e:
            logger.error(f"  Flood inventory download failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Landslide hazard zones
    # ------------------------------------------------------------------
    def fetch_landslide_zones(self, bbox_filter: bool = True) -> list[dict]:
        """Fetch landslide hazard zones from NDEM/GSI/Bhuvan."""
        logger.info("Fetching landslide hazard data...")
        zones = []

        # Try NDEM landslide hazard classification
        features = self._fetch_geojsonl("landslides", NDEM_FILES["landslide_hazard"])
        if bbox_filter and features:
            features = self._filter_by_bbox(features)

        for i, feat in enumerate(features):
            geom = self._extract_geometry(feat)
            if geom is None:
                continue

            centroid = geom.centroid
            bounds = geom.bounds
            radius_deg = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 2
            radius_km = radius_deg * 111.0

            props = feat.get("properties", {})
            severity = self._extract_severity(props, "landslide")

            zones.append({
                "id": f"ndma-landslide-{i:04d}",
                "hazard_type": "landslide",
                "severity": severity,
                "zone_type": "red" if severity >= 0.7 else ("orange" if severity >= 0.4 else "yellow"),
                "center_lat": centroid.y,
                "center_lon": centroid.x,
                "radius_km": round(radius_km, 1),
                "geom_wkt": geom.wkt[:500] if geom else None,
                "source": "NDEM",
                "properties": {k: str(v)[:100] for k, v in props.items() if v is not None},
            })

        # Also try Bhuvan landslides if available
        bhuvan_features = self._fetch_geojsonl("landslides", NDEM_FILES["bhuvan_landslides"])
        if bbox_filter and bhuvan_features:
            bhuvan_features = self._filter_by_bbox(bhuvan_features)

        for i, feat in enumerate(bhuvan_features):
            geom = self._extract_geometry(feat)
            if geom is None:
                continue
            centroid = geom.centroid
            bounds = geom.bounds
            radius_deg = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) / 2
            radius_km = radius_deg * 111.0

            props = feat.get("properties", {})
            severity = self._extract_severity(props, "landslide")

            zones.append({
                "id": f"bhuvan-landslide-{i:04d}",
                "hazard_type": "landslide",
                "severity": severity,
                "zone_type": "red" if severity >= 0.7 else ("orange" if severity >= 0.4 else "yellow"),
                "center_lat": centroid.y,
                "center_lon": centroid.x,
                "radius_km": round(radius_km, 1),
                "geom_wkt": geom.wkt[:500] if geom else None,
                "source": "Bhuvan",
                "properties": {k: str(v)[:100] for k, v in props.items() if v is not None},
            })

        logger.info(f"  Parsed {len(zones)} landslide hazard zones")
        return zones

    # ------------------------------------------------------------------
    # Seismic zones (from IS 1893 standard mapping)
    # ------------------------------------------------------------------
    def fetch_seismic_zones(self) -> list[dict]:
        """
        Return seismic zone classification based on IS 1893 standard.

        Uttarakhand falls in Zone IV (High Damage Risk) for most districts.
        This is the authoritative classification from BIS.
        """
        # IS 1893 seismic zonation for Uttarakhand districts
        uttarakhand_seismic = {
            "Chamoli": {"zone": "IV", "severity": 0.75},
            "Uttarkashi": {"zone": "IV", "severity": 0.75},
            "Rudraprayag": {"zone": "IV", "severity": 0.75},
            "Pithoragarh": {"zone": "IV", "severity": 0.75},
            "Almora": {"zone": "IV", "severity": 0.70},
            "Dehradun": {"zone": "IV", "severity": 0.65},
            "Tehri Garhwal": {"zone": "IV", "severity": 0.70},
            "Pauri Garhwal": {"zone": "IV", "severity": 0.70},
            "Haridwar": {"zone": "III", "severity": 0.50},
            "Udham Singh Nagar": {"zone": "III", "severity": 0.45},
            "Nainital": {"zone": "III", "severity": 0.50},
            "Champawat": {"zone": "IV", "severity": 0.65},
        }

        district_info = uttarakhand_seismic.get(
            self.district, {"zone": "IV", "severity": 0.70}
        )
        lat_center = (self.bbox[0] + self.bbox[2]) / 2
        lon_center = (self.bbox[1] + self.bbox[3]) / 2

        return [
            {
                "id": f"seismic-{self.district.lower()}",
                "hazard_type": "seismic",
                "severity": district_info["severity"],
                "zone_type": "red" if district_info["severity"] >= 0.7 else "orange",
                "center_lat": lat_center,
                "center_lon": lon_center,
                "radius_km": 50.0,  # district-wide
                "source": "IS 1893 / BIS",
                "properties": {
                    "seismic_zone": district_info["zone"],
                    "classification": "High Damage Risk Zone",
                },
            }
        ]

    # ------------------------------------------------------------------
    # Aggregate all hazard zones for a district
    # ------------------------------------------------------------------
    def fetch_all_hazard_zones(self, bbox_filter: bool = True) -> list[dict]:
        """Fetch all available hazard zone data for the district."""
        zones = []

        try:
            zones.extend(self.fetch_flood_inundation(bbox_filter))
        except Exception as e:
            logger.error(f"Flood zone fetch failed: {e}")

        try:
            zones.extend(self.fetch_landslide_zones(bbox_filter))
        except Exception as e:
            logger.error(f"Landslide zone fetch failed: {e}")

        try:
            zones.extend(self.fetch_seismic_zones())
        except Exception as e:
            logger.error(f"Seismic zone fetch failed: {e}")

        logger.info(f"Total hazard zones for {self.district}: {len(zones)}")
        return zones

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fetch_geojsonl(self, category: str, filename: str) -> list[dict]:
        """Download and decompress a GeoJSONL.7z file from ramSeraph releases.
        
        Caches parsed features in Supabase cloud, not local disk.
        """
        cloud_key = f"{category}_{filename.replace('.geojsonl.7z', '')}"
        cloud_data = self.cloud.download_district_data(self.district, cloud_key)
        if cloud_data and isinstance(cloud_data, list):
            logger.info(f"  Loaded {len(cloud_data)} features from cloud cache: {filename}")
            return cloud_data

        url = f"{RAMSERAPH_RELEASES[category]}/{filename}"
        logger.info(f"  Downloading {filename}...")
        try:
            resp = self.client.get(url)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"  Download failed for {filename}: {e}")
            return []

        # Decompress 7z to temp dir, parse, then discard local file
        tmp_path = self.cache_dir / filename.replace(".geojsonl.7z", ".geojsonl")
        try:
            import py7zr
            archive = py7zr.SevenZipFile(io.BytesIO(resp.content), mode="r")
            archive.extractall(path=self.cache_dir)
            archive.close()
        except ImportError:
            import lzma
            decompressed = lzma.decompress(resp.content)
            tmp_path.write_bytes(decompressed)
        except Exception as e:
            logger.warning(f"  7z decompression failed: {e}. Trying raw...")
            tmp_path.write_bytes(resp.content)

        features = self._parse_geojsonl(tmp_path)

        # Upload parsed features to cloud (much smaller than 7z)
        if features:
            self.cloud.upload_district_data(self.district, cloud_key, features)

        # Delete temp file to free disk
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

        return features

    def _parse_geojsonl(self, path: Path) -> list[dict]:
        """Parse a GeoJSONL file (one GeoJSON feature per line)."""
        features = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        feat = json.loads(line)
                        if "geometry" in feat or "type" in feat:
                            features.append(feat)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"  Failed to parse {path}: {e}")

        return features

    def _filter_by_bbox(self, features: list[dict]) -> list[dict]:
        """Filter GeoJSON features to those within the district bounding box."""
        lat_min, lon_min, lat_max, lon_max = self.bbox
        bbox_poly = box(lon_min, lat_min, lon_max, lat_max)
        filtered = []

        for feat in features:
            try:
                geom = self._extract_geometry(feat)
                if geom is None:
                    # Try point-based filtering
                    props = feat.get("properties", {})
                    lat = props.get("lat") or props.get("latitude")
                    lon = props.get("lon") or props.get("longitude") or props.get("lng")
                    if lat and lon:
                        pt = Point(float(lon), float(lat))
                        if bbox_poly.intersects(pt):
                            filtered.append(feat)
                    continue
                if bbox_poly.intersects(geom):
                    filtered.append(feat)
            except Exception:
                continue

        return filtered

    def _extract_geometry(self, feat: dict) -> Optional[any]:
        """Extract shapely geometry from a GeoJSON feature."""
        geom_data = feat.get("geometry")
        if geom_data is None:
            # Some features store geometry differently
            geom_data = feat.get("geom") or feat.get("the_geom")
        if geom_data is None:
            return None
        try:
            return shape(geom_data)
        except Exception:
            return None

    def _extract_severity(self, props: dict, hazard_type: str) -> float:
        """Extract or estimate severity (0-1) from feature properties."""
        # Try known severity fields
        for key in ["severity", "hazard_score", "risk_score", "threat_level"]:
            if key in props:
                val = props[key]
                if isinstance(val, (int, float)):
                    return min(1.0, max(0.0, float(val)))
                if isinstance(val, str):
                    try:
                        return min(1.0, max(0.0, float(val)))
                    except ValueError:
                        pass

        # Try text-based classification
        for key in ["classification", "risk_level", "hazard_class", "zone"]:
            val = str(props.get(key, "")).lower()
            if "high" in val or "extreme" in val or "zone iv" in val or "zone v" in val:
                return 0.85
            elif "moderate" in val or "medium" in val or "zone iii" in val:
                return 0.55
            elif "low" in val or "zone ii" in val:
                return 0.25

        # Default by hazard type
        defaults = {"flood": 0.6, "landslide": 0.6, "seismic": 0.7, "cyclone": 0.5}
        return defaults.get(hazard_type, 0.5)
