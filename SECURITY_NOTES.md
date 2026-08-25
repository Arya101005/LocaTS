# LocaTS — Security Notes

## KNOWN RISKS (documented, not yet fixed)

### 1. JWT Token Stored in localStorage (HIGH)
**Location:** `frontend/src/auth/AuthContext.jsx` — `localStorage.setItem('locats_token', token)`

**Risk:** localStorage is accessible to any JavaScript running on the page. XSS attacks
can steal the JWT and impersonate the user. This is the standard trade-off for SPAs
without a backend-rendered login flow.

**Mitigation (current):** 
- Supabase JWT has short expiry (configurable)
- CORS is restricted in production
- No sensitive PII is stored in the token itself

**Recommended fix:** Move to httpOnly secure cookie set by the backend on login.
This requires a backend endpoint that sets `Set-Cookie` headers and the frontend
sending `credentials: 'include'` on fetch calls.

**Status:** Documented as risk. Not fixed in this pass due to scope constraints.

### 2. Demo Credentials in Codebase (LOW — mitigated)
**Location:** `.env.example` only (removed from login page UI per P0)

**Risk:** If `.env` or `.env.example` is committed to a public repo, anyone can see
the demo credentials.

**Mitigation:** `.env` is in `.gitignore`. `.env.example` contains placeholder values
with a comment noting they are demo-only.

**Status:** Fixed. Demo credentials removed from UI, placed in `.env.example` with warning.

### 3. No Server-Side Rate Limiting on Crowd Reports (MEDIUM)
**Location:** `backend/app/api/routers/citizen.py` — `/api/citizen/report`

**Risk:** The current 5-minute device-based rate limit on the citizen portal is
client-side only (localStorage). An attacker can bypass it by clearing storage.
The backend endpoints accept unlimited submissions.

**Mitigation (current):** Reports require 3+ corroboration before influencing alerts
(edge 5.4). Single malicious reports are ignored by the fusion layer.

**Recommended fix:** Add server-side rate limiting keyed on IP address using
`slowapi` or a simple in-memory counter with TTL.

**Status:** Documented. Backend corroboration gating is the primary defense.

### 4. Family Search Returns Shelter Location (LOW)
**Location:** `backend/app/api/routers/citizen.py` — `/api/family/search`

**Risk:** A name-only search returns shelter assignment information. This could
reveal a person's location to someone with ill intent.

**Mitigation (current):** Results show only shelter name (not GPS coordinates).
Name is hashed (SHA-256) before comparison. No exact coordinates are exposed.

**Status:** Acceptable for hackathon scope. Production would require identity
verification (Aadhaar or similar) before releasing shelter location.

### 5. In-Memory State Not Multi-Instance Safe (LOW)
**Location:** `backend/app/api/state.py`

**Risk:** The write-through persistence layer saves to Supabase but reads from
in-memory state. Running multiple server instances would cause stale reads.

**Mitigation:** Documented as single-instance only. Supabase provides backup.

**Status:** Documented. See PRODUCTION_READINESS.md.

### 6. Twilio Auth Token in .env (LOW)
**Location:** `.env` file

**Risk:** The Twilio auth token is stored in plaintext in `.env`. If the server
is compromised, the token is exposed.

**Mitigation:** `.env` is not committed to git. Supabase credentials use the same
pattern. This is standard practice for environment variables.

**Status:** Acceptable. Use a secrets manager (Vault, AWS SSM) in production.

---

## WHAT WAS FIXED IN THIS PASS

| Item | What Changed | Files |
|------|-------------|-------|
| Demo credentials removed from UI | No longer visible on login page | `frontend/src/auth/LoginPage.jsx` |
| Demo credentials documented | Added to `.env.example` with warning | `.env.example` |
| Prototype badges added | WhatsApp, IVR pages show "Prototype" label | `frontend/src/components/WhatsAppBot.jsx`, `frontend/src/components/IVRDemo.jsx` |
| Feature Showcase audited | Numbers corrected, honest status labels | `frontend/src/components/FeatureShowcase.jsx` |

---

## PRODUCTION RECOMMENDATIONS

1. **Switch JWT to httpOnly cookies** — highest priority for any deployment
2. **Add `slowapi` rate limiting** — per-IP on all public endpoints
3. **Enable Supabase RLS policies** — currently set to "allow all for demo"
4. **Use a secrets manager** — replace `.env` with HashiCorp Vault or cloud KMS
5. **Add CSP headers** — prevent XSS via Content-Security-Policy
6. **Enable HTTPS everywhere** — HSTS header on all responses
