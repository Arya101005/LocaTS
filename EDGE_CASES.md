# LocaTS Edge Cases Registry

## Existing Edge Cases (Already Implemented)

1. **Hazard zone overlap with shelter** — Shelter inside hazard zone is auto-disabled
2. **Disconnected habitations** — No road access flagged for boat/air evacuation
3. **Accessibility gap** — Villages with disabled population but no accessible shelter
4. **Cross-district transfers** — Inter-district assignments flagged with confirmation
5. **Crowd report corroboration** — Single reports filtered; 3+ required
6. **Staleness decay** — Old sensor readings get reduced weight over time
7. **Offline sync conflict** — Last-write-wins for concurrent offline reports
8. **Audit hash chain** — Tamper-evident SHA-256 chain for relocation orders
9. **Solver timeout fallback** — Greedy heuristic used when OR-Tools times out

## New Edge Cases (Enhancement Phase)

### 1. Citizen Portal False-Safe (Problem 6.1)
**Scenario**: Backend is unreachable; citizen portal defaults to green/safe.
**Solution**: Failed API calls show explicit "Status Unknown — last known: [time]"
state. Never show green when data is unavailable.
**Implementation**: `CitizenPortal.jsx` catches fetch errors and sets
`statusMode: 'unknown'` with `lastKnownTime` field.

### 2. Conflicting Crowd Reports (Problem 6.2)
**Scenario**: 2 reports say "flooding" + 1 says "fine" for same village.
**Solution**: When reports contradict (not all same hazard_type or severity differs
by >0.4), enter "Conflicting Reports — Under Review" state instead of averaging.
**Implementation**: `fusion.py` checks report polarity; if mixed, alert_level set to
'advisory' with explanation "Conflicting crowd reports — awaiting corroboration."

### 3. SSE Disconnect During Emergency (Problem 6.3)
**Scenario**: WebSocket/SSE drops during active event; client shows stale data.
**Solution**: Auto-reconnect with exponential backoff (1s, 2s, 4s, max 30s).
Show "Live updates paused — reconnecting..." banner. On reconnect, fetch full
dashboard state to reconcile missed updates.
**Implementation**: `useSSE.js` hook handles reconnect + reconciliation.

### 4. Shelter Shortfall Oscillation (Problem 6.4)
**Scenario**: Predicted shortfall reduces capacity → fewer people routed there →
shortfall risk drops → capacity opens → optimizer re-assigns → loop.
**Solution**: Hysteresis — shortfall threshold has asymmetric bounds:
  - Reduce capacity when predicted exhaustion < 4 hours
  - Restore capacity only when predicted exhaustion > 8 hours
  - Minimum 15-minute cooldown between capacity adjustments
**Implementation**: `_shortfall_cooldown` dict in optimizer tracks last adjustment
time per shelter.

### 5. Cross-District Governance (Problem 6.5)
**Scenario**: System silently moves people across district boundary.
**Solution**: All cross-district transfers in `expanded` optimization are flagged
with `requires_confirmation: true`. Dashboard shows confirmation dialog before
executing cross-district assignments. API response includes `governance_flag: true`
for any inter-district transfers.

### 6. Help Button Spam (Problem 6.6)
**Scenario**: User rapidly taps "I need help" creating duplicate crowd reports.
**Solution**: Rate-limit: 1 help request per device per 5 minutes. Same village
within 10-minute window uses existing report (no duplicate). Backend validates
`client_timestamp` to enforce cooldown.

### 7. Rainfall API Failure (Problem 6.7)
**Scenario**: Open-Meteo API rate-limited or unreachable mid-demo.
**Solution**: Cache last successful response with `cached_at` timestamp. If API
fails, serve cached data with `staleness_minutes` field. UI shows "Rainfall data
from X minutes ago — live feed unavailable" banner. Simulated data available as
final fallback.

### 8. Public Family Search Privacy (Problem 6.8)
**Scenario**: Anyone can search displaced persons by name, exposing locations.
**Solution**: Public search requires partial ID verification (last 4 digits of
evacuee ID OR age range match). Response never includes exact GPS coordinates —
only shelter name and general area ("near Gopeshwar"). Full details require
admin authentication.

### 9. Admin-Citizen Data Sync (Problem 6.9)
**Scenario**: Admin sees "evacuated" while citizen app says "prepare to move."
**Solution**: Both portals read from same in-memory state. API responses include
`data_timestamp` field. Frontend compares `data_timestamp` with current time;
if >5 minutes stale, show "Data may be outdated" indicator. SSE pushes ensure
near-real-time sync.
