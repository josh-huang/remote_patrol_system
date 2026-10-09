"""Route-planning services for the Dynamic Patrol Routing System.

Everything here is pure Python with no Django dependency so it can be unit
tested in isolation and reused by the API, the AI agent and management
commands.

The module provides three layers:

1. **Road-network graph** — patrol sites (plus any "virtual" points such as a
   vehicle's live GPS position) are connected to their nearest neighbours,
   approximating a road network. Edge weights are great-circle distances
   multiplied by a circuity factor (urban roads are ~30% longer than a straight
   line). Because the graph is sparse, travelling between two far-apart sites
   goes *through* intermediate junctions, so shortest-path search is
   meaningful rather than trivially "the direct edge".

2. **Shortest-path algorithms** named in the proposal — Dijkstra,
   Bellman-Ford and Floyd-Warshall. Any of them can be used to build the
   all-pairs distance matrix that drives planning; they always agree on the
   result, which the test-suite asserts.

3. **Planners**
   * ``plan_patrol_routes`` — the daily multi-vehicle planner (a capacitated,
     priority-aware multi-TSP): balanced cheapest-insertion assignment,
     priority tiers, 2-opt intra-route and relocate inter-route improvement.
   * ``reroute_after_emergency`` — the *dynamic* re-planner. When a vehicle is
     diverted to an emergency it continues from the emergency site instead of
     driving back to where it left its original route. Both options are
     costed so the saving in mileage (and therefore CO2e) can be reported.
"""

from __future__ import annotations

import heapq
import math
import time
from dataclasses import dataclass, field

INF = float("inf")

# Urban road distance / straight-line distance ("detour index"). Published
# values for city road networks sit between 1.2 and 1.4.
DEFAULT_CIRCUITY = 1.3
# Each site is connected to this many nearest neighbours (plus a minimum
# spanning tree so the network is always connected).
DEFAULT_NEIGHBOURS = 5
# Priority boost applied to sites with an active emergency so they are always
# in the first tier of a plan.
EMERGENCY_PRIORITY = 100


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
    return radius * 2 * math.asin(math.sqrt(min(1.0, a)))


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
        if a == b:
            return
        self.adjacency.setdefault(a, {})[b] = weight
        self.adjacency.setdefault(b, {})[a] = weight

    @property
    def edge_count(self) -> int:
        return sum(len(n) for n in self.adjacency.values()) // 2

    @classmethod
    def complete_from_nodes(
        cls, nodes: list[Node], circuity: float = 1.0
    ) -> "Graph":
        """Fully-connected graph (every site directly reachable)."""
        graph = cls()
        for node in nodes:
            graph.add_node(node)
        for i, a in enumerate(nodes):
            for b in nodes[i + 1 :]:
                graph.add_edge(a.id, b.id, _edge_km(a, b, circuity))
        return graph

    @classmethod
    def road_network(
        cls,
        nodes: list[Node],
        neighbours: int = DEFAULT_NEIGHBOURS,
        circuity: float = DEFAULT_CIRCUITY,
    ) -> "Graph":
        """Sparse road-network approximation: k-nearest neighbours + MST.

        The minimum spanning tree (Prim) guarantees connectivity; the k-NN
        edges add the redundancy a real street grid has.
        """
        graph = cls()
        for node in nodes:
            graph.add_node(node)
        if len(nodes) < 2:
            return graph

        # k-nearest-neighbour edges.
        for a in nodes:
            nearest = sorted(
                (b for b in nodes if b.id != a.id),
                key=lambda b: haversine_km(a.lat, a.lng, b.lat, b.lng),
            )[:neighbours]
            for b in nearest:
                graph.add_edge(a.id, b.id, _edge_km(a, b, circuity))

        # Prim's MST over the complete graph to guarantee connectivity.
        in_tree = {nodes[0].id}
        by_id = {n.id: n for n in nodes}
        heap = [
            (_edge_km(nodes[0], b, circuity), nodes[0].id, b.id) for b in nodes[1:]
        ]
        heapq.heapify(heap)
        while heap and len(in_tree) < len(nodes):
            w, a, b = heapq.heappop(heap)
            if b in in_tree:
                continue
            in_tree.add(b)
            graph.add_edge(a, b, w)
            for c in nodes:
                if c.id not in in_tree:
                    heapq.heappush(heap, (_edge_km(by_id[b], c, circuity), b, c.id))
        return graph


