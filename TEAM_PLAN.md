# LocaTS — Team Division Plan

## Project: Intelligent Disaster Relocation Planning (SIH26191)

**5 team members, 5 segments, zero conflicts.**

---

## How to Work

1. Each member clones the repo into their own empty GitHub repo
2. Each person works **only** on their assigned files (listed below)
3. When done, submit a PR back to the main `dev` branch
4. The team lead merges all PRs in order

```bash
# Setup (run once)
git clone https://github.com/YOUR_ORG/LocaTS.git LocaTS-YourName
cd LocaTS-YourName
git remote set-url origin https://github.com/YOUR_USERNAME/LocaTS-YourName.git
git push -u origin dev

# Install
pip install -r requirements.txt
cd frontend && npm install && cd ..
cp .env.example .env   # Fill in your Supabase + Groq keys

# Run
python run.py          # Backend on :8000
cd frontend && npm run dev  # Frontend on :5173
```

---

## Segment 1: Core Framework & Dashboard (Member 1)

**Role:** Core Architect — "The Shell"

### Files to Own

| Layer | File | Description |
|-------|------|-------------|
| Frontend | `frontend/src/App.jsx` | Main layout, routing, nav, all inline components |
| Frontend | `frontend/src/App.css` | Global styles, design system |
| Frontend | `frontend/src/main.jsx` | React entry point |
| Frontend | `frontend/src/hooks/useSSE.js` | Server-Sent Events hook |
| Frontend | `frontend/src/components/Dashboard.jsx` | Command Overview dashboard |
| Backend | `backend/app/api/main.py` | FastAPI app setup, startup, router registration |
| Backend | `backend/app/api/routers/dashboard.py` | Dashboard data endpoint |

### Tasks

1. **App Layout & Navigation** (in `App.jsx`)
   - Maintain NAV_ITEMS array with icons and role permissions
   - Sidebar navigation with active states
   - Header with user email, role badge, SSE indicator, sign-out
   - Tab switching with `startTransition`
   - Role-based routing (citizen → CitizenPortal, admin/operator → sidebar)

2. **Dashboard (Command Overview)** (in `Dashboard.jsx`)
   - Hazard zone cards with severity colors (green/yellow/red)
   - Population statistics grid
   - Shelter capacity overview with progress bars
   - "Run Optimization" / "Re-Optimize" buttons with loading states
   - Crowd reports queue (first 25 recent reports)

3. **SSE Live Updates** (`useSSE.js`)
   - Auto-reconnect on disconnect
   - Connection status indicator (Live/Reconnecting/Offline)
   - Real-time data push to Dashboard

4. **CSS Design System** (`App.css`)
   - Card styles: `.card`, `.card-header`
   - Badge styles: `.badge-safe`, `.badge-warn`, `.badge-danger`, `.badge-info`
   - Button styles: `.btn-primary`, `.btn-secondary`, `.btn-sm`
   - Form styles: `.form-select`, `.form-input`
   - Layout: `.app-layout`, `.app-header`, `.app-sidebar`, `.app-main`
   - Loading: `.skeleton`, `.page-transition`
   - Alerts: `.alert-banner`, `.toast-notification`

5. **Shelter Management** (inline in `App.jsx`)
   - `ShelterManagement` component
   - Resource shortfall forecast cards
   - Shelter capacity grid

### UI Focus
- Consistent card and badge styling across all sections
- Loading skeletons for async data
- Toast notifications for errors
- Responsive sidebar (collapses on mobile)

### Verification Checklist
- [ ] Login loads Dashboard with real data
- [ ] Sidebar shows correct items per role
- [ ] SSE indicator shows Live/Offline correctly
- [ ] Optimization buttons trigger with loading spinner
- [ ] All nav items work (click → correct component)
- [ ] Mobile responsive layout

---

## Segment 2: Hazard Intelligence & Satellite (Member 2)

**Role:** Data Scientist — "The Brain"

### Files to Own

