"""
OpenStreetMap data ingestion via direct Overpass API calls.

Uses httpx (which handles connections reliably) instead of osmnx's
urllib3 backend. Fetches roads, healthcare, schools, settlements,
and water bodies from OpenStreetMap for Indian districts.

Usage:
    from backend.app.data.ingestion.osm_ingester import OSMIngester
    ingester = OSMIngester("Chamoli")
    data = ingester.fetch_all()
"""

from __future__ import annotations

import logging
import math
from typing import Optional

import httpx
import networkx as nx

logger = logging.getLogger(__name__)

# Chamoli bboxes: corridor = main habitation valley, full = entire district
CHAMOLI_CORRIDOR = (30.22, 79.20, 30.60, 79.65)  # ~40km x 50km along Alaknanda valley
CHAMOLI_FULL = (30.05, 79.05, 30.95, 79.95)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_HEADERS = {"User-Agent": "LocaTS-SIH2026/1.0 (research; hackathon project)"}

DISTRICT_BBOXES: dict[str, dict] = {
    "Chamoli": {
        "state": "Uttarakhand",
        "bbox": CHAMOLI_FULL,
        "corridor": CHAMOLI_CORRIDOR,
        "center": (30.45, 79.45),
        "population_2011": 370000,
    },
    "Almora": {
        "state": "Uttarakhand",
        "bbox": (29.45, 79.15, 29.95, 79.75),
        "center": (29.65, 79.45),
        "population_2011": 621927,
    },
    "Pithoragarh": {
        "state": "Uttarakhand",
        "bbox": (29.70, 80.05, 30.50, 81.00),
        "center": (30.10, 80.50),
        "population_2011": 483439,
    },
    "Uttarkashi": {
        "state": "Uttarakhand",
        "bbox": (30.40, 78.10, 31.15, 79.10),
        "center": (30.75, 78.60),
        "population_2011": 330911,
    },
    "Rudraprayag": {
        "state": "Uttarakhand",
        "bbox": (30.20, 78.75, 30.65, 79.25),
        "center": (30.40, 78.98),
        "population_2011": 242285,
    },
}


