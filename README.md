# Remote Patrol System

An enterprise-grade **AI-agent-driven security patrol platform**. A fleet of
patrol vehicles visits prioritised checkpoints on optimised routes; an
autonomous **AI agent ("Sentinel")** is the operational brain — it reads live
system state, plans routes, triages incidents, and proposes dispatch actions,
all through natural-language command and event-driven autonomy.

Built as a Django REST backend + React admin dashboard, with a documented API
contract for a Flutter duty-phone mobile app.

## The AI Agent is the core

Instead of AI being one isolated feature, the **agent orchestrates the whole
system**. Every capability (routing, emissions, fleet/incident queries, plan
creation) is exposed to the agent as a **tool**, and the agent decides which to
call and in what order.

```
Operator (natural language)  ──►  🧠 Agent "Sentinel"  ──►  tools ──► services/DB
                                    │  (LLM tool-calling loop)
Critical incident (event)  ───────►┘  (autonomous trigger)
```

- **Copilot mode** — operators chat with the agent ("plan a route for the 3
  high-priority sites with 2 vehicles and keep emissions low"); it chains tool
  calls and answers with real figures.
- **Autonomous mode** — when a high/critical incident is analysed, the agent
  proactively prepares a dispatch of the nearest available vehicle.
- **Human-in-the-loop governance** — the agent never executes state-changing
  actions itself. It queues them as **pending actions** that an operator
  confirms or rejects, and every tool call + action is stored for audit.
- **Fully offline-capable** — with no LLM key the agent falls back to a
  deterministic tool router, so the whole experience stays demoable.

---

## Architecture

```
                 ┌───────────────────────┐        ┌──────────────────────┐
                 │  React Admin Dashboard │        │  Flutter Duty-Phone  │
                 │   (MUI, Nivo, Maps)    │        │   app (per vehicle)  │
                 └───────────┬───────────┘        └──────────┬───────────┘
                             │  JWT / REST (JSON)            │
                             └───────────────┬───────────────┘
                                             ▼
                         ┌───────────────────────────────────────┐
                         │        Django + DRF API (v1)           │
                         │  accounts · fleet · patrol · incidents │
                         │        core.services (business)        │
                         │  routing │ emissions │ llm (AI)         │
                         └───────────────────┬───────────────────┘
                                             ▼
                                     ┌───────────────┐     ┌──────────────┐
                                     │  MySQL 8.0    │     │ OpenAI-compat │
                                     │  (Docker)     │     │  LLM (opt.)   │
                                     └───────────────┘     └──────────────┘
```

### Backend apps

| App | Responsibility |
|-----|----------------|
| `accounts` | Custom `User` (role: admin/guard) + `SecurityGuard` duty profile, JWT auth |
| `fleet` | `Vehicle` and `Location` (checkpoint) management |
| `patrol` | `PatrolPlan` / `PatrolStop` / `PatrolRecord` + real-time `VehiclePing` |
| `incidents` | `IncidentReport` + photos, with **AI analysis** on intake |
| `agent` | **The AI brain** — tool registry, decision loop, conversations, pending actions, event-driven autonomy |
| `core` | Shared base model + service layer (routing, emissions, LLM) + dashboards/reports |

### Agent app (`agent/`)

| File | Role |
|------|------|
| `tools.py` | Wraps services/ORM as agent tools (READ = auto, WRITE = confirm) |
| `engine.py` | The tool-calling decision loop + offline deterministic fallback |
| `autonomy.py` | Event-driven triggers (auto-dispatch on critical incidents) |
| `prompts.py` | Sentinel's system prompt |
| `models.py` | `AgentConversation`, `AgentMessage` (with reasoning trace), `AgentAction` (auditable pending actions) |

### Service layer (`core/services/`)

- **`routing.py`** — Dijkstra, Bellman-Ford, Floyd-Warshall shortest paths plus a
  multi-vehicle, priority-aware patrol planner (haversine-weighted graph).
- **`emissions.py`** — CO₂e estimation from mileage × engine-type factor, and a
  shortest-distance vs best-traffic comparison.
- **`llm.py`** — AI incident classification/severity/summary (text + vision) and
  narrative report generation. **Degrades to a deterministic mock when no API
  key is set**, so the whole system runs offline.

---

## Quick start (Docker — recommended)

```bash
cp .env.example .env          # then edit secrets/keys
docker compose up --build
```

- API: http://localhost:8000/api/v1/
- API docs (Swagger): http://localhost:8000/api/docs/
- Django admin: http://localhost:8000/admin/
- Dashboard: http://localhost:3000/

Demo data is seeded automatically. Log in with **`admin` / `admin12345`**.

## Local development (without Docker)

**Backend**

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on *nix)
pip install -r requirements.txt

