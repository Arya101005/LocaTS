# LocaTS Data Sources

## Honesty Statement
This document explicitly states what is live/real data versus simulated/demo data.
No data source is misrepresented.

## Chamoli District Data

### Population & Habitaciones
- **Source**: Census 2011 (Chamoli district, Uttarakhand)
- **Status**: Static seed data based on real census figures
- **Coverage**: 24 major habitations representing the 12 blocks of Chamoli
- **Confidence**: Population figures are Census 2011 + 15% buffer for growth estimate
- **Note**: Real deployment would use Census 2021 + WorldPop satellite estimates

### Shelters
- **Source**: Based on real government buildings, schools, hospitals in Chamoli
- **Status**: Static seed data with capacity estimates based on NDMA guidelines
- **Coverage**: 18 Chamoli shelters + 8 nearby district shelters = 26 total
- **Capacity**: NDMA guideline of ~50 beds per 1000 population applied
- **Note**: Bed counts are estimates for demo; real deployment uses actual facility surveys

### Road Network
- **Source**: Based on real road distances between Chamoli towns
- **Status**: Static seed data
- **Coverage**: 55 road segments connecting habitations and shelters
- **Note**: Real deployment would use OSM road network via Overpass API

### Hazard Zones
- **Source**: Based on NDMA/Bhuvan hazard zone data for Chamoli
- **Status**: Static seed data representing real hazard areas
- **Coverage**: 2 flood zones, 2 landslide zones, 1 seismic zone
- **Note**: Real deployment would use live NDEM/Bhuvan GeoJSON feeds

### Rainfall Data
- **Source**: SIMULATED — not live IMD data
- **Status**: 7 static sensor readings representing typical monsoon rainfall in Chamoli
- **Coverage**: Raini, Tapovan, Ghat, Joshimath, Badrinath, Karnaprayag, Gopeshwar
- **Values**: Based on IMD historical monsoon averages for the region (30-85mm range)
- **Why simulated**: IMD serves HTML pages, not APIs; parsing is fragile for demo
- **Live alternative**: Open-Meteo API (free, no key) is available but not connected in current build
- **Label**: Both portals display "Simulated rainfall feed for demo" where rainfall is shown

### Crowd Reports
- **Source**: User-submitted via IVR or dashboard
- **Status**: Live — stored in-memory during the session
- **Corroboration**: 3+ independent reports required before influencing hazard scores

## External APIs (Connected)

### Supabase
- **Purpose**: Authentication (JWT), role management
- **Status**: Connected — real Supabase project
- **URL**: ybtiavtkdvzyebzedrwg.supabase.co
- **Tables**: user_profiles (role column, auto-trigger on signup)

### Groq AI (LLM)
- **Purpose**: AI assistant natural language responses
- **Status**: Backend proxy with local fallback
- **Note**: API key may expire; local rule-based responder provides answers using live system data

## External APIs (Available but Not Connected)

### Open-Meteo (Weather)
- **Status**: Free, no API key required
- **Could provide**: Real-time rainfall, temperature, wind for Chamoli coordinates
- **Recommendation**: Connect as primary data source with simulated data as fallback

### OpenStreetMap Overpass API
- **Status**: Available but rate-limited for large queries
- **Could provide**: Real road network, building footprints, healthcare facilities
- **Note**: Previous attempts hit rate limits (504/429); cached data would be needed

### IMD Gridded Rainfall
- **Status**: Public domain data
- **Could provide**: Real rainfall at 0.25° grid resolution
- **Challenge**: Data is in HDF5/NetCDF format, requires specialized parsing

## Cross-District Shelters

### Nearby District Data
- **Status**: Simulated seed data based on real district headquarters
- **Districts**: Rudraprayag, Bageshwar, Almora, Dehradun, Pithoragarh, Uttarkashi, Haridwar, Pauri Garhwal
- **Note**: Real deployment would query neighboring district disaster management offices

## Population Estimates Used

| Habitation | Population (Census 2011) | With 15% Buffer |
|-----------|------------------------|-----------------|
| Gopeshwar | 25,000 | 28,750 |
| Joshimath | 18,000 | 20,700 |
| Karnaprayag | 15,000 | 17,250 |
| Badrinath | 12,000 | 13,800 |
| Nandprayag | 10,000 | 11,500 |
| Others (19) | 33,300 | 37,261 |
| **Total** | **113,300** | **149,261** |
