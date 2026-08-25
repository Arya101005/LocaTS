# LocaTS — Intelligent Hazard Identification & Optimized Relocation Planning

**SIH26191** | Ministry of Home Affairs, Disaster Management Theme

> Identifying hazard-based red zones, assessing carrying capacity of safe zones, and generating optimized, dynamically-updating relocation plans for vulnerable habitations.

## Architecture

```
                    +-----------------------+
                    |    Operator Dashboard  |
                    |  (React + MapLibre GL) |
                    +-----------+-----------+
                                |
                    +-----------v-----------+
                    |     FastAPI Backend    |
                    |   REST + OGC-ready     |
                    +-----------+-----------+
                                |
          +---------------------+---------------------+
          |                     |                     |
+---------v--------+  +---------v--------+  +---------v--------+
|  Hazard Fusion   |  |  Capacity Graph   |  |   Optimization    |
|  Layer           |  |  Builder          |  |   Engine          |
|                  |  |                   |  |                   |
| - Static zones   |  | - Habitsheds      |  | - OR-Tools MCF    |
| - Live sensors   |  | - Shelters        |  | - Rolling-horizon |
| - Crowd reports  |  | - Road network    |  | - Greedy fallback |
| - Bayesian fuse  |  | - Connectivity    |  | - Edge detection  |
+------------------+  +-------------------+  +-------------------+
                                |
                    +-----------v-----------+
                    |  Offline PWA          |
                    |  (Community Reports)  |
                    |  IndexedDB + Sync     |
                    +-----------------------+
```

## Quick Start

### Backend

```bash
cd backend
pip install fastapi uvicorn pydantic numpy networkx ortools shapely httpx python-dateutil structlog
cd ..
PYTHONPATH=. python -m uvicorn backend.app.api.main:app --reload --port 8000
```

### Run Demo

```bash
PYTHONPATH=. python scripts/demo.py
```

### Run Tests

```bash
# Edge case tests (14 tests)
PYTHONPATH=. python -m pytest backend/tests/test_edge_cases.py -v

# Real data ingestion tests (27 tests)
PYTHONPATH=. python -m pytest backend/tests/test_real_data.py -v

# All tests (41 tests)
PYTHONPATH=. python -m pytest backend/tests/ -v
```

### Frontend Dashboard

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

### Community Reporting PWA

```bash
cd pwa
npm install
npm run dev
# Opens at http://localhost:3001
```

## Real Data Integration

LocaTS ingests **real geographic and hazard data** from authoritative open sources:

| Source | Use | License | How Ingested |
|--------|-----|---------|-------------|
| **OpenStreetMap** | Road network, healthcare, shelters, settlements | ODbL | `osmnx` Overpass API |
| **NDEM/Bhuvan** | Landslide hazard zones, flood inundation | CC0 1.0 | `ramSeraph/india_natural_disasters` releases |
| **India Flood Inventory v3** | Historical flood event polygons (1960s-2020) | CC BY 4.0 | `yashveeeeeeer/india-geodata` releases |
| **IS 1893 Seismic Zonation** | District-level seismic zone classification | Public | BIS standard mapping |
| **IMD Rainfall** | Live/recent rainfall observations | Public domain | IMD API + stochastic fallback |
| **NIC HealthGIS** | Public health facility locations (PHCs, CHCs, hospitals) | India OGL | `yashveeeeeeer/india-geodata` |
| **Census 2011 / india-geodata** | Village-level population estimates | CC BY 4.0 | `yashveeeeeeer/india-geodata` |
| **NDMA Guidelines** | Shelter capacity, accessibility constraints | Government of India | Reference (not code) |

### Download Real Data

```bash
# Download real geographic data for Chamoli district and export as GeoJSON
PYTHONPATH=. python scripts/download_real_data.py --district Chamoli --export-dir frontend/public/data
```

This pulls live data from OSM, downloads hazard zones from NDMA/Bhuvan releases, and exports everything as GeoJSON files for the operator dashboard.

### Load Real Data via API

```bash
# Load real data through the API (auto-fetches from all sources)
curl -X POST http://localhost:8000/api/capacity/load-real?district=Chamoli&state=Uttarakhand
```

## Optimization Formulation

The core innovation is a **capacitated transportation problem** solved via OR-Tools SimpleMinCostFlow:

- **Source nodes:** Habitation clusters (supply = population with safety margin)
- **Sink nodes:** Shelters (demand = bed capacity)
- **Arcs:** Road paths (cost = distance x urgency_weight, capacity = min of supply/demand)
- **Dummy node:** Absorbs excess supply/demand for infeasible instances

**Rolling-horizon re-optimization:** When road segments fail or shelter capacities change, the system re-solves within a bounded time budget. No manual restart required.

## Solver Backend

- **Primary:** Google OR-Tools SimpleMinCostFlow (CPU)
- **Planned:** NVIDIA cuOpt (GPU) when hardware available
- **Fallback:** Greedy nearest-feasible-shelter heuristic (labeled as heuristic-fallback in output)

## Edge Cases Handled

See [EDGE_CASES.md](./EDGE_CASES.md) for complete documentation. Key cases:

| # | Edge Case | Handling |
|---|-----------|----------|
| 5.1 | Infeasible optimization | Equitable partial allocation + flagged unmet demand |
| 5.2 | Disconnected graph | Flag for non-road evacuation (boat/air) |
| 5.3 | Stale sensor data | Exponential trust decay |
| 5.4 | Malicious crowd reports | Corroboration gating (3+ reports required) |
| 5.5 | Race conditions | Atomic re-optimization with threading lock |
| 5.6 | Uncertain population | Configurable safety margin (+15%) |
| 5.7 | Accessibility infeasibility | Flagged as capacity gap, NOT dropped |
| 5.11 | Solver time-budget | Greedy fallback with explicit labeling |
| 5.12 | Multi-hazard shelter overlap | Cross-validation against all hazard layers |
| 5.13 | Cross-district shortfall | Inter-district flagging |

## Known Limitations

1. **IMD rainfall fallback** — IMD serves HTML, not JSON. Falls back to stochastic model based on published monthly statistics when live API unavailable.
2. **OSM rural coverage gaps** — Road network in remote Himalayan areas may be incomplete. System flags uncovered habitation clusters.
3. **Census data age** — 2011 census data is 15+ years old. 15% population buffer applied (configurable).
4. **No SMS/voice alerts** — API-ready but not connected to Twilio or TTS gateway.
5. **No GeoServer OGC endpoints** — REST API built; OGC requires GeoServer deployment.
6. **No full offline PWA caching** — Service worker not yet implemented.
7. **No GPU solver** — OR-Tools CPU used; cuOpt integration when GPU hardware available.
8. **In-memory state** — All data is volatile. Production needs PostgreSQL/PostGIS.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, OR-Tools, NetworkX, Pydantic, GeoPandas, Shapely
- **Data Ingestion:** osmnx (OSM), httpx (NDMA/Bhuvan API), shapely (geometry)
- **Frontend:** React 18, MapLibre GL, Vite
- **PWA:** React 18, IndexedDB (idb), Vite
- **Testing:** pytest (41 tests)
- **Solver:** Google OR-Tools SimpleMinCostFlow

## License

This project was built for Smart India Hackathon 2026. See individual data source licenses above.