class OSMIngester:
    """Fetches real OpenStreetMap data via direct Overpass API calls."""

    def __init__(
        self,
        district: str = "Chamoli",
        state: str = "Uttarakhand",
        use_corridor: bool = True,
    ):
        self.district = district
        self.state = state
        info = DISTRICT_BBOXES.get(district, {})
        if use_corridor and "corridor" in info:
            self.bbox = info["corridor"]
        else:
            self.bbox = info.get("bbox", CHAMOLI_FULL)
        self.full_bbox = info.get("bbox", self.bbox)
        self.center = info.get("center", (30.45, 79.45))
        self.population_2011 = info.get("population_2011", 370000)
        self.client = httpx.Client(timeout=120, follow_redirects=True)

    def close(self):
        self.client.close()

    # ------------------------------------------------------------------
    # Overpass API query helpers
    # ------------------------------------------------------------------
    def _overpass_query(self, query: str) -> dict:
        """Execute an Overpass API query and return JSON."""
        try:
            resp = self.client.post(
                OVERPASS_URL,
                data={"data": query},
                headers=OVERPASS_HEADERS,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"  Overpass query failed: {e}")
            return {"elements": []}

    def _bbox_str(self) -> str:
        """Format bbox for Overpass (south,west,north,east)."""
        return f"{self.bbox[0]},{self.bbox[1]},{self.bbox[2]},{self.bbox[3]}"

    # ------------------------------------------------------------------
    # Road network
    # ------------------------------------------------------------------
    def fetch_road_network(self) -> nx.MultiDiGraph:
        """Fetch the driveable road network for the district."""
        bbox = self._bbox_str()
        logger.info(f"Fetching road network for {self.district} (bbox: {bbox})...")

        query = f"""
[out:json][timeout:90];
(
  way({bbox})[highway];
);
out body;
>;
out skel qt;
"""
        data = self._overpass_query(query)
        elements = data.get("elements", [])

        if not elements:
            logger.warning("  No road data returned from Overpass")
            return nx.MultiDiGraph()

        # Build graph from OSM elements
        nodes = {}
        ways = []
        for el in elements:
            if el["type"] == "node":
                nodes[el["id"]] = {"x": el["lon"], "y": el["lat"]}
            elif el["type"] == "way":
                ways.append(el)

        G = nx.MultiDiGraph()
        for nid, ndata in nodes.items():
            G.add_node(nid, **ndata)

        for way in ways:
            nds = way.get("nodes", [])
            tags = way.get("tags", {})
            highway = tags.get("highway", "unclassified")
            length = 0

            for i in range(len(nds) - 1):
                u, v = nds[i], nds[i + 1]
                if u in nodes and v in nodes:
                    # Estimate length from coordinates
                    p1 = nodes[u]
                    p2 = nodes[v]
                    d = self._haversine(p1["y"], p1["x"], p2["y"], p2["x"])
                    length += d

                    capacity_map = {
                        "motorway": (200, 2000), "trunk": (150, 1500),
                        "primary": (120, 1200), "secondary": (80, 800),
                        "tertiary": (50, 500), "residential": (30, 300),
                        "unclassified": (20, 200), "service": (10, 100),
                    }
                    veh_cap, ppl_cap = capacity_map.get(highway, (40, 400))
                    travel_min = d / 30.0 * 60  # 30 km/h mountain avg

                    edge_data = {
                        "distance_km": round(d, 3),
                        "travel_time_minutes": round(travel_min, 1),
                        "highway_type": highway,
                        "capacity_vehicles_per_hour": veh_cap,
                        "people_throughput_per_hour": ppl_cap,
                    }
                    G.add_edge(u, v, **edge_data)
                    G.add_edge(v, u, **edge_data)

        logger.info(
            f"  Got {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"
        )
        return G

    # ------------------------------------------------------------------
    # Healthcare facilities
    # ------------------------------------------------------------------
    def fetch_healthcare_facilities(self) -> list[dict]:
        """Fetch hospitals, PHCs, CHCs from OSM."""
        bbox = self._bbox_str()
        logger.info(f"Fetching healthcare facilities for {self.district}...")

        query = f"""
[out:json][timeout:60];
(
  node({bbox})["amenity"="hospital"];
  node({bbox})["amenity"="clinic"];
  node({bbox})["healthcare"];
  way({bbox})["amenity"="hospital"];
  way({bbox})["amenity"="clinic"];
);
out center body;
"""
        data = self._overpass_query(query)
        elements = data.get("elements", [])

        facilities = []
        for el in elements:
            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            if not lat or not lon:
                continue
            tags = el.get("tags", {})
            name = tags.get("name", f"Healthcare at {lat:.4f},{lon:.4f}")
            beds_tag = tags.get("beds")
            # OSM rarely has beds tag for Indian healthcare; assign realistic defaults
            facility_type = tags.get("amenity", tags.get("healthcare", "clinic"))
            if beds_tag:
                beds = int(beds_tag)
            elif facility_type == "hospital":
                beds = 100  # District hospitals typically 100+ beds
            elif facility_type in ("clinic", "healthcare"):
                beds = 30   # PHC/CHC typically 10-30 beds
            else:
                beds = 50   # Default for unknown healthcare

            facilities.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "type": facility_type,
                "bed_capacity": beds,
                "healthcare_beds_per_hour": max(5, beds // 5),
                "water_capacity_liters_per_day": beds * 50,
            })

        logger.info(f"  Found {len(facilities)} healthcare facilities")
        return facilities

    # ------------------------------------------------------------------
    # Schools and community buildings (potential shelters)
    # ------------------------------------------------------------------
    def fetch_potential_shelters(self) -> list[dict]:
        """Fetch schools, community halls, govt buildings."""
        bbox = self._bbox_str()
        logger.info(f"Fetching potential shelters for {self.district}...")

        query = f"""
[out:json][timeout:60];
(
  node({bbox})["amenity"="school"];
  way({bbox})["amenity"="school"];
  node({bbox})["amenity"="community_centre"];
  way({bbox})["amenity"="community_centre"];
  node({bbox})["amenity"="townhall"];
);
out center body;
"""
        data = self._overpass_query(query)
        elements = data.get("elements", [])

        shelters = []
        for el in elements:
            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            if not lat or not lon:
                continue
            tags = el.get("tags", {})
            name = tags.get("name", f"Shelter at {lat:.4f},{lon:.4f}")
            building = tags.get("building", tags.get("amenity", "unknown"))

            # Schools/community halls as emergency shelters
            is_school = building in ("school", "education") or tags.get("amenity") == "school"
            is_community = building in ("community_centre", "public") or tags.get("amenity") in ("community_centre", "townhall")
            if is_school:
                bed_cap = 300   # School hall can hold ~300 people
            elif is_community:
                bed_cap = 500   # Community hall larger
            else:
                bed_cap = 200   # Generic building

            shelters.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "type": building,
                "bed_capacity": bed_cap,
                "healthcare_beds_per_hour": 10,
                "water_capacity_liters_per_day": bed_cap * 10,
                "is_accessible": True,
            })

        logger.info(f"  Found {len(shelters)} potential shelter buildings")
        return shelters

    # ------------------------------------------------------------------
    # Settlements / villages
    # ------------------------------------------------------------------
    def fetch_settlements(self) -> list[dict]:
        """Fetch named settlements and villages."""
        bbox = self._bbox_str()
        logger.info(f"Fetching settlements for {self.district}...")

        query = f"""
[out:json][timeout:60];
(
  node({bbox})["place"="village"];
  node({bbox})["place"="hamlet"];
  node({bbox})["place"="town"];
);
out body;
"""
        data = self._overpass_query(query)
        elements = data.get("elements", [])

        settlements = []
        for el in elements:
            tags = el.get("tags", {})
            name = tags.get("name", "Unnamed")
            place_type = tags.get("place", "village")
            population = tags.get("population")

            if population:
                try:
                    pop = int(population.replace(",", ""))
                except (ValueError, AttributeError):
                    pop = self._estimate_population(place_type)
            else:
                pop = self._estimate_population(place_type)

            settlements.append({
                "name": name,
                "lat": el["lat"],
                "lon": el["lon"],
                "place_type": place_type,
                "population_estimate": pop,
            })

        logger.info(f"  Found {len(settlements)} settlements")
        return settlements

    # ------------------------------------------------------------------
    # Water bodies
    # ------------------------------------------------------------------
    def fetch_water_bodies(self) -> list[dict]:
        """Fetch rivers, streams, and lakes for flood context."""
        bbox = self._bbox_str()
        logger.info(f"Fetching water bodies for {self.district}...")

        query = f"""
[out:json][timeout:60];
(
  way({bbox})["waterway"="river"];
  way({bbox})["waterway"="stream"];
  relation({bbox})["natural"="water"];
);
out center body;
"""
        data = self._overpass_query(query)
        elements = data.get("elements", [])

        water = []
        for el in elements:
            lat = el.get("lat") or (el.get("center", {}).get("lat"))
            lon = el.get("lon") or (el.get("center", {}).get("lon"))
            if not lat or not lon:
                continue
            tags = el.get("tags", {})
            name = tags.get("name", "Unnamed water body")
            wtype = tags.get("waterway", tags.get("natural", "water"))

            water.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "type": wtype,
            })

        logger.info(f"  Found {len(water)} water bodies")
        return water

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------
    def fetch_all(self) -> dict:
        """Fetch all available OSM data for the district."""
        result = {
            "district": self.district,
            "state": self.state,
            "bbox": self.bbox,
            "population_2011": self.population_2011,
        }

        try:
            road_graph = self.fetch_road_network()
            result["road_graph"] = road_graph
            result["road_segments"] = self._road_graph_to_segments(road_graph)
        except Exception as e:
            logger.error(f"Road network fetch failed: {e}")
            result["road_segments"] = []

        result["healthcare_facilities"] = self.fetch_healthcare_facilities()
        result["potential_shelters"] = self.fetch_potential_shelters()
        result["settlements"] = self.fetch_settlements()
        result["water_bodies"] = self.fetch_water_bodies()

        return result

    # ------------------------------------------------------------------
    # Convert OSM graph to our segment format
    # ------------------------------------------------------------------
    def _road_graph_to_segments(self, G: nx.MultiDiGraph) -> list[dict]:
        """Convert a NetworkX graph to road segment dicts."""
        segments = []
        seen = set()
        for u, v, data in G.edges(data=True):
            edge_key = tuple(sorted([u, v]))
            if edge_key in seen:
                continue
            seen.add(edge_key)

            u_data = G.nodes[u]
            v_data = G.nodes[v]

            segments.append({
                "from_lat": u_data["y"],
                "from_lon": u_data["x"],
                "to_lat": v_data["y"],
                "to_lon": v_data["x"],
                "distance_km": data.get("distance_km", 0),
                "travel_time_minutes": data.get("travel_time_minutes", 0),
                "highway_type": data.get("highway_type", "unknown"),
                "capacity_vehicles_per_hour": data.get("capacity_vehicles_per_hour", 40),
                "people_throughput_per_hour": data.get("people_throughput_per_hour", 400),
                "osm_from": u,
                "osm_to": v,
            })

        logger.info(f"  Converted {len(segments)} road segments")
        return segments

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _estimate_population(self, place_type: str) -> int:
        estimates = {"city": 50000, "town": 15000, "village": 2000, "hamlet": 300}
        return estimates.get(place_type, 1000)

    def _estimate_shelter_beds(self) -> int:
        """Estimate total shelter beds needed for the district.
        Based on NDMA guideline: 50 shelter places per 1000 population.
        We scale discovered shelters proportionally."""
        return max(100, self.population_2011 // 2)  # ~50% of population as shelter capacity

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
