#!/usr/bin/env python3
"""
Self-contained full pipeline test — starts its own server, runs all endpoints.
"""
import sys
import os
import threading
import time
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.data.sample.chamoli_data import (
    build_chamoli_sample, get_sample_hazard_zones, get_sample_sensor_readings
)

def run_server():
    import uvicorn
    from backend.app.api.main import app
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

def main():
    print("=" * 60)
    print("  LocaTS Full Pipeline Test (self-contained)")
    print("=" * 60)

    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(3)

    API = "http://127.0.0.1:8001"

    # 1. Health
    print("\n[1] Health check...")
    r = requests.get(f"{API}/health")
    assert r.status_code == 200, f"Health failed: {r.status_code}"
    print(f"    OK: {r.json()['status']}")

    # 2. Load graph
    print("\n[2] Load capacity graph...")
    graph = build_chamoli_sample()
    r = requests.post(f"{API}/api/capacity/load", json=graph.model_dump())
    assert r.status_code == 200, f"Load failed: {r.status_code} {r.text}"
    d = r.json()
    print(f"    OK: {d['habitations']} hab, {d['shelters']} shelters, {d['road_segments']} roads")
    print(f"    Beds: {d['capacity_summary']['total_beds_available']}")

    # 3. Add hazard zones
    print("\n[3] Add hazard zones...")
    for zone in get_sample_hazard_zones():
        r = requests.post(f"{API}/api/hazard/zones", json=zone)
        assert r.status_code == 200
    print(f"    OK: {len(get_sample_hazard_zones())} zones added")

    # 4. Add sensor readings
    print("\n[4] Add sensor readings...")
    for reading in get_sample_sensor_readings():
        r = requests.post(f"{API}/api/hazard/sensor", json=reading)
        assert r.status_code == 200
    print(f"    OK: {len(get_sample_sensor_readings())} readings added")

    # 5. Add crowd reports
    print("\n[5] Add crowd reports...")
    reports = [
        {"reporter_id": "u1", "hazard_type": "flood", "severity_estimate": 0.7, "description": "Water rising", "lat": 30.47, "lon": 79.55},
        {"reporter_id": "u2", "hazard_type": "flood", "severity_estimate": 0.8, "description": "Road submerged", "lat": 30.48, "lon": 79.54},
        {"reporter_id": "u3", "hazard_type": "flood", "severity_estimate": 0.75, "description": "River overflowing", "lat": 30.46, "lon": 79.56},
    ]
    for report in reports:
        r = requests.post(f"{API}/api/hazard/crowd-report", json=report)
        assert r.status_code == 200
    print(f"    OK: 3 reports added")

    # 6. Fuse hazard scores
    print("\n[6] Hazard fusion...")
    r = requests.post(f"{API}/api/hazard/fuse")
    assert r.status_code == 200, f"Fuse failed: {r.status_code} {r.text[:200]}"
    d = r.json()
    print(f"    OK: {d['total_evaluated']} scores computed")
    for key, score in list(d['fused_hazard_scores'].items())[:4]:
        print(f"    {key}: {score['confidence']:.3f} ({score['alert_level']})")

    # 7. Run optimization
    print("\n[7] Optimization (OR-Tools MCF)...")
    r = requests.post(f"{API}/api/optimize/solve", json={"time_budget_seconds": 30.0})
    assert r.status_code == 200, f"Optimize failed: {r.status_code} {r.text[:200]}"
    result = r.json()
    print(f"    Relocated: {result['total_people_relocated']:,}")
    print(f"    Unmet: {result['total_people_unmet']:,}")
    print(f"    Feasible: {result['is_feasible']}")
    print(f"    Fallback: {result['used_fallback_heuristic']}")
    print(f"    Solver: {result['solver_time_seconds']}s")
    print(f"    Assignments: {len(result['assignments'])}")
    print(f"    Inter-district: {result['inter_district_assignments']}")

    # 8. Road failure simulation
    print("\n[8] Simulate road failure...")
    r = requests.post(f"{API}/api/road/update", json={
        "road_id": "road-001", "new_status": "blocked", "damage_factor": 0.0
    })
    assert r.status_code == 200, f"Road update failed: {r.status_code} {r.text[:300]}"
    d = r.json()
    print(f"    OK: {d['road_id']} -> {d['new_status']}")

    # 9. Re-optimize
    print("\n[9] Re-optimize after road failure...")
    r = requests.post(f"{API}/api/optimize/re-solve", json={"time_budget_seconds": 30.0})
    assert r.status_code == 200, f"Re-solve failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    result = data['result']
    order = data['order']
    print(f"    Relocated: {result['total_people_relocated']:,}")
    print(f"    Unmet: {result['total_people_unmet']:,}")
    print(f"    Disconnected: {result['disconnected_habitations']}")
    print(f"    Order: {order['order_id']}, hash: {order['audit_hash']}")
    if order['hash_chain_previous']:
        print(f"    Chain prev: {order['hash_chain_previous']}")

    # 10. Dashboard
    print("\n[10] Dashboard...")
    r = requests.get(f"{API}/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    print(f"    Zones: {len(d['hazard_zones'])}, Reports: {d['crowd_reports_count']}, Orders: {d['relocation_orders_count']}")

    # 11. Orders audit trail
    print("\n[11] Relocation orders...")
    r = requests.get(f"{API}/api/orders")
    assert r.status_code == 200
    for o in r.json()['orders']:
        print(f"    {o['order_id']}: hash={o['audit_hash']}, prev={o['hash_chain_previous'] or 'genesis'}")

    print("\n" + "=" * 60)
    print("  ALL 11 API ENDPOINTS TESTED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
