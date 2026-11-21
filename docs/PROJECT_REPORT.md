# Dynamic Patrol Routing System — Project Report

Huang Jiashu · revised 20 November 2026

## Background

This system was first built as my undergraduate capstone (CSC3001 Capstone Project, Singapore Institute of Technology – University of Glasgow Joint Degree in Computing Science, August 2022 – April 2023), an industry project with a Singapore security services company. Its problem definition and design draft are kept in the repository.

The original source code was lost. The version described here is a 2026 rebuild written with AI assistance (Claude Code) from those two documents. It implements every original requirement and goes beyond the original scope in four places, marked as such in this report: the AI agent and LLM incident triage, real road distances through OSRM, the evaluation against OR-Tools, and the architecture hardening.

## Abstract

The Dynamic Patrol Routing System automates the nightly route planning of a security patrol fleet and cuts the mileage driven, and therefore the carbon emitted, by about half against manual planning: 56% on the demo night in the road model (102 km versus 232 km) and 48% when the same routes are costed on real driving distances (118 km versus 228 km). Its planner comes within 1.4–5.5% of Google OR-Tools while running in well under a second, and re-routing after an emergency saves a median 6.6 km per alarm on real roads.

Today, command-centre administrators plan routes for roughly 50 sites and 5 vehicles by hand, collect proof-of-visit photos over WhatsApp, and send vehicles back to their original route after every emergency. The system replaces this with three parts: a Django REST backend with a priority-aware multi-vehicle route planner and a dynamic re-router, a React command-centre dashboard, and a Flutter app on each vehicle's duty phone. When an emergency alarm diverts a vehicle, its remaining stops are re-planned from the emergency site instead of driving back, and the saving is recorded. An optional AI agent lets operators run the system in plain language, with every action it proposes held for human confirmation.

## Problem statement

Night patrols are planned by hand, recorded over WhatsApp and disrupted by emergencies in a way that wastes fuel, and none of this scales as the business grows.

The client, a security service provider, patrols about 50 sites across Singapore every night with 5 vehicles. How many vehicles can actually drive depends on their health: a vehicle that breaks down or is in maintenance leaves the rest of the fleet to cover its sites.

The current process has five problems:

1. **Manual planning.** Every night, administrators in the command centre decide which sites each driver visits. This is manageable at 50 sites and 5 vehicles, but it grows with every new contract and depends on the administrators' judgement rather than on distance.
2. **Proof of visit is scattered.** Guards photograph each site and send the pictures over WhatsApp. Photos are easily lost and cannot be searched or reported on.
3. **Emergencies cause backtracking.** When an alarm goes off, the nearest vehicle is told to go there. Afterwards it drives back to the site where it left its route and carries on, which costs extra time and fuel.
4. **No visibility.** The command centre has no single view of where vehicles are, which ones are fit to drive, or what the patrol costs in mileage and emissions.
5. **Carbon emissions.** One US gallon of petrol emits about 8,887 g of CO2. Every unnecessary kilometre adds to the company's footprint, against the global goal of net-zero emissions by 2050.

Formally, this is a vehicle routing problem that is **static and stochastic**: the sites are known in advance, but emergencies arise at random sites during the night and force changes to routes already under way.

## Project objectives

The project has two high-level targets: reduce carbon emissions, measured by the difference in mileage between the original and the proposed routes, and remove the need for administrators to plan routes every night.

These break down into four objectives from the problem definition:

1. **Daily automatic planning.** Plan each vehicle's route every day from the sites and the vehicles available that day, covering every site with the shortest overall distance.
2. **Dynamic re-planning.** Automatically re-plan the route of a vehicle diverted to an emergency, so it does not drive extra kilometres back to its old route.
3. **Command-centre dashboard.** Show real-time vehicle locations, vehicle details (plate number, driver in charge, health status, mileage), an emergency alert noticeboard and the estimated carbon footprint.
4. **Mobile app.** Let the guards in each vehicle view the night's route plan and contact the command centre directly.

## Requirements

Every requirement in the problem definition and the design draft is implemented. The table maps each one to the part of the system that delivers it.

