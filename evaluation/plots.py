"""Charts for the evaluation report (PNG, light surface so they read on
GitHub in both themes). One accent (blue) marks this system; comparison
series are grey; reference lines and labels are quiet."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e1"
ACCENT = "#2a78d6"  # categorical slot 1 (blue)
SECOND = "#eb6834"  # slot 2 (orange)
THIRD = "#1baf7a"  # slot 3 (aqua)
GREY_DARK = "#8d8c86"
GREY_LIGHT = "#c4c3bd"


def _style(ax, title: str, subtitle: str | None = None):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    lines = subtitle.count("\n") + 1 if subtitle else 0
    ax.set_title(title, loc="left", fontsize=12, color=INK, fontweight="bold", pad=10 + 14 * lines)
    if subtitle:
        ax.text(0, 1.02, subtitle, transform=ax.transAxes, fontsize=9, color=INK_2, va="bottom", linespacing=1.4)


def _figure(width=8.0, height=4.2):
    fig, ax = plt.subplots(figsize=(width, height), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def _save(fig, path: Path, source: str):
    fig.text(0.01, 0.01, source, fontsize=7.5, color=INK_2)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def planning_gap(summary: list[dict], path: Path):
    """Grouped bars: % longer than the OR-Tools reference, per method and size."""
    sizes = sorted({r["sites"] for r in summary})
    methods = [("Greedy nearest", GREY_LIGHT), ("Sweep", GREY_DARK), ("This system", ACCENT)]
    width = 0.26
    fig, ax = _figure()
    for m, (name, colour) in enumerate(methods):
        values = [next(r["gap_to_ortools_pct"] for r in summary if r["sites"] == n and r["method"] == name) for n in sizes]
        xs = [i + (m - 1) * width for i in range(len(sizes))]
        ax.bar(xs, values, width * 0.92, color=colour, label=name, zorder=2)
        if name == "This system":
            for x, v in zip(xs, values):
                ax.text(x, v + 0.8, f"{v:.1f}%", ha="center", va="bottom", fontsize=8.5, color=INK, fontweight="bold")
    vehicles = {r["sites"]: r["vehicles"] for r in summary}
    ax.set_xticks(range(len(sizes)), [f"{n} sites\n{vehicles[n]} vehicles" for n in sizes])
    ax.set_ylabel("km above OR-Tools (%)", color=INK_2, fontsize=9)
    ax.set_ylim(0, ax.get_ylim()[1] * 1.18)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper center", ncol=3)
    manual = [r for r in summary if r["method"].startswith("Manual")]
    lo, hi = min(r["gap_to_ortools_pct"] for r in manual), max(r["gap_to_ortools_pct"] for r in manual)
    _style(
        ax,
        "This system stays within a few percent of OR-Tools",
        f"Mean distance above the OR-Tools reference (5–30 s of search per instance).\n"
        f"The manual round-robin baseline is off the scale (+{lo:.0f}% to +{hi:.0f}%).",
    )
    _save(fig, path, "Random sites on Singapore's main island; approximate road-network distances.")


def scalability(rows: list[dict], time_limit: float, path: Path):
    fig, ax = _figure()
    series = [("5 vehicles", ACCENT), ("~10 sites per vehicle", SECOND)]
    for label, colour in series:
        pts = sorted((r["sites"], r["seconds"]) for r in rows if r["fleet"] == label)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=colour, linewidth=2, marker="o", markersize=5, label=label, zorder=3)
    ax.axhline(time_limit, color=GREY_DARK, linewidth=1, zorder=1)
    ax.text(min(r["sites"] for r in rows), time_limit * 1.25, f"{time_limit:.0f} s search budget: local search stops here",
            fontsize=8.5, color=INK_2, va="bottom")
    ax.set_yscale("log")
    ax.set_ylim(top=time_limit * 4)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g} s"))
    ax.set_xlabel("sites", color=INK_2, fontsize=9)
    ax.set_ylabel("planning time (log scale)", color=INK_2, fontsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="lower right")
    under = max((r["sites"] for r in rows if r["seconds"] < 1), default=0)
    _style(
        ax,
        f"Plans take under a second up to {under} sites",
        "Wall-clock time of one plan, single CPU core, pure Python.",
    )
    _save(fig, path, "Random sites on Singapore's main island.")


def reroute_savings(rows: list[dict], scenario: str, path: Path):
    saved = sorted(r["saved_km"] for r in rows if r["scenario"] == scenario)
    median = saved[len(saved) // 2]
    fig, ax = _figure(height=3.8)
    ax.hist(saved, bins=30, color=ACCENT, edgecolor=SURFACE, linewidth=0.8, zorder=2)
    ax.axvline(median, color=INK, linewidth=1, zorder=3)
    ax.text(median, ax.get_ylim()[1] * 0.95, f"  median {median:.1f} km", fontsize=9, color=INK, va="top")
    ax.set_xlabel("km saved by re-routing instead of driving back", color=INK_2, fontsize=9)
    ax.set_ylabel("simulated emergencies", color=INK_2, fontsize=9)
    _style(
        ax,
        f"Re-routing saves a median {median:.1f} km per emergency",
        f"{len(saved)} simulated alarms on the demo night, costed on real driving distances.",
    )
    _save(fig, path, "Real distances: OSRM (router.project-osrm.org), demo sites snapped to roads.")


def calibration(accuracy: list[dict], path: Path):
    fig, ax = _figure(width=6.0, height=5.4)
    colours = {"random_100": GREY_DARK, "demo_20": ACCENT}
    labels = {"random_100": "100 random sites", "demo_20": "20 demo sites"}
    top = 0
    for acc in sorted(accuracy, key=lambda a: a["instance"] != "random_100"):
        xs = [p["real"] for p in acc["points"]]
        ys = [p["model"] for p in acc["points"]]
        top = max(top, max(xs), max(ys))
        ax.scatter(xs, ys, s=6 if acc["instance"] == "random_100" else 14, color=colours[acc["instance"]],
                   alpha=0.35 if acc["instance"] == "random_100" else 0.9, linewidths=0,
                   label=f"{labels[acc['instance']]}: mean error {acc['mape_road_model_pct']:.0f}%", zorder=2)
    ax.plot([0, top], [0, top], color=INK, linewidth=1, zorder=3)
    ax.text(top * 0.72, top * 0.66, "model = real", fontsize=8.5, color=INK_2, rotation=40)
    ax.set_xlim(0, top * 1.02)
    ax.set_ylim(0, top * 1.02)
    ax.set_xlabel("real driving distance (km)", color=INK_2, fontsize=9)
    ax.set_ylabel("road-network model (km)", color=INK_2, fontsize=9)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc="upper left", markerscale=2)
    r_lo = min(a["correlation_road_model"] for a in accuracy)
    r_hi = max(a["correlation_road_model"] for a in accuracy)
    _style(
        ax,
        f"The road model follows real driving distances (r = {r_lo:.2f}–{r_hi:.2f})",
        "Every pair of sites; the line marks perfect agreement.",
    )
    _save(fig, path, "Real distances: OSRM table service; sites snapped to roads.")


def algorithm_runtimes(rows: list[dict], path: Path):
    fig, ax = _figure()
    names = {"dijkstra": ("Dijkstra", ACCENT), "bellman_ford": ("Bellman-Ford", SECOND), "floyd_warshall": ("Floyd-Warshall", THIRD)}
    for key, (label, colour) in names.items():
        pts = sorted((r["sites"], r["seconds"]) for r in rows if r["algorithm"] == key)
        ax.plot([p[0] for p in pts], [max(p[1], 1e-4) for p in pts], color=colour, linewidth=2, marker="o", markersize=5, label=label)
        ax.text(pts[-1][0] + 4, pts[-1][1], f"{label} {pts[-1][1]:.2f} s", va="center", fontsize=8.5, color=INK)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g} s"))
    ax.set_xlim(right=max(r["sites"] for r in rows) * 1.32)
    ax.set_xlabel("sites (graph nodes)", color=INK_2, fontsize=9)
    ax.set_ylabel("all-pairs matrix time (log scale)", color=INK_2, fontsize=9)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK_2, loc="upper left")
    _style(ax, "Dijkstra builds the distance matrix fastest", "All three algorithms return identical distances; only the run time differs.")
    _save(fig, path, "Approximate road network (5 nearest neighbours + MST); pure Python.")
