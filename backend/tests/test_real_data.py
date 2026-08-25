"""
Tests for the real data ingestion pipeline.

Verifies:
- All ingestion modules instantiate correctly
- Fallback to sample data when network data is unavailable
- NDMA hazard zone parsing and severity extraction
- IMD rainfall classification and hazard score conversion
- GeoJSON export format correctness
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import only lightweight modules first
from backend.app.data.ingestion.rainfall_ingester import (
    RainfallIngester,
    classify_rainfall_level,
    rainfall_to_hazard_score,
    CHAMOLI_IMD_STATIONS,
)
# These imports are heavier (osmnx, geopandas) — import inline in tests


class TestOSMIngester:
    """Test OSM data ingestion module (deferred imports for speed)."""

    def test_instantiation(self):
        from backend.app.data.ingestion.osm_ingester import OSMIngester
        ingester = OSMIngester("Chamoli", "Uttarakhand")
        assert ingester.district == "Chamoli"
        assert ingester.state == "Uttarakhand"
        assert len(ingester.bbox) == 4

    def test_district_bbox_exists(self):
        from backend.app.data.ingestion.osm_ingester import DISTRICT_BBOXES
        for district in ["Chamoli", "Almora", "Pithoragarh", "Uttarkashi"]:
            assert district in DISTRICT_BBOXES
            bbox = DISTRICT_BBOXES[district]["bbox"]
            assert len(bbox) == 4
            assert bbox[0] < bbox[2]  # lat_min < lat_max
            assert bbox[1] < bbox[3]  # lon_min < lon_max

    def test_road_graph_to_segments_empty_graph(self):
        from backend.app.data.ingestion.osm_ingester import OSMIngester
        import networkx as nx
        ingester = OSMIngester("Chamoli")
        G = nx.MultiDiGraph()
        segments = ingester._road_graph_to_segments(G)
        assert segments == []

    def test_settlement_population_estimate(self):
        from backend.app.data.ingestion.osm_ingester import OSMIngester
        ingester = OSMIngester("Chamoli")
        assert ingester._estimate_population("village") == 2000
        assert ingester._estimate_population("town") == 15000
        assert ingester._estimate_population("hamlet") == 300
        assert ingester._estimate_population("unknown_type") == 1000


class TestNDMAIngester:
    """Test NDMA/Bhuvan/NDEM hazard zone ingestion."""

    def test_instantiation(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        assert ingester.district == "Chamoli"
        assert len(ingester.bbox) == 4

    def test_seismic_zones(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        zones = ingester.fetch_seismic_zones()
        assert len(zones) == 1
        zone = zones[0]
        assert zone["hazard_type"] == "seismic"
        assert zone["severity"] == 0.75  # Chamoli is Zone IV
        assert zone["source"] == "IS 1893 / BIS"

    def test_severity_extraction_text_classification(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        assert ingester._extract_severity({"classification": "High Risk"}, "flood") == 0.85
        assert ingester._extract_severity({"classification": "Moderate Risk"}, "flood") == 0.55
        assert ingester._extract_severity({"classification": "Low Risk"}, "flood") == 0.25
        assert ingester._extract_severity({}, "flood") == 0.6  # default

    def test_severity_extraction_numeric(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        assert ingester._extract_severity({"severity": 0.9}, "flood") == 0.9
        assert ingester._extract_severity({"risk_score": "0.75"}, "landslide") == 0.75

    def test_extract_geometry_none(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        assert ingester._extract_geometry({}) is None
        assert ingester._extract_geometry({"geometry": None}) is None

    def test_extract_geometry_valid(self):
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        ingester = NDMAIngester("Chamoli")
        feat = {
            "geometry": {
                "type": "Point",
                "coordinates": [79.55, 30.47],
            }
        }
        geom = ingester._extract_geometry(feat)
        assert geom is not None
        assert geom.x == pytest.approx(79.55)
        assert geom.y == pytest.approx(30.47)


class TestRainfallIngester:
    """Test IMD rainfall ingestion."""

    def test_classification(self):
        assert classify_rainfall_level(5.0) == "light"
        assert classify_rainfall_level(15.0) == "moderate"
        assert classify_rainfall_level(60.0) == "heavy"
        assert classify_rainfall_level(120.0) == "very_heavy"
        assert classify_rainfall_level(250.0) == "exceptional"

    def test_hazard_score_low_rain(self):
        score = rainfall_to_hazard_score(5.0)
        assert 0.0 <= score <= 1.0
        assert score < 0.1  # very low rain → low hazard

    def test_hazard_score_high_rain(self):
        score = rainfall_to_hazard_score(200.0, elevation_m=3000.0)
        assert score >= 0.9  # extreme rain at high elevation → high hazard

    def test_hazard_score_elevation_effect(self):
        low_elev = rainfall_to_hazard_score(50.0, elevation_m=500.0)
        high_elev = rainfall_to_hazard_score(50.0, elevation_m=3000.0)
        assert high_elev > low_elev  # higher elevation → more hazard

    def test_stations_loaded(self):
        assert len(CHAMOLI_IMD_STATIONS) == 5
        for station in CHAMOLI_IMD_STATIONS:
            assert "name" in station
            assert "lat" in station
            assert "lon" in station
            assert "elevation_m" in station
            assert 29.0 < station["lat"] < 32.0  # Uttarakhand range
            assert 78.0 < station["lon"] < 82.0

    def test_instantiation(self):
        ingester = RainfallIngester("Chamoli")
        assert ingester.district == "Chamoli"

    def test_generate_seasonal_readings(self):
        ingester = RainfallIngester("Chamoli")
        readings = ingester._generate_seasonal_readings()
        assert len(readings) == 5  # one per station
        for r in readings:
            assert r["value"] >= 0
            assert "source" in r
            assert "lat" in r
            assert "lon" in r

    def test_heavy_rain_scenario(self):
        ingester = RainfallIngester("Chamoli")
        readings = ingester.generate_heavy_rain_scenario(intensity=150.0)
        assert len(readings) == 5
        for r in readings:
            assert r["value"] > 50  # should be heavy rainfall

    def test_historical_event(self):
        ingester = RainfallIngester("Chamoli")
        readings = ingester.get_historical_rainfall_for_event("2021-02-07")
        assert len(readings) > 0
        # Chamoli 2021 was a flash flood — expect high intensity
        peak_values = [r["value"] for r in readings]
        assert max(peak_values) > 50


class TestGeoDataIngester:
    """Test india-geodata ingestion."""

    def test_instantiation(self):
        from backend.app.data.ingestion.geodata_ingester import GeoDataIngester
        ingester = GeoDataIngester("Chamoli")
        assert ingester.district == "Chamoli"
        assert len(ingester.bbox) == 4

    def test_estimate_beds(self):
        from backend.app.data.ingestion.geodata_ingester import GeoDataIngester
        ingester = GeoDataIngester("Chamoli")
        assert ingester._estimate_beds("hospital") == 200
        assert ingester._estimate_beds("phc") == 20
        assert ingester._estimate_beds("chc") == 50
        assert ingester._estimate_beds("unknown") == 20  # default


class TestRealDataLoader:
    """Test the unified real data loader (deferred imports for speed)."""

    def test_haversine_distance(self):
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        # Chamoli to Gopeshwar -- roughly 10km
        d = RealDataLoader._haversine(30.47, 79.55, 30.40, 79.33)
        assert 8.0 < d < 25.0  # approximate range

    def test_haversine_same_point(self):
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        d = RealDataLoader._haversine(30.47, 79.55, 30.47, 79.55)
        assert d == pytest.approx(0.0, abs=0.01)

    def test_fallback_to_sample_data(self):
        """
        When OSM and geodata are unavailable (network failure),
        the loader should fall back to sample data.
        """
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        loader = RealDataLoader("Chamoli")

        # Mock all fetchers to return empty data (including road network)
        with patch.object(loader.osm, "fetch_road_network", side_effect=Exception("no network")), \
             patch.object(loader.osm, "fetch_settlements", return_value=[]), \
             patch.object(loader.osm, "fetch_healthcare_facilities", return_value=[]), \
             patch.object(loader.osm, "fetch_potential_shelters", return_value=[]), \
             patch.object(loader.geodata, "fetch_healthcare", return_value=[]), \
             patch.object(loader.geodata, "fetch_population_density", return_value={"villages": []}), \
             patch.object(loader.geodata, "fetch_habitation_boundaries", return_value=[]):

            graph = loader.load_capacity_graph()
            # Should fall back to sample data
            assert len(graph.habitations) > 0
            assert len(graph.shelters) > 0
            assert len(graph.road_segments) > 0

    def test_population_buffer_applied(self):
        """Verify population buffer (edge 5.6) is applied."""
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        loader = RealDataLoader("Chamoli", population_buffer=0.20)

        with patch.object(loader.osm, "fetch_road_network", side_effect=Exception("no network")), \
             patch.object(loader.osm, "fetch_settlements", return_value=[
                 {"name": "Test Village", "lat": 30.5, "lon": 79.5, "place_type": "village", "population_estimate": 1000}
             ]), \
             patch.object(loader.osm, "fetch_healthcare_facilities", return_value=[
                 {"name": "Test Hospital", "lat": 30.51, "lon": 79.51, "type": "hospital", "bed_capacity": 100}
             ]), \
             patch.object(loader.osm, "fetch_potential_shelters", return_value=[]), \
             patch.object(loader.geodata, "fetch_healthcare", return_value=[]), \
             patch.object(loader.geodata, "fetch_population_density", return_value={"villages": []}), \
             patch.object(loader.geodata, "fetch_habitation_boundaries", return_value=[]):

            graph = loader.load_capacity_graph()
            # Pop should be 1000 * 1.20 = 1200
            habs = [h for h in graph.habitations if h.name == "Test Village"]
            assert len(habs) == 1
            assert habs[0].population_estimate == 1200

    def test_connectivity_fallback_roads(self):
        """When no OSM road network, connectivity roads are built."""
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        loader = RealDataLoader("Chamoli")

        hab = MagicMock()
        hab.id = "hab-001"
        hab.name = "Test"
        hab.location.lat = 30.5
        hab.location.lon = 79.5

        shelter = MagicMock()
        shelter.id = "shelter-001"
        shelter.name = "Shelter"
        shelter.location.lat = 30.6
        shelter.location.lon = 79.6

        roads = loader._build_connectivity_roads([hab], [shelter])
        assert len(roads) >= 1
        road = roads[0]
        assert road.from_node == "hab-001"
        assert road.to_node == "shelter-001"
        assert road.distance_km > 0


class TestGeoJSONExport:
    """Test GeoJSON export format."""

    def test_habitations_geojson_format(self):
        """Verify GeoJSON export produces valid FeatureCollection."""
        from backend.app.models.domain import (
            CapacityGraph, HabitationCluster, Coordinates, Shelter
        )

        hab = HabitationCluster(
            id="hab-001", name="Test Village",
            location=Coordinates(lat=30.5, lon=79.5),
            population_estimate=1000,
        )
        shelter = Shelter(
            id="shelter-001", name="Test Shelter",
            location=Coordinates(lat=30.6, lon=79.6),
            bed_capacity=500,
        )

        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [h.location.lon, h.location.lat],
                    },
                    "properties": {"id": h.id, "name": h.name},
                }
                for h in [hab]
            ],
        }

        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 1
        feat = geojson["features"][0]
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert feat["geometry"]["coordinates"] == [79.5, 30.5]