def _edge_km(a: Node, b: Node, circuity: float) -> float:
    return haversine_km(a.lat, a.lng, b.lat, b.lng) * circuity


# ---------------------------------------------------------------------------
# Shortest-path algorithms
# ---------------------------------------------------------------------------
def dijkstra(graph: Graph, source: int) -> tuple[dict[int, float], dict[int, int | None]]:
    """Dijkstra's algorithm with a binary heap — O((V + E) log V)."""
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
    """Bellman-Ford — O(V·E). Handles negative weights and detects cycles."""
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
        if dist[u] != INF and dist[u] + w < dist[v] - 1e-12:
            raise ValueError("Graph contains a negative-weight cycle")
    return dist, prev


def floyd_warshall(
    graph: Graph,
) -> tuple[dict[int, dict[int, float]], dict[int, dict[int, int | None]]]:
    """Floyd-Warshall all-pairs shortest paths — O(V³)."""
    nodes = list(graph.adjacency)
    dist = {u: {v: INF for v in nodes} for u in nodes}
    nxt: dict[int, dict[int, int | None]] = {
        u: {v: None for v in nodes} for u in nodes
    }

    for u in nodes:
        dist[u][u] = 0.0
        nxt[u][u] = u
        for v, w in graph.adjacency[u].items():
            dist[u][v] = w
            nxt[u][v] = v

    for k in nodes:
        dk = dist[k]
        for i in nodes:
            dik = dist[i][k]
            if dik == INF:
                continue
            di = dist[i]
            ni = nxt[i]
            for j in nodes:
                cand = dik + dk[j]
                if cand < di[j]:
                    di[j] = cand
                    ni[j] = ni[k]
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


ALGORITHMS = ("dijkstra", "bellman_ford", "floyd_warshall")
_SINGLE_SOURCE = {"dijkstra": dijkstra, "bellman_ford": bellman_ford}


def shortest_path(
    graph: Graph, source: int, target: int, algorithm: str = "dijkstra"
) -> dict:
    """Return the shortest path + distance between two nodes."""
    started = time.perf_counter()
    if algorithm == "floyd_warshall":
        dist, nxt = floyd_warshall(graph)
        path: list[int] = []
        if nxt[source][target] is not None:
            node = source
            path = [node]
            while node != target:
                node = nxt[node][target]
                path.append(node)
        distance = dist[source][target]
    else:
        solver = _SINGLE_SOURCE.get(algorithm, dijkstra)
        dist, prev = solver(graph, source)
        path = reconstruct_path(prev, source, target)
        distance = dist[target]
    return {
        "algorithm": algorithm,
        "distance_km": None if distance == INF else round(distance, 3),
        "path": path,
        "runtime_ms": round((time.perf_counter() - started) * 1000, 3),
    }


def distance_matrix(
    graph: Graph, algorithm: str = "dijkstra"
) -> dict[int, dict[int, float]]:
    """All-pairs shortest road distances using the chosen algorithm."""
    if algorithm == "floyd_warshall":
        return floyd_warshall(graph)[0]
    solver = _SINGLE_SOURCE.get(algorithm, dijkstra)
    return {source: solver(graph, source)[0] for source in graph.adjacency}


def compare_algorithms(graph: Graph, source: int, target: int) -> list[dict]:
    """Run all three algorithms on the same query (used by the dashboard)."""
    return [shortest_path(graph, source, target, name) for name in ALGORITHMS]


