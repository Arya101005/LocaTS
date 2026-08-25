"""
Optimization Router
===================
Endpoints for the OR-Tools relocation optimizer: solving,
re-solving, expanded capacity, and what-if scenarios.

API Routes:
  POST /api/optimize/solve      — Run initial optimization
  POST /api/optimize/re-solve   — Rolling-horizon re-optimization
  POST /api/optimize/expanded   — Re-solve with nearby districts
  POST /api/whatif              — What-if scenario simulation
  GET  /api/nearby-capacity     — Find overflow shelter capacity
"""

from __future__ import annotations
import copy
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import backend.app.api.state as st
from backend.app.models.domain import (
    AlertLevel, RelocationOrder, RoadStatus,
    CapacityGraph, HazardType,
)
from backend.app.hazard_fusion.fusion import fuse_hazard_scores
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine

router = APIRouter(tags=["optimizer"])


# --- Schemas ---

class SolveRequest(BaseModel):
    time_budget_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    population_safety_margin: float = Field(default=0.15, ge=0.0, le=0.50)


class ReOptimizeRequest(BaseModel):
    time_budget_seconds: float = Field(default=30.0, ge=1.0, le=300.0)


class WhatIfScenario(BaseModel):
    rainfall_multiplier: float = Field(default=1.0, ge=0.1, le=5.0)
    block_road_ids: list[str] = Field(default_factory=list)
    disable_shelter_ids: list[str] = Field(default_factory=list)
    population_multiplier: float = Field(default=1.0, ge=0.5, le=3.0)


def _build_urgency_weights() -> tuple[dict, dict]:
    """Extract urgency weights and hazard scores from current confidences."""
    urgency, scores = {}, {}
    for key, conf in st.hazard_confidences.items():
        hid = key.split(":")[0]
        if conf.alert_level in (AlertLevel.EVACUATE, AlertLevel.RELOCATE):
            urgency[hid] = max(urgency.get(hid, 1.0), 1.0 + conf.confidence * 2.0)
        scores[hid] = conf.confidence
    return urgency, scores


# --- Endpoints ---

@router.post("/api/optimize/solve")
async def solve_relocation(req: SolveRequest):
    """Solve the full relocation optimization problem."""
    if not st.graph_data or not st.optimizer:
        raise HTTPException(400, "Graph and optimizer must be loaded first.")
    if st.graph_builder:
        st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)
    urgency, scores = _build_urgency_weights()
    st.optimizer.time_budget_seconds = req.time_budget_seconds
    result = st.optimizer.solve(st.graph_data, st.shortest_paths, urgency, scores)
    return result.model_dump()


@router.post("/api/optimize/re-solve")
async def re_solve_relocation(req: ReOptimizeRequest):
    """Rolling-horizon re-optimization with audit trail (edge 5.5)."""
    if not st.graph_data or not st.optimizer:
        raise HTTPException(400, "Graph and optimizer must be loaded first.")
    if st.graph_builder:
        st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)
    urgency, scores = _build_urgency_weights()
    st.optimizer.time_budget_seconds = req.time_budget_seconds
    result = st.optimizer.re_optimize(st.graph_data, st.shortest_paths, urgency, scores)

    order = RelocationOrder(order_id=f"order-{result.run_id}", result=result, issued_by="api")
    order.audit_hash = order.compute_hash()
    if st.relocation_orders:
        order.hash_chain_previous = st.relocation_orders[-1].audit_hash
    st.relocation_orders.append(order)

    return {"result": result.model_dump(), "order": {
        "order_id": order.order_id, "audit_hash": order.audit_hash,
        "hash_chain_previous": order.hash_chain_previous,
        "issued_at": order.issued_at.isoformat(),
    }}


@router.post("/api/optimize/expanded")
async def solve_expanded():
    """Re-solve with nearby district shelters included."""
    if not st.graph_data or not st.optimizer:
        raise HTTPException(400, "Graph and optimizer must be loaded first.")
    for s in st.graph_data.shelters:
        s.is_active = True
    if st.graph_builder:
        st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)
    urgency, scores = _build_urgency_weights()
    st.optimizer.time_budget_seconds = 30.0
    result = st.optimizer.solve(st.graph_data, st.shortest_paths, urgency, scores)

    inter_district = []
    for a in result.assignments:
        shelter = st.graph_data.get_shelter_by_id(a.shelter_id)
        hab = st.graph_data.get_habitation_by_id(a.habitation_id)
        if shelter and hab and getattr(shelter, "district", "") != getattr(hab, "district", ""):
            inter_district.append({
                "habitation": hab.name, "shelter": shelter.name,
                "district": shelter.district, "people": a.people_assigned,
                "distance_km": a.distance_km,
            })
    total_cap = sum(s.bed_capacity for s in st.graph_data.shelters)
    n = len(inter_district)
    msg = f"Expanded plan: {result.total_people_relocated:,} relocated."
    msg += f" {n} transfers to neighboring districts needed." if n else " All within Chamoli."
    return {"result": result.model_dump(), "inter_district_transfers": inter_district,
            "expanded_capacity": total_cap, "message": msg}


