"""Run the evaluation and write results, charts and a summary to docs/evaluation.

    pip install -r requirements-dev.txt
    python -m evaluation.run                 # full run (about 8 minutes)
    python -m evaluation.run --quick         # smaller samples, for a smoke test
    python -m evaluation.run --refresh-osrm  # re-download real road distances

Real road distances are read from evaluation/data (committed), so no network
is needed unless --refresh-osrm is given.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from datetime import date
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "docs" / "evaluation"
TIME_LIMIT = 5.0  # plan_patrol_routes' default search budget


def _setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dynamic_patrol_system.settings")
    os.environ.setdefault("USE_SQLITE", "True")
    import django

    django.setup()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--skip-ortools", action="store_true")
    parser.add_argument("--refresh-osrm", action="store_true")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT, help="output folder (default docs/evaluation)")
    args = parser.parse_args(argv)
    out = args.out
    _setup_django()

    from . import experiments as e
    from . import instances

    if args.quick:
        sizes, limits = {20: 2, 50: 2}, {20: 2, 50: 3}
        trials, runtime_sizes, scale_sizes = 100, [10, 25, 50], [50, 100, 200]
    else:
        sizes, limits = {20: 10, 50: 10, 100: 5, 200: 3}, {20: 5, 50: 10, 100: 20, 200: 30}
        trials, runtime_sizes, scale_sizes = 1000, [10, 25, 50, 100, 200], [50, 100, 200, 300, 500]

    print("E1 planning quality")
    quality_rows = e.planning_quality(sizes, None if args.skip_ortools else limits)
    print("E5 road-model accuracy (real roads)")
    real = e.osrm_instances(args.refresh_osrm)
    accuracy = [e.road_model_accuracy(name, nodes, matrix) for name, (nodes, matrix) in real.items()]
    demo_real = e.demo_night_on_real_roads(*real["demo_20"]) if "demo_20" in real else None

    print("E2 re-routing simulation")
    demo = instances.demo_sites()
    reroutes = e.simulate_reroutes(demo, 4, e._model_matrix(demo), trials, 1, "demo night, road model")
    if "demo_20" in real:
        nodes, matrix = real["demo_20"]
        reroutes += e.simulate_reroutes(nodes, 4, matrix, trials, 2, "demo night, real roads")
    for seed in range(5 if not args.quick else 1):
        nodes = instances.random_sites(50, seed=500 + seed)
        reroutes += e.simulate_reroutes(nodes, 5, e._model_matrix(nodes), trials // 5, seed, "50 random sites, road model")

    print("E3 shortest-path algorithms")
    runtimes = e.algorithm_runtimes(runtime_sizes)
    print("E4 scalability")
    scale = e.scalability(scale_sizes)

    results = {
        "generated": date.today().isoformat(),
        "python": platform.python_version(),
        "quick": args.quick,
        "planning_quality": {"summary": e.summarise_quality(quality_rows), "rows": quality_rows},
        "reroute": {"summary": e.summarise_reroutes(reroutes)},
        "algorithm_runtimes": runtimes,
        "scalability": scale,
        "road_model_accuracy": [{k: v for k, v in a.items() if k != "points"} for a in accuracy],
        "demo_night_real_roads": demo_real,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=1))

    if not args.no_plots:
        from . import plots

        if not args.skip_ortools:
            plots.planning_gap(results["planning_quality"]["summary"], out / "planning_quality.png")
        plots.scalability(scale, TIME_LIMIT, out / "scalability.png")
        plots.algorithm_runtimes(runtimes, out / "algorithm_runtimes.png")
        scenario = "demo night, real roads" if "demo_20" in real else "demo night, road model"
        plots.reroute_savings(reroutes, scenario, out / "reroute_savings.png")
        if accuracy:
            plots.calibration(accuracy, out / "road_model_accuracy.png")

    (out / "README.md").write_text(render_markdown(results))
    print(f"Wrote {out}")
    return 0


def _table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    head = "| " + " | ".join(title for _, title in columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(r[key]) for key, _ in columns) + " |" for r in rows]
    return "\n".join([head, rule, *body])


def render_markdown(results: dict) -> str:
    q = results["planning_quality"]["summary"]
    has_reference = bool(q) and "gap_to_ortools_pct" in q[0]
    quality_columns = [("sites", "Sites"), ("vehicles", "Vehicles"), ("method", "Method"), ("instances", "Instances"),
                       ("mean_km", "Mean km")]
    if has_reference:
        quality_columns += [("gap_to_ortools_pct", "vs OR-Tools (%)"), ("beats_ortools", "Instances shorter than OR-Tools")]
    else:
        quality_columns += [("gap_to_best_pct", "Gap to best (%)")]
    quality_columns += [("mean_seconds", "Mean time (s)")]
    lines = [
        "# Evaluation results",
        "",
        f"Generated by `python -m evaluation.run` on {results['generated']} (Python {results['python']})."
        + (" Quick run: small samples." if results["quick"] else ""),
        "Methodology and discussion: [`docs/PROJECT_REPORT.md`](../PROJECT_REPORT.md#testing-and-evaluation).",
        "",
        "## E1 Planning quality",
        "",
        "Total km per night, mean over random instances, and the mean gap to the OR-Tools reference on the same"
        " instance (negative = shorter than OR-Tools). Every method covers every site with the same balance cap."
        " OR-Tools ran guided local search for 5, 10, 20 and 30 s at 20, 50, 100 and 200 sites.",
        "",
        "![Planning quality](planning_quality.png)" if has_reference else "",
        "",
        _table(q, quality_columns),
        "",
        "## E2 Dynamic re-routing",
        "",
        "Random alarms during a planned night: drive back to the last visited site and resume (old practice) versus"
        " continue from the emergency site with the rest of the route re-optimised.",
        "",
        "![Re-routing savings](reroute_savings.png)",
        "",
        _table(results["reroute"]["summary"], [("scenario", "Scenario"), ("trials", "Trials"),
               ("mean_saved_km", "Mean saved (km)"), ("median_saved_km", "Median (km)"), ("p90_saved_km", "90th pct (km)"),
               ("share_with_saving_pct", "Alarms with a saving (%)"), ("mean_saving_pct_of_remaining", "Saving vs drive-back (%)")]),
        "",
        "## E3 Shortest-path algorithms",
        "",
        "![Algorithm run times](algorithm_runtimes.png)",
        "",
        _table(results["algorithm_runtimes"], [("sites", "Sites"), ("algorithm", "Algorithm"), ("seconds", "All-pairs time (s)"),
               ("agrees", "Same distances as Dijkstra")]),
        "",
        "## E4 Scalability",
        "",
        "![Scalability](scalability.png)",
        "",
        _table(results["scalability"], [("sites", "Sites"), ("vehicles", "Vehicles"), ("seconds", "Planning time (s)"), ("km", "Total km")]),
        "",
    ]
    if results["road_model_accuracy"]:
        lines += [
            "## E5 Road model against real roads",
            "",
            "Every pair of sites, real driving distances from OSRM. Error = mean absolute percentage error.",
            "",
            "![Road model accuracy](road_model_accuracy.png)",
            "",
            _table(results["road_model_accuracy"], [("instance", "Instance"), ("pairs", "Pairs"),
                   ("real_over_straight_median", "Real ÷ straight line (median)"),
                   ("mape_straight_line_pct", "Straight line error (%)"),
                   ("mape_straight_x_circuity_pct", "Straight × 1.3 error (%)"),
                   ("mape_road_model_pct", "Road model error (%)"),
                   ("correlation_road_model", "Road model correlation")]),
            "",
        ]
    if results["demo_night_real_roads"]:
        d = results["demo_night_real_roads"]
        saving = 100 * (1 - d["planned_on_model_km_real"] / d["manual_km_real"])
        lines += [
            "### The demo night costed on real roads",
            "",
            "| Plan | Model km | Real-road km |",
            "| --- | --- | --- |",
            f"| Manual round-robin | {d['manual_km_model']} | {d['manual_km_real']} |",
            f"| This system, planned on the model | {d['planned_on_model_km_model']} | {d['planned_on_model_km_real']} |",
            f"| This system, planned on real distances | – | {d['planned_on_real_km_real']} |",
            "",
            f"On real roads, the plan made on the model is {saving:.0f}% shorter than the manual baseline.",
            "",
        ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