# ---------------------------------------------------------------------------
# Route cost helpers
# ---------------------------------------------------------------------------
Matrix = dict[int, dict[int, float]]


def path_length(order: list[int], matrix: Matrix, start: int | None = None) -> float:
    """Length of an open path that optionally begins at ``start``."""
    seq = ([start] if start is not None else []) + list(order)
    return sum(matrix[a][b] for a, b in zip(seq, seq[1:]))


def leg_distances(order: list[int], matrix: Matrix, start: int | None = None) -> list[float]:
    """Distance of the leg *into* each stop of ``order``."""
    legs = []
    prev = start
    for node in order:
        legs.append(0.0 if prev is None else matrix[prev][node])
        prev = node
    return legs


def nearest_neighbour(nodes: list[int], matrix: Matrix, start: int | None) -> list[int]:
    """Greedy open-path construction from ``start``."""
    remaining = list(nodes)
    if not remaining:
        return []
    if start is None:
        current = remaining.pop(0)
        order = [current]
    else:
        current, order = start, []
    while remaining:
        nxt = min(remaining, key=lambda n: matrix[current][n])
        remaining.remove(nxt)
        order.append(nxt)
        current = nxt
    return order


def two_opt(order: list[int], matrix: Matrix, start: int | None = None) -> list[int]:
    """2-opt local search for an open path (start fixed, end free)."""
    best = list(order)
    if len(best) < 3:
        return best
    improved = True
    while improved:
        improved = False
        base = path_length(best, matrix, start)
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                length = path_length(candidate, matrix, start)
                if length < base - 1e-9:
                    best, base, improved = candidate, length, True
    return best


def optimise_path(
    stops: list[int], matrix: Matrix, start: int | None, priority: dict[int, int] | None = None
) -> list[int]:
    """Order ``stops`` priority-tier by tier, each tier NN + 2-opt optimised.

    Higher-priority sites are always visited before lower-priority ones; within
    a tier the order minimises distance. The end of one tier is the start of
    the next, so tiers chain smoothly.
    """
    priority = priority or {}
    tiers: dict[int, list[int]] = {}
    for stop in stops:
        tiers.setdefault(priority.get(stop, 0), []).append(stop)

    order: list[int] = []
    cursor = start
    for level in sorted(tiers, reverse=True):
        segment = two_opt(nearest_neighbour(tiers[level], matrix, cursor), matrix, cursor)
        order.extend(segment)
        if segment:
            cursor = segment[-1]
    return order


# ---------------------------------------------------------------------------
# Daily multi-vehicle planner
# ---------------------------------------------------------------------------
@dataclass
class PlannedRoute:
    vehicle_index: int
    start_id: int | None
    stop_order: list[int]
    total_distance_km: float
    legs_km: list[float] = field(default_factory=list)