@router.post("/api/whatif")
async def run_whatif(scenario: WhatIfScenario):
    """Live what-if scenario: modify rainfall, block roads, disable shelters."""
    if not st.graph_data or not st.optimizer:
        raise HTTPException(400, "Load graph and run initial optimization first.")

    sim_graph = copy.deepcopy(st.graph_data)
    if scenario.population_multiplier != 1.0:
        for h in sim_graph.habitations:
            h.population_estimate = int(h.population_estimate * scenario.population_multiplier)
    for road in sim_graph.road_segments:
        if road.id in scenario.block_road_ids:
            road.status = RoadStatus.BLOCKED
            road.damage_factor = 0.0
    for shelter in sim_graph.shelters:
        if shelter.id in scenario.disable_shelter_ids:
            shelter.is_active = False

    sim_builder = CapacityGraphBuilder(population_safety_margin=0.15)
    sim_graph = sim_builder.build(sim_graph)
    sim_paths = sim_builder.compute_shortest_paths(sim_graph)

    sim_sensors = []
    for s in st.sensor_readings:
        ms = s.model_copy()
        if ms.source == "imd_rainfall":
            ms.value *= scenario.rainfall_multiplier
        sim_sensors.append(ms)

    now = datetime.utcnow()
    sim_conf = {}
    for hab in sim_graph.habitations:
        for htype in [HazardType.FLOOD, HazardType.LANDSLIDE, HazardType.SEISMIC]:
            score = fuse_hazard_scores(
                habitation_id=hab.id, habitation_location=hab.location,
                hazard_type=htype,
                static_zones=[z for z in st.static_zones if z.hazard_type == htype],
                sensor_readings=sim_sensors, crowd_reports=st.crowd_reports, now=now,
            )
            sim_conf[f"{hab.id}:{htype.value}"] = score.confidence

    urgency_w = {}
    for hab in sim_graph.habitations:
        max_c = max((sim_conf.get(f"{hab.id}:{ht.value}", 0.0) for ht in [HazardType.FLOOD, HazardType.LANDSLIDE]), default=0.5)
        urgency_w[hab.id] = 1.0 + max_c * 2.0

    sim_opt = OptimizationEngine(time_budget_seconds=10.0)
    result = sim_opt.solve(sim_graph, sim_paths, urgency_w, sim_conf)
    return {"scenario": scenario.model_dump(), "result": result.model_dump(),
            "affected_habitations": [{"id": h.id, "name": h.name, "population": h.population_estimate} for h in sim_graph.habitations]}


@router.get("/api/nearby-capacity")
async def nearby_capacity():
    """Find nearby district shelters for overflow absorption."""
    if not st.graph_data or not st.optimizer or not st.optimizer._last_result:
        raise HTTPException(400, "Run optimization first.")
    result = st.optimizer._last_result
    unmet = result.total_people_unmet
    if unmet <= 0:
        return {"message": "No unmet need.", "nearby_shelters": [], "total_nearby_beds": 0}

    chamoli_ids = {s.id for s in st.graph_data.shelters if s.district == "Chamoli"}
    nearby = []
    for s in st.graph_data.shelters:
        if s.id not in chamoli_ids and s.is_active:
            avail = s.bed_capacity - s.beds_occupied
            if avail > 0:
                nearby.append({"id": s.id, "name": s.name, "district": s.district,
                               "bed_capacity": s.bed_capacity, "beds_available": avail})
    nearby.sort(key=lambda x: x["beds_available"], reverse=True)
    total = sum(s["beds_available"] for s in nearby)
    can_cover = total >= unmet
    return {"unmet_people": unmet, "total_nearby_beds": total, "can_cover_unmet": can_cover,
            "nearby_shelters": nearby,
            "recommendation": f"{len(nearby)} shelters have {total:,} beds. {'Enough.' if can_cover else f'Covers {total/unmet*100:.0f}%.'}"}


@router.get("/api/social-vulnerability")
async def get_social_vulnerability():
    """Get social vulnerability index for all habitations."""
    if not st.graph_data:
        raise HTTPException(400, "No graph loaded.")
    return {"habitations": [
        {"id": h.id, "name": h.name, "population": h.population_estimate,
         "vulnerability_index": h.social_vulnerability.vulnerability_index if h.social_vulnerability else 0,
         "evacuation_difficulty": h.social_vulnerability.evacuation_difficulty if h.social_vulnerability else "unknown"}
        for h in st.graph_data.habitations
    ]}
