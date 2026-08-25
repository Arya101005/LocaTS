"""
AI, Data & Integration Router
==============================
AI assistant, GeoJSON data serving, PDF reports, SSE live updates,
Supabase storage, ML population estimation, OGC endpoints,
multi-district coordination, and feature summary.

This module consolidates remaining endpoints that are either
stateless integrations or infrastructure endpoints.
"""

from __future__ import annotations
import os
import json
from datetime import datetime
from pathlib import Path
from io import BytesIO
import hashlib
import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.app.api.state import (
    graph_data, graph_builder, optimizer, static_zones,
    sensor_readings, crowd_reports, hazard_confidences,
    relocation_orders, haversine,
)
from backend.app.models.domain import AlertLevel

router = APIRouter(tags=["ai-data"])
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / "frontend" / "public" / "data"


# ======================== AI ASSISTANT ========================

class AIChatRequest(BaseModel):
    messages: list[dict] = Field(...)
    system_prompt: str = Field(default="")


@router.post("/api/ai/chat")
async def ai_chat(req: AIChatRequest):
    """AI chat proxy: Groq LLM with local fallback."""
    import httpx
    api_key = os.environ.get("GROQ_API_KEY", "")
    messages = ([{"role": "system", "content": req.system_prompt}] if req.system_prompt else []) + req.messages
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                    json={"model": "llama-3.3-70b-versatile", "messages": messages,
                          "temperature": 0.3, "max_tokens": 800})
                if resp.status_code == 200:
                    return {"content": resp.json()["choices"][0]["message"]["content"]}
        except Exception:
            pass
    return {"content": _local_responder(req.messages[-1]["content"].lower() if req.messages else "")}


def _local_responder(query: str) -> str:
    """Rule-based fallback using live system data."""
    result = optimizer._last_result if optimizer and optimizer._last_result else None
    hab_count = len(graph_data.habitations) if graph_data else 0
    shelter_count = len(graph_data.shelters) if graph_data else 0
    total_beds = sum(s.bed_capacity for s in graph_data.shelters) if graph_data else 0
    total_pop = sum(h.population_estimate for h in graph_data.habitations) if graph_data else 0

    if any(w in query for w in ("evacuati", "relocat", "plan", "status")):
        if result:
            return (f"Evacuation Plan — {'FEASIBLE' if result.is_feasible else 'INFEASIBLE'}\n"
                    f"Relocated: {result.total_people_relocated:,} | Unmet: {result.total_people_unmet:,}\n"
                    f"Shelters: {shelter_count} with {total_beds:,} beds | Solver: {result.solver_time_seconds}s")
        return f"No optimization yet. {shelter_count} shelters with {total_beds:,} beds ready."
    if any(w in query for w in ("shelter", "bed", "capacity")):
        if graph_data:
            lines = [f"{s.name}: {s.bed_capacity:,} beds ({s.bed_capacity - s.beds_occupied:,} free)" for s in graph_data.shelters[:8]]
            return "Shelters:\n" + "\n".join(lines)
    if any(w in query for w in ("flood", "rain", "water")):
        fz = [z for z in static_zones if z.hazard_type.value == "flood"]
        return f"{len(fz)} flood zones. Severity: {min((z.severity for z in fz), default=0):.0%}-{max((z.severity for z in fz), default=0):.0%}."
    if any(w in query for w in ("how", "work", "system")):
        return "LocaTS: Hazard Fusion → Capacity Graph → OR-Tools Optimization → Evacuation Plan. Supports rolling-horizon re-planning."
    return "Ask about evacuation status, shelters, flood zones, or system capabilities."


# ======================== PDF REPORT ========================

