"""Distance providers: where the planner's kilometres come from.

The planner only needs a symmetric site-to-site distance matrix (km). Two
providers produce one:

* ``RoadNetworkProvider`` (default) — the offline approximate road network in
  ``routing.py`` (k-nearest sites + MST, haversine × circuity), solved with
  Dijkstra, Bellman-Ford or Floyd-Warshall. No external service, deterministic.
* ``OSRMProvider`` — real driving distances on OpenStreetMap roads from an
  OSRM server's ``table`` service. Directional distances are averaged into a
  symmetric matrix (the planner's O(1) move costs assume symmetry).

Providers raise ``ProviderUnavailable`` when they cannot answer;
``matrix_with_fallback`` then uses the road-network model so planning never
stops. Select a provider with the ``ROUTING_PROVIDER`` setting.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Protocol

from . import routing
from .routing import Matrix, Node

logger = logging.getLogger(__name__)


class ProviderUnavailable(RuntimeError):
    """The provider could not produce a matrix (network error, bad reply)."""


class DistanceProvider(Protocol):
    name: str

    def matrix(self, nodes: list[Node], algorithm: str = "dijkstra") -> Matrix:
        """Symmetric all-pairs distances in km between ``nodes``."""


class RoadNetworkProvider:
    name = "road_network"

    def __init__(
        self,
        neighbours: int = routing.DEFAULT_NEIGHBOURS,
        circuity: float = routing.DEFAULT_CIRCUITY,
    ):
        self.neighbours = neighbours
        self.circuity = circuity

    def graph(self, nodes: list[Node]) -> routing.Graph:
        return routing.Graph.road_network(nodes, self.neighbours, self.circuity)

    def matrix(self, nodes: list[Node], algorithm: str = "dijkstra") -> Matrix:
        return routing.distance_matrix(self.graph(nodes), algorithm)


class OSRMProvider:
    """Driving distances from an OSRM ``table`` endpoint.

    The public demo server (router.project-osrm.org) is fine for experiments
    but has a fair-use policy; run your own OSRM container for production.
    """

    name = "osrm"

    def __init__(
        self,
        base_url: str = "https://router.project-osrm.org",
        timeout: float = 20.0,
        max_coordinates: int = 100,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_coordinates = max(2, max_coordinates)

    def matrix(self, nodes: list[Node], algorithm: str = "dijkstra") -> Matrix:
        """``algorithm`` is ignored: OSRM runs its own road-graph search."""
        try:
            return self.fetch(nodes)
        except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderUnavailable(str(exc)) from exc

    def fetch(self, nodes: list[Node]) -> Matrix:
        """Query OSRM in blocks of at most ``max_coordinates`` points."""
        n = len(nodes)
        metres = [[0.0] * n for _ in range(n)]
        block = max(1, self.max_coordinates // 2)
        for s0 in range(0, n, block):
            for d0 in range(0, n, block):
                src = list(range(s0, min(n, s0 + block)))
                dst = list(range(d0, min(n, d0 + block)))
                self._fill(nodes, src, dst, metres)

        out: Matrix = {a.id: {} for a in nodes}
        for i, a in enumerate(nodes):
            for j, b in enumerate(nodes):
                if i == j:
                    out[a.id][b.id] = 0.0
                    continue
                there, back = metres[i][j], metres[j][i]
                if there is None or back is None:  # unroutable pair: model distance
                    km = routing.haversine_km(a.lat, a.lng, b.lat, b.lng) * routing.DEFAULT_CIRCUITY
                else:
                    km = (there + back) / 2000.0
                out[a.id][b.id] = km
        return out

    def _fill(self, nodes, src, dst, metres) -> None:
        points = sorted(set(src) | set(dst))
        position = {idx: k for k, idx in enumerate(points)}
        coords = ";".join(f"{nodes[i].lng:.6f},{nodes[i].lat:.6f}" for i in points)
        query = urllib.parse.urlencode(
            {
                "annotations": "distance",
                "sources": ";".join(str(position[i]) for i in src),
                "destinations": ";".join(str(position[j]) for j in dst),
            }
        )
        url = f"{self.base_url}/table/v1/driving/{coords}?{query}"
        with urllib.request.urlopen(url, timeout=self.timeout) as response:  # noqa: S310 - fixed scheme from settings
            payload = json.load(response)
        if payload.get("code") != "Ok":
            raise ValueError(f"OSRM error: {payload.get('code')} {payload.get('message', '')}")
        for r, i in enumerate(src):
            for c, j in enumerate(dst):
                metres[i][j] = payload["distances"][r][c]


def make_provider(
    name: str,
    *,
    neighbours: int = routing.DEFAULT_NEIGHBOURS,
    circuity: float = routing.DEFAULT_CIRCUITY,
    osrm_url: str = "https://router.project-osrm.org",
    timeout: float = 20.0,
) -> DistanceProvider:
    if name == "osrm":
        return OSRMProvider(base_url=osrm_url, timeout=timeout)
    if name == "road_network":
        return RoadNetworkProvider(neighbours, circuity)
    raise ValueError(f"Unknown routing provider '{name}'.")


def matrix_with_fallback(
    provider: DistanceProvider,
    nodes: list[Node],
    algorithm: str = "dijkstra",
    fallback: DistanceProvider | None = None,
) -> tuple[Matrix, str]:
    """The provider's matrix, or the road-network model's if it is unavailable.

    Returns the matrix and the name of the provider that actually produced it.
    """
    try:
        return provider.matrix(nodes, algorithm), provider.name
    except ProviderUnavailable as exc:
        backup = fallback or RoadNetworkProvider()
        logger.warning("%s unavailable (%s); using %s.", provider.name, exc, backup.name)
        return backup.matrix(nodes, algorithm), backup.name
