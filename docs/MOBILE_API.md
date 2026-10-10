# Mobile (duty-phone) API contract

Integration guide for the **duty-phone app** carried on each patrol vehicle
(reference implementation: [`mobile/`](../mobile)). Each guard account is
linked to exactly one vehicle; every endpoint below automatically scopes data
to that vehicle, so the app never needs to send its vehicle id.

- Base URL: `http://<host>:8000/api/v1`
- Auth: JWT Bearer token
- Interactive schema: `http://<host>:8000/api/docs/` (OpenAPI at `/api/schema/`)

Bodies are JSON unless noted; photo uploads use `multipart/form-data`.

---

## 1. Authentication

`POST /auth/token/`

```json
{ "username": "guard1", "password": "guard12345" }
```

→ `{ "access": "<jwt>", "refresh": "<jwt>" }`

Send `Authorization: Bearer <access>` on every request. Refresh with
`POST /auth/token/refresh/ { "refresh": "<jwt>" }` (returns a new `access`
and a rotated `refresh`).

`GET /me/` → `{ id, username, first_name, last_name, phone, role, badge_number, vehicle: { id, plate_number } }`

---

## 2. Route plan & next location

`GET /mobile/route/` — everything the home screen needs in one call.

```json
{
  "vehicle": { "id": 1, "plate_number": "SPT 1001 A", "driver_name": "Ahmad Rahman", "...": "..." },
  "plan": { "id": 15, "name": "Tonight's patrol", "date": "2026-10-09", "status": "active" },
  "stops": [
    { "id": 301, "order": 0, "location": 3, "location_name": "Tuas Industrial Estate",
      "address": "…", "latitude": 1.32, "longitude": 103.65, "priority": 3,
      "leg_distance_km": 0.0, "source": "planned", "is_visited": true, "visited_at": "…" },
    { "id": 302, "order": 1, "location": 7, "location_name": "Jurong East",
      "leg_distance_km": 13.6, "source": "emergency", "is_visited": false, "...": "..." }
  ],
  "next_stop": { "id": 302, "...": "..." },
  "progress": { "visited": 1, "total": 6 },
  "remaining_km": 41.2,
  "command_centre_phone": "+65 6000 0000",
  "unread_messages": 1
}
```

- `next_stop` is the first unvisited stop. `source: "emergency"` means the
  command centre diverted this vehicle: show it prominently.
- After an emergency dispatch the remaining stops are **re-planned from the
  emergency site** — just re-fetch this endpoint (the reference app polls every
  30 s) and a command-centre message is also posted to the vehicle's channel.
- Returns `403` for accounts not linked to a vehicle.

---

## 3. Check in at a site (photos of the location)

`POST /stops/{id}/check_in/` — `multipart/form-data`

| Field | Type | Notes |
|-------|------|-------|
| `notes` | text | optional |
| `images` | file(s) | optional; repeat the field for multiple photos |

Marks the stop visited, writes a patrol record (distance + CO2e) and stores the
photos centrally (visible on the dashboard's **Patrol Records** page). Returns
the record (`201`). Stops of other vehicles return `404`.
(`/stops/{id}/mark_visited/` is an alias kept for older clients.)

---

## 4. Real-time position

`POST /pings/` while on duty (reference app: every 15 s)

```json
{ "latitude": 1.2835, "longitude": 103.861, "speed_kmh": 24.5 }
```

The vehicle is taken from the account; sending another vehicle's id returns `403`.

---

## 5. Incident report (with photos)

`POST /incidents/` — `multipart/form-data`

| Field | Type | Notes |
|-------|------|-------|
| `description` | text | required |
| `location` | int | optional site id |
| `uploaded_images` | file(s) | repeat the field for multiple photos |

The response includes the **AI triage** performed on submit:

```json
{
  "id": 41,
  "ai_category": "fire_hazard",
  "ai_severity": "critical",
  "ai_summary": "Possible fire at main entrance.",
  "ai_recommended_action": "Dispatch nearest unit immediately and alert emergency services.",
  "ai_anomaly_detected": true,
  "ai_tags": ["fire_hazard", "photo_attached"],
  "ai_source": "mock"
}
```

High/critical incidents at a site raise an emergency alert on the command
centre's noticeboard and the AI agent proposes a dispatch for an operator to
confirm. `GET /incidents/` lists the guard's own reports.

---

## 6. Contact the command centre

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/messages/` | The vehicle's message thread (oldest first, not paginated) |
| POST | `/messages/` | `{ "body": "Flat tyre at Orchard Road" }` |
| POST | `/messages/mark_read/` | Mark command-centre messages as read |
| GET | `/messages/contact/` | `{ "command_centre_phone": "+65 6000 0000" }` for the call button (`tel:` intent) |

---

## Error handling

| Status | Meaning |
|--------|---------|
| 400 | Validation error (field-level messages, or `detail`) |
| 401 | Missing/expired token → refresh or sign in again |
| 403 | Not permitted (e.g. account not linked to a vehicle, command-centre-only endpoint) |
| 404 | Not found *or* belongs to another vehicle |
