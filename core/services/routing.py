"""Route-planning services for the Remote Patrol System.

This module implements the three classic shortest-path algorithms named in the
project proposal (Dijkstra, Bellman-Ford, Floyd-Warshall) plus a multi-vehicle
patrol planner that assigns prioritised locations to a fleet.

The graph is derived from the geographic coordinates of patrol locations using
the haversine great-circle distance, so no external map/distance API is
required for planning (the frontend still renders the result on Google Maps).
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field

INF = float("inf")


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two lat/lng points, in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return radius * 2 * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Graph model
# ---------------------------------------------------------------------------
@dataclass
class Node:
    id: int
    name: str
    lat: float
    lng: float
    priority: int = 0


@dataclass
class Graph:
    """Weighted undirected graph keyed by node id."""

    nodes: dict[int, Node] = field(default_factory=dict)
    adjacency: dict[int, dict[int, float]] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        self.adjacency.setdefault(node.id, {})

    def add_edge(self, a: int, b: int, weight: float) -> None:
        self.adjacency.setdefault(a, {})[b] = weight
        self.adjacency.setdefault(b, {})[a] = weight

    @classmethod
    def complete_from_nodes(cls, nodes: list[Node]) -> "Graph":
        """Build a fully-connected graph using haversine distances as weights."""
        graph = cls()
        for node in nodes:
            graph.add_node(node)
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                graph.add_edge(
                    a.id, b.id, haversine_km(a.lat, a.lng, b.lat, b.lng)
                )
        return graph


# ---------------------------------------------------------------------------
# Shortest-path algorithms
# ---------------------------------------------------------------------------
def dijkstra(graph: Graph, source: int) -> tuple[dict[int, float], dict[int, int | None]]:
    """Dijkstra's algorithm. Requires non-negative weights (always true here)."""
    dist = {node: INF for node in graph.adjacency}
    prev: dict[int, int | None] = {node: None for node in graph.adjacency}
    dist[source] = 0.0
    heap: list[tuple[float, int]] = [(0.0, source)]

    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, weight in graph.adjacency[u].items():
            nd = d + weight
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))
    return dist, prev


def bellman_ford(
    graph: Graph, source: int
) -> tuple[dict[int, float], dict[int, int | None]]:
    """Bellman-Ford algorithm. Handles negative weights and detects cycles."""
    dist = {node: INF for node in graph.adjacency}
    prev: dict[int, int | None] = {node: None for node in graph.adjacency}
    dist[source] = 0.0

    edges = [
        (u, v, w)
        for u in graph.adjacency
        for v, w in graph.adjacency[u].items()
    ]

    for _ in range(len(graph.adjacency) - 1):
        updated = False
        for u, v, w in edges:
            if dist[u] != INF and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
                prev[v] = u
                updated = True
        if not updated:
            break

    for u, v, w in edges:
        if dist[u] != INF and dist[u] + w < dist[v]:
            raise ValueError("Graph contains a negative-weight cycle")
    return dist, prev


def floyd_warshall(
    graph: Graph,
) -> tuple[dict[int, dict[int, float]], dict[int, dict[int, int | None]]]:
    """Floyd-Warshall all-pairs shortest paths."""
    nodes = list(graph.adjacency)
    dist = {u: {v: INF for v in nodes} for u in nodes}
    nxt: dict[int, dict[int, int | None]] = {
        u: {v: None for v in nodes} for u in nodes
    }

    for u in nodes:
        dist[u][u] = 0.0
        for v, w in graph.adjacency[u].items():
            dist[u][v] = w
            nxt[u][v] = v

    for k in nodes:
        for i in nodes:
            for j in nodes:
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
                    nxt[i][j] = nxt[i][k]
    return dist, nxt


