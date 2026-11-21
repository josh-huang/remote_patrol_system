"""Comparison planners. All take the same distance matrix and cover every site.

* ``round_robin``      — the stand-in for manual planning used by the app.
* ``greedy_nearest``   — vehicles repeatedly take their nearest unvisited site.
* ``sweep``            — cluster-first, route-second: split sites into equal
                         angular sectors around the centroid, then NN + 2-opt.
* ``ortools``          — Google OR-Tools routing solver (guided local search),
                         used as a near-optimal reference.
"""

from __future__ import annotations

import math
import time

from core.services import routing
from core.services.routing import Matrix, Node


def total_km(routes: list[list[int]], matrix: Matrix) -> float:
    return sum(routing.path_length(r, matrix) for r in routes)


def capacity(n: int, k: int) -> int:
    """The planner's balance cap, applied to every method for a fair comparison."""
    return math.ceil(n / k) + 1


def round_robin(nodes: list[Node], k: int, matrix: Matrix) -> list[list[int]]:
    return [r.stop_order for r in routing.baseline_routes(nodes, k, matrix=matrix)]


def greedy_nearest(nodes: list[Node], k: int, matrix: Matrix) -> list[list[int]]:
    cap = capacity(len(nodes), k)
    ids = [n.id for n in nodes]
    # Seed vehicles with mutually distant sites (farthest-point heuristic).
    seeds = [ids[0]]
    while len(seeds) < k:
        seeds.append(max((i for i in ids if i not in seeds), key=lambda i: min(matrix[i][s] for s in seeds)))
    routes = [[s] for s in seeds]
    left = set(ids) - set(seeds)
    while left:
        best = None
        for v, route in enumerate(routes):
            if len(route) >= cap:
                continue
            row = matrix[route[-1]]
            site = min(left, key=row.__getitem__)
            if best is None or row[site] < best[0]:
                best = (row[site], v, site)
        _, v, site = best
        routes[v].append(site)
        left.discard(site)
    return routes


def sweep(nodes: list[Node], k: int, matrix: Matrix) -> list[list[int]]:
    clat = sum(n.lat for n in nodes) / len(nodes)
    clng = sum(n.lng for n in nodes) / len(nodes)
    ordered = sorted(nodes, key=lambda n: math.atan2(n.lat - clat, n.lng - clng))
    size = math.ceil(len(nodes) / k)
    sectors = [ordered[i : i + size] for i in range(0, len(ordered), size)]
    return [routing.two_opt(routing.nearest_neighbour([n.id for n in s], matrix, None), matrix) for s in sectors]


def ours(nodes: list[Node], k: int, matrix: Matrix) -> list[list[int]]:
    return [r.stop_order for r in routing.plan_patrol_routes(nodes, k, matrix=matrix, priority_tiers=False)]


def ortools(nodes: list[Node], k: int, matrix: Matrix, seconds: float) -> list[list[int]]:
    """Open routes (start and end anywhere) with the same balance cap."""
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    ids = [n.id for n in nodes]
    # Index 0 is a dummy depot at zero distance from everything, which turns
    # closed tours into open paths.
    def metres(a: int, b: int) -> int:
        if a == 0 or b == 0:
            return 0
        return int(round(matrix[ids[a - 1]][ids[b - 1]] * 1000))

    manager = pywrapcp.RoutingIndexManager(len(ids) + 1, k, 0)
    model = pywrapcp.RoutingModel(manager)
    transit = model.RegisterTransitCallback(
        lambda i, j: metres(manager.IndexToNode(i), manager.IndexToNode(j))
    )
    model.SetArcCostEvaluatorOfAllVehicles(transit)
    demand = model.RegisterUnaryTransitCallback(lambda i: 0 if manager.IndexToNode(i) == 0 else 1)
    model.AddDimensionWithVehicleCapacity(demand, 0, [capacity(len(ids), k)] * k, True, "stops")

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.FromMilliseconds(int(seconds * 1000))
    solution = model.SolveWithParameters(params)
    if solution is None:
        raise RuntimeError("OR-Tools found no solution")

    routes = []
    for v in range(k):
        index, route = model.Start(v), []
        while not model.IsEnd(index):
            node = manager.IndexToNode(index)
            if node:
                route.append(ids[node - 1])
            index = solution.Value(model.NextVar(index))
        routes.append(route)
    return routes


def timed(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start
