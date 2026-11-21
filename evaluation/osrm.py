"""Real driving distances for the evaluation, cached so runs are repeatable.

``--refresh-osrm`` queries the public OSRM demo server (a few requests per
instance) and writes the sites and matrix to ``evaluation/data``; later runs,
and CI, read the committed files and need no network.

Sites are first snapped to the nearest road (OSRM routes from there anyway),
and the snapped coordinates are what is stored and compared, so a point that
fell in a park or the sea does not distort the comparison.
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

from core.services.distance import OSRMProvider
from core.services.routing import Matrix, Node

DATA = Path(__file__).parent / "data"
SERVER = "https://router.project-osrm.org"


def snap_to_roads(nodes: list[Node]) -> list[Node]:
    coords = ";".join(f"{n.lng:.6f},{n.lat:.6f}" for n in nodes)
    url = f"{SERVER}/table/v1/driving/{coords}?sources=0&annotations=distance"
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed host
        waypoints = json.load(response)["destinations"]
    return [
        Node(n.id, n.name, w["location"][1], w["location"][0], n.priority)
        for n, w in zip(nodes, waypoints)
    ]


def load_or_fetch(name: str, nodes: list[Node], refresh: bool = False) -> tuple[list[Node], Matrix] | None:
    path = DATA / f"osrm_{name}.json"
    if refresh:
        snapped = snap_to_roads(nodes)
        matrix = OSRMProvider(base_url=SERVER).fetch(snapped)
        DATA.mkdir(exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "source": f"{SERVER} table service (driving); km, averaged over both directions; "
                    "sites snapped to the nearest road",
                    "sites": [
                        {"id": n.id, "name": n.name, "lat": n.lat, "lng": n.lng, "priority": n.priority}
                        for n in snapped
                    ],
                    "matrix": {a: {b: round(d, 4) for b, d in row.items()} for a, row in matrix.items()},
                },
                indent=1,
            )
        )
    if not path.exists():
        return None
    raw = json.loads(path.read_text())
    sites = [Node(s["id"], s["name"], s["lat"], s["lng"], s["priority"]) for s in raw["sites"]]
    matrix = {int(a): {int(b): d for b, d in row.items()} for a, row in raw["matrix"].items()}
    return sites, matrix
