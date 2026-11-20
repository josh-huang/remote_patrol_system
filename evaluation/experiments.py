"""The evaluation experiments. Each returns plain data (lists/dicts) for
``run.py`` to save and plot.

E1 planning quality    — our planner vs manual, greedy, sweep and OR-Tools
E2 dynamic re-routing  — Monte Carlo emergencies: drive back vs re-route
E3 shortest paths      — Dijkstra / Bellman-Ford / Floyd-Warshall run time
E4 scalability         — planner run time up to 500 sites
E5 road-model accuracy — the approximate road network vs real OSRM roads
"""

from __future__ import annotations

import random
import statistics
import time

from core.services import emissions, routing
from core.services.routing import Graph, Node

from . import baselines, instances, osrm

METHODS = {
    "Manual (round-robin)": baselines.round_robin,
    "Greedy nearest": baselines.greedy_nearest,
    "Sweep": baselines.sweep,
    "This system": baselines.ours,
}


def _model_matrix(nodes: list[Node]) -> routing.Matrix:
    return routing.distance_matrix(Graph.road_network(nodes))


# ---------------------------------------------------------------------------
# E1
# ---------------------------------------------------------------------------
def planning_quality(sizes: dict[int, int], ortools_seconds: dict[int, float] | None) -> list[dict]:
    """One row per (instance, method): total km and run time.

    ``sizes`` maps site count → number of random instances. ``ortools_seconds``
    maps site count → solver time limit; ``None`` skips OR-Tools.
    """
    rows = []
    for n, count in sizes.items():
        k = instances.fleet_size(n)
        for seed in range(count):
            nodes = instances.random_sites(n, seed=1000 * n + seed)
            matrix = _model_matrix(nodes)
            methods = dict(METHODS)
            if ortools_seconds:
                methods["OR-Tools (reference)"] = lambda nd, kk, mm: baselines.ortools(nd, kk, mm, ortools_seconds[n])
            for name, method in methods.items():
                routes, seconds = baselines.timed(method, nodes, k, matrix)
                assert sorted(s for r in routes for s in r) == sorted(x.id for x in nodes), name
                rows.append(
                    {
                        "sites": n,
                        "vehicles": k,
                        "seed": seed,
                        "method": name,
                        "km": round(baselines.total_km(routes, matrix), 3),
                        "seconds": round(seconds, 4),
                    }
                )
            print(f"  E1 n={n} seed={seed} done", flush=True)
    return rows


def summarise_quality(rows: list[dict]) -> list[dict]:
    """Mean km per method and size, and the gap to the best method per instance."""
    out = []
    for n in sorted({r["sites"] for r in rows}):
        sized = [r for r in rows if r["sites"] == n]
        best, reference = {}, {}
        for r in sized:
            best[r["seed"]] = min(best.get(r["seed"], float("inf")), r["km"])
            if r["method"].startswith("OR-Tools"):
                reference[r["seed"]] = r["km"]
        for method in dict.fromkeys(r["method"] for r in sized):
            mine = [r for r in sized if r["method"] == method]
            row = {
                "sites": n,
                "vehicles": mine[0]["vehicles"],
                "method": method,
                "instances": len(mine),
                "mean_km": round(statistics.mean(r["km"] for r in mine), 1),
                "gap_to_best_pct": round(statistics.mean(100 * (r["km"] / best[r["seed"]] - 1) for r in mine), 1),
                "mean_seconds": round(statistics.mean(r["seconds"] for r in mine), 3),
            }
            if reference:
                gaps = [100 * (r["km"] / reference[r["seed"]] - 1) for r in mine]
                row["gap_to_ortools_pct"] = round(statistics.mean(gaps), 1)
                row["beats_ortools"] = sum(g < -1e-9 for g in gaps)
            out.append(row)
    return out


# ---------------------------------------------------------------------------
# E2
# ---------------------------------------------------------------------------
def simulate_reroutes(
    nodes: list[Node], k: int, matrix: routing.Matrix, trials: int, seed: int, label: str
) -> list[dict]:
    """Random emergencies during a planned night.

    For each trial: a random vehicle has visited a random number of its stops
    and is somewhere on the road to its next stop when an alarm goes off at a
    site still waiting on another vehicle's route. We cost the old practice
    (go to the emergency, drive back to the last visited site, resume) against
    the system's re-route (continue from the emergency site, re-optimised).
    """
    rnd = random.Random(seed)
    plan = routing.plan_patrol_routes(nodes, k, matrix=matrix)
    by_id = {n.id: n for n in nodes}
    rows = []
    attempts = 0
    while len(rows) < trials and attempts < trials * 20:
        attempts += 1
        mine = rnd.choice(plan).stop_order
        if len(mine) < 2:
            continue
        visited = rnd.randint(1, len(mine) - 1)
        progress = visited / len(mine)
        waiting = [
            s
            for r in plan
            if r.stop_order is not mine
            for s in r.stop_order[int(progress * len(r.stop_order)) :]
        ]
        if not waiting:
            continue
        emergency = rnd.choice(waiting)
        last, nxt = by_id[mine[visited - 1]], by_id[mine[visited]]
        u = rnd.random()
        here = Node(-1, "vehicle", last.lat + u * (nxt.lat - last.lat), last.lng + u * (nxt.lng - last.lng))
        m = routing.attach_points(matrix, nodes, [here])
        result = routing.reroute_after_emergency(None, -1, emergency, mine[visited:], resume_id=last.id, matrix=m)
        rows.append(
            {
                "scenario": label,
                "baseline_km": result.baseline_km,
                "rerouted_km": result.rerouted_km,
                "saved_km": result.saved_km,
                "saved_kg_petrol": emissions.estimate_emission_kg(result.saved_km, "petrol"),
            }
        )
    return rows


