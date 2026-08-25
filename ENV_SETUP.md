# LocaTS — Environment Setup Guide

## Quick Start (No API Keys Required)

LocaTS works out of the box with built-in Chamoli district data. No external API keys are required for the core functionality.

```bash
# Copy the template
cp .env.example .env

# Run the server
PYTHONPATH=. python -m uvicorn backend.app.api.main:app --reload --port 8000
```

## Environment Variables

### Required (Supabase)

| Variable | Required | Description | Fallback |
|----------|----------|-------------|----------|
| `SUPABASE_URL` | Yes | Supabase project URL | None — data stays in-memory |
| `SUPABASE_KEY` | Yes | Supabase anon/service key | None — data stays in-memory |
| `SUPABASE_BUCKET` | No | Storage bucket name | `locats-data` |

**Fallback:** If Supabase is not configured, all data is stored in-memory and lost on restart. The system still functions fully for demo purposes.

### Optional (Enhanced Features)

| Variable | Required | Description | Fallback |
|----------|----------|-------------|----------|
| `GROQ_API_KEY` | No | Groq LLM API key for AI assistant | Local rule-based responder (keyword matching) |
| `SENTINEL_HUB_API_KEY` | No | Sentinel Hub for satellite imagery | NDMA hazard zone analysis (static proxy) |
| `TWILIO_ACCOUNT_SID` | No | Twilio account for SMS/voice | Web-only demo (no real calls) |
| `TWILIO_AUTH_TOKEN` | No | Twilio auth token | None — Twilio disabled |
| `TWILIO_PHONE_NUMBER` | No | Twilio phone number | None — calls from default |
| `TWILIO_VERIFY_SERVICE` | No | Twilio Verify service SID | Local OTP generation (dev only) |

## Fallback Behavior by Feature

### AI Assistant (`/api/ai/chat`)
- **With Groq key:** Uses llama-3.3-70b-versatile via Groq API
- **Without key:** Local rule-based responder answers from live system data (flood zones, shelter capacity, evacuation status)

### Satellite Monitor (`/api/satellite/change-detection`)
- **With Sentinel Hub key:** Real Sentinel-2 NDWI/NDSI change detection via Copernicus Data Space
- **Without key:** NDMA hazard zone analysis as satellite proxy

### IVR Phone Helpline (`/api/ivr/*`)
- **With Twilio:** Real phone calls via Twilio with TTS
- **Without Twilio:** Web-based demo simulation (no real calls)

### WhatsApp Bot (`/api/whatsapp/*`)
- **Status:** Prototype — web-based simulation only
- **Requires:** WhatsApp Business API credentials (not yet available)

### Rainfall Data (`/api/rainfall/*`)
- **Always:** Open-Meteo API (free, no key required)
- **Fallback:** Seasonal model based on IMD monthly averages

## Staging vs Production

### Staging (Current)
- Single-instance deployment
- In-memory state + Supabase write-through
- Demo credentials for testing
- All API keys optional

### Production (Future)
- Multi-instance requires Redis-backed state or full PostGIS
- Real authentication (no demo credentials)
- Rate limiting (Redis-backed)
- HTTPS required
- Secrets manager (Vault/AWS SMS) instead of `.env`

## Demo Credentials

For development testing only:
- **Email:** `admin@locats.gov.in`
- **Password:** `admin123`
- **Role:** admin (full access)

⚠️ Never use these in production. Create real accounts via Supabase Auth.
