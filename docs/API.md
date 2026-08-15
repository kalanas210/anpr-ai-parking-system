# ANPR AI Parking System — HTTP API Reference

This document describes the actual HTTP APIs and Socket.IO events exposed by the
two backend services of the ANPR AI Parking System. It is generated from the
source code and reflects only what the code implements.

## Base URLs

| Service | Base URL | Source |
| --- | --- | --- |
| Detection service (Flask + Socket.IO) | `http://localhost:5000` | `detection/app.py`, `detection/app_video.py` |
| Booking API (Express) | `http://localhost:5001/api` | `booking-system/server/index.js` |

> **Note on detection variants.** The detection service ships as two
> interchangeable Flask applications: `app.py` (live/RTSP source) and
> `app_video.py` (video-file source). Both bind to port `5000` and share the
> same core routes; only one runs at a time. Endpoints present in only one of
> the two files are marked accordingly below.

> **Note on the booking server port.** `index.js` reads the port from the
> `PORT` environment variable and falls back to `5000` if it is unset. The
> documented base URL of `5001` assumes `PORT=5001` (the configured value used
> by the rest of the system, e.g. the detection service's booking integration).

> **Authentication (booking API).** Protected routes expect a JSON Web Token in
> the `Authorization: Bearer <token>` header. Tokens are issued by the login and
> register endpoints. Access levels below are derived from the route middleware:
>
> - **Public** — no middleware.
> - **Auth** — requires the `protect` middleware (any authenticated user).
> - **Admin** — requires both `protect` and `admin` middleware (admin role).

---

## Detection Service

Base URL: `http://localhost:5000`

### Pages

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| GET | `/` | Render the login page (`login.html`). | `app.py`, `app_video.py` |
| GET | `/dashboard` | Render the main dashboard page (`index.html`). | `app.py`, `app_video.py` |

### Detection Control

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| POST | `/api/start-detection` | Start the background vehicle-detection thread. | `app.py`, `app_video.py` |
| POST | `/api/stop-detection` | Stop the running detection thread. | `app.py`, `app_video.py` |

### Parking Status & Records

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| GET | `/api/parking-status` | Return current per-slot occupancy status (serialized). | `app.py`, `app_video.py` |
| GET | `/api/parking-records` | List parking records; optional `?date=` query filter. | `app.py`, `app_video.py` |
| GET | `/api/unknown-vehicles` | List recent unknown/unreadable vehicle records (latest 50). | `app.py`, `app_video.py` |
| GET | `/api/statistics` | Return aggregate stats (today/total records, occupancy, etc.). | `app.py`, `app_video.py` |
| POST | `/api/fix-records` | Set missing exit times to now and recompute durations. | `app_video.py` only |
| POST | `/api/fix-incorrect-exit-times` | Correct records whose exit time precedes their entry time. | `app_video.py` only |
| GET | `/api/debug-records` | Return debug breakdown of active/completed parking records. | `app_video.py` only |

### OCR Configuration

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| POST | `/api/switch-ocr` | Switch OCR engine (`EasyOCR` or `OpenAI`); persists to DB. | `app.py`, `app_video.py` |
| GET | `/api/current-ocr` | Return the currently selected OCR method. | `app.py`, `app_video.py` |

### P10 LED Display

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| GET | `/api/p10-status` | Return current P10 display status / availability. | `app.py`, `app_video.py` |
| POST | `/api/p10-test` | Send a test message to the P10 display (`type` selects mode). | `app.py`, `app_video.py` |
| POST | `/api/p10/test-both-busy-non-booked` | Test display cycle for both slots busy, non-booked mode. | `app.py`, `app_video.py` |
| POST | `/api/p10/test-both-busy-unauthorized` | Test display cycle for both slots busy with unauthorized vehicles. | `app.py`, `app_video.py` |
| POST | `/api/p10/test-audio-alert` | Trigger the unauthorized-vehicle audio alert (test). | `app.py`, `app_video.py` |
| POST | `/api/p10/stop-audio-alert` | Stop the unauthorized-vehicle audio alert. | `app.py`, `app_video.py` |
| POST | `/api/p10/unauthorized-warning` | Trigger/test the unauthorized-vehicle warning on the display. | `app.py`, `app_video.py` |
| GET | `/api/p10/unauthorized-status` | Return current unauthorized-vehicle / display status. | `app.py`, `app_video.py` |

### Booking Integration (detection side)

These endpoints proxy the detection service's internal booking-integration
module; they are distinct from the Express Booking API below.

| Method | Path | Purpose | File(s) |
| --- | --- | --- | --- |
| GET | `/api/booking/status` | Return booking-integration status and active bookings. | `app.py`, `app_video.py` |
| POST | `/api/booking/validate` | Validate a vehicle (`slot_id`, `license_plate`) against bookings. | `app.py`, `app_video.py` |
| GET | `/api/booking/conflicts` | Return current booking conflicts. | `app.py`, `app_video.py` |

### Socket.IO Events

The detection service runs Socket.IO over the same port (`5000`).

**Handled events (client → server):**

| Event | Purpose | File(s) |
| --- | --- | --- |
| `connect` | On client connect, emit the current serialized slot status. | `app.py`, `app_video.py` |
| `disconnect` | Log client disconnect. | `app.py`, `app_video.py` |

**Emitted events (server → client):** the server broadcasts the following
events during operation: `parking_status_update`, `new_parking_record`,
`parking_record_updated`, `license_plate_detected` (`app_video.py`), and
`refresh_records` (`app_video.py`).

---

## Booking API

Base URL: `http://localhost:5001/api`

### Utility / Health (root, not under a router prefix)

Defined directly in `index.js`.

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/api/health` | Public | Health check; reports server status and which env vars are set. |
| GET | `/api/test-auth` | Public | Echo whether an `Authorization` header was supplied. |
| GET | `/api/test-stripe` | Public | Smoke-test Stripe connectivity by creating a test payment intent. |

### Auth — `/api/auth` (`routes/auth.js`)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | Public | Register a new user and return a JWT. |
| POST | `/api/auth/login` | Public | Authenticate credentials and return a JWT. |
| GET | `/api/auth/profile` | Auth | Get the authenticated user's profile. |
| PUT | `/api/auth/profile` | Auth | Update the authenticated user's name/phone. |

### Bookings — `/api/bookings` (`routes/bookings.js`)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/api/bookings/available-slots` | Public | List available slots for a date/time window (cross-checks live status for today). |
| POST | `/api/bookings` | Auth | Create a booking (validates conflicts and live occupancy for today). |
| GET | `/api/bookings/my-bookings` | Auth | List the authenticated user's bookings (paginated, optional `status`). |
| GET | `/api/bookings/active` | Public | List today's active bookings; auto-cancels expired ones. |
| GET | `/api/bookings/:id` | Auth | Get a booking by ID (owner or admin only). |
| PUT | `/api/bookings/:id/cancel` | Auth | Cancel the authenticated user's booking. |

### Payments — `/api/payments` (`routes/payments.js`)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/api/payments/test-origin` | Public | Debug helper that echoes computed request origin. |
| POST | `/api/payments/create-checkout-session` | Auth | Create a Stripe Checkout session for a booking. |
| POST | `/api/payments/webhook` | Public | Stripe webhook handler (verifies signature; updates payment status). |
| GET | `/api/payments/status/:bookingId` | Auth | Get the payment status of a booking (owner only). |
| POST | `/api/payments/verify-session` | Auth | Verify a Stripe Checkout session and finalize payment. |

### Admin — `/api/admin` (`routes/admin.js`)

All routes in this router require `protect` + `admin` (applied via
`router.use(protect, admin)`).

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/api/admin/bookings` | Admin | List all bookings with filtering and pagination. |
| GET | `/api/admin/statistics` | Admin | Return booking/revenue/occupancy statistics. |
| PUT | `/api/admin/bookings/:id/status` | Admin | Update a booking's status (sends SMS on completion/cancellation). |
| DELETE | `/api/admin/bookings/:id` | Admin | Delete a booking. |
| GET | `/api/admin/users` | Admin | List all users (paginated, optional `role`). |
| PUT | `/api/admin/users/:id/status` | Admin | Activate/deactivate a user account. |
| GET | `/api/admin/slot-conflicts` | Admin | List overlapping bookings (conflicts) for a date. |

### Slots — `/api/slots` (`routes/slots.js`)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/api/slots/status` | Public | Get slot status, optionally for a date/time window. |
| POST | `/api/slots/status` | Public | Record a slot status update (for detection-system integration). |
| GET | `/api/slots/history/:slotNumber` | Public | Get status history for a slot (1 or 2). |

> The `protect` middleware is imported in `routes/slots.js` but is **not**
> applied to any route; all slot routes are public as written.

### Parking Integration — `/api/parking` (`routes/parking-integration.js`)

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| POST | `/api/parking/unauthorized-vehicle` | Public | Report a detected plate; alerts the customer if it mismatches the booking. |
| POST | `/api/parking/slot-conflict` | Public | Report multiple plates in one slot; alerts affected customers. |
| GET | `/api/parking/slot-status` | Public | Get booking-derived slot status for the parking system. |
| GET | `/api/parking/realtime-status` | Public | Proxy live slot status from the detection service. |
| POST | `/api/parking/send-reminder` | Public | Send a booking reminder SMS by booking ID. |

> The source comment for `POST /api/parking/send-reminder` labels it
> "Private (admin only)", but the route has **no** `protect`/`admin`
> middleware, so it is effectively public as implemented.

---

## Environment Variables (names only)

No secret values are included here. The services read configuration from the
following environment variable **names**:

- **Detection service:** `FLASK_SECRET_KEY`, `MONGO_URI`, `ROBOFLOW_API_KEY`,
  `OPENAI_API_KEY`.
- **Booking API:** `MONGODB_URI`, `JWT_SECRET`, `STRIPE_SECRET_KEY`,
  `STRIPE_PUBLISH_KEY`, `STRIPE_WEBHOOK_SECRET`, `PORT`, `NODE_ENV`,
  `ALLOWED_ORIGINS`.

Required-at-startup variables for the Booking API are `MONGODB_URI`,
`JWT_SECRET`, and `STRIPE_SECRET_KEY` (the server exits if any are missing).
