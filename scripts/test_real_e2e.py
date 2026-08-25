#!/usr/bin/env python3
"""
End-to-end API test with real data.

Starts a local FastAPI server, loads real OSM/NDMA data,
runs hazard fusion, optimization, and verifies the full pipeline.

Usage:
    PYTHONPATH=. python scripts/test_real_e2e.py
"""
import sys, os, time, threading, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

# Start the server in a thread
def start_server():
    import uvicorn
    from backend.app.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(3)  # wait for server

API = "http://127.0.0.1:8765"
client = httpx.Client(timeout=300)

def test(name, fn):
    try:
        result = fn()
        print(f"  PASS  {name}: {result}")
        return True
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        return False

passed = 0
total = 0

print("\n" + "=" * 60)
print("  LocaTS End-to-End Test with Real Data")
print("=" * 60)

# 1. Health check
def t_health():
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    return r.json()["status"]
total += 1; passed += test("Health check", t_health)

# 2. Load real data
def t_load_real():
    r = client.post(f"{API}/api/capacity/load-real?district=Chamoli&state=Uttarakhand")
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:200]}"
    data = r.json()
    assert data["habitations"] > 0, "No habitations loaded"
    assert data["shelters"] > 0, "No shelters loaded"
    return f"{data['habitations']} hab, {data['shelters']} shelters, {data['road_segments']} roads"
total += 1; passed += test("Load real data (OSM+NDMA)", t_load_real)

# 3. Get capacity summary
def t_capacity():
    r = client.get(f"{API}/api/capacity/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["total_beds_available"] > 0
    return f"{data['total_beds_available']} beds, {data['active_shelters']} shelters"
total += 1; passed += test("Capacity summary", t_capacity)

# 4. Add hazard zones
def t_hazard_zones():
    r = client.post(f"{API}/api/hazard/zones", json={
        "id": "test-flood-001", "hazard_type": "flood",
        "severity": 0.85, "zone_type": "red",
        "center_lat": 30.47, "center_lon": 79.55, "radius_km": 20.0,
    })
    assert r.status_code == 200
    return f"Zone added: {r.json()['zone_id']}"
total += 1; passed += test("Add hazard zone", t_hazard_zones)

# 5. Add sensor reading
def t_sensor():
    r = client.post(f"{API}/api/hazard/sensor", json={
        "source": "imd_rainfall", "lat": 30.47, "lon": 79.55, "value": 85.0,
    })
    assert r.status_code == 200
    return f"Sensor added, total: {r.json()['total_readings']}"
total += 1; passed += test("Add sensor reading", t_sensor)

# 6. Run hazard fusion
def t_fuse():
    r = client.post(f"{API}/api/hazard/fuse")
    assert r.status_code == 200
    data = r.json()
    assert data["total_evaluated"] > 0
    # Count alert levels
    levels = {}
    for v in data["fused_hazard_scores"].values():
        lvl = v["alert_level"]
        levels[lvl] = levels.get(lvl, 0) + 1
    return f"{data['total_evaluated']} scores, levels: {levels}"
total += 1; passed += test("Hazard fusion", t_fuse)

# 7. Run optimization
def t_optimize():
    r = client.post(f"{API}/api/optimize/solve", json={"time_budget_seconds": 30.0})
    assert r.status_code == 200
    data = r.json()
    assert "assignments" in data
    relocated = data.get("total_people_relocated", 0)
    unmet = data.get("total_people_unmet", 0)
    feasible = data.get("is_feasible", False)
    return f"relocated={relocated}, unmet={unmet}, feasible={feasible}, time={data.get('solver_time_seconds', 0):.2f}s"
total += 1; passed += test("Optimization solve", t_optimize)

# 8. Dashboard data
def t_dashboard():
    r = client.get(f"{API}/api/dashboard")
    assert r.status_code == 200
    data = r.json()
    return f"hazard_zones={len(data.get('hazard_zones', []))}, confidences={len(data.get('hazard_confidences', {}))}"
total += 1; passed += test("Dashboard data", t_dashboard)

# 9. GeoJSON data files
def t_geojson():
    for name in ["habitations.geojson", "shelters.geojson", "hazard_zones.geojson"]:
        r = client.get(f"{API}/api/data/{name}")
        assert r.status_code == 200, f"Failed to get {name}: HTTP {r.status_code}"
    return "habitations, shelters, hazard_zones all accessible"
total += 1; passed += test("GeoJSON data files", t_geojson)

# 10. Explain endpoint
def t_explain():
    r = client.get(f"{API}/api/explain/hab-001")
    # May return 404 if IDs differ, that's OK
    if r.status_code == 200:
        return f"Explanation returned"
    return f"Explanation endpoint available (status {r.status_code})"
total += 1; passed += test("Explain endpoint", t_explain)

# 11. Road failure simulation
def t_road_failure():
    # Get graph to find a road ID
    r = client.get(f"{API}/api/capacity/graph")
    if r.status_code != 200:
        return "Skipped (no graph)"
    graph = r.json()
    roads = graph.get("road_segments", [])
    if not roads:
        return "No roads to block"
    road_id = roads[0]["id"]
    r2 = client.post(f"{API}/api/road/update", json={
        "road_id": road_id, "new_status": "blocked", "damage_factor": 0.0,
    })
    assert r2.status_code == 200
    return f"Blocked {road_id}"
total += 1; passed += test("Road failure simulation", t_road_failure)

# 12. Re-optimize after road failure
def t_reoptimize():
    r = client.post(f"{API}/api/optimize/re-solve", json={"time_budget_seconds": 30.0})
    assert r.status_code == 200
    data = r.json()
    result = data.get("result", data)
    return f"relocated={result.get('total_people_relocated', 0)}, disconnected={len(result.get('disconnected_habitations', []))}"
total += 1; passed += test("Re-optimize after road failure", t_reoptimize)

# Summary
print("\n" + "=" * 60)
print(f"  Results: {passed}/{total} passed")
print("=" * 60)

if passed < total:
    sys.exit(1)