| Layer | File | Description |
|-------|------|-------------|
| Frontend | `frontend/src/components/SatelliteMonitor.jsx` | Satellite imagery & rainfall viewer |
| Backend | `backend/app/api/routers/hazard.py` | Hazard zone & fusion API |
| Backend | `backend/app/api/routers/satellite_rainfall.py` | Satellite & rainfall API |
| Backend | `backend/app/hazard_fusion/fusion.py` | Multi-source hazard fusion engine |
| Backend | `backend/app/data/chamoli_dataset.py` | Chamoli district dataset loader |
| Backend | `backend/app/data/persistence.py` | Supabase persistence layer |

### Tasks

1. **Hazard Fusion Engine** (`fusion.py`)
   - Score hazards from: crowd reports + sensor data + static zones
   - Bayesian confidence calculation per village:hazard pair
   - Alert level classification: normal → advisory → evacuate → relocate
   - Return confidence dict keyed by `{village_id}:{hazard_type}`

2. **Hazard API** (`hazard.py`)
   - `GET /api/hazard/zones` — all static hazard zones
   - `GET /api/hazard/confidences` — current fusion scores
   - `GET /api/hazard/status/{village_id}` — village-specific risk
   - `POST /api/hazard/report` — submit crowd report (rate-limited)
   - `POST /api/hazard/simulate` — simulate sensor reading

3. **Satellite & Rainfall API** (`satellite_rainfall.py`)
   - `GET /api/satellite/ndvi` — vegetation health data
   - `GET /api/satellite/rainfall` — rainfall accumulation
   - `GET /api/satellite/sensors` — live sensor readings
   - `POST /api/satellite/fetch` — trigger satellite data refresh

4. **Satellite Monitor UI** (`SatelliteMonitor.jsx`)
   - Rainfall accumulation display (mm/hr)
   - NDVI anomaly percentage
   - Active hazard alerts count
   - Sensor readings table with timestamps
   - Color-coded severity indicators

5. **Data Layer** (`chamoli_dataset.py`, `persistence.py`)
   - Load Chamoli dataset (279 habitations, 26 shelters, 342 road segments)
   - Seed data to Supabase on startup
   - Ensure `st.graph_data`, `st.static_zones`, `st.sensor_readings` are populated

### UI Focus
- Color-coded hazard severity (green → yellow → orange → red)
- Animated alert indicators
- Clean data tables with sorting
- Loading states for satellite data fetch

### Verification Checklist
- [ ] Fusion engine computes correct confidence scores
- [ ] Satellite monitor shows rainfall and NDVI data
- [ ] Crowd reports influence hazard scores
- [ ] All API endpoints return proper JSON
- [ ] Dashboard hazard cards reflect real-time fusion data

---

## Segment 3: Optimization Engine & Capacity (Member 3)

**Role:** Optimization Engineer — "The Solver"

### Files to Own

| Layer | File | Description |
|-------|------|-------------|
| Frontend | `RelocationAnalysis` component | In `App.jsx` (Optimization Console) |
| Frontend | `ShelterManagement` component | In `App.jsx` (Shelter Management) |
| Backend | `backend/app/api/routers/optimizer.py` | Optimization API |
| Backend | `backend/app/api/routers/capacity.py` | Capacity graph API |
| Backend | `backend/app/optimizer/optimizer.py` | OR-Tools solver |
| Backend | `backend/app/capacity/graph_builder.py` | Capacity graph builder |
| Backend | `backend/app/models/domain.py` | Domain models |

### Tasks

1. **OR-Tools Optimizer** (`optimizer.py`)
   - Capacitated assignment problem
   - Minimize total evacuation distance
   - Respect shelter bed capacity constraints
   - Handle priority populations (elderly, disabled)
   - What-if scenarios (shelter closure, road blockage)
   - Feasibility detection
   - Time-budget controlled solving (30s default)

2. **Capacity Graph** (`graph_builder.py`)
   - Build graph from habitations, shelters, roads
   - Compute shortest paths (all pairs)
   - Population safety margin (15% buffer)
   - Road network analysis

