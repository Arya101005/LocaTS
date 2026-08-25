"""
LocaTS API — Entry Point
========================
FastAPI application setup, startup data loading, and router registration.
"""

from __future__ import annotations
import time
import json as json_mod
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.app.api.state as st
from backend.app.models.domain import (
    CapacityGraph, HabitationCluster, RoadSegment, Shelter,
    StaticHazardZone, HazardType, LiveSensorReading,
)
from backend.app.capacity.graph_builder import CapacityGraphBuilder
from backend.app.optimizer.optimizer import OptimizationEngine
from backend.app.data.persistence import persistence

app = FastAPI(title="LocaTS API", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


def _auto_load_data():
    cache_file = Path(__file__).parent.parent.parent.parent / "frontend" / "public" / "data" / "auto_cache.json"
    if cache_file.exists():
        try:
            cache = json_mod.loads(cache_file.read_text(encoding="utf-8"))
            if (time.time() - cache.get("_cached_at", 0)) / 3600 < 24:
                print("  [AutoLoad] Cache hit")
                st.graph_data = CapacityGraph(
                    habitations=[HabitationCluster(**h) for h in cache["habitations"]],
                    shelters=[Shelter(**s) for s in cache["shelters"]],
                    road_segments=[RoadSegment(**r) for r in cache["roads"]],
                )
                for z in cache.get("hazard_zones", []):
                    st.static_zones.append(StaticHazardZone(
                        id=z["id"], hazard_type=HazardType(z["hazard_type"]),
                        severity=z["severity"], zone_type=z["zone_type"],
                        center={"lat": z["center_lat"], "lon": z["center_lon"]},
                        radius_km=z["radius_km"],
                    ))
                for r in cache.get("sensor_readings", []):
                    st.sensor_readings.append(LiveSensorReading(**r))
                _rebuild_graph()
                return
        except Exception as e:
            print(f"  [AutoLoad] Cache failed: {e}")

    print("  [AutoLoad] Loading Chamoli district dataset...")
    try:
        from backend.app.data.chamoli_dataset import load_chamoli_dataset
        graph, zones, sensors = load_chamoli_dataset()
        st.graph_data = graph
        st.static_zones.extend(zones)
        st.sensor_readings.extend(sensors)
        _rebuild_graph()
        print(f"  [AutoLoad] Done: {len(st.graph_data.habitations)} habs, {len(st.graph_data.shelters)} shelters")
        print(f"  [AutoLoad] Beds: {sum(s.bed_capacity for s in st.graph_data.shelters):,} | Pop: {sum(h.population_estimate for h in st.graph_data.habitations):,}")
        if persistence.is_configured:
            try:
                stats = persistence.seed_from_graph(st.graph_data, st.static_zones, st.sensor_readings)
                print(f"  [AutoLoad] Supabase seeded: {stats}")
            except Exception as e:
                print(f"  [AutoLoad] Supabase seed: {e}")
    except Exception as e:
        print(f"  [AutoLoad] FAILED: {e}")
        import traceback; traceback.print_exc()


def _rebuild_graph():
    st.graph_builder = CapacityGraphBuilder(population_safety_margin=0.15)
    st.graph_data = st.graph_builder.build(st.graph_data)
    st.optimizer = OptimizationEngine(time_budget_seconds=30.0)
    st.shortest_paths = st.graph_builder.compute_shortest_paths(st.graph_data)


@app.on_event("startup")
async def startup_event():
    print("=" * 60)
    print("  LocaTS starting...")
    try:
        _auto_load_data()
        print("  Server ready")
    except Exception as e:
        print(f"  Startup failed: {e}")
        import traceback; traceback.print_exc()
    print("=" * 60)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0",
            "layers": {"hazard_fusion": "operational",
                       "capacity_graph": "operational" if st.graph_data else "not_loaded",
                       "optimizer": "operational" if st.optimizer else "not_initialized"}}


from backend.app.api.routers import (
    hazard, capacity, optimizer as opt_router,
    dashboard, citizen, communication,
    satellite_rainfall, ai_and_data,
)
app.include_router(hazard.router)
app.include_router(capacity.router)
app.include_router(opt_router.router)
app.include_router(dashboard.router)
app.include_router(citizen.router)
app.include_router(communication.router)
app.include_router(satellite_rainfall.router)
app.include_router(ai_and_data.router)

try:
    from backend.app.utils.auth import create_auth_routes
    create_auth_routes(app)
except Exception:
    pass
