# REPO_ANALYSIS.md — LocaTS (SIH26191)

## What We Forked

**Nothing.** We built LocaTS from scratch in a clean repository. No code was forked or copied from existing repositories.

## What We Referenced (but rewrote)

### 1. `lakshyaag/Route-Optimization-STM` — CVRP/SD-VRP formulation
- **What we took:** The conceptual formulation of evacuation as a capacitated vehicle routing problem. The constraint structure (stops as nodes, demand per node, vehicle/shelter capacity) informed our min-cost flow model.
- **What we rewrote:** The actual solver. They use OR-Tools CP-SAT for bus routing with Montreal GTFS data. We use OR-Tools SimpleMinCostFlow for a transportation problem (habitation-to-shelter assignment) with Indian road network data. The formulations are mathematically related but architecturally different — theirs is VRP (vehicle routes), ours is assignment/flow (who goes where, not how buses route).
- **Attribution:** The conceptual framing of disaster evacuation as a capacitated assignment problem is attributed to the CVRP literature and this repository.

### 2. `aajayssingh/EmergencyEvacuationModellingAndSimulation` — OSM + Boost graph
- **What we took:** The concept of building a road network graph from OSM data for Indian-context evacuation.
- **What we rewrote:** They use C++ Boost graph library with raw OSM parsing. We use Python NetworkX with `osmnx`-style graph construction. Completely different implementation language and approach.
- **Attribution:** Reference for Indian-context OSM graph construction.

### 3. `vijay-varadarajan/Disaster-Relief` — Real-time reporting
- **What we took:** The concept of a crowd-reporting layer alongside evacuation routing.
- **What we rewrote:** Their complaint management is a basic CRUD system. Our PWA uses IndexedDB offline-first storage with timestamp-based conflict resolution (edge 5.9), corroboration gating (edge 5.4), and privacy-preserving photo hashing.
- **Attribution:** Conceptual reference only.

### 4. `NVIDIA/cuopt` — GPU-accelerated solver
- **What we took:** The recommendation to use an existing solver rather than reimplementing from scratch.
- **What we did:** No GPU was available in our build environment, so we use OR-Tools SimpleMinCostFlow (CPU) as documented fallback. The solver backend is swappable — cuOpt integration is planned when GPU hardware is available.
- **Attribution:** Solver recommendation attributed to NVIDIA cuOpt documentation.

## What We Built From Scratch

1. **Hazard Fusion Layer** (`backend/app/hazard_fusion/fusion.py`)
   - Bayesian-style weighted scoring with explainable component scores
   - Staleness decay function for time-varying sensor trust
   - Crowd report corroboration gating (requires 3+ independent reports)
   - Outlier rejection for crowd reports
   - Predictive tiered alerting (advisory → evacuate → relocate)
   - All weights are transparent and documented

2. **Carrying Capacity Layer** (`backend/app/capacity/graph_builder.py`)
   - NetworkX-based road graph with bidirectional edges
   - Population uncertainty buffer (configurable safety margin)
   - Multi-hazard shelter cross-validation
   - Graph connectivity detection for disconnected habitations
   - Shortest path computation with accessibility checking

3. **Optimization Layer** (`backend/app/optimizer/optimizer.py`)
   - OR-Tools SimpleMinCostFlow formulation as balanced transportation problem
   - Dummy node balancing for infeasible instances
   - Rolling-horizon re-optimization with atomic capacity locking
   - Greedy heuristic fallback with time-budget enforcement
   - Edge case detection: infeasibility, disconnected graph, accessibility gaps, inter-district
   - Audit hash chain for tamper-evident relocation orders

4. **FastAPI Backend** (`backend/app/api/main.py`)
   - REST endpoints for all four layers
   - Hazard zone ingestion, sensor readings, crowd reports
   - Capacity graph management
   - Optimization triggers (solve / re-solve)
   - Offline report sync with conflict resolution
   - Operator dashboard aggregation endpoint

5. **Operator Dashboard** (`frontend/`)
   - React + MapLibre GL map visualization
   - Real-time hazard zone display
   - Shelter status and capacity monitoring
   - Relocation plan viewer with edge-case annotations
   - One-click optimization and re-optimization triggers

6. **Offline-first PWA** (`pwa/`)
   - IndexedDB-based offline storage
   - Geolocation capture
   - Photo capture with privacy-preserving SHA-256 hashing
   - Timestamp-based conflict resolution (last-write-wins)
   - Automatic sync when connectivity restores
   - Mobile-first responsive design

7. **Edge Case Tests** (`backend/tests/test_edge_cases.py`)
   - 14 tests covering all mandatory edge cases from Section 5
   - Infeasibility detection and partial allocation
   - Disconnected graph and road failure
   - Race condition protection (concurrent re-optimization)
   - Staleness decay verification
   - Crowd report corroboration gating
   - Accessibility gap detection
   - Multi-hazard shelter overlap
   - Cross-district assignment flagging

8. **Sample Data** (`backend/app/data/sample/chamoli_data.py`)
   - Chamoli district, Uttarakhand (real geography)
   - 8 habitations, 5 shelters, 15 road segments
   - Based on real district prone to floods and landslides
   - Population/capacity numbers are illustrative estimates, not census data

## Known Limitations

1. **No real Bhuvan/NDMA data ingestion** — We use sample hazard zones. Real integration would require GIS pipeline for Bhuvan WMS/WFS services.
2. **No OSM road network auto-import** — Road segments are manually defined. Production would use `osmnx` to build graphs from OSM data.
3. **No Twilio/SMS integration** — Alert dispatch is API-ready but not connected to a real SMS gateway.
4. **No GeoServer OGC endpoints** — REST API is built but OGC WFS/WMS serving requires GeoServer deployment.
5. **PWA service worker not implemented** — The offline storage works via IndexedDB, but a proper service worker for asset caching is planned.
6. **No real IMD/seismic feed integration** — Sensor readings are simulated. Production would poll IMD APIs.
