"""Carbon-footprint estimation for patrol vehicles.

Per the requirements, the two factors that drive emissions are **mileage** and
**engine type**.

The petrol factor is derived from the figure quoted in the proposal — about
8,887 g CO2 per US gallon of gasoline (2.35 kg/L) — and a typical patrol car
consumption of ~8.2 L/100 km, giving ~0.192 kg CO2e/km (consistent with the
US EPA "typical passenger vehicle"). The other engine types use published
fleet averages. Factors are centralised here so they are easy to tune.
"""

from __future__ import annotations

KG_CO2_PER_LITRE_PETROL = 8.887 / 3.785  # 8,887 g per US gallon

# kg CO2-equivalent emitted per kilometre travelled, by engine type.
EMISSION_FACTORS_KG_PER_KM = {
    "petrol": 0.192,
    "diesel": 0.171,
    "hybrid": 0.106,
    "electric": 0.050,  # grid-average upstream emissions, not zero
}

DEFAULT_ENGINE = "petrol"


def factor_for_engine(engine_type: str) -> float:
    return EMISSION_FACTORS_KG_PER_KM.get(
        (engine_type or "").lower(), EMISSION_FACTORS_KG_PER_KM[DEFAULT_ENGINE]
    )


def estimate_emission_kg(distance_km: float, engine_type: str) -> float:
    """Estimate CO2e (kg) for a trip of ``distance_km`` on a given engine type."""
    if distance_km is None or distance_km <= 0:
        return 0.0
    return round(distance_km * factor_for_engine(engine_type), 4)


def savings(baseline_km: float, optimised_km: float, engine_type: str) -> dict:
    """Mileage and CO2e saved by an optimised route versus a baseline."""
    saved_km = max(0.0, (baseline_km or 0.0) - (optimised_km or 0.0))
    return {
        "baseline_km": round(baseline_km or 0.0, 3),
        "optimised_km": round(optimised_km or 0.0, 3),
        "saved_km": round(saved_km, 3),
        "baseline_kg": estimate_emission_kg(baseline_km, engine_type),
        "optimised_kg": estimate_emission_kg(optimised_km, engine_type),
        "saved_kg": estimate_emission_kg(saved_km, engine_type),
        "saved_percent": round(100 * saved_km / baseline_km, 1) if baseline_km else 0.0,
    }


# Best-traffic model used for the "shortest distance vs best traffic"
# comparison in the requirements: a route that avoids congestion is typically
# ~12% longer, but smoother driving cuts the effective emission factor ~6%.
BEST_TRAFFIC_DISTANCE_FACTOR = 1.12
BEST_TRAFFIC_EMISSION_FACTOR = 0.94


def compare_plans(distance_km: float, engine_type: str) -> dict:
    """Compare a shortest-distance plan vs a longer 'best-traffic' plan."""
    factor = factor_for_engine(engine_type)
    shortest = round(distance_km * factor, 4)
    best_traffic = round(
        distance_km * BEST_TRAFFIC_DISTANCE_FACTOR * factor * BEST_TRAFFIC_EMISSION_FACTOR, 4
    )
    return {
        "engine_type": engine_type,
        "distance_km": round(distance_km, 3),
        "best_traffic_distance_km": round(distance_km * BEST_TRAFFIC_DISTANCE_FACTOR, 3),
        "shortest_distance_plan_kg": shortest,
        "best_traffic_plan_kg": best_traffic,
        "recommended": (
            "shortest_distance" if shortest <= best_traffic else "best_traffic"
        ),
    }
