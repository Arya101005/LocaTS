"""
India Geodata ingestion — downloads curated open GIS data for India.

Pulls from yashveeeeeeer/india-geodata:
- Healthcare facilities (PHCs, CHCs, hospitals)
- Population density (WorldPop 1km)
- Administrative boundaries (villages, habitations)
- Road infrastructure (PMGSY, national highways)
- Flood inventory (HydroSense Lab, IIT Delhi)

All data CC BY 4.0 / CC0 1.0 — see LICENSES/ in india-geodata repo.

Usage:
    from backend.app.data.ingestion.geodata_ingester import GeoDataIngester
    ingester = GeoDataIngester(district="Chamoli")
    data = ingester.fetch_all()
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# india-geodata GitHub API base
GITHUB_API = "https://api.github.com/repos/yashveeeeeeer/india-geodata/releases"
GITHUB_RAW = "https://raw.githubusercontent.com/yashveeeeeeer/india-geodata/main"

# Direct release download URLs (we'll resolve these dynamically)
RELEASE_TAGS = {
    "healthcare": "healthcare/facilities",
    "flood_inventory": "environment/flood-inventory",
    "flood_atlas": "environment/flood-atlas",
    "population_density": "remote-sensing/population",
    "admin_boundaries_villages": "admin/villages",
    "admin_boundaries_habitations": "admin/habitations",
    "roads_pmgsy": "infrastructure/roads-pmgsy",
    "roads_national": "infrastructure/roads-national",
    "education": "education/schools",
}

# District bounding boxes
DISTRICT_BBOXES: dict[str, dict] = {
    "Chamoli": {"bbox": (30.05, 79.05, 30.95, 79.95), "state": "Uttarakhand"},
    "Almora": {"bbox": (29.45, 79.15, 29.95, 79.75), "state": "Uttarakhand"},
    "Pithoragarh": {"bbox": (29.70, 80.05, 30.50, 81.00), "state": "Uttarakhand"},
    "Uttarkashi": {"bbox": (30.40, 78.10, 31.15, 79.10), "state": "Uttarakhand"},
    "Rudraprayag": {"bbox": (30.20, 78.75, 30.65, 79.25), "state": "Uttarakhand"},
    "Dehradun": {"bbox": (30.05, 77.80, 30.65, 78.55), "state": "Uttarakhand"},
}


class GeoDataIngester:
    """Downloads and parses open GIS data from india-geodata repository."""

    def __init__(self, district: str = "Chamoli", cache_dir: Optional[str] = None):
        self.district = district
        info = DISTRICT_BBOXES.get(district, DISTRICT_BBOXES["Chamoli"])
        self.bbox = info["bbox"]
        self.state = info["state"]
        self.cache_dir = Path(cache_dir or tempfile.gettempdir()) / "locats_geodata_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(timeout=120, follow_redirects=True)

    def close(self):
        self.client.close()

    # ------------------------------------------------------------------
    # Healthcare facilities
    # ------------------------------------------------------------------
    def fetch_healthcare(self) -> list[dict]:
        """
        Fetch public health facilities (PHCs, CHCs, hospitals) from
        india-geodata (source: planemad/india_health_facilities, NIC HealthGIS).
        """
        cache_path = self.cache_dir / "healthcare.geojson"
        if not cache_path.exists():
            self._download_release_asset("healthcare", cache_path, pattern="health")

        if not cache_path.exists():
            logger.warning("Healthcare data not available, using OSM fallback")
            return []

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])

            # Filter to district bbox
            lat_min, lon_min, lat_max, lon_max = self.bbox
            from shapely.geometry import box, shape
            bbox_poly = box(lon_min, lat_min, lon_max, lat_max)

            facilities = []
            for feat in features:
                geom = feat.get("geometry")
                if geom is None:
                    continue
                try:
                    s = shape(geom)
                    if not bbox_poly.intersects(s):
                        continue
                except Exception:
                    continue

                props = feat.get("properties", {})
                centroid = s.centroid

                # Map NIC facility types to our model
                facility_type = props.get("type", props.get("facility_type", "phc"))
                beds = self._estimate_beds(facility_type)

                facilities.append({
                    "name": props.get("name", props.get("facility_name", "Unknown")),
                    "lat": centroid.y,
                    "lon": centroid.x,
                    "type": facility_type,
                    "bed_capacity": beds,
                    "healthcare_beds_per_hour": max(2, beds // 10),
                    "water_capacity_liters_per_day": beds * 40,
                    "district": props.get("district", self.district),
                    "block": props.get("block", props.get("subdistrict", "")),
                    "source": "NIC HealthGIS / india-geodata",
                })

            logger.info(f"  Filtered {len(facilities)} healthcare facilities in {self.district}")
            return facilities

        except Exception as e:
            logger.error(f"  Healthcare parse failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Population density (WorldPop 1km)
    # ------------------------------------------------------------------
    def fetch_population_density(self) -> dict:
        """
        Fetch WorldPop population density grid for the district.

        Returns summary stats and per-settlement population estimates.
        """
        # WorldPop data is in GeoTIFF format — too large to download directly
        # Instead, use the india-geodata summary CSVs if available
        # For now, use the village-level census data

        logger.info(f"Fetching population data for {self.district}...")
        census_data = self._fetch_census_villages()

        if census_data:
            # Aggregate to settlement-level estimates
            total_pop = sum(v.get("population", 0) for v in census_data)
            return {
                "district": self.district,
                "total_population_census_2011": total_pop,
                "num_villages": len(census_data),
                "villages": census_data,
                "source": "Census 2011 / india-geodata",
            }

        return {
            "district": self.district,
            "total_population_census_2011": 370000,
            "num_villages": 0,
            "villages": [],
            "source": "Estimated (census data unavailable)",
        }

    def _fetch_census_villages(self) -> list[dict]:
        """Fetch village-level census data."""
        cache_path = self.cache_dir / "census_villages.geojson"
        if not cache_path.exists():
            self._download_release_asset(
                "admin_boundaries_villages", cache_path, pattern="village"
            )

        if not cache_path.exists():
            return []

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])

            lat_min, lon_min, lat_max, lon_max = self.bbox
            from shapely.geometry import box, shape
            bbox_poly = box(lon_min, lat_min, lon_max, lon_max)

            villages = []
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry")

                # Filter by district name
                district_name = props.get("district", props.get("DISTRICT", ""))
                if self.district.lower() not in str(district_name).lower():
                    continue

                centroid = None
                if geom:
                    try:
                        s = shape(geom)
                        centroid = s.centroid
                    except Exception:
                        pass

                pop = props.get("population", props.get("TOT_P", props.get("tot_p", 0)))
                try:
                    pop = int(float(pop)) if pop else 0
                except (ValueError, TypeError):
                    pop = 0

                if pop > 0 or centroid:
                    villages.append({
                        "name": props.get("name", props.get("NAME", "Unknown")),
                        "lat": centroid.y if centroid else None,
                        "lon": centroid.x if centroid else None,
                        "population": pop,
                        "block": props.get("block", props.get("SUBDISTRICT", "")),
                    })

            logger.info(f"  Found {len(villages)} villages in {self.district}")
            return villages

        except Exception as e:
            logger.error(f"  Census village parse failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Road infrastructure
    # ------------------------------------------------------------------
    def fetch_roads(self) -> list[dict]:
        """Fetch road infrastructure data (PMGSY rural + national highways)."""
        cache_path = self.cache_dir / "roads.geojson"
        if not cache_path.exists():
            self._download_release_asset("roads_national", cache_path, pattern="road")

        if not cache_path.exists():
            logger.warning("Road data not available from india-geodata")
            return []

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])

            lat_min, lon_min, lat_max, lon_max = self.bbox
            from shapely.geometry import box, shape
            bbox_poly = box(lon_min, lat_min, lon_max, lon_max)

            roads = []
            for feat in features:
                geom = feat.get("geometry")
                if geom is None:
                    continue
                try:
                    s = shape(geom)
                    if not bbox_poly.intersects(s):
                        continue
                except Exception:
                    continue

                props = feat.get("properties", {})
                centroid = s.centroid
                length_km = s.length * 111.0  # rough degree-to-km

                road_type = props.get("highway", props.get("road_type", "tertiary"))
                capacity_map = {
                    "motorway": (200, 2000), "trunk": (150, 1500),
                    "primary": (120, 1200), "secondary": (80, 800),
                    "tertiary": (50, 500), "residential": (30, 300),
                }
                veh_cap, ppl_cap = capacity_map.get(road_type, (40, 400))

                roads.append({
                    "name": props.get("name", ""),
                    "lat": centroid.y,
                    "lon": centroid.x,
                    "type": road_type,
                    "distance_km": round(length_km, 2),
                    "capacity_vehicles_per_hour": veh_cap,
                    "people_throughput_per_hour": ppl_cap,
                    "source": "india-geodata / MoRTH",
                })

            logger.info(f"  Filtered {len(roads)} road segments in {self.district}")
            return roads

        except Exception as e:
            logger.error(f"  Road parse failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Administrative boundaries (habitations)
    # ------------------------------------------------------------------
    def fetch_habitation_boundaries(self) -> list[dict]:
        """Fetch habitation-level boundary polygons from india-geodata."""
        cache_path = self.cache_dir / "habitations.geojson"
        if not cache_path.exists():
            self._download_release_asset(
                "admin_boundaries_habitations", cache_path, pattern="habitation"
            )

        if not cache_path.exists():
            return []

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            features = data.get("features", [])

            from shapely.geometry import box, shape
            lat_min, lon_min, lat_max, lon_max = self.bbox
            bbox_poly = box(lon_min, lat_min, lon_max, lon_max)

            habitations = []
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry")

                district_name = props.get("district", props.get("DISTRICT", ""))
                if self.district.lower() not in str(district_name).lower():
                    continue

                centroid = None
                if geom:
                    try:
                        s = shape(geom)
                        if bbox_poly.intersects(s):
                            centroid = s.centroid
                    except Exception:
                        continue
                else:
                    continue

                pop = props.get("population", props.get("TOT_P", 0))
                try:
                    pop = int(float(pop)) if pop else 0
                except (ValueError, TypeError):
                    pop = 0

                habitations.append({
                    "name": props.get("name", props.get("NAME", "Unknown")),
                    "lat": centroid.y,
                    "lon": centroid.x,
                    "population": pop,
                    "block": props.get("block", ""),
                    "geom_wkt": s.wkt[:300] if geom else None,
                })

            logger.info(f"  Found {len(habitations)} habitations in {self.district}")
            return habitations

        except Exception as e:
            logger.error(f"  Habitation parse failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Aggregate fetch
    # ------------------------------------------------------------------
    def fetch_all(self) -> dict:
        """Fetch all available india-geodata datasets for the district."""
        return {
            "district": self.district,
            "state": self.state,
            "bbox": self.bbox,
            "healthcare_facilities": self.fetch_healthcare(),
            "population_data": self.fetch_population_density(),
            "roads": self.fetch_roads(),
            "habitations": self.fetch_habitation_boundaries(),
        }

    # ------------------------------------------------------------------
    # Download helpers
    # ------------------------------------------------------------------
    def _download_release_asset(
        self, tag: str, dest_path: Path, pattern: str = ""
    ) -> bool:
        """Download an asset from a GitHub release."""
        try:
            # List release assets
            tag_encoded = tag.replace("/", "%2F")
            url = f"{GITHUB_API}/tags/{tag_encoded}"
            resp = self.client.get(url)

            if resp.status_code == 404:
                # Try the release directly
                url = f"https://api.github.com/repos/yashveeeeeeer/india-geodata/releases"
                resp = self.client.get(url, params={"per_page": 100})
                if resp.status_code != 200:
                    return False

                releases = resp.json()
                release = None
                for r in releases:
                    if tag in r.get("tag_name", "") or tag in r.get("name", ""):
                        release = r
                        break
                if not release:
                    return False
            else:
                release = resp.json()

            # Find matching asset
            assets = release.get("assets", [])
            target_asset = None
            for asset in assets:
                name = asset.get("name", "")
                if pattern.lower() in name.lower() and (
                    name.endswith(".geojson")
                    or name.endswith(".json")
                    or name.endswith(".csv")
                ):
                    target_asset = asset
                    break

            if not target_asset:
                # Try any geojson
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".geojson"):
                        target_asset = asset
                        break

            if not target_asset:
                logger.warning(f"  No matching asset for {pattern} in release {tag}")
                return False

            # Download
            dl_url = target_asset.get("browser_download_url")
            logger.info(f"  Downloading {target_asset['name']}...")
            resp = self.client.get(dl_url)
            resp.raise_for_status()
            dest_path.write_bytes(resp.content)
            logger.info(f"  Saved to {dest_path} ({len(resp.content)} bytes)")
            return True

        except Exception as e:
            logger.error(f"  Download failed for {tag}/{pattern}: {e}")
            return False

    def _estimate_beds(self, facility_type: str) -> int:
        """Estimate bed capacity by facility type."""
        estimates = {
            "hospital": 200,
            "district_hospital": 300,
            "chc": 50,  # Community Health Centre
            "phc": 20,  # Primary Health Centre
            "sub_centre": 5,
            "clinic": 15,
            "dispensary": 10,
        }
        return estimates.get(str(facility_type).lower(), 20)
