# LocaTS — API Contract

All team members must follow these endpoint formats exactly.
The frontend (Segment 1) calls these endpoints. Changes here break other segments.

**Base URL:** `/api` (proxied by Vercel or localhost:8000)

---

## Authentication (Segment 5)

### POST /api/auth/signup
```json
// Request
{ "email": "string", "password": "string", "name": "string" }

// Response (200)
{
  "status": "signup_complete",
  "message": "Account created successfully! Please sign in.",
  "access_token": "jwt_string",
  "user": { "email": "string", "id": "uuid" },
  "role": "citizen"
}

// Error (400)
{ "detail": "An account with this email already exists." }
```

### POST /api/auth/login
```json
// Request
{ "email": "string", "password": "string" }

// Response (200)
{
  "access_token": "jwt_string",
  "refresh_token": "",
  "expires_at": 1234567890,
  "user": { "email": "string", "id": "uuid" },
  "role": "admin|operator|citizen|viewer"
}

// Error (401)
{ "detail": "Invalid email or password." }
```

### GET /api/auth/me
```json
// Headers: Authorization: Bearer <token>
// Response (200)
{ "user": { "sub": "uuid", "email": "string", "role": "string" } }
```

### GET /api/auth/users
```json
// Headers: Authorization: Bearer <token> (admin only)
// Response (200)
{
  "users": [
    { "id": "uuid", "email": "string", "full_name": "string", "role": "string", "is_active": true }
  ]
}
```

### PUT /api/auth/users/{user_id}/role?role=new_role
```json
// Headers: Authorization: Bearer <token> (admin only)
// Response (200)
{ "status": "updated", "user_id": "uuid", "new_role": "operator" }
```

---

## Dashboard (Segment 1)

### GET /api/dashboard
```json
// Response (200)
{
  "hazard_zones": [
    { "id": "hz-001", "hazard_type": "flood", "severity": 0.8, "zone_type": "evacuate", "center": {"lat": 30.4, "lon": 79.3}, "radius_km": 5.0 }
  ],
  "hazard_confidences": {
    "hab-001:flood": { "confidence": 0.75, "alert_level": "advisory", "hazard_type": "flood" }
  },
  "capacity_summary": {
    "total_population": 295900,
    "active_shelters": 26,
    "total_beds_available": 247000,
    "shelters": [
      { "id": "sh-001", "name": "Govt Inter College Gopeshwar", "bed_capacity": 5000, "beds_occupied": 1200 }
    ]
  },
  "latest_result": {
    "is_feasible": true,
    "total_people_relocated": 280000,
    "total_people_unmet": 15900,
    "assignments": [
      { "habitation_id": "hab-001", "shelter_id": "sh-001", "people": 1500, "distance_km": 12.3 }
    ]
  },
  "crowd_reports": [
    { "id": "cr-00001", "reporter_id": "citizen-1", "hazard_type": "flood", "severity_estimate": 0.7, "description": "River rising fast", "timestamp": "2026-08-25T10:00:00" }
  ],
  "sensor_readings": []
}
```

---

## Hazard (Segment 2)

### GET /api/hazard/zones
```json
// Response (200)
{ "zones": [{ "id": "hz-001", "hazard_type": "flood", "severity": 0.8, "zone_type": "evacuate", "center": {"lat": 30.4, "lon": 79.3}, "radius_km": 5.0 }] }
```

### GET /api/hazard/confidences
```json
// Response (200)
{ "confidences": { "hab-001:flood": { "confidence": 0.75, "alert_level": "advisory", "hazard_type": "flood" } } }
```

### POST /api/hazard/report
```json
// Request
{ "reporter_id": "citizen-1", "hazard_type": "flood", "severity_estimate": 0.7, "description": "string", "lat": 30.4, "lon": 79.3 }

// Response (200)
{ "status": "accepted", "report_id": "cr-00001", "message": "Report received." }
```

### POST /api/hazard/simulate
```json
// Request
{ "sensor_id": "s-001", "sensor_type": "water_level", "value": 4.5, "lat": 30.4, "lon": 79.3 }

// Response (200)
{ "status": "accepted", "reading_id": "sr-001" }
```

---

## Satellite & Rainfall (Segment 2)

### GET /api/satellite/rainfall
```json
// Response (200)
{
  "readings": [
    { "timestamp": "2026-08-25T10:00:00", "rainfall_mm": 12.5, "location": {"lat": 30.4, "lon": 79.3} }
  ],
  "total_24h_mm": 45.2,
  "status": "moderate"
}
```

### GET /api/satellite/sensors
```json
// Response (200)
{
  "sensors": [
    { "sensor_id": "s-001", "type": "water_level", "value": 4.5, "unit": "m", "lat": 30.4, "lon": 79.3, "timestamp": "2026-08-25T10:00:00", "status": "normal" }
  ]
}
```

---

## Optimization (Segment 3)

### POST /api/optimize/solve
```json
// Request
{ "time_budget_seconds": 30.0 }

// Response (200)
{ "status": "solving", "message": "Optimization started. Check /api/optimize/result for results." }
```

