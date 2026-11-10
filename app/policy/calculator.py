import math

from app.policy.models import (
    RecommendationMetrics,
    RecommendationScore,
    ScenarioInput,
    SimulationResult,
)

MODEL_VERSION = "elasticity-demo-v1"


def _rate(value: float, name: str) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1.")


def simulate_policy(inputs: ScenarioInput) -> SimulationResult:
    for name in ("promotion_rate", "access_rate", "event_rate"):
        _rate(getattr(inputs, name), name)
    numeric_inputs = {
        "baseline_visits": inputs.baseline_visits,
        "promotion_elasticity": inputs.promotion_elasticity,
        "access_elasticity": inputs.access_elasticity,
        "event_elasticity": inputs.event_elasticity,
        "capacity_limit": inputs.capacity_limit,
        "intervention_cost": inputs.intervention_cost,
    }
    if any(not math.isfinite(value) for value in numeric_inputs.values()):
        raise ValueError("Scenario values must be finite numbers.")
    if inputs.baseline_visits < 0 or inputs.capacity_limit <= 0:
        raise ValueError("Visit counts must be non-negative and capacity_limit must be positive.")
    if inputs.capacity_limit < inputs.baseline_visits:
        raise ValueError("capacity_limit must be greater than or equal to baseline_visits.")
    elasticities = (
        inputs.promotion_elasticity,
        inputs.access_elasticity,
        inputs.event_elasticity,
    )
    if any(value < 0 for value in elasticities):
        raise ValueError("Elasticities must be non-negative.")
    if inputs.intervention_cost <= 0:
        raise ValueError("intervention_cost must be greater than zero.")
    impact = (
        inputs.promotion_rate * inputs.promotion_elasticity
        + inputs.access_rate * inputs.access_elasticity
        + inputs.event_rate * inputs.event_elasticity
    )
    raw = inputs.baseline_visits * (1 + impact)
    projected = min(raw, inputs.capacity_limit)
    incremental = projected - inputs.baseline_visits
    return SimulationResult(
        impact=impact,
        projected_visits_raw=raw,
        projected_visits=projected,
        incremental_visits=incremental,
        cost_efficiency=incremental / inputs.intervention_cost,
        cost_per_incremental_visit=(
            inputs.intervention_cost / incremental if incremental > 0 else None
        ),
        capacity_constrained=raw > inputs.capacity_limit,
        data_class="derived",
        model_version=MODEL_VERSION,
        coefficients={
            "promotion_elasticity": inputs.promotion_elasticity,
            "access_elasticity": inputs.access_elasticity,
            "event_elasticity": inputs.event_elasticity,
        },
    )


def score_recommendation(metrics: RecommendationMetrics) -> RecommendationScore:
    values = {
        "growth_opportunity": metrics.growth_opportunity,
        "cost_efficiency": metrics.cost_efficiency,
        "capacity_headroom": metrics.capacity_headroom,
        "data_quality": metrics.data_quality,
    }
    for name, value in values.items():
        _rate(value, name)
    weights = {
        "growth_opportunity": 0.35,
        "cost_efficiency": 0.25,
        "capacity_headroom": 0.20,
        "data_quality": 0.20,
    }
    components = {name: values[name] * weights[name] for name in values}
    score = sum(components.values())
    priority = "high" if score >= 0.75 else "medium" if score >= 0.50 else "review"
    return RecommendationScore(score=score, priority=priority, components=components)
