from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LocationDto(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class DestinationCreate(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    region_id: str = Field(min_length=1, max_length=64)
    location: LocationDto
    description: str | None = Field(default=None, max_length=2000)
    source_label: str = Field(min_length=2, max_length=200)
    dataset_version_id: str = Field(min_length=1, max_length=100)
    change_reason: str = Field(min_length=3, max_length=500)


class DestinationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    location: LocationDto | None = None
    change_reason: str = Field(min_length=3, max_length=500)


class ObservationCreate(BaseModel):
    destination_id: str | None = None
    region_id: str | None = None
    visitor_category: Literal["domestic", "international"]
    period_start: date
    period_end: date
    visitor_count: int = Field(ge=0)
    unit: Literal["visitor_count"]
    source_label: str = Field(min_length=2, max_length=200)
    dataset_version_id: str = Field(min_length=1, max_length=100)
    effective_at: datetime
    rationale: str = Field(min_length=3, max_length=1000)
    supersedes_id: str | None = None

    @model_validator(mode="after")
    def valid_target_and_period(self):
        if (self.destination_id is None) == (self.region_id is None):
            raise ValueError("exactly one of destination_id or region_id is required")
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class ImportRow(BaseModel):
    destination_id: str
    visitor_category: Literal["domestic", "international"]
    visitor_count: int
    period_start: date | None = None
    period_end: date | None = None

    @model_validator(mode="after")
    def valid_row_period(self):
        if (self.period_start is None) != (self.period_end is None):
            raise ValueError("period_start and period_end must be provided together")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class ImportCreate(BaseModel):
    source_label: str = Field(min_length=2, max_length=200)
    dataset_version_id: str = Field(min_length=1, max_length=100)
    period_start: date
    period_end: date
    rows: list[ImportRow] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def valid_period(self):
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class AcceptImport(BaseModel):
    review_note: str = Field(min_length=3, max_length=1000)
    accepted_row_policy: Literal["valid_only"]


class PublicationCreate(BaseModel):
    dataset_version_id: str = Field(min_length=1, max_length=100)
    disclosure_scope: Literal["public_summary", "public_detail"]
    approval_note: str = Field(min_length=3, max_length=1000)
    expires_at: datetime | None = None


class AdminDestination(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    name: str
    category: str
    region_id: str
    latitude: float
    longitude: float
    description: str | None
    status: str
    public_visible: bool
    version: int
    source_label: str
    dataset_version_id: str
    created_at: datetime
    updated_at: datetime


class DestinationEnvelope(BaseModel):
    data: AdminDestination


class DestinationsResponse(BaseModel):
    items: list[AdminDestination]


class ImportData(BaseModel):
    id: str
    dataset_version_id: str
    source_label: str
    period_start: date
    period_end: date
    status: str
    total_rows: int
    accepted_rows: int
    rejected_rows: int
    version: int
    created_at: datetime


class ImportEnvelope(BaseModel):
    data: ImportData


class ImportsResponse(BaseModel):
    items: list[ImportData]


class ObservationData(BaseModel):
    id: str
    destination_id: str | None
    region_id: str | None
    visitor_category: str
    period_start: date
    period_end: date
    visitor_count: int
    data_class: str
    validation_status: str
    publication_status: str
    dataset_version_id: str
    source_label: str
    version: int
    created_at: datetime


class ObservationEnvelope(BaseModel):
    data: ObservationData


class PublicationData(BaseModel):
    id: str
    dataset_version_id: str
    disclosure_scope: str
    approval_note: str
    status: str
    version: int
    created_at: datetime


class PublicationEnvelope(BaseModel):
    data: PublicationData


class AuditItem(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: str | None
    actor_subject: str
    request_id: str
    reason: str
    occurred_at: datetime


class AuditResponse(BaseModel):
    items: list[AuditItem]


class MeResponse(BaseModel):
    subject: str
    display_name: str
    permissions: list[str]
    auth_mode: str
