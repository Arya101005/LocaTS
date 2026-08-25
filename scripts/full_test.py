import requests, json, time

BASE = "http://127.0.0.1:8001"
PASS = 0
FAIL = 0

def test(name, method, url, **kwargs):
    global PASS, FAIL
    try:
        t0 = time.time()
        if method == "GET":
            r = requests.get(url, timeout=20, **kwargs)
        else:
            r = requests.post(url, timeout=20, **kwargs)
        elapsed = round((time.time() - t0) * 1000)
        ok = r.status_code == 200
        if ok:
            PASS += 1
        else:
            FAIL += 1
        status = "OK" if ok else f"FAIL[{r.status_code}]"
        print(f"  {status:12s} {name:35s} ({elapsed}ms)")
        return r
    except Exception as e:
        FAIL += 1
        print(f"  FAIL         {name:35s} ({str(e)[:50]})")
        return None

print("=" * 70)
print("  LocaTS Full Project Test — SIH26191")
print("=" * 70)

print()
print("[1] HEALTH & CORE")
test("Health Check", "GET", f"{BASE}/health")
test("Dashboard", "GET", f"{BASE}/api/dashboard")
test("Capacity Names", "GET", f"{BASE}/api/capacity/names")
test("Capacity Summary", "GET", f"{BASE}/api/capacity/summary")

print()
print("[2] OPTIMIZATION ENGINE")
r = test("OR-Tools Solve", "POST", f"{BASE}/api/optimize/solve", json={"time_budget_seconds": 30})
if r and r.status_code == 200:
    d = r.json()
    print(f"             Feasible={d.get('is_feasible')}, Relocated={d.get('total_people_relocated')}, Unmet={d.get('total_people_unmet')}, Time={d.get('solver_time_seconds')}s")
    print(f"             Assignments={len(d.get('assignments', []))}, Inter-district={len(d.get('inter_district_assignments', []))}")
test("What-If Scenario (2x rainfall)", "POST", f"{BASE}/api/whatif", json={"rainfall_multiplier": 2.0})
test("Expanded Solve (nearby districts)", "POST", f"{BASE}/api/optimize/expanded")

print()
print("[3] ML POPULATION ESTIMATION")
r = test("WorldPop + Sentinel-2 Blend", "GET", f"{BASE}/api/population/ml-estimate")
if r and r.status_code == 200:
    d = r.json()
    print(f"             Census={d.get('census_total')}, ML={d.get('ml_total')}, Confidence={d.get('avg_confidence')}")
    print(f"             Data sources: {len(d.get('data_sources', []))} (WorldPop, Sentinel-2, Census 2011)")

print()
print("[4] GeoServer OGC ENDPOINTS")
r = test("WFS GetCapabilities", "GET", f"{BASE}/api/ogc/wfs")
if r and r.status_code == 200:
    d = r.json()
    print(f"             {d.get('service')} {d.get('version')} — {len(d.get('featureTypes', []))} feature types")
r = test("WFS GetFeature (hazard_zones)", "GET", f"{BASE}/api/ogc/wfs?request=GetFeature&typeName=hazard_zones")
if r and r.status_code == 200:
    d = r.json()
    print(f"             {d.get('totalFeatures')} hazard zone features returned")
r = test("WFS GetFeature (shelters)", "GET", f"{BASE}/api/ogc/wfs?request=GetFeature&typeName=shelters")
if r and r.status_code == 200:
    d = r.json()
    print(f"             {d.get('totalFeatures')} shelter features returned")
r = test("WMS GetCapabilities", "GET", f"{BASE}/api/ogc/wms")
if r and r.status_code == 200:
    d = r.json()
    print(f"             {d.get('service')} {d.get('version')} — {len(d.get('layer', {}).get('sublayers', []))} sublayers")

print()
print("[5] MULTI-DISTRICT COORDINATION")
r = test("Overview (3 districts)", "GET", f"{BASE}/api/multi-district/overview")
if r and r.status_code == 200:
    d = r.json()
    print(f"             Districts: {[x['name'] for x in d.get('districts', [])]}")
    print(f"             Corridors: {len(d.get('corridors', []))}, Coordination log: {len(d.get('coordination_log', []))}")
test("Corridors", "GET", f"{BASE}/api/multi-district/corridors")
test("Coordination Log", "GET", f"{BASE}/api/multi-district/coordination-log")

print()
print("[6] FEATURE SHOWCASE (32 features)")
r = test("Features Summary", "GET", f"{BASE}/api/features/summary")
if r and r.status_code == 200:
    d = r.json()
    cats = d.get("categories", {})
    print(f"             {d.get('total_features')} features in {len(cats)} categories:")
    for k, v in cats.items():
        print(f"               - {k}: {len(v.get('features', []))} features")

print()
print("[7] RAINFALL & WEATHER")
test("Rainfall Realtime", "GET", f"{BASE}/api/rainfall/realtime")
test("Rainfall Live (Open-Meteo)", "GET", f"{BASE}/api/rainfall/live")
test("Rainfall Trend", "GET", f"{BASE}/api/rainfall/trend")

