"""
Hazard Fusion Router
====================
Endpoints for managing hazard zones, sensor readings, crowd reports,
and Bayesian fusion scoring.

API Routes:
  POST /api/hazard/zones      — Add a static hazard zone
  POST /api/hazard/sensor     — Add a live sensor reading
  POST /api/hazard/crowd-report — Submit a crowd report
  POST /api/hazard/fuse       — Run fusion scoring
  GET  /api/hazard/confidences — Get all fused scores
"""

from __future__ import annotations
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.api.state import (
    graph_data, static_zones, sensor_readings,
    crowd_reports, hazard_confidences, haversine,
)
from backend.app.data.persistence import persistence
from backend.app.hazard_fusion.fusion import fuse_hazard_scores
from backend.app.models.domain import (
    HazardType, StaticHazardZone, LiveSensorReading, CrowdReport,
)

router = APIRouter(prefix="/api/hazard", tags=["hazard"])


# --- Schemas ---

class HazardZoneAdd(BaseModel):
    id: str
    hazard_type: HazardType
    severity: float = Field(ge=0, le=1)
    zone_type: str = "red"
    center_lat: float
    center_lon: float
    radius_km: float = 5.0


class SensorReadingAdd(BaseModel):
    source: str
    lat: float
    lon: float
    value: float


class CrowdReportAdd(BaseModel):
    reporter_id: str
    hazard_type: HazardType
    severity_estimate: float = Field(ge=0, le=1)
    description: str = ""
    lat: float
    lon: float


# --- Endpoints ---

@router.post("/zones")
async def add_hazard_zone(zone: HazardZoneAdd):
    """Add a static hazard zone to the fusion layer."""
    new_zone = StaticHazardZone(
        id=zone.id, hazard_type=zone.hazard_type, severity=zone.severity,
        zone_type=zone.zone_type,
        center={"lat": zone.center_lat, "lon": zone.center_lon},
        radius_km=zone.radius_km,
    )
    static_zones.append(new_zone)
    persistence.save_hazard_zone({
        "id": zone.id,
        "hazard_type": zone.hazard_type.value if hasattr(zone.hazard_type, "value") else zone.hazard_type,
        "severity": zone.severity,
        "center": {"lat": zone.center_lat, "lon": zone.center_lon},
        "radius_km": zone.radius_km, "district": "Chamoli",
    })
    return {"status": "added", "zone_id": zone.id, "total_zones": len(static_zones)}


@router.post("/sensor")
async def add_sensor_reading(reading: SensorReadingAdd):
    """Add a live sensor reading (IMD rainfall, seismic, etc.)."""
    sensor_readings.append(LiveSensorReading(
        source=reading.source,
        location={"lat": reading.lat, "lon": reading.lon},
        value=reading.value, timestamp=datetime.utcnow(),
    ))
    return {"status": "added", "total_readings": len(sensor_readings)}


@router.post("/crowd-report")
async def add_crowd_report(report: CrowdReportAdd):
    """Submit a crowd report (edge 5.4: needs 3+ corroboration)."""
    report_id = f"cr-{len(crowd_reports)+1:05d}"
    crowd_reports.append(CrowdReport(
        id=report_id, reporter_id=report.reporter_id,
        hazard_type=report.hazard_type, severity_estimate=report.severity_estimate,
        description=report.description,
        location={"lat": report.lat, "lon": report.lon}, timestamp=datetime.utcnow(),
    ))
    return {"status": "accepted", "report_id": report_id,
            "note": "Report queued. Requires corroboration from >=3 independent sources."}


@router.post("/fuse")
async def fuse_hazards():
    """Run hazard fusion across all habitations."""
    if not graph_data or not graph_data.habitations:
        raise HTTPException(400, "No habitations loaded.")

    now = datetime.utcnow()
    results = {}
    for hab in graph_data.habitations:
        rel_sensors = [s for s in sensor_readings if haversine(hab.location, s.location) <= 10.0]
        rel_reports = [r for r in crowd_reports if haversine(hab.location, r.location) <= 10.0]
        for htype in [HazardType.FLOOD, HazardType.LANDSLIDE, HazardType.SEISMIC]:
            score = fuse_hazard_scores(
                habitation_id=hab.id, habitation_location=hab.location,
                hazard_type=htype,
                static_zones=[z for z in static_zones if z.hazard_type == htype],
                sensor_readings=rel_sensors,
                crowd_reports=[r for r in rel_reports if r.hazard_type == htype],
                now=now,
            )
            key = f"{hab.id}:{htype.value}"
            hazard_confidences[key] = score
            results[key] = {
                "confidence": score.confidence,
                "alert_level": score.alert_level.value,
                "is_stale": score.is_stale,
                "component_scores": score.component_scores,
            }
    return {"fused_hazard_scores": results, "total_evaluated": len(results)}


@router.get("/confidences")
async def get_confidences():
    """Get all current fused hazard confidence scores."""
    return {
        "confidences": {
            k: {
                "habitation_id": v.habitation_id,
                "hazard_type": v.hazard_type.value,
                "confidence": v.confidence,
                "alert_level": v.alert_level.value,
                "is_stale": v.is_stale,
                "staleness_minutes": v.staleness_minutes,
            }
            for k, v in hazard_confidences.items()
        }
    }
