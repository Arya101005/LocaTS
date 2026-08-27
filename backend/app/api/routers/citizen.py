"""
Citizen & Family Router
=======================
Public endpoints for the citizen portal (no auth required)
and family reunification tracking.

API Routes:
  GET  /api/citizen/status/{village_id} — Village hazard status
  GET  /api/citizen/villages            — List all villages
  POST /api/citizen/report              — Crowd report (simplified)
  GET  /api/citizen/shelters            — Shelter list with capacity
  POST /api/family/register             — Register evacuee
  POST /api/family/search               — Search for family member
  POST /api/family/status               — Update evacuee status
  GET  /api/family/shelter/{shelter_id} — List shelter evacuees
"""

from __future__ import annotations
import hashlib as hl
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import backend.app.api.state as st
from backend.app.data.persistence import persistence
from backend.app.models.domain import (
    CrowdReport, EvacueeRegistration, FamilySearch,
    EvacueeStatusUpdate, HazardType,
)

router = APIRouter(tags=["citizen"])

# In-memory evacuee store
_evacuees: list = []


class CitizenReport(BaseModel):
    reporter_id: str
    hazard_type: str
    severity_estimate: float = Field(ge=0, le=1)
    description: str = ""
    lat: float = 30.40
    lon: float = 79.33


# --- Citizen Endpoints (no auth) ---

@router.get("/api/citizen/status/{village_id}")
async def citizen_village_status(village_id: str):
    """Public: shows hazard status for a specific village."""
    if not st.graph_data:
        raise HTTPException(503, "System data not loaded.")
    hab = st.graph_data.get_habitation_by_id(village_id)
    if not hab:
        raise HTTPException(404, "Village not found.")

    hazard_level, hazard_detail = "normal", "No active hazard warnings."
    for key, conf in st.hazard_confidences.items():
        if key.startswith(village_id + ":"):
            if conf.alert_level.value in ("evacuate", "relocate"):
                hazard_level, hazard_detail = "critical", f"{conf.hazard_type.value} risk. EVACUATE."
                break
            elif conf.alert_level.value == "advisory":
                hazard_level, hazard_detail = "warning", f"Advisory: elevated {conf.hazard_type.value} risk."

    nearest, n_dist = None, float("inf")
    for s in st.graph_data.shelters:
        if s.is_active:
            d = st.haversine(hab.location, s.location)
            if d < n_dist:
                n_dist, nearest = d, s

    assigned_name, assigned_dist = None, None
    if st.optimizer and st.optimizer._last_result:
        for a in st.optimizer._last_result.assignments:
            if a.habitation_id == village_id:
                s = st.graph_data.get_shelter_by_id(a.shelter_id)
                assigned_name, assigned_dist = s.name if s else a.shelter_id, a.distance_km
                break

    if hazard_level == "critical":
        action = f"EVACUATE NOW to {assigned_name or 'nearest shelter'} ({assigned_dist or n_dist:.1f}km)."
        urgency = "high"
    elif hazard_level == "warning":
        action = f"Prepare to move. Nearest: {nearest.name} ({n_dist:.1f}km)."
        urgency = "medium"
    else:
        action, urgency = "Stay alert. No immediate action needed.", "low"

    return {"village_id": village_id, "village_name": hab.name, "block": hab.block,
            "population": hab.population_estimate, "hazard_level": hazard_level,
            "hazard_detail": hazard_detail, "action_text": action, "action_urgency": urgency,
            "nearest_shelter": {"name": nearest.name, "distance_km": round(n_dist, 1),
                                "beds_available": nearest.bed_capacity - nearest.beds_occupied} if nearest else None,
            "assigned_shelter": {"name": assigned_name, "distance_km": assigned_dist} if assigned_name else None}


@router.get("/api/citizen/villages")
async def citizen_village_list():
    """Public: list all villages with current hazard status."""
    if not st.graph_data:
        raise HTTPException(503, "System data not loaded.")
    villages = []
    for h in st.graph_data.habitations:
        level = "normal"
        for key, conf in st.hazard_confidences.items():
            if key.startswith(h.id + ":"):
                if conf.alert_level.value in ("evacuate", "relocate"):
                    level = "critical"; break
                elif conf.alert_level.value == "advisory":
                    level = "warning"
        villages.append({"id": h.id, "name": h.name, "block": h.block,
                         "lat": h.location.lat, "lon": h.location.lon,
                         "population": h.population_estimate, "hazard_level": level})
    return {"villages": villages, "total": len(villages)}


@router.post("/api/citizen/report")
async def citizen_crowd_report(report: CitizenReport, request: Request):
    """Simplified citizen crowd report endpoint. Rate-limited per IP."""
    from backend.app.api.rate_limit import check_rate_limit
    check_rate_limit(request, "citizen_report", max_requests=10, window_seconds=300)
    report_id = f"cr-{len(st.crowd_reports)+1:05d}"
    ht = report.hazard_type
    if isinstance(ht, str):
        try:
            ht = HazardType(ht)
        except ValueError:
            ht = HazardType.FLOOD
    st.crowd_reports.append(CrowdReport(
        id=report_id, reporter_id=report.reporter_id,
        hazard_type=ht, severity_estimate=report.severity_estimate,
        description=report.description,
        location={"lat": report.lat, "lon": report.lon}, timestamp=datetime.utcnow(),
    ))
    persistence.save_crowd_report({
        "id": report_id,
        "reporter_id": report.reporter_id,
        "hazard_type": ht.value if hasattr(ht, "value") else ht,
        "severity_estimate": report.severity_estimate,
        "description": report.description,
        "lat": report.lat,
        "lon": report.lon,
        "timestamp": datetime.utcnow().isoformat(),
        "district": "Chamoli",
    })
    return {"status": "accepted", "report_id": report_id,
            "message": "Report received. Verified by multiple sources before influencing alerts."}


