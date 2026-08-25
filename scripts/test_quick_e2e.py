#!/usr/bin/env python3
"""Quick e2e test with sample data (no network calls)."""
import sys, os, time, threading, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

def start_server():
    import uvicorn
    from backend.app.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=8770, log_level="error")

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(3)

API = "http://127.0.0.1:8770"
c = httpx.Client(timeout=30)
passed = total = 0

def test(name, fn):
    global passed, total
    total += 1
    try:
        r = fn()
        print(f"  PASS  {name}: {r}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")

print("\n" + "=" * 60)
print("  LocaTS Quick E2E Test (sample data)")
print("=" * 60)

# 1. Health
def t():
    r = c.get(f"{API}/health"); assert r.status_code == 200; return "ok"
test("Health", t)

# 2. Load sample graph
def t():
    from backend.app.data.sample.chamoli_data import build_chamoli_sample
    graph = build_chamoli_sample()
    r = c.post(f"{API}/api/capacity/load", json=graph.model_dump())
    assert r.status_code == 200, r.text[:200]
    d = r.json(); return f"{d['habitations']} hab, {d['shelters']} shelters"
test("Load sample graph", t)

# 3. Capacity summary
def t():
    r = c.get(f"{API}/api/capacity/summary"); assert r.status_code == 200
    d = r.json(); return f"{d['total_beds_available']} beds"
test("Capacity summary", t)

# 4. Add hazard zone
def t():
    r = c.post(f"{API}/api/hazard/zones", json={
        "id": "z-1", "hazard_type": "flood", "severity": 0.85,
        "center_lat": 30.47, "center_lon": 79.55, "radius_km": 20.0,
    }); assert r.status_code == 200; return "added"
test("Add hazard zone", t)

# 5. Add sensor
def t():
    r = c.post(f"{API}/api/hazard/sensor", json={
        "source": "imd_rainfall", "lat": 30.47, "lon": 79.55, "value": 85.0,
    }); assert r.status_code == 200; return f"total={r.json()['total_readings']}"
test("Add sensor reading", t)

# 6. Fuse hazards
def t():
    r = c.post(f"{API}/api/hazard/fuse"); assert r.status_code == 200
    d = r.json(); return f"{d['total_evaluated']} scores"
test("Hazard fusion", t)

# 7. Optimize
def t():
    r = c.post(f"{API}/api/optimize/solve", json={"time_budget_seconds": 30.0})
    assert r.status_code == 200; d = r.json()
    return f"relocated={d['total_people_relocated']}, feasible={d['is_feasible']}"
test("Optimization", t)

# 8. Dashboard
def t():
    r = c.get(f"{API}/api/dashboard"); assert r.status_code == 200
    d = r.json(); return f"zones={len(d.get('hazard_zones',[]))}"
test("Dashboard", t)

# 9. GeoJSON files
def t():
    for f in ["habitations.geojson", "shelters.geojson", "hazard_zones.geojson"]:
        r = c.get(f"{API}/api/data/{f}"); assert r.status_code == 200
    return "3 files ok"
test("GeoJSON data", t)

# 10. Road failure + re-optimize
def t():
    r = c.get(f"{API}/api/capacity/graph"); assert r.status_code == 200
    roads = r.json().get("road_segments", [])
    if not roads: return "no roads"
    r2 = c.post(f"{API}/api/road/update", json={
        "road_id": roads[0]["id"], "new_status": "blocked", "damage_factor": 0.0,
    }); assert r2.status_code == 200
    r3 = c.post(f"{API}/api/optimize/re-solve", json={"time_budget_seconds": 30.0})
    assert r3.status_code == 200; d = r3.json().get("result", r3.json())
    return f"relocated={d['total_people_relocated']}"
test("Road failure + re-optimize", t)

# 11. What-if
def t():
    r = c.post(f"{API}/api/whatif", json={"rainfall_multiplier": 2.0})
    assert r.status_code == 200; return "scenario ran"
test("What-if scenario", t)

# 12. Backtest
def t():
    r = c.get(f"{API}/api/backtest/events"); assert r.status_code == 200
    events = r.json().get("events", []); return f"{len(events)} events"
test("Backtest events", t)

# 13. Explain
def t():
    r = c.get(f"{API}/api/explain/hab-001"); return f"status={r.status_code}"
test("Explain endpoint", t)

# 14. Social vulnerability
def t():
    r = c.get(f"{API}/api/social-vulnerability"); assert r.status_code == 200
    return f"{len(r.json().get('habitations', []))} hab"
test("Social vulnerability", t)

print(f"\n{'='*60}")
print(f"  Results: {passed}/{total} passed")
print(f"{'='*60}")
sys.exit(0 if passed == total else 1)