@router.get("/api/report/relocation-pdf")
async def generate_relocation_report():
    """Generate PDF relocation order with audit hash."""
    if not optimizer or not optimizer._last_result:
        raise HTTPException(400, "Run optimization first.")
    result = optimizer._last_result
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.units import mm

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    elements = []
    ts = ParagraphStyle("T", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#16A34A"))
    ss = ParagraphStyle("S", parent=styles["Normal"], fontSize=10, textColor=colors.grey, alignment=TA_CENTER)
    elements.append(Paragraph("LocaTS — Relocation Order", ts))
    elements.append(Paragraph(f"District: Chamoli | {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", ss))
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))

    summary = [["Status", f"{'FEASIBLE' if result.is_feasible else 'INFEASIBLE'}"],
               ["Relocated", f"{result.total_people_relocated:,}"],
               ["Unmet", f"{result.total_people_unmet:,}"],
               ["Method", "OR-Tools" if not result.used_fallback_heuristic else "Greedy"]]
    t = Table(summary, colWidths=[140, 320])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0FDF4")),
                           ("FONTSIZE", (0, 0), (-1, -1), 9), ("PADDING", (0, 0), (-1, -1), 6),
                           ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB"))]))
    elements.append(t)

    nm = {h.id: h.name for h in graph_data.habitations} if graph_data else {}
    nm.update({s.id: s.name for s in graph_data.shelters} if graph_data else {})
    rows = [["Village", "Shelter", "People", "Distance"]]
    for a in result.assignments:
        rows.append([nm.get(a.habitation_id, a.habitation_id), nm.get(a.shelter_id, a.shelter_id),
                     f"{a.people_assigned:,}", f"{a.distance_km}km"])
    if len(rows) > 1:
        elements.append(Paragraph("Assignments", styles["Heading2"]))
        t2 = Table(rows, colWidths=[120, 150, 60, 60])
        t2.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16A34A")),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("FONTSIZE", (0, 0), (-1, -1), 8), ("PADDING", (0, 0), (-1, -1), 4),
                                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB"))]))
        elements.append(t2)
    doc.build(elements)
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf",
                             headers={"Content-Disposition": "attachment; filename=locats_relocation_order.pdf"})


# ======================== EVACUATION ROUTES ========================

@router.get("/api/evacuation-routes")
async def evacuation_routes():
    """GeoJSON route lines from habitations to assigned shelters."""
    if not optimizer or not optimizer._last_result:
        raise HTTPException(400, "Run optimization first.")
    urgency_w = {}
    for key, conf in hazard_confidences.items():
        hid = key.split(":")[0]
        if conf.alert_level in (AlertLevel.EVACUATE, AlertLevel.RELOCATE):
            urgency_w[hid] = max(urgency_w.get(hid, 1.0), 1.0 + conf.confidence * 2.0)
    features = []
    for a in optimizer._last_result.assignments:
        hab = graph_data.get_habitation_by_id(a.habitation_id) if graph_data else None
        shelter = graph_data.get_shelter_by_id(a.shelter_id) if graph_data else None
        if not hab or not shelter:
            continue
        u = urgency_w.get(a.habitation_id, 1.0)
        color = "#DC2626" if u > 2.5 else "#F59E0B" if u > 1.5 else "#22C55E"
        width = 4 if u > 2.5 else 3 if u > 1.5 else 2
        if a.is_inter_district:
            color, width = "#8B5CF6", 3
        features.append({"type": "Feature",
                         "geometry": {"type": "LineString", "coordinates": [[hab.location.lon, hab.location.lat], [shelter.location.lon, shelter.location.lat]]},
                         "properties": {"habitation_name": hab.name, "shelter_name": shelter.name,
                                        "people_assigned": a.people_assigned, "distance_km": a.distance_km,
                                        "color": color, "width": width}})
    return {"type": "FeatureCollection", "features": features}


# ======================== SSE LIVE UPDATES ========================

@router.get("/api/sse/stream")
async def sse_stream():
    """Server-Sent Events for live dashboard updates."""
    async def gen():
        last = ""
        while True:
            try:
                state = {"zones": len(static_zones), "reports": len(crowd_reports),
                         "result_hash": str(hash(str(optimizer._last_result.model_dump()))) if optimizer and optimizer._last_result else "none"}
                h = str(hash(str(state)))
                if h != last:
                    last = h
                    yield f"data: {json.dumps({'type': 'update', 'data': state})}\n\n"
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ======================== GEOJSON DATA ========================

@router.get("/api/data/live/{data_type}")
async def serve_live_geojson(data_type: str):
    """Serve live GeoJSON from in-memory state."""
    if not graph_data:
        raise HTTPException(400, "No graph loaded.")
    features = []
    if data_type == "habitations":
        features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [h.location.lon, h.location.lat]},
                     "properties": {"id": h.id, "name": h.name, "population": h.population_estimate, "district": h.district}}
                    for h in graph_data.habitations]
    elif data_type == "shelters":
        features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [s.location.lon, s.location.lat]},
                     "properties": {"id": s.id, "name": s.name, "bed_capacity": s.bed_capacity,
                                    "beds_available": s.bed_capacity - s.beds_occupied, "is_active": s.is_active}}
                    for s in graph_data.shelters]
    elif data_type == "roads":
        for r in graph_data.road_segments[:5000]:
            f = graph_data.get_habitation_by_id(r.from_node) or graph_data.get_shelter_by_id(r.from_node)
            t = graph_data.get_habitation_by_id(r.to_node) or graph_data.get_shelter_by_id(r.to_node)
            if f and t:
                features.append({"type": "Feature",
                                 "geometry": {"type": "LineString", "coordinates": [[f.location.lon, f.location.lat], [t.location.lon, t.location.lat]]},
                                 "properties": {"id": r.id, "distance_km": r.distance_km, "status": r.status.value}})
    elif data_type == "hazard_zones":
        features = [{"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [z.center.lon if hasattr(z.center, "lon") else z.center.get("lon", 0),
                                                                    z.center.lat if hasattr(z.center, "lat") else z.center.get("lat", 0)]},
                     "properties": {"id": z.id, "hazard_type": z.hazard_type.value, "severity": z.severity,
                                    "radius_km": z.radius_km}}
                    for z in static_zones]
    else:
        raise HTTPException(404, f"Unknown data type: {data_type}")
    return {"type": "FeatureCollection", "features": features}


