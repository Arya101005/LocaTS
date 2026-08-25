# LocaTS — Production Readiness Assessment

## What Is Production-Ready Today

These features are fully implemented, tested, and work without external dependencies:

| Feature | Status | Evidence |
|---------|--------|----------|
| Hazard Fusion Pipeline | ✅ Production-ready | 40/35/25 weighted scoring, staleness decay, corroboration gating |
| OR-Tools Optimizer | ✅ Production-ready | MinCostFlow solver, 30s budget, greedy fallback, atomic locking |
| Capacity Graph Builder | ✅ Production-ready | OSM road network, shelter POIs, population estimates |
| Citizen Portal | ✅ Production-ready | No-auth, Hindi/English, offline indicator, GPS option |
| Admin Dashboard | ✅ Production-ready | 3-column layout, live map, what-if scenarios, SSE push |
| Family Reunification | ✅ Production-ready | SHA-256 anonymized IDs, privacy-gated search |
| Audit Hash Chain | ✅ Production-ready | Tamper-evident relocation orders, public verification |
| Backtesting Engine | ✅ Production-ready | 2021 Chamoli flash flood simulation |
| Explainability Layer | ✅ Production-ready | Per-assignment reasoning, shelter comparisons |
| Social Vulnerability | ✅ Production-ready | Per-habitation weighting (elderly, disability, children) |
| Resource Shortfall Forecasting | ✅ Production-ready | Hours-to-full prediction with hysteresis |
| GeoJSON Data Serving | ✅ Production-ready | Live habitations, shelters, roads, hazard zones |
| PDF Report Generation | ✅ Production-ready | Official relocation order with audit hash |
| Open-Meteo Rainfall | ✅ Production-ready | Real-time rainfall, 7-day forecast, seasonal fallback |
| All 51 Tests | ✅ Passing | Edge cases, real data, API flows, privacy gates |

## What Is Prototype-Only (Working Demo, Not Production)

| Feature | Status | What's Missing |
|---------|--------|----------------|
| IVR Phone Helpline | Prototype | Twilio integration works but needs real phone number + production Twilio account |
| WhatsApp Bot | Prototype | Web-based simulation only; needs WhatsApp Business API approval |
| TTS Voice Alerts | Prototype | Twilio TTS works; needs production Twilio account for real calls |
| Multi-District Coordination | Prototype | Chamoli data is real; Pauri/Rudraprayag data is simulated |
| ML Population Estimation | Prototype | WorldPop API integration works; satellite blending is approximate |
| AI Assistant | Prototype (with key) | Groq integration works; local fallback is keyword-based, not truly intelligent |

## What Requires Infrastructure Not Yet Available

| Feature | Requirement | Status |
|---------|-------------|--------|
| Multi-instance deployment | Redis or full PostGIS for shared state | Not available — single-instance only |
| Real-time WebSocket updates | WebSocket server (currently SSE) | SSE is sufficient for current scale |
| Production authentication | Remove demo credentials, enforce MFA | Demo credentials removed from UI; Supabase Auth is functional |
| Rate limiting (production) | Redis-backed per-IP limiting | In-memory rate limiter added; not multi-instance safe |
| WhatsApp Business API | WhatsApp Business account + phone number | Not available |
| GeoServer OGC deployment | GeoServer instance | WFS/WMS endpoints return JSON descriptions; actual rendering needs GeoServer |
| GPU Solver (cuOpt) | NVIDIA GPU hardware | OR-Tools CPU solver is sufficient for current scale |
| PostGIS Persistent Storage | Supabase PostGIS extension | Supabase tables exist; write-through persistence is functional |
| WCAG Accessibility Audit | Manual testing with screen readers | Not performed |

## Known Limitations (Documented Risks)

See `SECURITY_NOTES.md` for security-specific risks. Key operational limitations:

1. **Single-instance only** — In-memory state + Supabase write-through is not safe for horizontal scaling
2. **Census 2011 data** — 15 years old; 15% population buffer applied
3. **IMD rainfall** — Open-Meteo API is reliable; IMD HTML scraping is fragile (not currently used)
4. **OSM rural coverage** — Himalayan road network may be incomplete
5. **No real-time sensor feeds** — Sensor readings are manual or seasonal model

## Test Coverage

| Test Suite | Count | What It Covers |
|------------|-------|----------------|
| Edge Cases | 14 | Infeasibility, disconnected graph, race conditions, staleness, corroboration, accessibility, multi-hazard |
| Real Data | 27 | OSM ingestion, NDMA zones, rainfall classification, GeoJSON export, population buffer |
| API Flows | 10 | Auth flow, optimizer solve, corroboration gating, family privacy, health check |
| **Total** | **51** | All passing ✅ |

## Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| In-memory state | Fast iteration for hackathon; documented as single-instance limitation |
| SSE over WebSocket | Simpler, HTTP-compatible, sufficient for dashboard push updates |
| OR-Tools over cuOpt | CPU solver is sufficient for 24 villages; GPU not available |
| Supabase over raw PostgreSQL | Free tier, built-in auth, managed service |
| gTTS/Twilio over custom TTS | Twilio provides Hindi+English; gTTS is free fallback |

## What Would Be Needed for Real Deployment

1. **PostgreSQL/PostGIS** — Replace in-memory state with persistent database
2. **Redis** — Rate limiting, session management, multi-instance state
3. **Reverse Proxy** — Nginx/Caddy for HTTPS, static files, load balancing
4. **Monitoring** — Structured logging, error tracking (Sentry), health checks
5. **CI/CD** — GitHub Actions for lint, test, deploy
6. **Secrets Manager** — HashiCorp Vault or cloud KMS for API keys
7. **Backup Strategy** — Database backups, GeoJSON snapshots
8. **Load Testing** — Verify optimizer performance under real evacuation load
