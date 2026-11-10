# ruff: noqa: E501

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ScenarioCreate(BaseModel):
    destination_name: str = Field(min_length=2, max_length=160)
    period: str = Field(min_length=4, max_length=30)
    input_dataset_version_id: str = Field(min_length=1, max_length=100)
    baseline_visits: float = Field(ge=0)
    promotion_rate: float = Field(ge=0, le=1)
    access_rate: float = Field(ge=0, le=1)
    event_rate: float = Field(ge=0, le=1)
    promotion_elasticity: float = Field(ge=0)
    access_elasticity: float = Field(ge=0)
    event_elasticity: float = Field(ge=0)
    capacity_limit: float = Field(gt=0)
    intervention_cost: float = Field(gt=0)
    assumptions: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def capacity_covers_baseline(self):
        if self.capacity_limit < self.baseline_visits:
            raise ValueError("capacity_limit must be greater than or equal to baseline_visits.")
        return self


class RecommendationCreate(BaseModel):
    scenario_id: str
    title: str = Field(min_length=3, max_length=200)
    risk: str = Field(min_length=2, max_length=100)


class ReportCreate(BaseModel):
    template: Literal[
        "tourism_overview",
        "distribution",
        "performance_analysis",
        "policy_simulation",
        "policy_recommendation",
    ]
    resource_id: str
    period: str = Field(min_length=4, max_length=30)
