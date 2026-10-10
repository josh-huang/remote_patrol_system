# Dynamic Patrol Routing System

A command-centre platform for night-patrol vehicle fleets. It **plans every
vehicle's route automatically** each night from the vehicles that are actually
fit to drive and the sites that must be visited, **re-plans a vehicle's route
on the fly when it is diverted to an emergency** (so it carries on from the
emergency site instead of driving back), and **tracks the CO2e saved** by both.

It has three parts:

| Part | Tech | For |
|------|------|-----|
| Backend API (`/`) | Django 4.2, DRF, JWT, MySQL | everything |
| Command-centre dashboard (`frontend/`) | React 18, MUI, Nivo, Google Maps | admins |
| Duty-phone app (`mobile/`) | Flutter | the guards in each vehicle |

📄 Full write-up: [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md) — problem
statement, solution, algorithms, technology stack and evaluation.

An optional AI agent ("Sentinel") lets operators drive the system in natural
language and reacts to serious incidents; every state-changing action it
proposes waits for an operator to confirm.

---

## Requirements → implementation

From the capstone problem definition and design draft.

### Objectives

| Requirement | How it is met |
|---|---|
| Plan each vehicle's route every day from the sites and **available** vehicles; cover every site; shortest overall distance | `core/services/routing.py → plan_patrol_routes`: capacitated, priority-aware multi-vehicle planner (balanced cheapest insertion, priority tiers, 2-opt, inter-route relocate). Only *operational* vehicles (available and not `in_service`/`out_of_service`) are planned. Every site is covered exactly once (tested). |
| No admin planning every night | `python manage.py plan_daily` (schedule with cron) or the one-click **Automatic plan** on the dashboard (`POST /plans/auto_daily/`). |
| Re-plan the route of a vehicle involved in an emergency, without driving back | `reroute_after_emergency` + `patrol.services.dispatch_alert`: the vehicle goes to the emergency site and the rest of its stops are re-optimised from there. The site is removed from other vehicles' routes. The old practice (drive back to the last site and resume) is costed too, and the saving is stored on the alert and plan. |
| Vehicles break down / go into maintenance | Unschedulable vehicles are excluded from new plans; **Rebalance** (`POST /plans/{id}/rebalance/`) hands a broken-down vehicle's unvisited sites to the rest of the fleet. |
| Reduce carbon emission, measured from the mileage difference | `core/services/emissions.py`: CO2e = mileage × engine-type factor (petrol factor derived from the proposal's 8,887 g CO2/gallon). Each plan stores the **manual baseline** (sites handed out round-robin, unoptimised) next to the optimised route; re-routes store their saving. The dashboard and reports show km and kg CO2e saved. |
| Dashboard: real-time location of each vehicle | **Live Map** and dashboard map (Google Maps, or a schematic SVG map when no key is set), fed by duty-phone GPS pings. |
| Dashboard: vehicle details (plate, driver in charge, contact, health status, mileage) | **Dashboard → Fleet status** and **Vehicles**: plate, model, driver in charge, contact number, health status, next location, route progress, mileage this patrol and total. |
| Dashboard: emergency alert noticeboard | **Dashboard** and **Emergency Alerts**: raise, dispatch & re-route, resolve; shows the new route vs the old practice. |
| Dashboard: estimated carbon footprint | KPI tiles, per-vehicle emission history chart (30 days), carbon-savings panel, reports. |
| Mobile app: view the route plan and next location | `mobile/` **Route** screen (`GET /mobile/route/`), with Google Maps navigation and emergency re-route alerts. |
| Mobile app: contact the command centre (message or call) | **Command** screen: message thread (`/messages/`) + call button. Dashboard **Messages** page for the command-centre side. |

### Design draft features

| Draft item | Where |
|---|---|
| Add / remove locations and vehicles | **Locations**, **Vehicles** pages (full CRUD); **Guards** page links accounts to vehicles |
| Manually plan routes | **Route Planning → Manual plan** (`POST /plans/{id}/manual_route/`) |
| Past patrol records | **Patrol Records** page, with the guards' site photos |
| Daily or monthly report | **Reports** page (`GET /reports/patrol/?period=daily|monthly`), AI narrative, CSV download |
| Compare shortest distance vs best traffic | `POST /routing/compare-emissions/` |
| Graph of past emission per vehicle | Dashboard chart (`GET /dashboard/emissions/`) |
| Each mobile account linked to one vehicle | `SecurityGuard.assigned_vehicle`; all mobile endpoints scope to it |
| Submit pictures of the location | **Check in** (`POST /stops/{id}/check_in/` with `images`) → stored centrally as `PatrolRecordImage` (replaces WhatsApp) |
| Submit incident report | **Incident** screen (`POST /incidents/`), AI-triaged |
| Central MySQL database (vehicles, locations, daily plans, guard images) | MySQL 8 in Docker (SQLite for quick local runs) |
| Admin (username, password); Security Guard (name, id, availability, vehicle, on duty, is driver) | `accounts.User` (role admin/guard) + `SecurityGuard` |
| Vehicle (plate, driver in charge, maintenance status, availability, current route, current location, next location) | `fleet.Vehicle` + serializer fields `driver_name`, `current_plan`, `current_latitude/longitude`, `next_location` |
| Location (name, image, emergency trigger, priority) | `fleet.Location` |
| Shortest path: Dijkstra, Bellman-Ford, Floyd-Warshall | `core/services/routing.py`; any of the three builds the planner's distance matrix; **Route Planning → Shortest path** compares them |
| `shortestRoute(location_list, priority_location, num_car)` | `plan_patrol_routes(nodes, num_vehicles, …)` — priority is carried on each node |

> The draft mentions Firestore for the mobile app; this build uses the same
> Django API and MySQL database for both clients, which keeps a single source
> of truth (one of the proposal's goals).

---

## How routing works

1. **Road network.** Sites (plus virtual nodes such as a vehicle's live GPS
   position) are joined to their 5 nearest neighbours plus a minimum spanning
   tree, with great-circle distance × 1.3 road-circuity factor as edge weight.
   Because the graph is sparse, travel between far-apart sites goes *through*
   intermediate junctions, so shortest-path search is meaningful. All active
   sites are always part of the network so distances are consistent between
   plans and re-routes. Tunable via `ROUTING_CIRCUITY` / `ROUTING_NEIGHBOURS`.
2. **Distance matrix** from Dijkstra (binary heap), Bellman-Ford or
   Floyd-Warshall — they produce identical matrices (tested).
3. **Daily plan.** Seed each vehicle with a top-priority site, cheapest-insert
   the rest under a balance cap, order each route tier-by-tier (emergency →
   high → normal priority) with nearest-neighbour + 2-opt, then relocate sites
   between vehicles while it shortens the total.
4. **Emergency re-route.** Current position → emergency site → remaining stops
   re-optimised from the emergency site, compared against the old practice of
   driving back to the last visited site and resuming the original order.

On the seeded Singapore data the optimised nightly plan is ~105 km against a
~232 km manual baseline (≈55% less mileage and CO2e).

---

## Quick start (Docker)

```bash
cp .env.example .env          # edit secrets/keys
docker compose up --build
```

- Dashboard: http://localhost:3000 — `admin` / `admin12345`
- API: http://localhost:8000/api/v1/ · Swagger: http://localhost:8000/api/docs/
- Django admin: http://localhost:8000/admin/

Demo data (fleet, 20 Singapore sites, two weeks of patrol history, tonight's
in-progress plan, an active alarm, incidents, messages) is seeded on first boot.

## Local development

**Backend** (Python 3.11+)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export USE_SQLITE=True DJANGO_DEBUG=True             # PowerShell: $env:USE_SQLITE="True"
python manage.py migrate
python manage.py seed_demo            # --reset to start over
python manage.py runserver
python manage.py test                 # backend test-suite
```

**Dashboard**

```bash
cd frontend
cp .env.example .env                  # optional REACT_APP_GOOGLE_MAPS_API_KEY
npm install --legacy-peer-deps
npm start
```

**Duty-phone app** — see [`mobile/README.md`](mobile/README.md):

```bash
cd mobile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000/api/v1   # guard1 / guard12345
```

**Nightly automation**

```bash
# crontab: plan tonight's patrol at 21:00 with every operational vehicle
0 21 * * *  cd /app && python manage.py plan_daily --algorithm dijkstra
```

---

## Configuration

All settings are environment variables — see [`.env.example`](.env.example).

| Variable | Purpose |
|----------|---------|
| `USE_SQLITE` | `True` to skip MySQL for local runs |
| `MYSQL_*` | Database connection |
| `COMMAND_CENTRE_PHONE` | Number the duty phone's *Call* button dials |
| `ROUTING_CIRCUITY`, `ROUTING_NEIGHBOURS` | Road-network model |
| `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_TEXT_MODEL`, `LLM_VISION_MODEL` | OpenAI-compatible LLM. **Empty key = deterministic offline mode** |
| `GOOGLE_MAPS_API_KEY` / `REACT_APP_GOOGLE_MAPS_API_KEY` | Google Maps on the dashboard (schematic map otherwise) |
| `CORS_ALLOWED_ORIGINS` | Dashboard origin(s) |

---

## Architecture

```
 React dashboard (admins)        Flutter duty phone (guards, 1 per vehicle)
          │  JWT / REST                         │
          └──────────────┬──────────────────────┘
                         ▼
   Django REST API  /api/v1
   ├── accounts   User (admin/guard), SecurityGuard ↔ Vehicle
   ├── fleet      Vehicle, Location
   ├── patrol     PatrolPlan, PatrolStop, PatrolRecord (+ photos), VehiclePing
   │              services.py ← single place for planning / check-in / dispatch
   ├── incidents  IncidentReport (+ photos, AI triage), EmergencyAlert
   ├── comms      Message (vehicle ↔ command centre)
   ├── agent      AI agent: tools, decision loop, pending actions, autonomy
   └── core       routing, emissions, LLM services; dashboard & reports
                         ▼
                      MySQL 8
```

Permissions: admins have full access. Guards can only read their own
vehicle's stops, records, pings, messages and their own incident reports, and
cannot reach planning, fleet management, dashboards or the agent.

### Key endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/token/` | JWT login |
| GET | `/me/` | Profile (+ linked vehicle) |
| CRUD | `/vehicles/`, `/locations/`, `/guards/` | Fleet management |
| POST | `/plans/auto_daily/` | Create + auto-route tonight's plan |
| POST | `/plans/{id}/plan_route/` · `/manual_route/` · `/rebalance/` | Re-plan, manual plan, rebalance |
| GET/POST | `/alerts/` | Emergency noticeboard / raise |
| POST | `/alerts/{id}/dispatch/` · `/resolve/` | Divert + re-route / close |
| POST | `/locations/{id}/trigger_emergency/` | Site alarm |
| GET | `/mobile/route/` | Duty phone: route + next stop |
| POST | `/stops/{id}/check_in/` | Visit + site photos |
| POST | `/pings/` · GET `/pings/live/` | GPS in / live positions out |
| GET/POST | `/messages/` · `/messages/inbox/` | Messaging |
| CRUD | `/incidents/` | Incident reports + AI triage |
| GET | `/records/` | Past patrol records |
| GET | `/dashboard/summary/` · `/dashboard/emissions/` | KPIs, alerts, carbon |
| GET | `/reports/patrol/?period=daily\|monthly[&export=csv]` | Reports |
| POST | `/routing/shortest-path/` · `/routing/compare-emissions/` | Algorithms, emissions |
| POST | `/agent/chat/` · `/agent/actions/{id}/confirm/` | AI agent |

Full, always-current contract at `/api/docs/`; mobile guide in
[`docs/MOBILE_API.md`](docs/MOBILE_API.md).

## AI agent

The **AI Assistant** page talks to "Sentinel", an LLM tool-calling agent whose
tools wrap the same service layer (plans, alerts, dispatch, routes, incidents,
emissions, reports). Read tools run immediately; write tools are queued as
pending actions for an operator to confirm. When a high/critical incident is
reported at a site, the agent raises an emergency alert and proposes
dispatching the nearest operational vehicle. Without `LLM_API_KEY` a
deterministic keyword router (English and Chinese) keeps it fully demoable.

## Tests

```bash
USE_SQLITE=True python manage.py test        # 58 backend tests
cd frontend && CI=true npm run build         # dashboard build (warnings fail)
cd mobile && flutter analyze && flutter test # duty-phone app
```

CI runs all three on every push (`.github/workflows/ci.yml`).