# Use sqlite for a zero-dependency run, or set MySQL vars in .env
set USE_SQLITE=True               # PowerShell: $env:USE_SQLITE="True"
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

**Frontend**

```bash
cd frontend
cp .env.example .env              # set REACT_APP_GOOGLE_MAPS_API_KEY
npm install --legacy-peer-deps
npm start
```

---

## Configuration

All settings are environment-driven — see [`.env.example`](.env.example).

| Variable | Purpose |
|----------|---------|
| `USE_SQLITE` | `True` to skip MySQL for quick local runs |
| `MYSQL_*` | Database connection |
| `LLM_API_KEY` | OpenAI-compatible key. **Empty = mock AI mode** |
| `LLM_BASE_URL` / `LLM_TEXT_MODEL` / `LLM_VISION_MODEL` | LLM provider/model |
| `GOOGLE_MAPS_API_KEY` / `REACT_APP_GOOGLE_MAPS_API_KEY` | Live-map rendering |
| `CORS_ALLOWED_ORIGINS` | Dashboard origin(s) |

---

## AI integration

Two layers, both degradable to a deterministic mock when `LLM_API_KEY` is empty:

1. **The agent (`agent/`)** — the system's brain. Operators drive the platform
   in natural language via the **AI Assistant** dashboard page (`/assistant`),
   and the agent autonomously reacts to serious incidents. See
   "[The AI Agent is the core](#the-ai-agent-is-the-core)".

2. **Incident triage (`core.services.llm`)** — when a guard submits a report
   (text + optional photos), it is classified into a validated schema:
   `category`, `severity`, `summary`, `recommended_action`, `anomaly_detected`,
   `tags`, `source`. Reports also get an LLM-written executive narrative.

---

## Key API endpoints (v1)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/token/` | Obtain JWT (username/password) |
| GET | `/me/` | Current user profile |
| GET/POST | `/vehicles/`, `/locations/` | Fleet CRUD |
| GET/POST | `/plans/` | Patrol plans |
| POST | `/plans/{id}/plan_route/` | Auto-generate optimised route |
| POST | `/pings/` | Real-time position (mobile) |
| GET | `/pings/live/` | Latest vehicle positions (map) |
| POST | `/incidents/` | Submit report → AI analysis |
| POST | `/routing/shortest-path/` | Shortest path between two locations |
| POST | `/routing/compare-emissions/` | Plan CO₂e comparison |
| GET | `/reports/patrol/?period=daily\|monthly` | Report + AI narrative |
| GET | `/dashboard/summary/` | Dashboard KPIs |
| POST | `/agent/chat/` | **Talk to the AI agent** (tool-calling) |
| GET | `/agent/actions/?status=pending` | Pending actions (incl. autonomous) |
| POST | `/agent/actions/{id}/confirm/` | Confirm & execute a proposed action |
| POST | `/agent/actions/{id}/reject/` | Reject a proposed action |

Full, always-current contract at **`/api/docs/`**. See
[`docs/MOBILE_API.md`](docs/MOBILE_API.md) for the Flutter integration guide.

---

## Tech stack

- **Backend**: Django 4.2, Django REST Framework, SimpleJWT, drf-spectacular
- **DB**: MySQL 8 (PyMySQL driver; sqlite fallback)
- **AI**: OpenAI-compatible SDK (text + vision), mock fallback
- **Frontend**: React 18, MUI, Nivo charts, `@react-google-maps/api`
- **Infra**: Docker Compose (db + web + frontend), Gunicorn
