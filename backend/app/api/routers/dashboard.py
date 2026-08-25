"""
Dashboard Router
================
Core dashboard data, relocation orders, offline sync,
backtesting, explainability, and resource forecasts.

API Routes:
  GET  /api/dashboard             — Aggregated dashboard data
  GET  /api/orders                — Relocation orders
  POST /api/offline/report        — Submit offline report
  POST /api/offline/sync          — Sync offline reports
  GET  /api/backtest/events       — List backtest events
  GET  /api/backtest/{event_id}   — Run backtest
  GET  /api/explain/{hab_id}      — Explainability
  GET  /api/resources/forecasts   — Resource forecasts
  GET  /api/resources/shortfall-forecast — Shelter shortfall
"""

from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, HTTPException

from backend.app.api.state import (
    graph_data, graph_builder, optimizer, static_zones,
    sensor_readings, crowd_reports, offline_reports,
    relocation_orders, hazard_confidences,
)

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard")
async def dashboard_data():
    """Aggregated data for the operator dashboard."""
    summary = {}
    if graph_data and graph_builder:
        summary = graph_builder.get_shelter_capacity_summary(graph_data)
    return {
        "hazard_zones": [
            {"id": z.id, "type": z.hazard_type.value, "severity": z.severity, "center": z.center}
            for z in static_zones
        ],
        "sensor_readings_count": len(sensor_readings),
        "crowd_reports_count": len(crowd_reports),
        "capacity_summary": summary,
        "hazard_confidences": {
            k: {"confidence": v.confidence, "alert_level": v.alert_level.value}
            for k, v in hazard_confidences.items()
        },
        "latest_result": optimizer._last_result.model_dump() if optimizer and optimizer._last_result else None,
        "relocation_orders_count": len(relocation_orders),
    }


@router.get("/api/orders")
async def get_relocation_orders():
    """Get all issued relocation orders with audit hashes."""
    return {"orders": [{
        "order_id": o.order_id, "audit_hash": o.audit_hash,
        "hash_chain_previous": o.hash_chain_previous,
        "issued_at": o.issued_at.isoformat(), "issued_by": o.issued_by,
        "total_relocated": o.result.total_people_relocated,
        "is_feasible": o.result.is_feasible,
    } for o in relocation_orders]}


@router.post("/api/offline/report")
async def submit_offline_report(report):
    """Submit offline report (edge 5.9: last-write-wins conflict resolution)."""
    existing = [r for r in offline_reports if r.client_id == report.client_id
                and r.report.hazard_type == report.report.hazard_type
                and abs(r.client_timestamp - report.client_timestamp) < 60]
    if existing:
        for old in existing:
            if report.client_timestamp >= old.client_timestamp:
                offline_reports.remove(old)
                offline_reports.append(report)
        return {"status": "conflict_resolved", "resolution": "last_write_wins"}
    offline_reports.append(report)
    return {"status": "accepted", "sync_status": "pending"}


@router.post("/api/offline/sync")
async def sync_offline_reports():
    """Sync pending offline reports into the main crowd report pool."""
    synced = 0
    for off in offline_reports:
        if off.sync_status == "pending":
            crowd_reports.append(off.report)
            off.sync_status = "synced"
            synced += 1
    return {"synced": synced, "total_pending": sum(1 for r in offline_reports if r.sync_status == "pending")}


@router.get("/api/backtest/events")
async def list_backtest_events():
    """List available historical events for backtesting."""
    from backend.app.utils.backtest import HISTORICAL_EVENTS
    return {"events": [{
        "event_id": e.event_id, "name": e.name, "district": e.district,
        "hazard_type": e.hazard_type.value, "date": e.date,
        "description": e.description,
    } for e in HISTORICAL_EVENTS.values()]}


@router.get("/api/backtest/{event_id}")
async def run_backtest(event_id: str):
    """Run historical backtest against a documented disaster event."""
    if not graph_data or not static_zones:
        raise HTTPException(400, "Load graph and hazard zones first.")
    from backend.app.utils.backtest import run_backtest as _run_backtest
    try:
        result = _run_backtest(
            event_id=event_id, graph_data=graph_data,
            hazard_zones=[{"id": z.id, "hazard_type": z.hazard_type.value,
                           "severity": z.severity, "center_lat": z.center.lat,
                           "center_lon": z.center.lon, "radius_km": z.radius_km}
                          for z in static_zones],
        )
        return result.model_dump()
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/api/explain/{habitation_id}")
async def explain_habitation(habitation_id: str):
    """Full explainability for a habitation."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    hab = graph_data.get_habitation_by_id(habitation_id)
    if not hab:
        raise HTTPException(404, f"Habitation {habitation_id} not found.")

    hazard_exp = {}
    for key, conf in hazard_confidences.items():
        if key.startswith(habitation_id + ":"):
            hazard_exp[key] = {"confidence": conf.confidence,
                               "alert_level": conf.alert_level.value,
                               "explanation": conf.explanation.model_dump() if conf.explanation else None,
                               "component_scores": conf.component_scores}

    assign_exp = []
    if optimizer and optimizer._last_result:
        for a in optimizer._last_result.assignments:
            if a.habitation_id == habitation_id:
                assign_exp.append({
                    "shelter_id": a.shelter_id, "people_assigned": a.people_assigned,
                    "distance_km": a.distance_km,
                    "explanation": a.explanation.model_dump() if a.explanation else None,
                    "shelter_comparison": [c.model_dump() for c in a.shelter_comparison],
                })
    return {"habitation_id": habitation_id, "habitation_name": hab.name,
            "population": hab.population_estimate,
            "social_vulnerability": hab.social_vulnerability.model_dump() if hab.social_vulnerability else None,
            "hazard_explanations": hazard_exp, "assignment_explanations": assign_exp}


@router.get("/api/resources/forecasts")
async def get_resource_forecasts():
    """Resource shortfall forecasts for all shelters."""
    if not optimizer or not optimizer._last_result:
        raise HTTPException(400, "Run optimization first.")
    return {"forecasts": [f.model_dump() for f in optimizer._last_result.resource_forecasts]}


@router.get("/api/resources/shortfall-forecast")
async def shortfall_forecast():
    """Forecast when each shelter runs out of beds/water."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    forecasts = []
    for s in graph_data.shelters:
        if not s.is_active:
            continue
        avail = s.bed_capacity - s.beds_occupied
        arrival = max(1, avail * 0.1)
        hours_full = avail / arrival if arrival > 0 else float("inf")
        water_h = (s.water_capacity_liters_per_day / 24) / max(1, s.bed_capacity * 0.05) if s.water_capacity_liters_per_day > 0 else float("inf")
        status = "critical" if hours_full < 4 else "warning" if hours_full < 8 else "adequate"
        forecasts.append({
            "shelter_id": s.id, "shelter_name": s.name, "district": s.district,
            "bed_capacity": s.bed_capacity, "beds_occupied": s.beds_occupied,
            "beds_available": avail,
            "occupancy_pct": round((s.beds_occupied / max(1, s.bed_capacity)) * 100, 1),
            "estimated_hours_to_full": round(hours_full, 1),
            "water_hours_remaining": round(water_h, 1), "status": status,
        })
    forecasts.sort(key=lambda x: x["estimated_hours_to_full"])
    return {"forecasts": forecasts, "timestamp": datetime.utcnow().isoformat()}