def plan_patrol_routes(
    nodes: list[Node],
    num_vehicles: int,
    depot_id: int | None = None,
    start_ids: list[int | None] | None = None,
    algorithm: str = "dijkstra",
    graph: Graph | None = None,
    priority_tiers: bool = True,
) -> list[PlannedRoute]:
    """Assign every site to a vehicle and order each vehicle's stops.

    Mirrors the proposal signature
    ``shortestRoute(location_list, priority_location, num_car) -> List``.

    * ``nodes``      – sites to cover (priority on each node).
    * ``depot_id``   – optional shared start site (e.g. the command centre).
    * ``start_ids``  – optional per-vehicle start node ids (e.g. a virtual node
      at each vehicle's live position); overrides ``depot_id``.
    * ``algorithm``  – which shortest-path algorithm builds the road distances.

    Strategy:
      1. Build the road network and all-pairs distance matrix.
      2. Seed each vehicle with the highest-priority unassigned site.
      3. Cheapest-insertion of the remaining sites with a balance cap
         (ceil(n / vehicles) + 1 stops) so work is shared fairly.
      4. Re-order each route tier-by-tier (NN + 2-opt).
      5. Inter-route *relocate* moves while they reduce total distance.
    """
    if num_vehicles < 1:
        raise ValueError("num_vehicles must be >= 1")

    graph = graph or Graph.road_network(nodes)
    matrix = distance_matrix(graph, algorithm)
    node_by_id = {n.id: n for n in graph.nodes.values()}

    if start_ids is None:
        start_ids = [depot_id if depot_id in node_by_id else None] * num_vehicles
    start_set = {s for s in start_ids if s is not None}
    priority = {n.id: n.priority for n in nodes} if priority_tiers else {}

    candidates = sorted(
        [n.id for n in nodes if n.id not in start_set],
        key=lambda nid: (-node_by_id[nid].priority, node_by_id[nid].name, nid),
    )
    if not candidates:
        return [
            PlannedRoute(i, start_ids[i], [], 0.0, []) for i in range(num_vehicles)
        ]

    cap = math.ceil(len(candidates) / num_vehicles) + 1
    routes: list[list[int]] = [[] for _ in range(num_vehicles)]

    def route_cost(i: int, order: list[int]) -> float:
        return path_length(order, matrix, start_ids[i])

    # 2. Seed: spread the top-priority sites, nearest start first.
    seeds = candidates[:num_vehicles]
    free = set(range(num_vehicles))
    for site in seeds:
        best = min(
            free,
            key=lambda i: matrix[start_ids[i]][site] if start_ids[i] is not None else 0.0,
        )
        routes[best].append(site)
        free.discard(best)

    # 3. Cheapest insertion with balance cap.
    for site in candidates[num_vehicles:]:
        best_i, best_pos, best_delta = None, None, INF
        for i, order in enumerate(routes):
            if len(order) >= cap:
                continue
            base = route_cost(i, order)
            for pos in range(len(order) + 1):
                delta = route_cost(i, order[:pos] + [site] + order[pos:]) - base
                if delta < best_delta:
                    best_i, best_pos, best_delta = i, pos, delta
        routes[best_i].insert(best_pos, site)

    # 4. Intra-route optimisation respecting priority tiers.
    routes = [optimise_path(r, matrix, start_ids[i], priority) for i, r in enumerate(routes)]

    # 5. Inter-route relocate: move a site to another vehicle when the km
    # saved by removing it exceeds the km added by its cheapest insertion.
    for _ in range(100):
        moved = False
        for a in range(num_vehicles):
            for site in list(routes[a]):
                if len(routes[a]) <= 1:
                    break
                without = [s for s in routes[a] if s != site]
                gain = route_cost(a, routes[a]) - route_cost(a, without)
                for b in range(num_vehicles):
                    if b == a or len(routes[b]) >= cap:
                        continue
                    pos, added = cheapest_insertion(routes[b], site, matrix, start_ids[b])
                    if added < gain - 1e-6:
                        routes[a] = without
                        routes[b].insert(pos, site)
                        moved = True
                        break
        if not moved:
            break
    routes = [optimise_path(r, matrix, start_ids[i], priority) for i, r in enumerate(routes)]

    return [
        PlannedRoute(
            vehicle_index=i,
            start_id=start_ids[i],
            stop_order=order,
            total_distance_km=round(route_cost(i, order), 3),
            legs_km=[round(x, 3) for x in leg_distances(order, matrix, start_ids[i])],
        )
        for i, order in enumerate(routes)
    ]