| Area | Requirement | Implemented by |
| --- | --- | --- |
| Planning | Daily plan from available vehicles and sites, every site covered, shortest total distance | Multi-vehicle planner; `plan_daily` command; one-click Automatic plan |
| Planning | Shortest path with Dijkstra, Bellman-Ford and Floyd-Warshall | Routing service; Shortest path tool on the dashboard |
| Planning | Re-plan a vehicle diverted to an emergency | Emergency dispatch with dynamic re-routing |
| Planning | Vehicles unavailable because of their health status | Vehicles in service or out of service are excluded; Rebalance moves a broken-down vehicle's sites |
| Planning | Manual route planning | Route Planning, Manual plan tab |
| Carbon | Estimate emissions from mileage and engine type | Emissions service (kg CO2e per km by engine type) |
| Carbon | Compare original and proposed routes; graph past emissions per vehicle | Manual baseline stored per plan; per-vehicle 30-day chart; carbon-savings panel |
| Dashboard | Add or remove locations and vehicles | Locations, Vehicles and Guards pages |
| Dashboard | Real-time vehicle location on Google Maps | Live Map, fed by duty-phone GPS pings |
| Dashboard | Vehicle details: plate, contact, driver in charge, health status, mileage | Fleet status table and Vehicles page |
| Dashboard | Emergency alert noticeboard | Dashboard noticeboard and Emergency Alerts page |
| Dashboard | Past patrol records; daily or monthly report | Patrol Records (with photos); Reports with CSV export |
| Mobile | Each account linked to one vehicle | Guard profile's assigned vehicle; all mobile endpoints scoped to it |
| Mobile | View the route plan and next location | Route screen with navigation to the next site |
| Mobile | Submit pictures of the location | Check-in with camera or gallery photos, stored centrally |
| Mobile | Submit an incident report | Incident screen with photos and AI triage |
| Mobile | Contact the command centre by message or phone | Command screen: message thread and Call button |
| Data | Central MySQL database for vehicles, locations, daily plans and guard images | MySQL 8 (SQLite for local development) |

## Solution overview and architecture

The solution is one backend serving two clients: a web dashboard for the command centre and a mobile app for each vehicle, both reading and writing the same central database.

![System architecture: 2 clients, 6 backend apps, 1 service layer, optional OSRM and LLM services](images/architecture.png)

Every business rule (planning, check-in, dispatch, re-routing, rebalancing, incident triage) lives in one service layer per domain, which the API, the AI agent, the nightly command and the demo seeder all call. A rule therefore behaves the same no matter who triggers it.

**Domain events.** Apps react to each other through events rather than direct imports. Incident triage publishes `incident_triaged`, to which the AI agent subscribes; dispatching a vehicle publishes `vehicle_dispatched`, to which messaging subscribes and sends the instruction to the duty phone in the same transaction. A failing subscriber to triage is logged and never blocks incident intake.

**Concurrency.** Alerts, plans, stops and sites are row-locked while they change, and only an active alert can be dispatched. Two operators, or an operator and the agent, therefore cannot divert two vehicles to the same emergency, and a double-tapped check-in records one visit.

**Data model.** The main entities follow the design draft: users with an admin or guard role; a guard profile with badge, availability, on-duty and driver flags and its linked vehicle; vehicles with plate, model, engine type, odometer, health status, availability and last known position; sites with coordinates, priority and an emergency flag. A plan holds ordered stops per vehicle, its total and baseline distance and emissions, and its re-route savings. Visits are stored as patrol records with their photos; GPS pings, incident reports, emergency alerts and messages complete the model.

**Roles and security.** Administrators have full access. Guards can only read their own vehicle's stops, records, pings and messages and their own incident reports, and cannot reach planning, fleet management, dashboards or the agent. Login is rate-limited, a deployment check refuses to start production with the development secret key, HTTPS settings switch on behind TLS, and the health endpoint probes the database.

## Route planning and dynamic re-routing

The planner covers every site exactly once, visits higher-priority sites first and minimises total distance; the re-router continues from the emergency site rather than going back. Both are pure Python with no external map service, so they are fast, testable and free to run.

### Road-network model

