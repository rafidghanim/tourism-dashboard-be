from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioInput:
    baseline_visits: float
    promotion_rate: float
    access_rate: float
    event_rate: float
    promotion_elasticity: float
    access_elasticity: float
    event_elasticity: float
    capacity_limit: float
    intervention_cost: float


@dataclass(frozen=True)
class SimulationResult:
    impact: float
    projected_visits_raw: float
    projected_visits: float
    incremental_visits: float
    cost_efficiency: float
    cost_per_incremental_visit: float | None
    capacity_constrained: bool
    data_class: str
    model_version: str
    coefficients: dict[str, float]


@dataclass(frozen=True)
class RecommendationMetrics:
    growth_opportunity: float
    cost_efficiency: float
    capacity_headroom: float
    data_quality: float


@dataclass(frozen=True)
class RecommendationScore:
    score: float
    priority: str
    components: dict[str, float]