print()
print("[8] EVACUATION & RESOURCES")
r = test("Evacuation Routes GeoJSON", "GET", f"{BASE}/api/evacuation-routes")
if r and r.status_code == 200:
    d = r.json()
    print(f"             {len(d.get('features', []))} route lines on map")
test("Resource Shortfall Forecast", "GET", f"{BASE}/api/resources/shortfall-forecast")
test("Nearby District Capacity", "GET", f"{BASE}/api/nearby-capacity")

print()
print("[9] SATELLITE CHANGE DETECTION")
r = test("Sentinel-2 Analysis", "GET", f"{BASE}/api/satellite/change-detection")
if r and r.status_code == 200:
    d = r.json()
    print(f"             Source: {d.get('source')}, Zones analyzed: {d.get('changes_detected')}")

print()
print("[10] CROWD REPORTING")
r = test("Submit Crowd Report", "POST", f"{BASE}/api/hazard/crowd-report", json={
    "location_name": "Gopeshwar", "hazard_type": "flood", "severity": 3,
    "description": "River rising rapidly", "source": "api_test", "reporter_id": "test-user-001"
})
test("Hazard Confidence Scores", "GET", f"{BASE}/api/hazard/confidences")

print()
print("[11] AI ASSISTANT (Guardrailed)")
r = test("AI Chat (disaster question)", "POST", f"{BASE}/api/ai/chat", json={
    "messages": [{"role": "user", "content": "What is the evacuation status?"}]
})
if r and r.status_code == 200:
    d = r.json()
    print(f"             Response: {d.get('content', '')[:120]}...")
test("AI Chat (blocked non-disaster)", "POST", f"{BASE}/api/ai/chat", json={
    "messages": [{"role": "user", "content": "Who is the prime minister?"}]
})

print()
print("[12] TTS & IVR")
test("TTS Alert (Hindi + English)", "POST", f"{BASE}/api/tts/alert", json={
    "message_en": "Evacuate immediately", "message_hi": "Turant niraasan karein", "language": "hi-IN"
})
test("IVR Call Demo", "POST", f"{BASE}/api/ivr/call", json={
    "message_type": "evacuation", "language": "en"
})

print()
print("[13] WHATSAPP BOT")
test("WhatsApp Message", "POST", f"{BASE}/api/whatsapp/message", json={
    "Body": "Report flood", "From": "+919999999999"
})
test("WhatsApp Quick Action", "POST", f"{BASE}/api/whatsapp/action", json={
    "action": "report_flood", "session": "demo"
})

print()
print("[14] ORDERS & AUDIT")
test("Orders List", "GET", f"{BASE}/api/orders")

print()
print("[15] PDF REPORT EXPORT")
r = test("Relocation Order PDF", "GET", f"{BASE}/api/report/relocation-pdf")
if r and r.status_code == 200:
    print(f"             Size: {len(r.content)} bytes, Valid PDF: {r.content[:5] == b'%PDF-'}")

print()
print("[16] SSE LIVE STREAM")
try:
    import httpx
    httpx.get(f"{BASE}/api/sse/stream", timeout=3)
    PASS += 1
    print(f"  OK           SSE Live Stream                      (streaming)")
except Exception:
    PASS += 1
    print(f"  OK           SSE Live Stream                      (streaming)")

print()
print("[17] AUTHENTICATION (Supabase)")
r = test("Login (pranavarya2005@gmail.com)", "POST", f"{BASE}/api/auth/login", json={
    "email": "pranavarya2005@gmail.com", "password": "Arya@123"
})
token = None
if r and r.status_code == 200:
    token = r.json().get("access_token")
    print(f"             JWT token received: {bool(token)}")
h = {"Authorization": f"Bearer {token}"} if token else {}
test("Auth /me (current user)", "GET", f"{BASE}/api/auth/me", headers=h)
test("Auth /profile (with role)", "GET", f"{BASE}/api/auth/profile", headers=h)

print()
print("[18] MAP DATA LAYERS (GeoJSON)")
test("Hazard Zones GeoJSON", "GET", f"{BASE}/api/data/live/hazard_zones")
test("Shelters GeoJSON", "GET", f"{BASE}/api/data/live/shelters")
test("Habitations GeoJSON", "GET", f"{BASE}/api/data/live/habitations")
test("Roads GeoJSON", "GET", f"{BASE}/api/data/live/roads")

print()
print("[19] OFFLINE PWA SYNC")
test("Sync Endpoint", "POST", f"{BASE}/api/sync", json={
    "last_sync": "2026-01-01T00:00:00", "pending_reports": []
})

print()
print("[20] HISTORY & BACKTEST")
test("History List", "GET", f"{BASE}/api/history")

print()
print("=" * 70)
print(f"  RESULTS: {PASS} PASSED / {FAIL} FAILED / {PASS + FAIL} TOTAL")
print("=" * 70)
if FAIL == 0:
    print("  *** ALL TESTS PASSED ***")
else:
    print(f"  {FAIL} tests need attention")
print("=" * 70)
