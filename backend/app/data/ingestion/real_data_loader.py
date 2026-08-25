"""
Unified real data loader for LocaTS.

Combines all ingestion pipelines (OSM, NDMA, india-geodata, IMD) and
converts their output into our domain models (CapacityGraph, hazard zones,
sensor readings).

This replaces the sample data with real geographic/hazard data.

Usage:
    from backend.app.data.ingestion.real_data_loader import RealDataLoader
    loader = RealDataLoader(district="Chamoli")
    graph = loader.load_capacity_graph()
    hazards = loader.load_hazard_zones()
"""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime
from typing import Optional

from backend.app.models.domain import (
    CapacityGraph,
    Coordinates,
    CrowdReport,
    HabitationCluster,
    HazardConfidence,
    HazardType,
    LiveSensorReading,
    RoadSegment,
    RoadStatus,
    Shelter,
    SocialVulnerability,
    StaticHazardZone,
)
from backend.app.data.ingestion.osm_ingester import OSMIngester
from backend.app.data.ingestion.ndma_ingester import NDMAIngester
from backend.app.data.ingestion.geodata_ingester import GeoDataIngester
from backend.app.data.ingestion.rainfall_ingester import RainfallIngester
from backend.app.data.cloud_storage import CloudStorage

logger = logging.getLogger(__name__)

# Population buffer for uncertainty (edge 5.6)
POPULATION_BUFFER_FRACTION = 0.15


