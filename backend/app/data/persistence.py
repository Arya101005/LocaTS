"""
Write-through persistence layer for LocaTS.

Wraps the in-memory global state in main.py with Supabase read/write.
On startup: loads from Supabase → populates in-memory.
On mutation: writes to Supabase AND updates in-memory.

This means existing code keeps working without modification,
but data now persists across restarts.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class PersistenceLayer:
    """
    Write-through cache: in-memory state + Supabase PostGIS.
    
    Usage:
        p = PersistenceLayer()
        p.save_habitation(hab_dict)
        habitations = p.load_all_habitations()
    """

    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL", "")
        self.key = os.environ.get("SUPABASE_KEY", "")
        self._client = None

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)

    @property
    def client(self):
        if self._client is None and self.is_configured:
            try:
                from supabase import create_client
                self._client = create_client(self.url, self.key)
                logger.info("  Supabase connected for persistence")
            except Exception as e:
                logger.warning(f"  Supabase connection failed: {e}")
        return self._client

    def _table(self, name: str):
        if self.client:
            return self.client.table(name)
        return None

    # ------------------------------------------------------------------
    # Habitations
    # ------------------------------------------------------------------
    def save_habitation(self, hab: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "id": hab.get("id", ""),
                "district": hab.get("district", ""),
                "name": hab.get("name", ""),
                "lat": hab.get("lat", 0) or (hab.get("location", {}).get("lat", 0) if isinstance(hab.get("location"), dict) else 0),
                "lon": hab.get("lon", 0) or (hab.get("location", {}).get("lon", 0) if isinstance(hab.get("location"), dict) else 0),
                "population_estimate": hab.get("population_estimate", 0),
                "data": json.dumps(hab),
            }
            self._table("habitations").upsert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"  Save habitation failed: {e}")
            return False

    def load_all_habitations(self) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("habitations").select("*").execute()
            rows = result.data or []
            # Reconstruct domain objects from stored data
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    if not data:
                        # Reconstruct from flat columns
                        data = {
                            "id": row["id"],
                            "name": row["name"],
                            "location": {"lat": row["lat"], "lon": row["lon"]},
                            "population_estimate": row["population_estimate"],
                            "district": row.get("district", ""),
                        }
                    out.append(data)
                except Exception:
                    pass
            logger.info(f"  Loaded {len(out)} habitations from Supabase")
            return out
        except Exception as e:
            logger.warning(f"  Load habitations failed: {e}")
            return []

    def clear_habitations(self) -> bool:
        if not self.client:
            return False
        try:
            self._table("habitations").delete().neq("id", "").execute()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Shelters
    # ------------------------------------------------------------------
    def save_shelter(self, shelter: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "id": shelter.get("id", ""),
                "district": shelter.get("district", ""),
                "name": shelter.get("name", ""),
                "lat": shelter.get("lat", 0) or (shelter.get("location", {}).get("lat", 0) if isinstance(shelter.get("location"), dict) else 0),
                "lon": shelter.get("lon", 0) or (shelter.get("location", {}).get("lon", 0) if isinstance(shelter.get("location"), dict) else 0),
                "bed_capacity": shelter.get("bed_capacity", 0),
                "data": json.dumps(shelter),
            }
            self._table("shelters").upsert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"  Save shelter failed: {e}")
            return False

    def load_all_shelters(self) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("shelters").select("*").execute()
            rows = result.data or []
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    if not data:
                        data = {
                            "id": row["id"],
                            "name": row["name"],
                            "location": {"lat": row["lat"], "lon": row["lon"]},
                            "bed_capacity": row["bed_capacity"],
                            "district": row.get("district", ""),
                        }
                    out.append(data)
                except Exception:
                    pass
            logger.info(f"  Loaded {len(out)} shelters from Supabase")
            return out
        except Exception as e:
            logger.warning(f"  Load shelters failed: {e}")
            return []

    def clear_shelters(self) -> bool:
        if not self.client:
            return False
        try:
            self._table("shelters").delete().neq("id", "").execute()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Roads
    # ------------------------------------------------------------------
    def save_road(self, road: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "id": road.get("id", ""),
                "district": road.get("district", ""),
                "from_node": road.get("from_node", ""),
                "to_node": road.get("to_node", ""),
                "distance_km": road.get("distance_km", 0),
                "data": json.dumps(road),
            }
            self._table("road_segments").upsert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"  Save road failed: {e}")
            return False

    def load_all_roads(self) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("road_segments").select("*").execute()
            rows = result.data or []
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    if not data:
                        data = {
                            "id": row["id"],
                            "from_node": row["from_node"],
                            "to_node": row["to_node"],
                            "distance_km": row["distance_km"],
                            "district": row.get("district", ""),
                        }
                    out.append(data)
                except Exception:
                    pass
            logger.info(f"  Loaded {len(out)} roads from Supabase")
            return out
        except Exception as e:
            logger.warning(f"  Load roads failed: {e}")
            return []

    def clear_roads(self) -> bool:
        if not self.client:
            return False
        try:
            self._table("road_segments").delete().neq("id", "").execute()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Hazard zones
    # ------------------------------------------------------------------
    def save_hazard_zone(self, zone: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "id": zone.get("id", ""),
                "district": zone.get("district", ""),
                "hazard_type": zone.get("hazard_type", ""),
                "severity": zone.get("severity", 0),
                "data": json.dumps(zone),
            }
            self._table("hazard_zones").upsert(row).execute()
            return True
        except Exception as e:
            logger.warning(f"  Save hazard zone failed: {e}")
            return False

    def load_all_hazard_zones(self) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("hazard_zones").select("*").execute()
            rows = result.data or []
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    if not data:
                        data = {
                            "id": row["id"],
                            "hazard_type": row["hazard_type"],
                            "severity": row["severity"],
                            "district": row.get("district", ""),
                        }
                    out.append(data)
                except Exception:
                    pass
            logger.info(f"  Loaded {len(out)} hazard zones from Supabase")
            return out
        except Exception as e:
            logger.warning(f"  Load hazard zones failed: {e}")
            return []

    def clear_hazard_zones(self) -> bool:
        if not self.client:
            return False
        try:
            self._table("hazard_zones").delete().neq("id", "").execute()
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Evacuees / Family reunification
    # ------------------------------------------------------------------
    def save_evacuee(self, evacuee: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "evacuee_id": evacuee.get("evacuee_id", evacuee.get("id", "")),
                "name_hash": evacuee.get("name_hash", ""),
                "shelter_id": evacuee.get("shelter_id", evacuee.get("registered_shelter_id", "")),
                "status": evacuee.get("status", "safe"),
                "data": json.dumps(evacuee),
            }
            self._table("evacuees").upsert(row, on_conflict="evacuee_id").execute()
            return True
        except Exception as e:
            logger.warning(f"  Save evacuee failed: {e}")
            return False

    def load_evacuees(self, shelter_id: Optional[str] = None) -> list[dict]:
        if not self.client:
            return []
        try:
            q = self._table("evacuees").select("*")
            if shelter_id:
                q = q.eq("shelter_id", shelter_id)
            result = q.execute()
            rows = result.data or []
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    if not data:
                        data = {
                            "evacuee_id": row["evacuee_id"],
                            "name_hash": row.get("name_hash", ""),
                            "shelter_id": row.get("shelter_id", ""),
                            "status": row.get("status", "safe"),
                        }
                    out.append(data)
                except Exception:
                    pass
            return out
        except Exception as e:
            logger.warning(f"  Load evacuees failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Relocation orders (audit trail)
    # ------------------------------------------------------------------
    def save_relocation_order(self, order: dict) -> bool:
        if not self.client:
            return False
        try:
            row = {
                "order_id": order.get("order_id", ""),
                "district": order.get("district", ""),
                "audit_hash": order.get("audit_hash", ""),
                "data": json.dumps(order),
            }
            self._table("relocation_orders").upsert(row, on_conflict="order_id").execute()
            return True
        except Exception as e:
            logger.warning(f"  Save relocation order failed: {e}")
            return False

    def load_relocation_orders(self, limit: int = 50) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("relocation_orders").select("*").order("created_at", desc=True).limit(limit).execute()
            rows = result.data or []
            out = []
            for row in rows:
                try:
                    data = json.loads(row.get("data", "{}")) if isinstance(row.get("data"), str) else row.get("data", {})
                    out.append(data)
                except Exception:
                    pass
            return out
        except Exception as e:
            logger.warning(f"  Load relocation orders failed: {e}")
            return []

    def load_crowd_reports(self, limit: int = 100) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("crowd_reports").select("*").order("timestamp", desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"  Load crowd reports failed: {e}")
            return []

    def load_evacuees(self) -> list[dict]:
        if not self.client:
            return []
        try:
            result = self._table("evacuees").select("*").execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"  Load evacuees failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Bulk operations for startup seeding
    # ------------------------------------------------------------------
    def seed_from_graph(self, graph_data, static_zones: list, sensor_readings: list) -> dict:
        """
        Save the current in-memory state to Supabase.
        Called after data is loaded from sample/real sources.
        """
        stats = {"habitations": 0, "shelters": 0, "roads": 0, "zones": 0, "sensors": 0}

        if not self.is_configured:
            return stats

        # Save habitations
        for h in (graph_data.habitations if graph_data else []):
            hab_dict = {
                "id": h.id,
                "name": h.name,
                "location": {"lat": h.location.lat if hasattr(h.location, 'lat') else h.location.get("lat", 0),
                             "lon": h.location.lon if hasattr(h.location, 'lon') else h.location.get("lon", 0)},
                "population_estimate": h.population_estimate,
                "district": getattr(h, "district", ""),
            }
            if self.save_habitation(hab_dict):
                stats["habitations"] += 1

        # Save shelters
        for s in (graph_data.shelters if graph_data else []):
            shelter_dict = {
                "id": s.id,
                "name": s.name,
                "location": {"lat": s.location.lat if hasattr(s.location, 'lat') else s.location.get("lat", 0),
                             "lon": s.location.lon if hasattr(s.location, 'lon') else s.location.get("lon", 0)},
                "bed_capacity": s.bed_capacity,
                "district": getattr(s, "district", ""),
                "is_active": getattr(s, "is_active", True),
                "is_accessible": getattr(s, "is_accessible", True),
            }
            if self.save_shelter(shelter_dict):
                stats["shelters"] += 1

        # Save roads
        for r in (graph_data.road_segments if graph_data else []):
            road_dict = {
                "id": r.id,
                "from_node": r.from_node,
                "to_node": r.to_node,
                "distance_km": r.distance_km,
                "travel_time_minutes": r.travel_time_minutes,
                "capacity_vehicles_per_hour": r.capacity_vehicles_per_hour,
                "people_throughput_per_hour": r.people_throughput_per_hour,
                "status": r.status.value if hasattr(r.status, 'value') else r.status,
                "district": getattr(r, "district", ""),
            }
            if self.save_road(road_dict):
                stats["roads"] += 1

        # Save hazard zones
        for z in static_zones:
            zone_dict = {
                "id": z.id,
                "hazard_type": z.hazard_type.value if hasattr(z.hazard_type, 'value') else z.hazard_type,
                "severity": z.severity,
                "radius_km": z.radius_km,
                "center": {"lat": z.center.lat if hasattr(z.center, 'lat') else z.center.get("lat", 0),
                           "lon": z.center.lon if hasattr(z.center, 'lon') else z.center.get("lon", 0)},
                "district": getattr(z, "district", "Chamoli"),
                "source": getattr(z, "source", ""),
            }
            if self.save_hazard_zone(zone_dict):
                stats["zones"] += 1

        logger.info(f"  Seeded Supabase: {stats}")
        return stats

    def load_to_graph(self):
        """
        Load data from Supabase and return as raw dicts.
        The caller (main.py) converts these to domain objects.
        """
        if not self.is_configured:
            return None

        habitations = self.load_all_habitations()
        shelters = self.load_all_shelters()
        roads = self.load_all_roads()
        zones = self.load_all_hazard_zones()

        if not habitations and not shelters:
            logger.info("  Supabase empty — using sample data")
            return None

        logger.info(f"  Loaded from Supabase: {len(habitations)} habs, {len(shelters)} shelters, {len(roads)} roads, {len(zones)} zones")
        return {
            "habitations": habitations,
            "shelters": shelters,
            "roads": roads,
            "hazard_zones": zones,
        }


# Singleton
persistence = PersistenceLayer()