def summarise_reroutes(rows: list[dict]) -> list[dict]:
    out = []
    for label in dict.fromkeys(r["scenario"] for r in rows):
        saved = sorted(r["saved_km"] for r in rows if r["scenario"] == label)
        base = [r["baseline_km"] for r in rows if r["scenario"] == label]
        out.append(
            {
                "scenario": label,
                "trials": len(saved),
                "mean_saved_km": round(statistics.mean(saved), 2),
                "median_saved_km": round(statistics.median(saved), 2),
                "p90_saved_km": round(saved[int(0.9 * (len(saved) - 1))], 2),
                "share_with_saving_pct": round(100 * sum(s > 0.05 for s in saved) / len(saved), 1),
                "mean_saving_pct_of_remaining": round(100 * sum(saved) / sum(base), 1),
            }
        )
    return out


# ---------------------------------------------------------------------------
# E3, E4
# ---------------------------------------------------------------------------
def algorithm_runtimes(sizes: list[int]) -> list[dict]:
    rows = []
    for n in sizes:
        graph = Graph.road_network(instances.random_sites(n, seed=7))
        reference = None
        for name in routing.ALGORITHMS:
            start = time.perf_counter()
            matrix = routing.distance_matrix(graph, name)
            seconds = time.perf_counter() - start
            if reference is None:
                reference = matrix
            agree = all(abs(matrix[a][b] - reference[a][b]) < 1e-9 for a in matrix for b in matrix[a])
            rows.append({"sites": n, "algorithm": name, "seconds": round(seconds, 4), "agrees": agree})
        print(f"  E3 n={n} done", flush=True)
    return rows


def scalability(sizes: list[int]) -> list[dict]:
    rows = []
    for n in sizes:
        nodes = instances.random_sites(n, seed=11)
        matrix = _model_matrix(nodes)
        for fleet, k in (("5 vehicles", 5), ("~10 sites per vehicle", instances.fleet_size(n))):
            plan, seconds = baselines.timed(routing.plan_patrol_routes, nodes, k, matrix=matrix)
            rows.append(
                {
                    "sites": n,
                    "fleet": fleet,
                    "vehicles": k,
                    "seconds": round(seconds, 3),
                    "km": round(sum(r.total_distance_km for r in plan), 1),
                }
            )
        print(f"  E4 n={n} done", flush=True)
    return rows


# ---------------------------------------------------------------------------
# E5
# ---------------------------------------------------------------------------
def road_model_accuracy(name: str, nodes: list[Node], real: routing.Matrix) -> dict:
    """Compare straight-line, straight-line × circuity and the road-network model
    against real driving distances for every pair of sites."""
    model = _model_matrix(nodes)
    pairs = []
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            straight = routing.haversine_km(a.lat, a.lng, b.lat, b.lng)
            if straight < 0.1:  # effectively the same spot; ratios are meaningless
                continue
            pairs.append((straight, model[a.id][b.id], real[a.id][b.id]))

    def mape(est):
        return round(100 * statistics.mean(abs(e - r) / r for e, (_, _, r) in zip(est, pairs)), 1)

    ratios = sorted(r / s for s, _, r in pairs)
    q = statistics.quantiles(ratios, n=4)
    return {
        "instance": name,
        "sites": len(nodes),
        "pairs": len(pairs),
        "real_over_straight_median": round(statistics.median(ratios), 3),
        "real_over_straight_iqr": [round(q[0], 3), round(q[2], 3)],
        "mape_straight_line_pct": mape([s for s, _, _ in pairs]),
        "mape_straight_x_circuity_pct": mape([s * routing.DEFAULT_CIRCUITY for s, _, _ in pairs]),
        "mape_road_model_pct": mape([m for _, m, _ in pairs]),
        "correlation_road_model": round(statistics.correlation([m for _, m, _ in pairs], [r for *_, r in pairs]), 3),
        "points": [{"straight": round(s, 3), "model": round(m, 3), "real": round(r, 3)} for s, m, r in pairs],
    }


def demo_night_on_real_roads(nodes: list[Node], real: routing.Matrix, vehicles: int = 4) -> dict:
    """Does the demo night's saving hold when every route is costed on real roads?"""
    model = _model_matrix(nodes)

    def on_real(routes):
        return round(sum(routing.path_length(r.stop_order, real) for r in routes), 1)

    planned_on_model = routing.plan_patrol_routes(nodes, vehicles, matrix=model)
    planned_on_real = routing.plan_patrol_routes(nodes, vehicles, matrix=real)
    manual = routing.baseline_routes(nodes, vehicles, matrix=real)
    return {
        "vehicles": vehicles,
        "manual_km_real": on_real(manual),
        "planned_on_model_km_real": on_real(planned_on_model),
        "planned_on_real_km_real": on_real(planned_on_real),
        "planned_on_model_km_model": round(sum(r.total_distance_km for r in planned_on_model), 1),
        "manual_km_model": round(sum(r.total_distance_km for r in routing.baseline_routes(nodes, vehicles, matrix=model)), 1),
    }


def osrm_instances(refresh: bool) -> dict[str, tuple[list[Node], routing.Matrix]]:
    """Road-snapped sites and real distances; instances with no data are left out."""
    candidates = {
        "demo_20": instances.demo_sites(),
        "random_100": instances.random_sites(100, seed=2026),
    }
    found = {}
    for name, nodes in candidates.items():
        loaded = osrm.load_or_fetch(name, nodes, refresh)
        if loaded:
            found[name] = loaded
    return found
