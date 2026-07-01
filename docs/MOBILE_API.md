# Mobile (Flutter) API Contract

This document is the integration guide for the **duty-phone app** carried on
each patrol vehicle. Each account is linked to one vehicle. The backend is the
same Django REST API used by the admin dashboard.

- Base URL: `http://<host>:8000/api/v1`
- Auth: JWT Bearer token
- Interactive schema: `http://<host>:8000/api/docs/` (OpenAPI at `/api/schema/`)

All request/response bodies are JSON unless noted (incident upload is
`multipart/form-data`).

---

## 1. Authentication

### Obtain token
`POST /auth/token/`

```json
{ "username": "guard1", "password": "guard12345" }
```

Response:

```json
{ "access": "<jwt>", "refresh": "<jwt>" }
```

Send `Authorization: Bearer <access>` on every subsequent request. Refresh with
`POST /auth/token/refresh/` `{ "refresh": "<jwt>" }`.

### Who am I / which vehicle
`GET /me/` → user profile (id, username, role, name).
`GET /guards/?assigned_vehicle=<id>` or fetch the guard profile to resolve the
linked vehicle.

---

## 2. View the route plan & next location

`GET /stops/?vehicle=<vehicleId>&is_visited=false&ordering=order`

```json
[
  {
    "id": 12, "order": 0, "location_name": "Marina Bay Sands",
    "latitude": 1.2834, "longitude": 103.8607,
    "leg_distance_km": 0.0, "is_visited": false
  }
]
```

The **next location** is the first unvisited stop (lowest `order`).

Mark a stop reached (also writes a patrol record):
`POST /stops/{id}/mark_visited/`

---

## 3. Report real-time position

Post continuously (e.g. every 5–15s) while on duty:

`POST /pings/`

```json
{ "vehicle": 3, "latitude": 1.2835, "longitude": 103.861, "speed_kmh": 24.5 }
```

The backend caches the latest position for the command-centre live map.

---

## 4. Submit an incident report (with photos)

`POST /incidents/`  — `multipart/form-data`

| Field | Type | Notes |
|-------|------|-------|
| `description` | text | required |
| `vehicle` | int | optional |
| `location` | int | optional |
| `uploaded_images` | file(s) | repeat the field for multiple photos |

The response includes the **AI analysis** performed on submit:

```json
{
  "id": 41,
  "description": "Smoke seen near the entrance…",
  "ai_category": "fire_hazard",
  "ai_severity": "critical",
  "ai_summary": "Possible fire at main entrance.",
  "ai_recommended_action": "Dispatch nearest unit and alert emergency services.",
  "ai_anomaly_detected": true,
  "ai_tags": ["fire_hazard", "photo_attached"],
  "ai_source": "llm"
}
```

---

## 5. Contact command center

The proposal calls for message/phone contact with the command centre. Phone
calls are handled natively by the device (`tel:` intent). For in-app messaging,
incident reports with a `description` serve as the message channel today; a
dedicated messaging endpoint can be added under `/messages/` as a follow-up.

---

## 6. Submit location photos (routine, no incident)

Attach the photo to the corresponding stop's location via a location update, or
submit as a low-severity incident. A dedicated `/stops/{id}/photo/` endpoint is
a recommended enhancement.

---

## Error handling

| Status | Meaning |
|--------|---------|
| 401 | Missing/expired token → refresh or re-login |
| 400 | Validation error (body has field-level messages) |
| 403 | Authenticated but not permitted (write ops are admin-only for some resources) |

---

## Suggested Flutter data flow

1. Login → store `access`/`refresh` securely (e.g. `flutter_secure_storage`).
2. Resolve the linked vehicle id once, cache it.
3. Background timer → `POST /pings/`.
4. Screen: list unvisited `/stops/`, show next location on a map, `mark_visited`.
5. Incident screen: capture photo(s) + text → `POST /incidents/`, show AI result.
