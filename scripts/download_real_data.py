#!/usr/bin/env python3
"""
Download real data for LocaTS and export as GeoJSON for the dashboard.

Usage:
    python scripts/download_real_data.py [--district Chamoli] [--export-dir frontend/public/data]

This script:
1. Downloads real road networks, healthcare facilities, and settlements from OSM
2. Downloads hazard zones from NDMA/Bhuvan/NDEM
3. Downloads population and census data from india-geodata
4. Exports everything as GeoJSON files for the React dashboard
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.data.ingestion.real_data_loader import RealDataLoader
from backend.app.data.ingestion.ndma_ingester import NDMAIngester
from backend.app.data.ingestion.rainfall_ingester import RainfallIngester

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def export_geojson(
    district: str = "Chamoli",
    export_dir: str = "frontend/public/data",
):
    """Download real data and export as GeoJSON files."""
    export_path = Path(export_dir)
    export_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"=" * 60)
    logger.info(f"Downloading real data for {district} district")
    logger.info(f"Export directory: {export_path}")
    logger.info(f"=" * 60)

    # 1. Load capacity graph (habitations, shelters, roads)
    logger.info("\n[1/4] Loading capacity graph from OSM + india-geodata...")
    loader = RealDataLoader(district=district)

    try:
        graph = loader.load_capacity_graph()

        # Export habitations as GeoJSON
        hab_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [h.location.lon, h.location.lat],
                    },
                    "properties": {
                        "id": h.id,
                        "name": h.name,
                        "population": h.population_estimate,
                        "district": h.district,
                        "block": h.block,
                        "elevation_m": h.elevation_m,
                        "social_vulnerability": (
                            h.social_vulnerability.vulnerability_index
                            if h.social_vulnerability
                            else 0.0
                        ),
                    },
                }
                for h in graph.habitations
            ],
        }
        (export_path / "habitations.geojson").write_text(
            json.dumps(hab_geojson, indent=2), encoding="utf-8"
        )
        logger.info(f"  Exported {len(graph.habitations)} habitations")

        # Export shelters as GeoJSON
        shelter_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [s.location.lon, s.location.lat],
                    },
                    "properties": {
                        "id": s.id,
                        "name": s.name,
                        "bed_capacity": s.bed_capacity,
                        "beds_available": s.beds_available,
                        "healthcare_beds_per_hour": s.healthcare_beds_per_hour,
                        "water_capacity_lpd": s.water_capacity_liters_per_day,
                        "is_accessible": s.is_accessible,
                        "shelter_type": s.shelter_type,
                        "district": s.district,
                        "is_active": s.is_active,
                    },
                }
                for s in graph.shelters
            ],
        }
        (export_path / "shelters.geojson").write_text(
            json.dumps(shelter_geojson, indent=2), encoding="utf-8"
        )
        logger.info(f"  Exported {len(graph.shelters)} shelters")

        # Export roads as GeoJSON (LineStrings)
        road_geojson = {
            "type": "FeatureCollection",
            "features": [],
        }
        node_positions = {}
        for h in graph.habitations:
            node_positions[h.id] = (h.location.lon, h.location.lat)
        for s in graph.shelters:
            node_positions[s.id] = (s.location.lon, s.location.lat)

        for road in graph.road_segments:
            from_pos = node_positions.get(road.from_node)
            to_pos = node_positions.get(road.to_node)
            if from_pos and to_pos:
                road_geojson["features"].append({
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [from_pos, to_pos],
                    },
                    "properties": {
                        "id": road.id,
                        "from_node": road.from_node,
                        "to_node": road.to_node,
                        "distance_km": road.distance_km,
                        "travel_time_min": road.travel_time_minutes,
                        "status": road.status.value,
                        "throughput": road.people_throughput_per_hour,
                        "damage_factor": road.damage_factor,
                    },
                })
        (export_path / "roads.geojson").write_text(
            json.dumps(road_geojson, indent=2), encoding="utf-8"
        )
        logger.info(f"  Exported {len(road_geojson['features'])} road segments")

    finally:
        loader.close()

    # 2. Load hazard zones from NDMA/Bhuvan
    logger.info("\n[2/4] Loading hazard zones from NDMA/Bhuvan...")
    ndma = NDMAIngester(district=district)
    try:
        hazard_zones = ndma.fetch_all_hazard_zones(bbox_filter=True)

        hazard_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [z["center_lon"], z["center_lat"]],
                    },
                    "properties": {
                        "id": z["id"],
                        "hazard_type": z["hazard_type"],
                        "severity": z["severity"],
                        "zone_type": z["zone_type"],
                        "radius_km": z["radius_km"],
                        "source": z.get("source", "unknown"),
                    },
                }
                for z in hazard_zones
            ],
        }
        (export_path / "hazard_zones.geojson").write_text(
            json.dumps(hazard_geojson, indent=2), encoding="utf-8"
        )
        logger.info(f"  Exported {len(hazard_zones)} hazard zones")
    finally:
        ndma.close()

    # 3. Load rainfall data
    logger.info("\n[3/4] Loading rainfall data from IMD...")
    rainfall = RainfallIngester(district=district)
    try:
        readings = rainfall.fetch_current_rainfall()

        rainfall_geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [r["lon"], r["lat"]],
                    },
                    "properties": {
                        "station": r.get("station", ""),
                        "value_mm": r["value"],
                        "source": r.get("source", ""),
                        "quality": r.get("quality", ""),
                        "timestamp": r.get("timestamp", ""),
                    },
                }
                for r in readings
            ],
        }
        (export_path / "rainfall.geojson").write_text(
            json.dumps(rainfall_geojson, indent=2), encoding="utf-8"
        )
        logger.info(f"  Exported {len(readings)} rainfall readings")
    finally:
        rainfall.close()

    # 4. Export metadata
    logger.info("\n[4/4] Exporting metadata...")
    metadata = {
        "district": district,
        "data_sources": {
            "road_network": "OpenStreetMap via osmnx (ODbL)",
            "healthcare": "NIC HealthGIS / india-geodata (India OGL)",
            "hazard_zones": "NDEM/Bhuvan (CC0 1.0) via ramSeraph/india_natural_disasters",
            "flood_inventory": "HydroSense Lab, IIT Delhi (CC BY 4.0) via india-geodata",
            "population": "Census 2011 / india-geodata",
            "rainfall": "IMD gridded rainfall (public domain)",
            "seismic": "IS 1893 / BIS (standard zonation)",
        },
        "export_files": [
            "habitations.geojson",
            "shelters.geojson",
            "roads.geojson",
            "hazard_zones.geojson",
            "rainfall.geojson",
        ],
        "attribution": (
            "Data: OpenStreetMap contributors (ODbL), "
            "ramSeraph/india_natural_disasters (CC0 1.0), "
            "yashveeeeeeer/india-geodata (CC BY 4.0), "
            "IMD Pune (public domain), "
            "HydroSense Lab IIT Delhi (CC BY 4.0), "
            "NIC HealthGIS (India OGL). "
            "See each dataset's metadata.json for full license text."
        ),
    }
    (export_path / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    logger.info(f"\n{'=' * 60}")
    logger.info(f"DONE! Exported to {export_path}/")
    logger.info(f"  habitation.geojson  - {len(graph.habitations)} habitations")
    logger.info(f"  shelters.geojson    - {len(graph.shelters)} shelters")
    logger.info(f"  roads.geojson       - {len(road_geojson['features'])} roads")
    logger.info(f"  hazard_zones.geojson - {len(hazard_zones)} zones")
    logger.info(f"  rainfall.geojson    - {len(readings)} readings")
    logger.info(f"  metadata.json       - data source attribution")
    logger.info(f"{'=' * 60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download real data for LocaTS")
    parser.add_argument("--district", default="Chamoli", help="District name")
    parser.add_argument(
        "--export-dir",
        default="frontend/public/data",
        help="Export directory for GeoJSON files",
    )
    args = parser.parse_args()
    export_geojson(district=args.district, export_dir=args.export_dir)