class RealDataLoader:
    """
    Loads real geographic, hazard, and population data for a district.

    Chains together four ingestion pipelines:
    1. OSMIngester → road network, shelters, POIs
    2. NDMAIngester → hazard zone polygons (flood, landslide, seismic)
    3. GeoDataIngester → healthcare, population, admin boundaries
    4. RainfallIngester → live/recent rainfall telemetry
    """

    def __init__(
        self,
        district: str = "Chamoli",
        state: str = "Uttarakhand",
        cache_dir: Optional[str] = None,
        population_buffer: float = POPULATION_BUFFER_FRACTION,
    ):
        self.district = district
        self.state = state
        self.population_buffer = population_buffer

        self.osm = OSMIngester(district, state)
        self.ndma = NDMAIngester(district, cache_dir)
        self.geodata = GeoDataIngester(district, cache_dir)
        self.rainfall = RainfallIngester(district)

    def close(self):
        self.osm.close() if hasattr(self.osm, "close") else None
        self.ndma.close()
        self.geodata.close()
        self.rainfall.close()

    # ------------------------------------------------------------------
    # Capacity Graph (our domain model)
    # ------------------------------------------------------------------
    def load_capacity_graph(self) -> CapacityGraph:
        """
        Build a full CapacityGraph from real data sources.

        Priority:
        1. OSM settlements + india-geodata census villages → habitation clusters
        2. OSM healthcare + india-geodata healthcare → shelters with beds
        3. OSM road network → road segments (mapped to our node IDs)
        4. Fallback connectivity if no road network available
        """
        logger.info(f"Loading real capacity graph for {self.district}, {self.state}...")
        logger.info("=" * 60)

        # ================================================================
        # Phase 1: Build habitation clusters
        # ================================================================
        habitations = []
        try:
            settlements = self.osm.fetch_settlements()
            habitations.extend(self._convert_settlements(settlements))
            logger.info(f"  Settlements: {len(settlements)} from OSM")
        except Exception as e:
            logger.warning(f"  OSM settlement fetch failed: {e}")

        try:
            pop_data = self.geodata.fetch_population_density()
            census_villages = pop_data.get("villages", [])
            existing_names = {h.name for h in habitations}
            for cv in census_villages:
                if cv.get("name") and cv["name"] not in existing_names:
                    habitations.append(self._census_village_to_habitation(cv))
            logger.info(f"  Census villages added: {len(census_villages)}")
        except Exception as e:
            logger.warning(f"  Census village fetch failed: {e}")

        # ================================================================
        # Phase 2: Build shelters
        # ================================================================
        shelters = []
        try:
            healthcare = self.geodata.fetch_healthcare()
            shelters.extend(self._convert_healthcare_to_shelters(healthcare))
            logger.info(f"  Healthcare shelters: {len(shelters)} from india-geodata")
        except Exception as e:
            logger.warning(f"  Healthcare fetch failed: {e}")

        try:
            osm_healthcare = self.osm.fetch_healthcare_facilities()
            existing_names = {s.name for s in shelters}
            for hc in osm_healthcare:
                if hc["name"] not in existing_names:
                    shelters.append(self._hc_dict_to_shelter(hc))
            logger.info(f"  OSM healthcare shelters added: {len(osm_healthcare)}")
        except Exception as e:
            logger.warning(f"  OSM healthcare fetch failed: {e}")

        try:
            potential = self.osm.fetch_potential_shelters()
            for ps in potential:
                if ps["name"] not in {s.name for s in shelters}:
                    shelters.append(self._hc_dict_to_shelter(ps))
            logger.info(f"  OSM building shelters added: {len(potential)}")
        except Exception as e:
            logger.warning(f"  OSM potential shelter fetch failed: {e}")

        # If we have no habitations or shelters at all, generate synthetic ones
        if not habitations:
            logger.warning("  No real settlement data — creating synthetic habitations from district population")
            habitations = self._generate_synthetic_habitations()
        if not shelters:
            logger.warning("  No real shelter data — creating synthetic shelters from district population")
            shelters = self._generate_synthetic_shelters()

        # Save graph to Supabase cloud for next time
        try:
            cloud = CloudStorage()
            if cloud.is_configured:
                graph_dict = CapacityGraph(
                    habitations=habitations, shelters=shelters, road_segments=[],
                ).model_dump()
                cloud.upload_full_graph(self.district, graph_dict)
        except Exception as e:
            logger.debug(f"  Cloud save skipped: {e}")

        # Scale shelter capacity to match district population
        # NDMA guideline: ~50 shelter places per 1000 population for emergencies
        total_beds = sum(s.bed_capacity for s in shelters)
        target_beds = max(total_beds, self.osm.population_2011 // 2)  # 50% of population
        if total_beds > 0 and total_beds < target_beds:
            scale = target_beds / total_beds
            for s in shelters:
                s.bed_capacity = int(s.bed_capacity * scale)
                s.water_capacity_liters_per_day = int(s.water_capacity_liters_per_day * scale)
                s.healthcare_beds_per_hour = max(10, s.bed_capacity // 20)
            logger.info(f"  Scaled shelter beds from {total_beds} to {sum(s.bed_capacity for s in shelters)} (target: {target_beds})")

        # Store for road segment mapping
        self._current_habitations = habitations
        self._current_shelters = shelters

        # ================================================================
        # Phase 3: Build road network
        # ================================================================
        road_segments = []
        try:
            road_graph = self.osm.fetch_road_network()
            raw_segments = self.osm._road_graph_to_segments(road_graph)
            road_segments = self._convert_road_segments(raw_segments)
            logger.info(f"  Roads: {len(road_segments)} segments from OSM")
        except Exception as e:
            logger.warning(f"  OSM road fetch failed: {e}")

        # ================================================================
        # Phase 4: Fallback connectivity
        # ================================================================
        if not road_segments:
            road_segments = self._build_connectivity_roads(habitations, shelters)
            logger.info(f"  Fallback roads: {len(road_segments)} straight-line connections")

        # Apply population buffer (edge 5.6)
        for h in habitations:
            buffered_pop = int(h.population_estimate * (1 + self.population_buffer))
            h.population_estimate = buffered_pop

        graph = CapacityGraph(
            habitations=habitations,
            shelters=shelters,
            road_segments=road_segments,
        )

        logger.info(f"\n  Final capacity graph:")
        logger.info(f"    Habitations: {len(habitations)} (total pop: {sum(h.population_estimate for h in habitations):,})")
        logger.info(f"    Shelters: {len(shelters)} (total beds: {sum(s.bed_capacity for s in shelters):,})")
        logger.info(f"    Road segments: {len(road_segments)}")

        return graph

    # ------------------------------------------------------------------
    # Hazard zones (from NDMA/Bhuvan)
    # ------------------------------------------------------------------
    def load_hazard_zones(self) -> list[dict]:
        """Load real hazard zone data from NDMA/Bhuvan/NDEM sources."""
        logger.info(f"Loading hazard zones for {self.district}...")
        zones = self.ndma.fetch_all_hazard_zones(bbox_filter=True)
        logger.info(f"  Total hazard zones: {len(zones)}")
        return zones

    # ------------------------------------------------------------------
    # Rainfall telemetry
    # ------------------------------------------------------------------
    def load_rainfall(self) -> list[dict]:
        """Load current/recent rainfall data from IMD."""
        logger.info(f"Loading rainfall data for {self.district}...")
        readings = self.rainfall.fetch_current_rainfall()
        logger.info(f"  Total rainfall readings: {len(readings)}")
        return readings

    def load_heavy_rain_scenario(self, intensity: float = 80.0) -> list[dict]:
        """Generate a heavy rainfall scenario for demo."""
        return self.rainfall.generate_heavy_rain_scenario(intensity)

    def load_historical_event(self, event_date: str) -> list[dict]:
        """Load rainfall for a historical disaster event."""
        return self.rainfall.get_historical_rainfall_for_event(event_date)

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    def _convert_road_segments(self, raw_segments: list[dict]) -> list[RoadSegment]:
        """Convert OSM road segments to our RoadSegment model."""
        segments = []
        node_counter = 0

        # Build a node → ID mapping
        node_to_id: dict[tuple[float, float], str] = {}

        def get_node_id(lat: float, lon: float) -> str:
            nonlocal node_counter
            key = (round(lat, 4), round(lon, 4))
            if key not in node_to_id:
                # Find nearest habitation or shelter
                node_id = self._find_nearest_node(lat, lon)
                if node_id:
                    node_to_id[key] = node_id
                else:
                    node_counter += 1
                    node_id = f"road-node-{node_counter:04d}"
                    node_to_id[key] = node_id
            return node_to_id[key]

        for seg in raw_segments:
            from_id = get_node_id(seg["from_lat"], seg["from_lon"])
            to_id = get_node_id(seg["to_lat"], seg["to_lon"])

            if from_id == to_id:
                continue  # Skip self-loops

            segments.append(RoadSegment(
                id=f"road-{len(segments)+1:04d}",
                from_node=from_id,
                to_node=to_id,
                distance_km=seg["distance_km"],
                travel_time_minutes=seg["travel_time_minutes"],
                capacity_vehicles_per_hour=seg["capacity_vehicles_per_hour"],
                people_throughput_per_hour=seg["people_throughput_per_hour"],
                status=RoadStatus.OPEN,
                damage_factor=1.0,
            ))

        return segments

    def _find_nearest_node(self, lat: float, lon: float) -> Optional[str]:
        """Find the nearest habitation or shelter to a road node."""
        best_dist = float("inf")
        best_id = None

        # This is called during road segment conversion, so we check
        # against already-converted habitations and shelters
        for hab in getattr(self, "_current_habitations", []):
            d = self._haversine(lat, lon, hab.location.lat, hab.location.lon)
            if d < best_dist:
                best_dist = d
                best_id = hab.id

        for shelter in getattr(self, "_current_shelters", []):
            d = self._haversine(lat, lon, shelter.location.lat, shelter.location.lon)
            if d < best_dist:
                best_dist = d
                best_id = shelter.id

        # If closest node is >5km away, this road isn't really connecting anything
        if best_dist > 5.0:
            return None

        return best_id

    def _convert_healthcare_to_shelters(
        self, facilities: list[dict]
    ) -> list[Shelter]:
        """Convert healthcare facility dicts to Shelter model objects."""
        shelters = []
        for i, fac in enumerate(facilities):
            district = fac.get("district", self.district)

            # Multi-hazard check (edge 5.12) — would check against hazard zones
            # For now, mark all as active
            shelters.append(Shelter(
                id=f"shelter-health-{i:04d}",
                name=fac["name"],
                location=Coordinates(lat=fac["lat"], lon=fac["lon"]),
                bed_capacity=fac.get("bed_capacity", 100),
                healthcare_beds_per_hour=fac.get("healthcare_beds_per_hour", 10),
                water_capacity_liters_per_day=fac.get("water_capacity_liters_per_day", 5000),
                is_accessible=True,
                shelter_type="healthcare",
                district=district,
                is_active=True,
            ))

        return shelters

    def _hc_dict_to_shelter(self, d: dict) -> Shelter:
        """Convert a healthcare/shelter dict to Shelter model."""
        return Shelter(
            id=f"shelter-{uuid.uuid4().hex[:8]}",
            name=d["name"],
            location=Coordinates(lat=d["lat"], lon=d["lon"]),
            bed_capacity=d.get("bed_capacity", 200),
            healthcare_beds_per_hour=d.get("healthcare_beds_per_hour", 10),
            water_capacity_liters_per_day=d.get("water_capacity_liters_per_day", 5000),
            is_accessible=d.get("is_accessible", True),
            shelter_type=d.get("type", "community_hall"),
            district=self.district,
            is_active=True,
        )

    def _convert_settlements(self, settlements: list[dict]) -> list[HabitationCluster]:
        """Convert OSM settlement dicts to HabitationCluster model objects."""
        clusters = []
        for s in settlements:
            clusters.append(HabitationCluster(
                id=f"hab-osm-{uuid.uuid4().hex[:8]}",
                name=s["name"],
                location=Coordinates(lat=s["lat"], lon=s["lon"]),
                population_estimate=s.get("population_estimate", 1000),
                population_confidence=0.7,  # OSM population estimates are rough
                has_accessible_population=True,
                accessible_population_fraction=0.12,
                district=self.district,
                block="",
            ))

        return clusters

    def _census_village_to_habitation(self, v: dict) -> HabitationCluster:
        """Convert a census village dict to HabitationCluster model."""
        return HabitationCluster(
            id=f"hab-census-{uuid.uuid4().hex[:8]}",
            name=v["name"],
            location=Coordinates(lat=v["lat"], lon=v["lon"]),
            population_estimate=v.get("population", 1000),
            population_confidence=0.85,  # census data is more reliable
            has_accessible_population=True,
            accessible_population_fraction=0.12,
            district=self.district,
            block=v.get("block", ""),
        )

    def _build_connectivity_roads(
        self, habitations: list[HabitationCluster], shelters: list[Shelter]
    ) -> list[RoadSegment]:
        """
        When OSM road network is unavailable, build minimum connectivity:
        connect each habitation to its nearest shelter.
        """
        segments = []
        for hab in habitations:
            # Find 2-3 nearest shelters
            distances = []
            for shelter in shelters:
                d = self._haversine(
                    hab.location.lat, hab.location.lon,
                    shelter.location.lat, shelter.location.lon,
                )
                distances.append((shelter.id, d))

            distances.sort(key=lambda x: x[1])

            for shelter_id, dist in distances[:3]:
                if dist > 100:  # don't connect if >100km away
                    continue

                # Estimate road distance as 1.4x straight-line (mountain roads)
                road_dist = dist * 1.4
                travel_min = road_dist / 30.0 * 60  # 30 km/h avg

                segments.append(RoadSegment(
                    id=f"road-{len(segments)+1:04d}",
                    from_node=hab.id,
                    to_node=shelter_id,
                    distance_km=round(road_dist, 1),
                    travel_time_minutes=round(travel_min, 1),
                    capacity_vehicles_per_hour=50,
                    people_throughput_per_hour=400,
                    status=RoadStatus.OPEN,
                    damage_factor=1.0,
                ))

        return segments

    def _generate_synthetic_habitations(self) -> list[HabitationCluster]:
        """Generate synthetic habitations from district population data."""
        # Chamoli major towns with approximate coordinates and populations
        SYNTHETIC_HABS = [
            {"name": "Gopeshwar", "lat": 30.40, "lon": 79.33, "pop": 25000},
            {"name": "Joshimath", "lat": 30.56, "lon": 79.57, "pop": 18000},
            {"name": "Karnaprayag", "lat": 30.27, "lon": 79.32, "pop": 15000},
            {"name": "Badrinath", "lat": 30.74, "lon": 79.49, "pop": 12000},
            {"name": "Nandprayag", "lat": 30.33, "lon": 79.32, "pop": 10000},
            {"name": "Chamoli", "lat": 30.45, "lon": 79.45, "pop": 8000},
            {"name": "Tharali", "lat": 30.25, "lon": 79.55, "pop": 6000},
            {"name": "Ghat", "lat": 30.38, "lon": 79.62, "pop": 5000},
            {"name": "Pokhri", "lat": 30.42, "lon": 79.60, "pop": 4000},
            {"name": "Raini", "lat": 30.47, "lon": 79.55, "pop": 3000},
            {"name": "Tapovan", "lat": 30.49, "lon": 79.58, "pop": 2500},
            {"name": "Auli", "lat": 30.60, "lon": 79.58, "pop": 2000},
        ]
        return [HabitationCluster(
            id=f"hab-synth-{i:03d}", name=h["name"],
            location=Coordinates(lat=h["lat"], lon=h["lon"]),
            population_estimate=h["pop"], population_confidence=0.7,
            has_accessible_population=True, accessible_population_fraction=0.12,
            district=self.district, block="",
        ) for i, h in enumerate(SYNTHETIC_HABS)]

    def _generate_synthetic_shelters(self) -> list[Shelter]:
        """Generate synthetic shelters scaled to district population."""
        SYNTHETIC_SHELTERS = [
            {"name": "District Hospital, Gopeshwar", "lat": 30.40, "lon": 79.33, "beds": 5000, "type": "hospital"},
            {"name": "Govt College, Joshimath", "lat": 30.56, "lon": 79.57, "beds": 4000, "type": "school"},
            {"name": "Community Hall, Karnaprayag", "lat": 30.27, "lon": 79.32, "beds": 4000, "type": "community_hall"},
            {"name": "ITBP Camp, Joshimath", "lat": 30.55, "lon": 79.58, "beds": 6000, "type": "govt_building"},
            {"name": "Tent Colony, Srinagar", "lat": 30.22, "lon": 79.18, "beds": 8000, "type": "tent"},
            {"name": "District Hospital, Srinagar", "lat": 30.23, "lon": 79.19, "beds": 5000, "type": "hospital"},
            {"name": "School Complex, Nandprayag", "lat": 30.33, "lon": 79.32, "beds": 3000, "type": "school"},
            {"name": "Govt Building, Badrinath", "lat": 30.74, "lon": 79.49, "beds": 3000, "type": "govt_building"},
        ]
        return [Shelter(
            id=f"shelter-synth-{i:03d}", name=s["name"],
            location=Coordinates(lat=s["lat"], lon=s["lon"]),
            bed_capacity=s["beds"], healthcare_beds_per_hour=max(10, s["beds"] // 50),
            water_capacity_liters_per_day=s["beds"] * 50,
            is_accessible=True, shelter_type=s["type"],
            district=self.district, is_active=True,
        ) for i, s in enumerate(SYNTHETIC_SHELTERS)]

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great-circle distance in km."""
        R = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