3. **Domain Models** (`domain.py`)
   - `HabitationCluster(id, name, block, location, population_estimate)`
   - `Shelter(id, name, district, location, bed_capacity, beds_occupied)`
   - `RoadSegment(from_id, to_id, distance_km, travel_time_min)`
   - `CapacityGraph(habitations, shelters, road_segments)`
   - `RelocationAssignment(habitation_id, shelter_id, people, distance_km)`
   - `OptimizationResult(assignments, total_people_relocated, is_feasible)`
   - `StaticHazardZone(id, hazard_type, severity, zone_type, center, radius_km)`
   - `LiveSensorReading(sensor_id, sensor_type, value, timestamp, location)`

4. **Optimizer API** (`optimizer.py` router)
   - `POST /api/optimize/solve` — run optimization (body: `{time_budget_seconds}`)
   - `POST /api/optimize/re-solve` — re-optimize
   - `GET /api/optimize/result` — get latest result
   - `GET /api/optimize/assignments` — list all assignments

5. **Capacity API** (`capacity.py` router)
   - `GET /api/capacity/summary` — shelter capacity overview
   - `GET /api/resources/shortfall-forecast` — resource shortfall prediction

6. **Optimization Console UI** (in `App.jsx`)
   - Feasibility panel (FEASIBLE/INFEASIBLE badge + progress bar)
   - Stats grid: Population, Relocated, Unmet Need, Bed Ratio
   - PDF report download button (`/api/report/relocation-pdf`)

### UI Focus
- Green/red feasibility indicators
- Progress bars showing evacuation coverage
- Clean assignment tables
- Loading spinner during optimization (30s)

### Verification Checklist
- [ ] Solver runs and returns valid assignments
- [ ] Feasible plans show green, infeasible show red
- [ ] Capacity summary shows correct bed counts
- [ ] Shortfall forecast predicts resource gaps
- [ ] PDF report downloads
- [ ] Re-optimization works

---

## Segment 4: Citizen Portal & Communications (Member 4)

**Role:** Public-Facing Developer — "The Interface"

### Files to Own

| Layer | File | Description |
|-------|------|-------------|
| Frontend | `frontend/src/components/CitizenPortal.jsx` | Citizen-facing portal |
| Frontend | `frontend/src/components/FamilySearch.jsx` | Family reunification |
| Frontend | `frontend/src/components/IVRDemo.jsx` | Phone/IVR demo |
| Frontend | `frontend/src/components/WhatsAppBot.jsx` | WhatsApp bot demo |
| Backend | `backend/app/api/routers/citizen.py` | Citizen + family API |
| Backend | `backend/app/api/routers/communication.py` | Communication API |

### Tasks

1. **Citizen Portal** (`CitizenPortal.jsx`)
   - Village status cards with hazard levels
   - "EVACUATE NOW" alerts with urgency colors
   - Nearest shelter info with distance and capacity
   - Shelter list with status (open/limited/full)
   - Crowd report submission form
   - Mobile-first responsive design

2. **Citizen API** (`citizen.py`)
   - `GET /api/citizen/status/{village_id}` — village hazard status
   - `GET /api/citizen/villages` — list all villages with hazard level
   - `POST /api/citizen/report` — submit crowd report (rate-limited)
   - `GET /api/citizen/shelters` — list shelters with capacity

3. **Family Reunification** (`FamilySearch.jsx`)
   - Search by name + secondary identifier (privacy)
   - Results: shelter location, status, evacuee ID
   - Register evacuee form
   - Update evacuee status (safe/missing/hospitalized)

4. **Family API** (in `citizen.py`)
   - `POST /api/family/register` — register evacuee
   - `POST /api/family/search` — search for family member
   - `POST /api/family/status` — update evacuee status
   - `GET /api/family/shelter/{id}` — list shelter evacuees

5. **Phone/IVR Demo** (`IVRDemo.jsx`)
   - Interactive IVR call simulation
   - Call flow visualization
   - SMS alert composition

6. **WhatsApp Bot Demo** (`WhatsAppBot.jsx`)
   - WhatsApp message flow visualization
   - Bot response templates
   - Alert distribution demo

7. **Communication API** (`communication.py`)
   - Twilio SMS/voice endpoints
   - WhatsApp webhook handler
   - Alert distribution logic

