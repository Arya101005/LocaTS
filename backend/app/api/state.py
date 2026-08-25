"""
Shared global state for all API routers.

CRITICAL: Routers MUST use `import backend.app.api.state as st`
and access as `st.graph_data`, NOT `from ... import graph_data`.
The direct import captures the initial None value and won't see updates.
"""

from __future__ import annotations
from typing import Optional
from backend.app.models.domain import (
    CapacityGraph, HazardConfidence, HazardType, LiveSensorReading,
    CrowdReport, OfflineReport, RelocationOrder, StaticHazardZone,
)
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine

graph_data: Optional[CapacityGraph] = None
graph_builder: Optional[CapacityGraphBuilder] = None
optimizer: Optional[OptimizationEngine] = None
shortest_paths: dict = {}
hazard_confidences: dict[str, HazardConfidence] = {}
static_zones: list[StaticHazardZone] = []
sensor_readings: list[LiveSensorReading] = []
crowd_reports: list[CrowdReport] = []
offline_reports: list[OfflineReport] = []
relocation_orders: list[RelocationOrder] = []


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def haversine(loc_a, loc_b) -> float:
    lat_a = loc_a.lat if hasattr(loc_a, "lat") else (loc_a.get("lat", 0) if isinstance(loc_a, dict) else 0)
    lon_a = loc_a.lon if hasattr(loc_a, "lon") else (loc_a.get("lon", 0) if isinstance(loc_a, dict) else 0)
    lat_b = loc_b.lat if hasattr(loc_b, "lat") else (loc_b.get("lat", 0) if isinstance(loc_b, dict) else 0)
    lon_b = loc_b.lon if hasattr(loc_b, "lon") else (loc_b.get("lon", 0) if isinstance(loc_b, dict) else 0)
    return _haversine(lat_a, lon_a, lat_b, lon_b)