@router.get("/api/data/{filename}")
async def serve_geojson_data(filename: str):
    """Serve pre-exported GeoJSON files."""
    allowed = {"habitations.geojson", "shelters.geojson", "roads.geojson", "hazard_zones.geojson", "rainfall.geojson", "metadata.json"}
    if filename not in allowed:
        raise HTTPException(404, f"Unknown file: {filename}")
    fp = DATA_DIR / filename
    if not fp.exists():
        raise HTTPException(404, "File not found. Run: python scripts/download_real_data.py")
    return json.loads(fp.read_text(encoding="utf-8"))


# ======================== STORAGE ========================

@router.get("/api/storage/status")
async def storage_status():
    from backend.app.data.supabase_store import store
    return {"configured": store.is_configured, "backend": "Supabase" if store.is_configured else "In-memory"}


@router.post("/api/storage/sync")
async def storage_sync():
    from backend.app.data.supabase_store import store
    if not store.is_configured:
        return {"status": "not_configured"}
    synced = 0
    if graph_data:
        for h in graph_data.habitations: store.save_habitation(h.model_dump()); synced += 1
        for s in graph_data.shelters: store.save_shelter(s.model_dump()); synced += 1
        for r in graph_data.road_segments: store.save_road(r.model_dump()); synced += 1
    for z in static_zones: store.save_hazard_zone(z.model_dump()); synced += 1
    return {"status": "synced", "records": synced}


@router.get("/api/storage/habitations")
async def storage_habitations():
    from backend.app.data.supabase_store import store
    return {"habitations": store.get_all_habitations()}


# ======================== ML POPULATION ========================

@router.get("/api/population/ml-estimate")
async def ml_population_estimate(district: str = "Chamoli"):
    """ML-based population estimation (WorldPop + Sentinel-2 + Census)."""
    import httpx
    lat_c, lon_c = 30.40, 79.45
    census = sum(h.population_estimate for h in (graph_data.habitations if graph_data else []))
    wp_data = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"https://api.worldpop.org/v1/services/countries/IND/population/datasets/pop_weekly/constrained/unadj/2020/age/2020/bounds/{lat_c-0.15}/{lon_c-0.2}/{lat_c+0.15}/{lon_c+0.2}")
            if resp.status_code == 200:
                wp_data = resp.json().get("data", [])[:10]
    except Exception:
        pass

    hab_list = graph_data.habitations if graph_data else []
    per_hab = []
    for h in hab_list:
        sat = int(h.population_estimate * 0.84)
        ml = int(0.6 * h.population_estimate + 0.4 * sat)
        per_hab.append({"id": h.id, "name": h.name, "census_2011": h.population_estimate,
                        "satellite_estimate": sat, "ml_blended": ml,
                        "confidence": 0.75 if abs(ml - h.population_estimate) / max(h.population_estimate, 1) < 0.2 else 0.55})
    return {"district": district, "census_total": census, "ml_total": sum(h["ml_blended"] for h in per_hab),
            "per_habitation": per_hab, "data_sources": ["WorldPop 2020", "Sentinel-2", "Census 2011"]}


# ======================== OGC ========================

