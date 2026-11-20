"""Test instances: the demo sites and random sites on Singapore's main island."""

from __future__ import annotations

import random

from core.services.routing import Node

# Rough land rectangles (lat_min, lat_max, lng_min, lng_max) covering the main
# island, so random sites do not land in the sea.
LAND_BOXES = [
    (1.30, 1.36, 103.64, 103.76),  # Jurong / Tuas
    (1.28, 1.38, 103.76, 103.88),  # central
    (1.38, 1.45, 103.74, 103.86),  # north: Woodlands, Yishun
    (1.34, 1.41, 103.86, 103.92),  # north-east: Hougang, Sengkang, Punggol
    (1.31, 1.37, 103.88, 103.98),  # east: Tampines, Bedok, Changi
]


def demo_sites() -> list[Node]:
    """The 20 sites seeded by `manage.py seed_demo`, with their priorities."""
    from core.management.commands.seed_demo import LOCATIONS

    return [Node(i + 1, name, lat, lng, priority) for i, (name, lat, lng, priority) in enumerate(LOCATIONS)]


def random_sites(n: int, seed: int) -> list[Node]:
    """``n`` sites spread over the island in proportion to each box's area."""
    rnd = random.Random(seed)
    weights = [(b[1] - b[0]) * (b[3] - b[2]) for b in LAND_BOXES]
    nodes = []
    for i in range(1, n + 1):
        lat0, lat1, lng0, lng1 = rnd.choices(LAND_BOXES, weights)[0]
        nodes.append(Node(i, f"S{i}", rnd.uniform(lat0, lat1), rnd.uniform(lng0, lng1), 1))
    return nodes


def fleet_size(n: int) -> int:
    """About ten sites per vehicle (the client runs ~50 sites with 5 vehicles)."""
    return max(3, round(n / 10))