@router.get("/api/citizen/shelters")
async def citizen_shelters():
    """Public: list shelters with live capacity (no GPS)."""
    if not st.graph_data:
        raise HTTPException(503, "System data not loaded.")
    shelters = []
    for s in st.graph_data.shelters:
        if not s.is_active:
            continue
        avail = s.bed_capacity - s.beds_occupied
        shelters.append({"id": s.id, "name": s.name, "district": s.district,
                         "lat": s.location.lat, "lon": s.location.lon,
                         "type": s.shelter_type, "bed_capacity": s.bed_capacity,
                         "beds_available": avail,
                         "status": "open" if avail > 100 else "limited" if avail > 0 else "full",
                         "is_accessible": s.is_accessible})
    shelters.sort(key=lambda x: x["beds_available"], reverse=True)
    return {"shelters": shelters, "total": len(shelters)}


# --- Family Reunification ---

@router.post("/api/family/register")
async def register_evacuee(evacuee: EvacueeRegistration):
    """Register an evacuee at a shelter. Generates anonymized ID."""
    if not evacuee.evacuee_id:
        evacuee.evacuee_id = f"EVC-{hl.sha256(f'{evacuee.name_hash}:{evacuee.registered_shelter_id}:{time.time()}'.encode()).hexdigest()[:12].upper()}"
    if evacuee.name_hash and not all(c in "0123456789abcdef" for c in evacuee.name_hash.lower()):
        evacuee.name_hash = hl.sha256(evacuee.name_hash.encode()).hexdigest()[:16]
    _evacuees.append(evacuee)
    persistence.save_evacuee({
        "evacuee_id": evacuee.evacuee_id,
        "name_hash": evacuee.name_hash,
        "home_habitation_id": evacuee.home_habitation_id,
        "age_range": evacuee.age_range,
        "registered_shelter_id": evacuee.registered_shelter_id,
        "status": evacuee.status,
        "needs_medical": evacuee.needs_medical,
        "needs_accessibility": evacuee.needs_accessibility,
        "notes": evacuee.notes,
        "registered_at": evacuee.registered_at.isoformat(),
    })
    return {"status": "registered", "evacuee_id": evacuee.evacuee_id,
            "message": f"Evacuee registered at {evacuee.registered_shelter_id}."}


@router.post("/api/family/search")
async def search_family(search: FamilySearch):
    """Search for a family member across all shelters.

    PRIVACY: Name alone is not sufficient. At least one secondary identifier
    (home_habitation_id or age_range) is required to return results.
    This prevents location tracking by name-only queries.
    """
    if not search.home_habitation_id and not search.age_range:
        return {
            "results": [],
            "message": "To protect privacy, please provide at least one additional identifier: home village or age group.",
            "requires_secondary_id": True,
        }
    q_hash = hl.sha256(search.search_name.encode()).hexdigest()[:16]
    results = []
    for ev in _evacuees:
        if (ev.name_hash == q_hash
                and (not search.home_habitation_id or ev.home_habitation_id == search.home_habitation_id)
                and (not search.age_range or ev.age_range == search.age_range)):
            s_name = ""
            if st.graph_data:
                s = st.graph_data.get_shelter_by_id(ev.registered_shelter_id)
                if s:
                    s_name = s.name
            results.append({"evacuee_id": ev.evacuee_id, "shelter_id": ev.registered_shelter_id,
                            "shelter_name": s_name, "status": ev.status,
                            "registered_at": ev.registered_at.isoformat(), "is_match": True})
    return {"results": results, "message": f"Found {len(results)} record(s)." if results else "No match found."}


@router.post("/api/family/status")
async def update_evacuee_status(update: EvacueeStatusUpdate):
    """Update an evacuee's status (safe, missing, hospitalized)."""
    for ev in _evacuees:
        if ev.evacuee_id == update.evacuee_id:
            ev.status, ev.notes = update.new_status, update.notes
            return {"status": "updated", "evacuee_id": update.evacuee_id}
    raise HTTPException(404, f"Evacuee {update.evacuee_id} not found")


@router.get("/api/family/shelter/{shelter_id}")
async def list_shelter_evacuees(shelter_id: str):
    """List all evacuees at a specific shelter."""
    evacuees = [e for e in _evacuees if e.registered_shelter_id == shelter_id]
    counts = {}
    for e in evacuees:
        counts[e.status] = counts.get(e.status, 0) + 1
    return {"shelter_id": shelter_id, "total": len(evacuees), "status_counts": counts,
            "evacuees": [{"evacuee_id": e.evacuee_id, "age_range": e.age_range,
                          "status": e.status, "needs_medical": e.needs_medical,
                          "needs_accessibility": e.needs_accessibility,
                          "registered_at": e.registered_at.isoformat()} for e in evacuees]}
