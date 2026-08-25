"""
Capacity Graph Router
=====================
Endpoints for loading and managing the capacity graph
(habitations, shelters, road network).

API Routes:
  POST /api/capacity/load       — Load graph from request body
  POST /api/capacity/load-real  — Load real geographic data
  GET  /api/capacity/summary    — Shelter capacity summary
  GET  /api/capacity/graph      — Full graph data
  GET  /api/capacity/names      — ID→name lookup map
  POST /api/road/update         — Update road status
  POST /api/shelter/update      — Update shelter occupancy
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.state import (
    graph_data, graph_builder, shortest_paths,
    static_zones, sensor_readings, optimizer,
)
from backend.app.models.domain import (
    CapacityGraph, RoadStatus, StaticHazardZone,
    HazardType, LiveSensorReading,
)
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine

router = APIRouter(tags=["capacity"])


# --- Schemas ---

class RoadStatusUpdate(BaseModel):
    road_id: str
    new_status: RoadStatus
    damage_factor: float = Field(default=1.0, ge=0, le=1)


class ShelterCapacityUpdate(BaseModel):
    shelter_id: str
    beds_occupied: int = Field(ge=0)


# --- Endpoints ---

@router.post("/api/capacity/load")
async def load_capacity_graph(graph: CapacityGraph):
    """Load the full capacity graph (habitations, shelters, roads)."""
    import backend.app.api.state as st
    st.graph_data = graph
    st.graph_builder = CapacityGraphBuilder(population_safety_margin=0.15)
    st.graph_data = st.graph_builder.build(st.graph_data)
    st.optimizer = OptimizationEngine(time_budget_seconds=30.0)
    st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)
    return {
        "status": "loaded",
        "habitations": len(st.graph_data.habitations),
        "shelters": len(st.graph_data.shelters),
        "road_segments": len(st.graph_data.road_segments),
        "capacity_summary": st.graph_builder.get_shelter_capacity_summary(st.graph_data),
    }


@router.post("/api/capacity/load-real")
async def load_real_data(district: str = "Chamoli", state: str = "Uttarakhand"):
    """Load REAL geographic data from OSM, NDMA/Bhuvan, and india-geodata."""
    import backend.app.api.state as st
    try:
        from backend.app.data.ingestion.real_data_loader import RealDataLoader
        from backend.app.data.ingestion.ndma_ingester import NDMAIngester
        from backend.app.data.ingestion.rainfall_ingester import RainfallIngester

        loader = RealDataLoader(district=district, state=state)
        try:
            st.graph_data = loader.load_capacity_graph()
        finally:
            loader.close()

        ndma = NDMAIngester(district=district)
        try:
            for z in ndma.fetch_all_hazard_zones():
                st.static_zones.append(StaticHazardZone(
                    id=z["id"], hazard_type=HazardType(z["hazard_type"]),
                    severity=z["severity"], zone_type=z["zone_type"],
                    center={"lat": z["center_lat"], "lon": z["center_lon"]},
                    radius_km=z["radius_km"],
                ))
        finally:
            ndma.close()

        rainfall = RainfallIngester(district=district)
        try:
            for r in rainfall.fetch_current_rainfall():
                st.sensor_readings.append(LiveSensorReading(
                    source=r.get("source", "imd"),
                    location={"lat": r["lat"], "lon": r["lon"]}, value=r["value"],
                ))
        finally:
            rainfall.close()

        st.graph_builder = CapacityGraphBuilder(population_safety_margin=0.15)
        st.graph_data = st.graph_builder.build(st.graph_data)
        st.optimizer = OptimizationEngine(time_budget_seconds=30.0)
        st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)

        return {
            "status": "loaded", "district": district, "state": state,
            "habitations": len(st.graph_data.habitations),
            "shelters": len(st.graph_data.shelters),
            "road_segments": len(st.graph_data.road_segments),
            "hazard_zones": len(st.static_zones),
            "sensor_readings": len(st.sensor_readings),
            "capacity_summary": st.graph_builder.get_shelter_capacity_summary(st.graph_data),
        }
    except Exception as e:
        raise HTTPException(500, f"Real data loading failed: {e}")


@router.get("/api/capacity/summary")
async def get_capacity_summary():
    """Get a summary of shelter capacity."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    if not graph_builder:
        raise HTTPException(500, "Graph builder not initialized.")
    return graph_builder.get_shelter_capacity_summary(graph_data)


@router.get("/api/capacity/graph")
async def get_graph_data():
    """Get the full capacity graph data."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    return graph_data.model_dump()


@router.get("/api/capacity/names")
async def get_name_map():
    """Return ID→name lookup map for all loaded entities."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    names = {}
    for h in graph_data.habitations:
        names[h.id] = h.name
    for s in graph_data.shelters:
        names[s.id] = s.name
    return {"names": names}


@router.post("/api/road/update")
async def update_road_status(update: RoadStatusUpdate):
    """Update road status — triggers graph rebuild for re-optimization."""
    import backend.app.api.state as st
    if not st.graph_data:
        raise HTTPException(400, "No graph loaded.")
    found = False
    for road in st.graph_data.road_segments:
        if road.id == update.road_id:
            road.status = update.new_status
            road.damage_factor = update.damage_factor
            found = True
            break
    if not found:
        raise HTTPException(404, f"Road {update.road_id} not found.")
    if st.graph_builder:
        st.graph_data = st.graph_builder.build(st.graph_data)
        st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)
    return {"status": "updated", "road_id": update.road_id,
            "note": "Graph rebuilt. Call /api/optimize/re-solve to re-optimize."}


@router.post("/api/shelter/update")
async def update_shelter_capacity(update: ShelterCapacityUpdate):
    """Update shelter occupancy."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    for shelter in graph_data.shelters:
        if shelter.id == update.shelter_id:
            shelter.beds_occupied = update.beds_occupied
            return {"status": "updated", "shelter_id": update.shelter_id,
                    "beds_occupied": update.beds_occupied}
    raise HTTPException(404, f"Shelter {update.shelter_id} not found.")
