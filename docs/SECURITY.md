# Security & secret handling

This project loads **every** credential from environment variables. No secrets are committed to the
repository — each component provides an `.env.example` template, and the real `.env` files are
git-ignored.

## Where secrets live

| Variable | Component | Used for |
|----------|-----------|----------|
| `MONGO_URI` / `MONGODB_URI` | detection + booking server | MongoDB Atlas connection |
| `OPENAI_API_KEY` | detection | GPT-4o-mini plate OCR |
| `ROBOFLOW_API_KEY` | detection | license-plate localization |
| `RTSP_URL` | detection | camera stream (contains camera password) |
| `ESP32_IP` / `ESP32_KEY` | detection | P10 LED display auth |
| `JWT_SECRET` | booking server | signing auth tokens |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | booking server | payments |
| `STRIPE_PUBLISH_KEY` / `REACT_APP_STRIPE_PUBLISHABLE_KEY` | booking server + client | Stripe.js (publishable, safe for browser) |
| `SMS_USER_ID` / `SMS_API_KEY` / `SMS_SENDER_ID` | booking server | SMS notifications |
| WiFi SSID / password | `arduino/p10_code.ino` | ESP32 network join |

## ⚠️ Rotate the old credentials

An earlier version of this codebase had live credentials hard-coded in source. Removing them from
the code is **not enough** — anything that was ever committed or shared must be regenerated. If you
are the original author, rotate the following now:

1. **OpenAI API key** — https://platform.openai.com/api-keys → revoke the old key, create a new one.
2. **MongoDB Atlas** — Database Access → change the database user's password (or create a new
   user and delete the old one). Also restrict network access to known IPs.
3. **Roboflow API key** — Roboflow → Settings → API → regenerate the private API key.
4. **Stripe keys** — https://dashboard.stripe.com/apikeys → roll the secret key; even test keys
   should be rotated since they were exposed.
5. **JWT secret** — generate a fresh long random value, e.g. `openssl rand -hex 32`.
6. **SMS gateway (ozonedesk)** — request a new API key from the provider.
7. **WiFi password** — if the firmware's network password was real, change it on your router.
8. **RTSP camera password** — change the camera's admin password.

After rotating, put the new values **only** in your local `.env` files (never commit them).

## Secret-handling rules for this repo

- Copy each `.env.example` → `.env` and fill in real values locally.
- `.env` is git-ignored; double-check with `git status` before every commit.
- The booking server **fails fast** at startup if `MONGODB_URI`, `JWT_SECRET`, or
  `STRIPE_SECRET_KEY` are missing — it will not silently fall back to baked-in values.
- Only `REACT_APP_*` variables reach the browser; never put a secret key in the client `.env`.

## Hardening backlog (known, not yet done)

These are tracked for future work and are intentionally documented rather than hidden:

- Protect the detection→booking endpoints (`POST /api/slots/status`, `GET /api/bookings/active`)
  with a service API key — they are currently unauthenticated.
- Validate the Stripe checkout redirect origin against an allow-list (open-redirect hardening).
- Add rate limiting / replay protection to the Stripe webhook endpoint.
- Remove development-only test endpoints (`/api/test-stripe`, `/api/test-auth`) in production builds.
