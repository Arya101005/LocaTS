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


def _load_persisted_state():
    """Load crowd reports, evacuees, and orders from Supabase on startup."""
    if not persistence.is_configured:
        return
    try:
        from backend.app.api.routers.citizen import _evacuees
        reports = persistence.load_crowd_reports(limit=200)
        for r in reports:
            try:
                from backend.app.models.domain import CrowdReport, HazardType
                ht = r.get("hazard_type", "flood")
                if isinstance(ht, str):
                    try:
                        ht = HazardType(ht)
                    except ValueError:
                        ht = HazardType.FLOOD
                st.crowd_reports.append(CrowdReport(
                    id=r.get("id", f"cr-{len(st.crowd_reports)+1:05d}"),
                    reporter_id=r.get("reporter_id", "unknown"),
                    hazard_type=ht,
                    severity_estimate=float(r.get("severity_estimate", 0.5)),
                    description=r.get("description", ""),
                    location={"lat": float(r.get("lat", 30.40)), "lon": float(r.get("lon", 79.33))},
                    timestamp=datetime.fromisoformat(r.get("timestamp", datetime.utcnow().isoformat())),
                ))
            except Exception:
                pass
        print(f"  [Persist] Loaded {len(reports)} crowd reports")

        evacuees = persistence.load_evacuees()
        for e in evacuees:
            try:
                from backend.app.models.domain import EvacueeRegistration
                _evacuees.append(EvacueeRegistration(
                    evacuee_id=e.get("evacuee_id", ""),
                    name_hash=e.get("name_hash", ""),
                    home_habitation_id=e.get("home_habitation_id"),
                    age_range=e.get("age_range"),
                    registered_shelter_id=e.get("registered_shelter_id", ""),
                    status=e.get("status", "safe"),
                    needs_medical=bool(e.get("needs_medical", False)),
                    needs_accessibility=bool(e.get("needs_accessibility", False)),
                    notes=e.get("notes", ""),
                    registered_at=datetime.fromisoformat(e.get("registered_at", datetime.utcnow().isoformat())),
                ))
            except Exception:
                pass
        print(f"  [Persist] Loaded {len(evacuees)} evacuees")

        orders = persistence.load_relocation_orders(limit=50)
        for o in orders:
            try:
                from backend.app.models.domain import RelocationOrder, OptimizationResult
                data = o.get("data", {})
                if data:
                    result = OptimizationResult(**data)
                    order = RelocationOrder(
                        order_id=o.get("order_id", ""),
                        result=result,
                        issued_by=o.get("issued_by", "system"),
                        issued_at=datetime.fromisoformat(o.get("issued_at", datetime.utcnow().isoformat())),
                    )
                    order.audit_hash = o.get("audit_hash", "")
                    order.hash_chain_previous = o.get("hash_chain_previous", "")
                    st.relocation_orders.append(order)
            except Exception:
                pass
        print(f"  [Persist] Loaded {len(orders)} relocation orders")
    except Exception as e:
        print(f"  [Persist] Load failed: {e}")


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
    _load_persisted_state()
    try:
        from backend.app.utils.local_auth import preload_users
        preload_users()
        print("  Auth: ready (users preloaded)")
    except Exception as e:
        print(f"  Auth init: skipped ({e})")
    try:
        from backend.app.utils.db_fix import _run_sql, _get_mgmt_token
        if _get_mgmt_token():
            result = _run_sql("""
CREATE OR REPLACE FUNCTION exec_sql(sql_query TEXT)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE result JSONB;
BEGIN
  EXECUTE sql_query;
  GET DIAGNOSTICS result = ROW_COUNT;
  RETURN jsonb_build_object('ok', true, 'rows_affected', result);
EXCEPTION WHEN OTHERS THEN
  RETURN jsonb_build_object('ok', false, 'error', SQLERRM);
END;
$$;

CREATE TABLE IF NOT EXISTS local_users (
  id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT DEFAULT '',
  role TEXT DEFAULT 'citizen',
  district TEXT DEFAULT 'Chamoli',
  phone TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT true,
  password_hash TEXT NOT NULL,
  salt TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_users_email ON local_users (email);
ALTER TABLE local_users ENABLE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE policyname = 'local_users_full_access' AND tablename = 'local_users'
  ) THEN
    CREATE POLICY "local_users_full_access" ON local_users
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;
            """)
            if result.get("ok"):
                print("  Auth: local_users table ready")
                from backend.app.utils import local_auth
                local_auth._table_verified = False
            else:
                print(f"  Auth: table setup skipped ({result.get('error', '')[:80]})")
        else:
            print("  Auth: no SUPABASE_MGMT_TOKEN — run migrations/create_local_users_table.sql manually")
    except Exception as e:
        print(f"  Auth table setup: skipped ({e})")
    print("=" * 60)


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0",
            "layers": {"hazard_fusion": "operational",
                       "capacity_graph": "operational" if st.graph_data else "not_loaded",
                       "optimizer": "operational" if st.optimizer else "not_initialized"}}


# Keep local dev health endpoint too
@app.get("/health")
async def health_dev():
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