### UI Focus
- **Mobile-first** — citizens use phones during disasters
- Large touch targets, high contrast text
- Emergency color coding (red/yellow/green)
- Fast loading (lazy-loaded)

### Verification Checklist
- [ ] Citizen portal loads without login
- [ ] Village status shows correct hazard levels
- [ ] Crowd report submission works
- [ ] Family search returns results with privacy protection
- [ ] IVR demo shows call flow
- [ ] WhatsApp demo visualizes messages

---

## Segment 5: AI, Auth & Admin Tools (Member 5)

**Role:** Intelligence & Security — "The Guardian"

### Files to Own

| Layer | File | Description |
|-------|------|-------------|
| Frontend | `frontend/src/components/AIAssistant.jsx` | AI chat assistant |
| Frontend | `frontend/src/components/AuditVerify.jsx` | Audit log & verification |
| Frontend | `frontend/src/components/MultiDistrict.jsx` | Multi-district view |
| Frontend | `frontend/src/components/FeatureShowcase.jsx` | Feature showcase |
| Frontend | `frontend/src/auth/AuthContext.jsx` | Auth React context |
| Frontend | `frontend/src/auth/LoginPage.jsx` | Login/signup page |
| Backend | `backend/app/api/routers/ai_and_data.py` | AI + data API |
| Backend | `backend/app/utils/auth.py` | Auth routes |
| Backend | `backend/app/utils/local_auth.py` | JWT + DB persistence |
| Backend | `backend/app/utils/db_fix.py` | DB auto-fix |
| Migration | `migrations/create_local_users_table.sql` | SQL migration |

### Tasks

1. **AI Assistant** (`AIAssistant.jsx` + `ai_and_data.py`)
   - Chat interface with message history
   - Groq LLM integration
   - Context-aware (injects current hazard data)
   - Quick action buttons (Analyze Risk, Find Shelter, etc.)
   - Markdown rendering
   - `POST /api/ai/chat`, `GET /api/ai/suggestions`

2. **Authentication System**
   - `AuthContext.jsx` — React context (login, signup, logout, token)
   - `LoginPage.jsx` — login/signup UI with validation
   - `auth.py` — FastAPI routes (signup, login, me, users, roles)
   - `local_auth.py` — JWT + database persistence
   - Run SQL migration on deploy

3. **User Management** (UserManagement in `App.jsx`)
   - Admin user list with roles
   - Role summary cards
   - Role assignment dropdown
   - Refresh button

4. **Audit Log** (`AuditVerify.jsx` + AuditLog in `App.jsx`)
   - Hash chain verification
   - Order timeline
   - `GET /api/orders`, `GET /api/audit/verify/{id}`

5. **Multi-District** (`MultiDistrict.jsx`)
   - District selector
   - Per-district statistics
   - Cross-district comparison

6. **Feature Showcase** (`FeatureShowcase.jsx`)
   - 32 feature cards
   - Tech stack overview
   - Architecture diagram

### UI Focus
- AI chat: message bubbles, typing indicators
- Auth: polished login/signup with feedback
- Admin: data tables with role badges
- Audit: hash chain visualization

### Verification Checklist
- [ ] AI responds to disaster questions
- [ ] Signup → login → dashboard works
- [ ] Admin manages users and roles
- [ ] Audit log verifies order hashes
- [ ] Multi-district view loads

---

## Shared Rules

1. **Code conventions:**
   - React functional components with hooks
   - FastAPI async endpoints with Pydantic models
   - CSS classes from `App.css` (don't inline everything)
   - Consistent error responses

2. **Testing requirements:**
   - Every API endpoint returns proper HTTP status codes
   - Every frontend component handles loading/error states
   - No console errors in browser
   - Responsive design

3. **Before submitting PR:**
   - Pull latest from `dev` branch
   - Resolve any conflicts
   - Run `npm run build` (frontend builds clean)
   - Test your features end-to-end

## Merge Order

1. **Segment 1** (Core) — foundational
2. **Segment 5** (Auth) — needed for protected routes
3. **Segment 2** (Hazard) — data layer
4. **Segment 3** (Optimizer) — reads from hazard
5. **Segment 4** (Citizen) — uses all APIs