def baseline_routes(
    nodes: list[Node],
    num_vehicles: int,
    start_ids: list[int | None] | None = None,
    algorithm: str = "dijkstra",
    graph: Graph | None = None,
) -> list[PlannedRoute]:
    """The *manual* baseline the command centre uses today.

    Sites are handed out round-robin in list order (priority, then name) and
    visited in that order, with no distance optimisation. The difference
    between this and ``plan_patrol_routes`` is the mileage — and so the CO2e —
    that automated planning saves.
    """
    graph = graph or Graph.road_network(nodes)
    matrix = distance_matrix(graph, algorithm)
    start_ids = start_ids or [None] * num_vehicles
    start_set = {s for s in start_ids if s is not None}
    ordered = sorted(
        [n for n in nodes if n.id not in start_set], key=lambda n: (-n.priority, n.name, n.id)
    )
    routes: list[list[int]] = [[] for _ in range(num_vehicles)]
    for idx, node in enumerate(ordered):
        routes[idx % num_vehicles].append(node.id)
    return [
        PlannedRoute(
            vehicle_index=i,
            start_id=start_ids[i],
            stop_order=order,
            total_distance_km=round(path_length(order, matrix, start_ids[i]), 3),
            legs_km=[round(x, 3) for x in leg_distances(order, matrix, start_ids[i])],
        )
        for i, order in enumerate(routes)
    ]


# ---------------------------------------------------------------------------
# Dynamic re-routing after an emergency
# ---------------------------------------------------------------------------
@dataclass
class RerouteResult:
    new_order: list[int]
    new_legs_km: list[float]
    rerouted_km: float
    baseline_order: list[int]
    baseline_km: float

    @property
    def saved_km(self) -> float:
        return round(max(0.0, self.baseline_km - self.rerouted_km), 3)

    def as_dict(self) -> dict:
        return {
            "new_order": self.new_order,
            "new_legs_km": self.new_legs_km,
            "rerouted_km": self.rerouted_km,
            "baseline_order": self.baseline_order,
            "baseline_km": self.baseline_km,
            "saved_km": self.saved_km,
        }


def reroute_after_emergency(
    graph: Graph,
    current_id: int,
    emergency_id: int,
    remaining_ids: list[int],
    resume_id: int | None = None,
    algorithm: str = "dijkstra",
    priority: dict[int, int] | None = None,
) -> RerouteResult:
    """Re-plan a vehicle's route after it is diverted to an emergency.

    * ``current_id``    – node for the vehicle's current position.
    * ``emergency_id``  – node of the site raising the alert.
    * ``remaining_ids`` – unvisited stops, in the original planned order.
    * ``resume_id``     – the site the vehicle had last reached before the
      diversion. Today's manual practice is to drive back there and carry on
      from what is left of the original route; that is the *baseline*.

    The dynamic plan instead continues from the emergency site and re-optimises
    the remaining stops (priority tiers + 2-opt), never driving back.
    """
    matrix = distance_matrix(graph, algorithm)
    remaining = [s for s in remaining_ids if s not in (emergency_id, current_id)]

    # Baseline: current -> emergency -> back to resume point -> original order.
    baseline_order = [emergency_id]
    if resume_id is not None and resume_id not in (emergency_id, current_id):
        baseline_order.append(resume_id)
    baseline_order += [s for s in remaining if s != resume_id]
    baseline_km = path_length(baseline_order, matrix, current_id)

    # Dynamic: current -> emergency -> optimised remaining stops.
    tail = optimise_path(remaining, matrix, emergency_id, priority)
    new_order = [emergency_id] + tail
    rerouted_km = path_length(new_order, matrix, current_id)

    return RerouteResult(
        new_order=new_order,
        new_legs_km=[round(x, 3) for x in leg_distances(new_order, matrix, current_id)],
        rerouted_km=round(rerouted_km, 3),
        baseline_order=baseline_order,
        baseline_km=round(baseline_km, 3),
    )


def cheapest_insertion(
    order: list[int], site: int, matrix: Matrix, start: int | None
) -> tuple[int, float]:
    """Best position (and added km) to insert ``site`` into an open path."""
    base = path_length(order, matrix, start)
    best_pos, best_delta = len(order), INF
    for pos in range(len(order) + 1):
        delta = path_length(order[:pos] + [site] + order[pos:], matrix, start) - base
        if delta < best_delta:
            best_pos, best_delta = pos, delta
    return best_pos, best_delta
