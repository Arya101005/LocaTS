#!/usr/bin/env python3
"""
Full API pipeline test — exercises every endpoint.
"""
import json
import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.data.sample.chamoli_data import build_chamoli_sample, get_sample_hazard_zones, get_sample_sensor_readings

API = "http://127.0.0.1:8000"

def main():
    print("=" * 60)
    print("  LocaTS API Pipeline Test")
    print("=" * 60)

    # 1. Health check
    print("\n[1] Health check...")
    r = requests.get(f"{API}/health")
    print(f"    Status: {r.status_code}")
    print(f"    Solver: {r.json()['solver']}")

    # 2. Load capacity graph
    print("\n[2] Loading capacity graph...")
    graph = build_chamoli_sample()
    r = requests.post(f"{API}/api/capacity/load", json=graph.model_dump())
    print(f"    Status: {r.status_code}")
    data = r.json()
    print(f"    Habitations: {data['habitations']}, Shelters: {data['shelters']}")
    print(f"    Roads: {data['road_segments']}")
    summary = data['capacity_summary']
    print(f"    Beds available: {summary['total_beds_available']}")
    print(f"    Active shelters: {summary['active_shelters']}")

    # 3. Add hazard zones
    print("\n[3] Adding hazard zones...")
    for zone in get_sample_hazard_zones():
        r = requests.post(f"{API}/api/hazard/zones", json=zone)
        print(f"    {zone['id']}: {r.json()['status']}")

    # 4. Add sensor readings
    print("\n[4] Adding sensor readings...")
    for reading in get_sample_sensor_readings():
        r = requests.post(f"{API}/api/hazard/sensor", json=reading)
    print(f"    Added {len(get_sample_sensor_readings())} readings: {r.json()['status']}")

    # 5. Add crowd reports (3 for corroboration)
    print("\n[5] Adding crowd reports (3 for corroboration)...")
    reports = [
        {"reporter_id": "user-1", "hazard_type": "flood", "severity_estimate": 0.7, "description": "Water rising fast near bridge", "lat": 30.47, "lon": 79.55},
        {"reporter_id": "user-2", "hazard_type": "flood", "severity_estimate": 0.8, "description": "Road submerged, cars stuck", "lat": 30.48, "lon": 79.54},
        {"reporter_id": "user-3", "hazard_type": "flood", "severity_estimate": 0.75, "description": "River overflowing banks", "lat": 30.46, "lon": 79.56},
    ]
    for report in reports:
        r = requests.post(f"{API}/api/hazard/crowd-report", json=report)
        print(f"    {report['reporter_id']}: {r.json()['status']} (id: {r.json()['report_id']})")

    # 6. Fuse hazard scores
    print("\n[6] Running hazard fusion...")
    r = requests.post(f"{API}/api/hazard/fuse")
    data = r.json()
    print(f"    Evaluated {data['total_evaluated']} hazard scores")
    for key, score in list(data['fused_hazard_scores'].items())[:6]:
        print(f"    {key}: confidence={score['confidence']}, alert={score['alert_level']}")

    # 7. Run optimization
    print("\n[7] Running optimization...")
    r = requests.post(f"{API}/api/optimize/solve", json={"time_budget_seconds": 30.0})
    result = r.json()
    print(f"    Relocated: {result['total_people_relocated']:,}")
    print(f"    Unmet: {result['total_people_unmet']:,}")
    print(f"    Feasible: {result['is_feasible']}")
    print(f"    Fallback: {result['used_fallback_heuristic']}")
    print(f"    Solver time: {result['solver_time_seconds']}s")
    print(f"    Assignments: {len(result['assignments'])}")
    print(f"    Inter-district: {result['inter_district_assignments']}")
    print(f"    Disconnected: {result['disconnected_habitations']}")
    print(f"    Audit hash: {result['run_id']}")

    # 8. Simulate road failure
    print("\n[8] Simulating road failure (road-001 BLOCKED)...")
    r = requests.post(f"{API}/api/road/update", json={
        "road_id": "road-001", "new_status": "blocked", "damage_factor": 0.0
    })
    print(f"    {r.json()['status']}: {r.json()['road_id']} -> {r.json()['new_status']}")

    # 9. Re-optimize
    print("\n[9] Re-optimizing after road failure...")
    r = requests.post(f"{API}/api/optimize/re-solve", json={"time_budget_seconds": 30.0})
    data = r.json()
    result = data['result']
    order = data['order']
    print(f"    Relocated: {result['total_people_relocated']:,}")
    print(f"    Unmet: {result['total_people_unmet']:,}")
    print(f"    Disconnected: {result['disconnected_habitations']}")
    print(f"    Order: {order['order_id']}, hash: {order['audit_hash']}")
    if order['hash_chain_previous']:
        print(f"    Chain: prev={order['hash_chain_previous']}")

    # 10. Check dashboard
    print("\n[10] Dashboard summary...")
    r = requests.get(f"{API}/api/dashboard")
    data = r.json()
    print(f"    Hazard zones: {len(data['hazard_zones'])}")
    print(f"    Sensor readings: {data['sensor_readings_count']}")
    print(f"    Crowd reports: {data['crowd_reports_count']}")
    print(f"    Relocation orders: {data['relocation_orders_count']}")
    print(f"    Active shelters: {data['capacity_summary'].get('active_shelters', 0)}")

    # 11. Check orders
    print("\n[11] Relocation orders audit trail...")
    r = requests.get(f"{API}/api/orders")
    for o in r.json()['orders']:
        print(f"    {o['order_id']}: hash={o['audit_hash']}, prev={o['hash_chain_previous'] or 'genesis'}, relocated={o['total_relocated']}")

    print("\n" + "=" * 60)
    print("  ALL API ENDPOINTS TESTED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