Sites are joined into an approximate road network rather than a complete graph. Each site is linked to its 5 nearest neighbours, and a minimum spanning tree (Prim's algorithm) is added so the network is always connected. Each edge weighs the great-circle (haversine) distance multiplied by a road-circuity factor of 1.3, since urban roads typically run 20–40% longer than a straight line.

Because the graph is sparse, a trip between two far-apart sites passes through intermediate sites. This makes the shortest-path algorithms meaningful: on a complete graph, the direct edge would always be the answer. Every active site is always part of the network, so the distance from A to B is the same in a daily plan, a manual plan and a re-route.

### Shortest-path algorithms

All three algorithms named in the proposal are implemented, and any of them can build the all-pairs distance matrix the planner uses:

- **Dijkstra** with a binary heap, O((V + E) log V) per source.
- **Bellman-Ford**, O(V·E) per source, which also detects negative cycles.
- **Floyd-Warshall**, O(V³) for all pairs at once.

Tests confirm they produce identical matrices, and the dashboard's Shortest path tool runs all three on the same query and shows each one's distance and run time.

### Daily multi-vehicle planner

The planner implements the proposal's `shortestRoute(location_list, priority_location, num_car)` as a capacitated, priority-aware multi-vehicle routing heuristic with multi-start local search:

1. Read the distance matrix (cached; see *Distance providers* below).
2. Build four starting plans: one seeds each vehicle with a highest-priority site and inserts the rest at the position that adds the least distance; three sweep the sites around their centroid into equal sectors, at different rotations. Every vehicle gets at least one stop and at most ceil(n / vehicles) + 1, so the work is shared fairly.
3. Improve each start with local search until no move helps: 2-opt inside a route, relocating a site (within or between routes), swapping two sites between routes, and exchanging the tails of two routes (2-opt*).
4. Order each route tier by tier (emergency sites first, then high and normal priority) and keep the shortest plan. A tier-aware insertion plan is always a candidate, since it can win when priority tiers dominate.

Every move is costed in constant time from the matrix, because only the edges at its ends change. On 300 sites this cut planning time from 4.5 s to 0.4 s compared with re-summing whole routes, and 500 sites plan within a 5 s search budget.

Only operational vehicles are planned: those marked available and not in service or out of service. Vehicles can start from a shared depot or from their live GPS positions. The `plan_daily` command runs this nightly from cron, so no administrator input is needed.

### Distance providers (added in the rebuild)

Where the kilometres come from is pluggable. The default provider is the road-network model above: offline, deterministic, and the place where the three shortest-path algorithms run. The OSRM provider returns real driving distances on OpenStreetMap roads from an OSRM server's table service, averaged over both directions so the matrix stays symmetric. If OSRM cannot be reached, planning falls back to the model automatically.

The site-to-site matrix depends only on site coordinates, so it is cached under a fingerprint of them: adding, moving or deactivating a site produces a new cache key, and nothing has to be invalidated by hand. A vehicle's live position joins the network as a *leaf* through its nearest sites. A route can start there but never passes through it, so a moving vehicle never forces the matrix to be recomputed.

### Dynamic re-routing after an emergency

When an alarm is raised at a site, the command centre (or the AI agent, with confirmation) dispatches the nearest operational vehicle. The re-router then:

1. Sends the vehicle from its current position to the emergency site.
2. Re-optimises its remaining unvisited stops starting **from the emergency site**.
3. Removes the emergency site from any other vehicle's remaining route, so it is not visited twice.
4. Costs the old practice for comparison: drive to the emergency, back to the last site visited, then resume the original order.
5. Stores the difference in km and kg CO2e on the alert and the plan, and messages the vehicle's duty phone.

When a vehicle breaks down mid-patrol, **Rebalance** inserts its unvisited sites into the remaining routes of the other vehicles, each at its cheapest position.

## Carbon emission estimation

Emissions are estimated from the two factors the design draft names, mileage and engine type, and every saving is measured as kilometres not driven.

```math
\text{CO}_2\text{e (kg)} = \text{distance (km)} \times f_{\text{engine}}
```

| Engine type | Factor (kg CO2e per km) | Basis |
| --- | --- | --- |
| Petrol | 0.192 | 8,887 g CO2 per US gallon (2.35 kg per litre) at about 8.2 L per 100 km; matches the US EPA typical passenger vehicle |
| Diesel | 0.171 | Fleet average |
| Hybrid | 0.106 | Fleet average |
| Electric | 0.050 | Grid-average upstream emissions, not zero |

The factors live in one module so they are easy to tune.

Savings come from two sources:

- **Planning.** Each plan stores a *manual baseline* next to the optimised route: the same sites handed out round-robin in priority order and visited in that order, with no distance optimisation. This stands in for planning by hand. Saved CO2e is the baseline's emissions minus the plan's, per vehicle and engine type.
- **Re-routing.** Each emergency dispatch stores the km and CO2e saved against driving back to the original route.

The dashboard and reports show both, and the system can also compare a shortest-distance plan with a best-traffic plan (modelled as 12% longer but with 6% lower emissions per km from smoother driving), as the design draft asks.

## Command-centre dashboard

The React dashboard gives administrators one place to see the night's patrol, act on emergencies and manage the fleet; it is restricted to admin accounts.

| Page | What administrators do there |
| --- | --- |
| Dashboard | KPIs (operational vehicles, sites patrolled, active alerts, CO2e emitted and saved), the emergency noticeboard, a live map of vehicles and routes, the fleet status table, per-vehicle emissions over 30 days and a carbon-savings panel |
| Live Map | Vehicle positions and each vehicle's remaining route, refreshed every 5 s; sites with an active alarm pulse red |
| Route Planning | Automatic plan (vehicles, sites, algorithm, depot or live start), Manual plan (stop order per vehicle), plan history with Rebalance, and the shortest-path comparison of the three algorithms |
| Emergency Alerts | Raise an alert, dispatch the nearest or a chosen vehicle, see the new route against the old practice with km and CO2e saved, and resolve |
| Incidents | AI-triaged reports from guards with photos; acknowledge or resolve |
| Messages | One conversation per vehicle with unread counts |
| Vehicles, Locations, Guards | Add, edit and remove; link guard accounts to vehicles; trigger a site alarm |
| Patrol Records | Past visits filtered by vehicle and date, with the site photos |
| Reports | Daily or monthly totals, per-vehicle distance and emissions, carbon savings, an AI-written summary and CSV download |
| AI Assistant | Chat with the agent and confirm or reject the actions it proposes |

Maps use Google Maps when an API key is configured. Without one, a schematic SVG map projects the same sites, vehicles and routes, so the dashboard works out of the box.

## Duty-phone mobile app

The Flutter app runs on the phone in each vehicle. Each guard account is linked to one vehicle, and the server scopes every request to that vehicle, so the app never sends a vehicle id and a guard cannot see another vehicle's data.

- **Route.** Shows the night's plan, progress and the next location, with a Navigate button that opens Google Maps directions. It refreshes every 30 s and warns the driver when the command centre re-routes them to an emergency.
- **Check in.** Marks a site visited with camera or gallery photos and notes. The photos are stored centrally against the visit, replacing WhatsApp.
- **Incident.** Sends a description, the site and photos, and shows the AI's severity, category and recommended action straight away.
- **Command.** A message thread with the command centre and a Call button that dials the command-centre hotline.
- **On duty.** A switch that posts the phone's GPS position every 15 s, which drives the dashboard's live map.

The app talks to the same REST API as the dashboard, using JWT tokens that refresh automatically. The design draft suggested Firestore for mobile data; using the shared API and MySQL database instead keeps one source of truth for both clients.

## AI agent and incident triage (added in the rebuild)

AI is used in two places, and in both a human stays in control: the agent proposes, an operator confirms.

**Incident triage.** When a guard submits a report, a language model (with vision for photos) classifies it into a fixed schema: category, severity (low to critical), summary, recommended action and an anomaly flag. Model output is checked against that schema before it is stored.

**Agent ("Sentinel").** Operators can run the system in plain language, for example "plan tonight's patrol" or "handle the active emergency alerts". The agent calls the same service layer as the dashboard through about a dozen tools:

- **Read tools** run immediately: fleet, sites, live positions, routes, alerts, incidents, shortest paths, emissions and reports.
- **Write tools** never run directly: creating a plan, raising or dispatching an alert and changing an incident's status are queued as pending actions for an operator to confirm or reject. Every tool call and its result is stored for audit.

**Autonomy.** When an incident is triaged as high or critical at a known site, the system raises an emergency alert and the agent queues a dispatch of the nearest operational vehicle, including the re-route, for the operator to confirm.

The model provider is configurable (any OpenAI-compatible API). With no API key, deterministic fallbacks take over (keyword-based triage, and a keyword router for the agent in English and Chinese), so the whole system can be demonstrated offline.

## Technology stack

The stack follows the design draft (Django, MySQL, React, Flutter) and adds only what the features need.

| Layer | Technology | Why |
| --- | --- | --- |
| Backend framework | Python, Django 4.2, Django REST Framework | Mature ORM and admin; one API serves both the dashboard and the app |
| Authentication | JWT (SimpleJWT) with refresh-token rotation | Stateless tokens suit a mobile client; roles separate admins and guards |
| API documentation | drf-spectacular (OpenAPI 3, Swagger UI) | Always-current contract for the mobile app |
| Database | MySQL 8 (PyMySQL driver); SQLite for development | Central store required by the proposal; SQLite for zero-setup runs |
| Algorithms | Pure Python: haversine, Prim's MST, Dijkstra, Bellman-Ford, Floyd-Warshall, insertion, sweep and local-search heuristics | No paid routing API; fully unit-testable |
| Dashboard | React 18, Material UI, MUI Data Grid, Nivo charts | Component library for data-heavy admin pages |
| Maps | Google Maps JavaScript API (`@react-google-maps/api`), SVG fallback | Live tracking as specified; works without a key |
| Mobile app | Flutter (Dart) with http, geolocator, image_picker, url_launcher, shared_preferences | One codebase for Android and iOS; GPS, camera, maps and phone calls |
| AI | OpenAI-compatible chat and vision models via the `openai` SDK, with offline fallback | Provider-agnostic; demoable without a key |
| Real road distances | OSRM table service (optional provider) | True driving distances without a paid API; falls back to the model |
| Evaluation | Google OR-Tools (reference solver), matplotlib | Near-optimal benchmark and charts; development-only dependencies |
| Deployment | Docker Compose (MySQL, Gunicorn web, dashboard), environment-based settings | Same setup on any machine |
| Quality | Django test runner, GitHub Actions CI (backend tests, schema check, dashboard build, Flutter analyze and test) | Every push is checked |

## Testing and evaluation

Automated tests cover every layer, and a reproducible evaluation (`python -m evaluation.run`, added in the rebuild) measures the planner against stronger baselines, simulates emergencies, and checks the road model against real driving distances. Full tables: [`docs/evaluation/`](evaluation/README.md).

### Tests

| Suite | Count | Covers |
| --- | --- | --- |
| Backend (Django) | 76 tests | Algorithm correctness and agreement, O(1) move costs against full recomputation, planner coverage, balance and priority order, re-route never worse than driving back, OSRM provider and fallback, matrix cache, concurrency (double dispatch), events, login throttle, deploy check, every API flow, role-based access, the evaluation code |
| Dashboard | Production build with warnings treated as errors | All 12 pages also opened in a headless browser with no console errors |
| Mobile (Flutter) | Static analysis plus 2 tests | Sign-in screen; parsing of the route payload |

### Planning quality against stronger baselines

On random sites across Singapore's main island (about ten sites per vehicle), every method covered every site under the same balance cap. Google OR-Tools, an industrial routing solver, ran guided local search for 5–30 s per instance as a near-optimal reference.

![Planning quality](evaluation/planning_quality.png)

| Sites, vehicles | This system vs OR-Tools | Greedy nearest | Sweep | Manual round-robin | This system's time |
| --- | --- | --- | --- | --- | --- |
| 20, 3 (10 instances) | +1.4% | +25.9% | +27.7% | +264% | 0.003 s |
| 50, 5 (10 instances) | +3.2% (shorter on 1) | +29.7% | +22.6% | +532% | 0.02 s |
| 100, 10 (5 instances) | +5.5% (shorter on 1) | +28.2% | +46.0% | +911% | 0.12 s |
| 200, 20 (3 instances) | +1.8% (shorter on 2) | +28.7% | +55.4% | +1260% | 0.6 s |

This system's plans are within 1.4–5.5% of OR-Tools, and shorter than OR-Tools on 4 of the 28 instances, at a fraction of the run time. The round-robin baseline is a deliberately simple stand-in for manual planning; against random sites it is far worse than a person would be, so the credible comparison is with the greedy and sweep heuristics, which this system beats by 20–50%.

An earlier version of the planner (insertion plus relocation only) was 26% above OR-Tools at 50 sites. The evaluation exposed this, and the multi-start local search described above closed most of the gap.

### Dynamic re-routing

1,000 simulated alarms per scenario: a random vehicle is between two stops when an alarm goes off at a site still waiting on another vehicle's route. The old practice (go to the emergency, drive back to the last visited site, resume) is costed against the system's re-route.

![Re-routing savings](evaluation/reroute_savings.png)

| Scenario | Median saved | Mean saved | 90th percentile | Alarms with a saving | Saving vs driving back |
| --- | --- | --- | --- | --- | --- |
| Demo night, real roads | 6.6 km | 8.5 km | 20.0 km | 95.7% | 17.7% |
| Demo night, road model | 11.3 km | 13.7 km | 27.1 km | 100% | 25.9% |
| 50 random sites, road model | 2.6 km | 4.7 km | 12.4 km | 81.5% | 8.4% |

A re-route saves nothing when the site the vehicle would drive back to already lies on its way; the system then reports 0 km.

### Road model against real roads

Real driving distances for every pair of the 20 demo sites and of 100 random sites came from the OSRM routing engine on OpenStreetMap data, with sites snapped to the nearest road.

![Road model accuracy](evaluation/road_model_accuracy.png)

| Sites | Real ÷ straight line (median) | Straight line error | Straight × 1.3 error | Road model error | Correlation |
| --- | --- | --- | --- | --- | --- |
| 20 demo | 1.37 | 29.5% | 11.6% | 11.8% | 0.987 |
| 100 random | 1.45 | 32.6% | 14.0% | 15.0% | 0.960 |

Errors are mean absolute percentage errors. The model's 1.3 circuity factor is the best fit: higher values make the model overestimate, because the sparse network already adds detours. The network does not beat a plain straight-line × 1.3 estimate on accuracy; its value is that it gives the shortest-path algorithms a real graph to search. Where accuracy matters, the OSRM provider uses real distances.

On real roads the demo night still halves: the manual round-robin plan is 228.0 km, the plan made on the model 117.8 km (48% shorter), and a plan made directly on OSRM distances 109.9 km (52% shorter).

### Shortest-path algorithms and scaling

![Algorithm run times](evaluation/algorithm_runtimes.png)

All three algorithms return identical distance matrices. At 200 sites the all-pairs matrix takes 0.04 s with Dijkstra, 0.10 s with Floyd-Warshall and 0.24 s with Bellman-Ford, so Dijkstra is the default.

![Scalability](evaluation/scalability.png)

A full plan takes under a second up to 200 sites and about 1–1.6 s at 300; at 500 sites the local search reaches its 5 s budget and returns its best plan so far.

The manual baseline is still a stand-in, not the client's recorded routes, so the real-world saving should be confirmed against actual mileage.

## Limitations and future work

The main limits come from approximating the road network and from validating on demo data rather than live operations.

- **The default distances are approximate.** The road model is off by 12–15% on average against real roads. The OSRM provider fixes this for distance, but neither models traffic or travel time, so the best-traffic comparison is still modelled; a time-aware matrix (OSRM durations, or a traffic API) is the next step.
- **Heuristic, not optimal.** Multi-vehicle routing is NP-hard. The planner is within 1.4–5.5% of OR-Tools; using OR-Tools itself as an optional solver, with priority tiers expressed as constraints, would close the rest at the cost of seconds per plan.
- **Scale.** Pure Python reaches its 5 s budget at about 500 sites. Beyond that, a compiled solver or a cluster-first split into regions would be needed.
- **No time windows or shift limits.** Plans balance the number of stops, not driving time, and do not model site opening hours or a maximum shift length.
- **Emission factors are averages.** Per-vehicle fuel consumption from telematics would make the estimates specific to each vehicle.
- **Validation.** The manual baseline should be compared with the client's recorded routes, and the Flutter app still needs testing on physical Android and iOS devices.
- **Notifications.** The duty phone polls for re-routes and messages; push notifications (for example Firebase Cloud Messaging) would deliver emergencies instantly.
- **Background work.** LLM triage and very large plans run inside the web request. A task queue (Celery or RQ) would move them out, and a shared Redis cache would let all web workers reuse one distance matrix.

## Conclusion

The Dynamic Patrol Routing System meets all four objectives of the problem definition. Nightly routes are planned automatically from the vehicles fit to drive, covering every site with priority sites first. Vehicles diverted to an emergency carry on from the emergency site instead of driving back. The command centre has live tracking, vehicle details, an emergency noticeboard and a carbon view. Guards plan, check in, report and contact the command centre from one app.

The evaluation supports the design: plans within a few percent of an industrial solver in under a second, about half the mileage and CO2e of the manual baseline even on real roads, and a median 6.6 km saved per emergency diversion. The nightly planning task disappears altogether. The next steps are travel-time-aware distances and validation against the client's recorded routes.
