"""Carbon-footprint estimation for patrol vehicles.

Factors that affect emissions (per the proposal): mileage and engine type.

Emission factors are approximate, based on public figures such as the US EPA
"typical passenger vehicle" (~0.192 kg CO2e/km for petrol) and manufacturer
fleet data. They are intentionally centralised here so they are easy to tune.
"""

from __future__ import annotations

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
    """Estimate CO2e (kg) for a trip of `distance_km` on a given engine type."""
    if distance_km is None or distance_km < 0:
        return 0.0
    return round(distance_km * factor_for_engine(engine_type), 4)


def compare_plans(distance_km: float, engine_type: str) -> dict:
    """Compare a shortest-distance plan vs a longer 'best-traffic' plan.

    The proposal asks whether to optimise for shortest distance or best
    traffic; this quantifies the emission trade-off. We model a best-traffic
    route as ~12% longer distance but smoother (fewer stop-start) driving,
    which we approximate as a 6% lower effective emission factor.
    """
    factor = factor_for_engine(engine_type)
    shortest = round(distance_km * factor, 4)
    best_traffic = round(distance_km * 1.12 * factor * 0.94, 4)
    return {
        "engine_type": engine_type,
        "distance_km": round(distance_km, 3),
        "shortest_distance_plan_kg": shortest,
        "best_traffic_plan_kg": best_traffic,
        "recommended": (
            "shortest_distance"
            if shortest <= best_traffic
            else "best_traffic"
        ),
    }