### GET /api/optimize/result
```json
// Response (200)
{
  "is_feasible": true,
  "total_people_relocated": 280000,
  "total_people_unmet": 15900,
  "total_distance_km": 1250.5,
  "assignments": [
    { "habitation_id": "hab-001", "shelter_id": "sh-001", "people": 1500, "distance_km": 12.3 }
  ],
  "shelter_summary": [
    { "shelter_id": "sh-001", "assigned": 3500, "capacity": 5000, "utilization": 0.7 }
  ]
}
```

### GET /api/capacity/summary
```json
// Response (200)
{
  "total_population": 295900,
  "active_shelters": 26,
  "total_beds": 312000,
  "total_beds_available": 247000,
  "utilization_pct": 20.8,
  "shelters": [
    { "id": "sh-001", "name": "string", "district": "Chamoli", "bed_capacity": 5000, "beds_occupied": 1200, "beds_available": 3800, "status": "open" }
  ]
}
```

### GET /api/resources/shortfall-forecast
```json
// Response (200)
{
  "forecasts": [
    { "shelter_id": "sh-001", "shelter_name": "string", "district": "Chamoli", "beds_occupied": 1200, "bed_capacity": 5000, "occupancy_pct": 24.0, "estimated_hours_to_full": 48, "water_hours_remaining": 72, "status": "ok" }
  ]
}
```

---

## Citizen Portal (Segment 4)

### GET /api/citizen/status/{village_id}
```json
// Response (200)
{
  "village_id": "hab-001",
  "village_name": "Gopeshwar",
  "block": "Chamoli",
  "population": 12000,
  "hazard_level": "critical|warning|normal",
  "hazard_detail": "Flood risk. EVACUATE.",
  "action_text": "EVACUATE NOW to Govt Inter College (12.3km).",
  "action_urgency": "high|medium|low",
  "nearest_shelter": { "name": "string", "distance_km": 12.3, "beds_available": 3800 },
  "assigned_shelter": { "name": "string", "distance_km": 15.0 }
}
```

### GET /api/citizen/villages
```json
// Response (200)
{
  "villages": [
    { "id": "hab-001", "name": "Gopeshwar", "block": "Chamoli", "lat": 30.4, "lon": 79.3, "population": 12000, "hazard_level": "critical|warning|normal" }
  ],
  "total": 279
}
```

### POST /api/citizen/report
```json
// Request
{ "reporter_id": "citizen-1", "hazard_type": "flood", "severity_estimate": 0.7, "description": "string", "lat": 30.4, "lon": 79.3 }

// Response (200)
{ "status": "accepted", "report_id": "cr-00001", "message": "Report received." }
```

### GET /api/citizen/shelters
```json
// Response (200)
{
  "shelters": [
    { "id": "sh-001", "name": "string", "district": "Chamoli", "lat": 30.4, "lon": 79.3, "type": "school", "bed_capacity": 5000, "beds_available": 3800, "status": "open|limited|full", "is_accessible": true }
  ],
  "total": 26
}
```

### POST /api/family/register
```json
// Request
{ "name_hash": "sha256_of_name", "home_habitation_id": "hab-001", "registered_shelter_id": "sh-001", "age_range": "30-40", "needs_medical": false, "needs_accessibility": false }

// Response (200)
{ "status": "registered", "evacuee_id": "EVC-XXXXXXXXXXXX", "message": "Evacuee registered at sh-001." }
```

### POST /api/family/search
```json
// Request
{ "search_name": "John Doe", "home_habitation_id": "hab-001", "age_range": "30-40" }

// Response (200)
{ "results": [{ "evacuee_id": "EVC-XXX", "shelter_id": "sh-001", "shelter_name": "string", "status": "safe", "registered_at": "ISO8601", "is_match": true }], "message": "Found 1 record(s)." }
```

---

## Communication (Segment 4)

### POST /api/communication/send-sms
```json
// Request
{ "to": "+919876543210", "message": "Evacuation alert: Move to nearest shelter immediately." }

// Response (200)
{ "status": "sent", "message_id": "twilio_sid" }
```

### POST /api/communication/send-whatsapp
```json
// Request
{ "to": "+919876543210", "message": "Emergency alert from LocaTS" }

// Response (200)
{ "status": "sent", "message_id": "twilio_sid" }
```

---

## AI Assistant (Segment 5)

### POST /api/ai/chat
```json
// Request
{ "message": "What is the flood risk in Gopeshwar?", "context": {} }

// Response (200)
{ "response": "Based on current sensor data...", "suggestions": ["Check shelter availability", "View satellite imagery"] }
```

### GET /api/ai/suggestions
```json
// Response (200)
{ "suggestions": ["Analyze flood risk", "Find nearest shelter", "Check evacuation status"] }
```

---

## Audit (Segment 5)

### GET /api/orders
```json
// Response (200)
{ "orders": [{ "order_id": "ORD-001", "issued_at": "2026-08-25T10:00:00", "audit_hash": "abc123...", "is_feasible": true, "total_relocated": 280000 }] }
```

### GET /api/audit/verify/{order_id}
```json
// Response (200)
{ "hash_match": true, "verification_result": "Order verified. Hash chain intact.", "plain_explanation": "The order has not been tampered with." }
```

---

## Error Format

All errors return:
```json
{ "detail": "Human-readable error message" }
```

With appropriate HTTP status codes:
- `400` — Bad request (validation error)
- `401` — Not authenticated
- `403` — Forbidden (wrong role)
- `404` — Not found
- `500` — Server error
