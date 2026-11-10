from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class ProvenanceDto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_class: str
    dataset_version_id: str
    source_label: str
    last_updated: datetime
    is_demo: bool
    warnings: list[str]


class PeriodDto(BaseModel):
    start: date
    end: date


class OverviewDataDto(BaseModel):
    total_visits: int
    domestic_visits: int
    international_visits: int
    destination_count: int


class OverviewResponse(BaseModel):
    data: OverviewDataDto
    period: PeriodDto
    provenance: ProvenanceDto
    availability: str
    is_demo: bool


class DistributionItemDto(BaseModel):
    label: str
    count: int
    percentage: float


class DistributionResponse(BaseModel):
    items: list[DistributionItemDto]
    denominator: int
    period: PeriodDto
    provenance: ProvenanceDto
    availability: str
    methodology: str


class TrendPointDto(BaseModel):
    period_start: date
    period_end: date
    value: int | None
    comparison_value: int | None


class TrendsResponse(BaseModel):
    grain: str
    series: list[TrendPointDto]
    period: PeriodDto
    provenance: ProvenanceDto
    availability: str
    methodology: str


class PageDto(BaseModel):
    next_cursor: str | None
    has_more: bool


class MetaDto(BaseModel):
    generated_at: datetime


class DestinationDto(BaseModel):
    id: str
    name: str
    category: str
    region_id: str
    latitude: float
    longitude: float
    visits: int
    status: str


class DestinationsResponse(BaseModel):
    items: list[DestinationDto]
    page: PageDto
    meta: MetaDto
    provenance: ProvenanceDto


class DestinationDetailResponse(BaseModel):
    data: DestinationDto
    period: PeriodDto
    provenance: ProvenanceDto
    availability: str


class MetricDto(BaseModel):
    code: str
    name: str
    unit: str
    formula_version: str


class RankingItemDto(DestinationDto):
    rank: int
    metric_value: int


class RankingResponse(BaseModel):
    items: list[RankingItemDto]
    page: PageDto
    meta: MetaDto
    period: PeriodDto
    metric: MetricDto
    direction: str
    tie_breaker: str
    provenance: ProvenanceDto


class MapFeatureDto(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: dict
    properties: dict


class MapLayerResponse(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MapFeatureDto]
    period: PeriodDto
    provenance: ProvenanceDto
    availability: str
    resolution: str
    disclosure_note: str


class MetadataResponse(BaseModel):
    dataset_key: str
    dataset_version_id: str
    source_label: str
    data_class: str
    methodology_note: str
    last_updated: datetime
    is_demo: bool
