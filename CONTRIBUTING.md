# Contributing to LocaTS

## Team Workflow

This project is divided into **5 segments** with clear ownership.
Each team member works on their own fork and submits PRs.

## Quick Start

```bash
# 1. Fork the repo to your GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/LocaTS.git
cd LocaTS
git checkout -b segment-N-yourname  # e.g., segment-1-dashboard

# 3. Install dependencies
pip install -r requirements.txt
cd frontend && npm install && cd ..

# 4. Setup environment
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_KEY, GROQ_API_KEY

# 5. Run locally
python run.py                    # Backend :8000
cd frontend && npm run dev       # Frontend :5173
```

## Branch Naming

```
segment-1-dashboard
segment-2-hazard
segment-3-optimizer
segment-4-citizen
segment-5-ai-auth
```

## What to Work On

**ONLY work on files assigned to your segment.** See `TEAM_PLAN.md` for full list.

| Segment | Your Focus |
|---------|-----------|
| 1 - Core | App.jsx, App.css, Dashboard, SSE, main.py, dashboard.py |
| 2 - Hazard | SatelliteMonitor, hazard.py, fusion.py, satellite_rainfall.py |
| 3 - Optimizer | optimizer.py, capacity.py, domain.py, RelocationAnalysis UI |
| 4 - Citizen | CitizenPortal, FamilySearch, IVR, WhatsApp, citizen.py |
| 5 - AI/Auth | AIAssistant, Auth, Login, AuditVerify, MultiDistrict |

## Code Style

### React (Frontend)
- Functional components with hooks (no class components)
- Use CSS classes from `App.css` when possible
- Handle loading and error states in every component
- No `console.log` in production code
- Run `npx eslint src/` before committing

### Python (Backend)
- FastAPI async endpoints
- Pydantic models for request/response
- Proper HTTP status codes (200, 400, 401, 403, 404, 500)
- Error responses: `{"detail": "message"}` or `{"error": "message"}`

## Before Submitting PR

1. Pull latest from `dev`: `git pull origin dev`
2. Resolve any conflicts locally
3. Run frontend build: `cd frontend && npm run build`
4. Test your features end-to-end
5. Use the PR template (`.github/PULL_REQUEST_TEMPLATE.md`)

## API Contract

All endpoints are documented in `API_CONTRACT.md`. Do NOT change
response formats without notifying all team members.

## Merge Order

PRs are merged in this order:
1. Segment 1 (Core) — first, no dependencies
2. Segment 5 (Auth) — needed for protected routes
3. Segment 2 (Hazard) — data layer
4. Segment 3 (Optimizer) — reads from hazard
5. Segment 4 (Citizen) — uses all APIs

After your PR is merged, pull the latest `dev` and re-test your features.

## Getting Help

- Read `README.md` for project overview
- Read `TEAM_PLAN.md` for your segment details
- Read `API_CONTRACT.md` for endpoint formats
- Check existing code for patterns before writing new code