def reconstruct_path(prev: dict[int, int | None], source: int, target: int) -> list[int]:
    """Rebuild the node path from a `prev` map produced by Dijkstra/Bellman-Ford."""
    path: list[int] = []
    node: int | None = target
    while node is not None:
        path.append(node)
        if node == source:
            break
        node = prev[node]
    path.reverse()
    return path if path and path[0] == source else []


ALGORITHMS = {
    "dijkstra": dijkstra,
    "bellman_ford": bellman_ford,
}


def shortest_path(
    graph: Graph, source: int, target: int, algorithm: str = "dijkstra"
) -> dict:
    """Return the shortest path + distance between two nodes."""
    if algorithm == "floyd_warshall":
        dist, nxt = floyd_warshall(graph)
        if nxt[source][target] is None and source != target:
            return {"algorithm": algorithm, "distance_km": None, "path": []}
        path = [source]
        node = source
        while node != target:
            node = nxt[node][target]
            if node is None:
                return {"algorithm": algorithm, "distance_km": None, "path": []}
            path.append(node)
        return {
            "algorithm": algorithm,
            "distance_km": round(dist[source][target], 3),
            "path": path,
        }

    solver = ALGORITHMS.get(algorithm, dijkstra)
    dist, prev = solver(graph, source)
    path = reconstruct_path(prev, source, target)
    distance = dist[target]
    return {
        "algorithm": algorithm,
        "distance_km": None if distance == INF else round(distance, 3),
        "path": path,
    }


# ---------------------------------------------------------------------------
# Multi-vehicle patrol planner
# ---------------------------------------------------------------------------
@dataclass
class PlannedRoute:
    vehicle_index: int
    stop_order: list[int]
    total_distance_km: float


def plan_patrol_routes(
    nodes: list[Node],
    num_vehicles: int,
    depot_id: int | None = None,
) -> list[PlannedRoute]:
    """Assign locations to vehicles and order each vehicle's stops.

    Strategy:
      1. High-priority locations are seeded first so every vehicle picks up an
         important stop before optional ones.
      2. Remaining stops are greedily assigned to the vehicle whose current
         route ends closest to them (a nearest-neighbour / cheapest-insertion
         heuristic — a pragmatic approximation of the NP-hard multi-TSP).

    Mirrors the proposal signature:
        shortestRoute(location_list, priority_location, num_car) -> List
    """
    if num_vehicles < 1:
        raise ValueError("num_vehicles must be >= 1")

    graph = Graph.complete_from_nodes(nodes)
    node_by_id = {n.id: n for n in nodes}

    def dist(a: int, b: int) -> float:
        return graph.adjacency[a].get(b, INF)

    depot = depot_id if depot_id in node_by_id else None

    # Order candidate stops: higher priority first, then by name for stability.
    candidates = sorted(
        [n.id for n in nodes if n.id != depot],
        key=lambda nid: (-node_by_id[nid].priority, node_by_id[nid].name),
    )

    routes = [
        PlannedRoute(
            vehicle_index=i,
            stop_order=[depot] if depot is not None else [],
            total_distance_km=0.0,
        )
        for i in range(num_vehicles)
    ]

    # Seed each vehicle with the top priority stops (round-robin) for balance.
    for i, nid in enumerate(candidates[:num_vehicles]):
        route = routes[i]
        if route.stop_order:
            route.total_distance_km += dist(route.stop_order[-1], nid)
        route.stop_order.append(nid)
    remaining = candidates[num_vehicles:]

    # Greedily insert the rest onto whichever route-end is nearest.
    for nid in remaining:
        best_route = None
        best_cost = INF
        for route in routes:
            tail = route.stop_order[-1] if route.stop_order else None
            cost = dist(tail, nid) if tail is not None else 0.0
            if cost < best_cost:
                best_cost = cost
                best_route = route
        best_route.stop_order.append(nid)
        best_route.total_distance_km += 0.0 if best_cost == INF else best_cost

    for route in routes:
        route.total_distance_km = round(route.total_distance_km, 3)
    return routes