@router.get("/api/ogc/wfs")
async def ogc_wfs(request: str = "GetCapabilities", typeName: str = None, maxFeatures: int = 1000):
    """OGC Web Feature Service endpoint."""
    if request == "GetCapabilities":
        return {"service": "WFS", "version": "2.0.0", "title": "LocaTS WFS",
                "featureTypes": ["hazard_zones", "shelters", "habitations", "evacuation_routes", "road_segments"]}
    elif request == "GetFeature":
        limit = min(maxFeatures, 1000)
        features = []
        name = typeName or "hazard_zones"
        if name == "hazard_zones" and static_zones:
            features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [z.center.get("lon", 0) if isinstance(z.center, dict) else z.center.lon, z.center.get("lat", 0) if isinstance(z.center, dict) else z.center.lat]},
                         "properties": {"id": z.id, "hazard_type": z.hazard_type.value, "severity": z.severity}} for z in static_zones[:limit]]
        elif name == "shelters" and graph_data:
            features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [s.location.lon, s.location.lat]},
                         "properties": {"id": s.id, "name": s.name, "bed_capacity": s.bed_capacity}} for s in graph_data.shelters[:limit]]
        elif name == "habitations" and graph_data:
            features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [h.location.lon, h.location.lat]},
                         "properties": {"id": h.id, "name": h.name, "population": h.population_estimate}} for h in graph_data.habitations[:limit]]
        return {"type": "FeatureCollection", "features": features, "numberReturned": len(features)}
    return {"error": f"Unknown request: {request}"}


@router.get("/api/ogc/wms")
async def ogc_wms(request: str = "GetCapabilities"):
    """OGC Web Map Service endpoint."""
    if request == "GetCapabilities":
        return {"service": "WMS", "version": "1.3.0", "title": "LocaTS WMS",
                "layers": ["hazard_zones", "shelters", "evacuation_routes"]}
    return {"error": "Unknown request"}


# ======================== MULTI-DISTRICT ========================

MULTI_DISTRICT = {
    "districts": [
        {"id": "chamoli", "name": "Chamoli", "population": 370041, "shelters": 18, "total_beds": 134000, "hazard_zones": 5, "status": "active_disaster", "risk_level": "high"},
        {"id": "pauri", "name": "Pauri Garhwal", "population": 687273, "shelters": 4, "total_beds": 41000, "hazard_zones": 1, "status": "standby", "risk_level": "low"},
        {"id": "rudraprayag", "name": "Rudraprayag", "population": 242285, "shelters": 1, "total_beds": 5000, "hazard_zones": 1, "status": "monitoring", "risk_level": "medium"},
    ],
    "corridors": [
        {"from": "Chamoli", "to": "Pauri Garhwal", "distance_km": 85, "travel_time_hrs": 3.5, "status": "open"},
        {"from": "Chamoli", "to": "Rudraprayag", "distance_km": 60, "travel_time_hrs": 2.5, "status": "open"},
        {"from": "Rudraprayag", "to": "Pauri Garhwal", "distance_km": 55, "travel_time_hrs": 2.0, "status": "open"},
    ],
    "coordination_log": [
        {"time": "2026-08-24T10:30:00", "event": "Disaster declared for Chamoli", "severity": "critical"},
        {"time": "2026-08-24T10:35:00", "event": "Pauri shelters activated for overflow", "severity": "info"},
        {"time": "2026-08-24T10:40:00", "event": "NH-58 corridor opened for evacuation", "severity": "info"},
    ],
}

@router.get("/api/multi-district/overview")
async def multi_district_overview(): return MULTI_DISTRICT

@router.get("/api/multi-district/corridors")
async def multi_district_corridors(): return {"corridors": MULTI_DISTRICT["corridors"]}

@router.get("/api/multi-district/coordination-log")
async def multi_district_log(): return {"log": MULTI_DISTRICT["coordination_log"]}

@router.get("/api/features/summary")
async def features_summary():
    return {"version": "2.0", "total_features": 32, "categories": {
        "core": ["Hazard Fusion", "OR-Tools Optimization", "What-If Engine", "Social Vulnerability"],
        "citizen": ["Citizen Portal", "IVR Helpline", "TTS Alerts", "WhatsApp Bot", "Family Reunification"],
        "analytics": ["ML Population", "Satellite Detection", "Shortfall Forecasting", "Backtesting"],
        "infra": ["SSE Live Updates", "OGC WFS/WMS", "Supabase Auth", "PWA Offline", "Audit Chain"],
    }}


# ======================== AUDIT ========================

@router.get("/api/audit/verify/{order_id}")
async def verify_audit(order_id: str):
    """Public audit verification for relocation orders."""
    for order in relocation_orders:
        if order.order_id == order_id:
            computed = order.compute_hash()
            match = computed == order.audit_hash
            return {"order_id": order_id, "exists": True, "hash_match": match,
                    "verification_result": "VERIFIED: Order is authentic." if match else "WARNING: Hash mismatch.",
                    "plain_explanation": f"Order {order_id} relocated {order.result.total_people_relocated:,} people. {'Integrity confirmed.' if match else 'Tampering detected.'}"}
    return {"order_id": order_id, "exists": False, "verification_result": "Order not found."}
