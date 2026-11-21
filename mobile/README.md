# Patrol Duty Phone (Flutter)

The mobile app carried on each patrol vehicle. Each guard account is linked to
one vehicle (set on the dashboard's **Guards** page).

| Requirement | Screen |
|---|---|
| View the overall route plan and the next location | **Route** — progress, next-location card with *Navigate* (Google Maps), full stop list. Refreshes every 30 s and alerts the driver when the command centre re-routes them to an emergency. |
| Submit pictures of the location | **Route → Check in** — camera/gallery photos + notes, stored centrally against the visit. |
| Submit incident report | **Incident** — description, site, photos; shows the AI triage result. High/critical reports raise an emergency alert on the dashboard. |
| Contact the command centre (message or call) | **Command** — message thread with the command centre and a *Call* button. |
| Real-time location tracking | *On duty* switch on the Route screen posts GPS pings every 15 s. |

## Run

```bash
flutter pub get
# Android emulator reaches the host's Django server on 10.0.2.2
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1
# Physical device: use your computer's LAN IP
flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1
```

Demo login: `guard1` / `guard12345` (after `python manage.py seed_demo`).

Cleartext HTTP is enabled for local development; serve the API over HTTPS in
production and remove `usesCleartextTraffic` from the Android manifest.

## Test

```bash
flutter analyze
flutter test
```

API contract: [`../docs/MOBILE_API.md`](../docs/MOBILE_API.md).
