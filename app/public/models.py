from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

DataClass = Literal[
    "demonstration", "official_verified", "external_imported", "manual_entry", "derived", "forecast"
]
VisitorCategory = Literal["all", "domestic", "international"]
Availability = Literal["available", "no_data", "partial", "stale", "error"]


@dataclass(frozen=True)
class Provenance:
    data_class: DataClass
    dataset_version_id: str
    source_label: str
    last_updated: datetime
    is_demo: bool
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class Period:
    start: date
    end: date


@dataclass(frozen=True)
class OverviewRecord:
    total_visits: int
    domestic_visits: int
    international_visits: int
    destination_count: int
    period: Period
    provenance: Provenance


@dataclass(frozen=True)
class DistributionRecord:
    label: str
    count: int


@dataclass(frozen=True)
class TrendRecord:
    period_start: date
    period_end: date
    value: int | None
    comparison_value: int | None


@dataclass(frozen=True)
class DestinationRecord:
    id: str
    name: str
    category: str
    region_id: str
    latitude: float
    longitude: float
    visits: int
    status: Literal["good", "attention", "review"]
    public_visible: bool = True


@dataclass(frozen=True)
class Page:
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class DestinationPage:
    items: tuple[DestinationRecord, ...]
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True)
class MapPoint:
    id: str
    name: str
    latitude: float
    longitude: float
    visits: int


@dataclass(frozen=True)
class MetricDefinition:
    code: str
    name: str
    unit: str
    formula_version: str


@dataclass(frozen=True)
class MetadataRecord:
    dataset_key: str
    dataset_version_id: str
    source_label: str
    data_class: DataClass
    methodology_note: str
    last_updated: datetime
