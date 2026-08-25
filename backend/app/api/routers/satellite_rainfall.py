"""
Satellite & Rainfall Router
===========================
Sentinel-2 satellite change detection and Open-Meteo rainfall data.

API Routes:
  GET /api/satellite/detect           — Satellite change detection (legacy)
  GET /api/satellite/imagery          — Before/after imagery URLs
  GET /api/satellite/change-detection — Full NDWI/NDSI analysis
  GET /api/rainfall/live              — Current rainfall (Open-Meteo)
  GET /api/rainfall/trend             — Rainfall trend + forecast
  GET /api/rainfall/realtime          — Real-time rainfall (Open-Meteo)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.api.state import graph_data

router = APIRouter(tags=["satellite"])


@router.get("/api/satellite/detect")
async def satellite_detect(district: str = "Chamoli"):
    """Detect changes from Sentinel-2 imagery."""
    from backend.app.utils.satellite import satellite_detector
    changes = satellite_detector.detect_changes(district=district)
    return {"district": district, "changes_detected": len(changes), "changes": changes}


@router.get("/api/satellite/imagery")
async def satellite_imagery(lat: float, lon: float, before: str = "", after: str = ""):
    """Get before/after satellite imagery URLs."""
    from backend.app.utils.satellite import satellite_detector
    return satellite_detector.get_before_after_imagery_urls(lat, lon, before, after)


@router.get("/api/satellite/change-detection")
async def satellite_change_detection(district: str = "Chamoli"):
    """Full Sentinel-2 NDWI/NDSI change detection analysis."""
    from backend.app.utils.satellite import satellite_detector
    changes = satellite_detector.detect_changes(district=district)
    return {"district": district, "is_live_satellite": not satellite_detector.use_demo,
            "source": "Sentinel-2 (Sentinel Hub)" if not satellite_detector.use_demo else "NDMA hazard zones",
            "changes_detected": len(changes), "changes": changes,
            "note": "Real Sentinel-2 NDWI/NDSI active." if not satellite_detector.use_demo else "Using hazard zone proxy."}


@router.get("/api/rainfall/live")
async def rainfall_live(district: str = "Chamoli"):
    """Current rainfall from Open-Meteo API."""
    from backend.app.data.ingestion.openmeteo_rainfall import get_openmeteo
    metro = get_openmeteo(district)
    readings = metro.get_current_rainfall()
    return {"readings": readings, "count": len(readings), "source": "Open-Meteo API", "district": district}


@router.get("/api/rainfall/trend")
async def rainfall_trend(hours: int = 24, district: str = "Chamoli"):
    """Rainfall trend (past + forecast)."""
    from backend.app.data.ingestion.openmeteo_rainfall import get_openmeteo
    metro = get_openmeteo(district)
    return {"trend": metro.get_rainfall_trend(hours=hours), "hours": hours, "district": district, "source": "Open-Meteo API"}


@router.get("/api/rainfall/realtime")
async def rainfall_realtime():
    """Real-time rainfall from Open-Meteo (7 Chamoli stations)."""
    import httpx
    coords = [
        {"name": "Gopeshwar", "lat": 30.40, "lon": 79.33},
        {"name": "Joshimath", "lat": 30.56, "lon": 79.57},
        {"name": "Karnaprayag", "lat": 30.27, "lon": 79.32},
        {"name": "Badrinath", "lat": 30.74, "lon": 79.49},
        {"name": "Nandprayag", "lat": 30.33, "lon": 79.32},
        {"name": "Tharali", "lat": 30.25, "lon": 79.55},
        {"name": "Ghat", "lat": 30.38, "lon": 79.62},
    ]
    readings, is_live = [], False
    try:
        lats = ",".join(str(c["lat"]) for c in coords)
        lons = ",".join(str(c["lon"]) for c in coords)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://api.open-meteo.com/v1/forecast",
                                    params={"latitude": lats, "longitude": lons,
                                            "current_weather": "true", "hourly": "precipitation",
                                            "past_hours": 1, "forecast_hours": 0})
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else [data]
                for i, d in enumerate(items):
                    cw = d.get("current_weather", {})
                    precip = d.get("hourly", {}).get("precipitation", [0])
                    readings.append({"name": coords[i]["name"], "lat": coords[i]["lat"],
                                     "lon": coords[i]["lon"], "rainfall_mm": precip[-1] if precip else 0,
                                     "temperature": cw.get("temperature", 0),
                                     "wind_speed": cw.get("windspeed", 0), "source": "open-meteo-live"})
                is_live = True
    except Exception:
        pass
    return {"readings": readings, "is_live": is_live,
            "source": "Open-Meteo (live)" if is_live else "Simulated",
            "total_rainfall_mm": sum(r["rainfall_mm"] for r in readings),
            "max_rainfall_mm": max((r["rainfall_mm"] for r in readings), default=0)}
