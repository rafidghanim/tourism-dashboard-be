from datetime import date
from typing import Protocol

from .models import (
    DestinationPage,
    DestinationRecord,
    DistributionRecord,
    MapPoint,
    MetadataRecord,
    OverviewRecord,
    TrendRecord,
    VisitorCategory,
)


class PublicTourismRepository(Protocol):
    def get_overview(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ) -> OverviewRecord: ...
    def get_distribution(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ) -> tuple[DistributionRecord, ...]: ...
    def get_trends(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        grain: str,
    ) -> tuple[TrendRecord, ...]: ...
    def list_destinations(
        self,
        region_id: str,
        search: str | None,
        category: str | None,
        status: str | None,
        cursor: str | None,
        limit: int,
        period_start: date | None = None,
        period_end: date | None = None,
    ) -> DestinationPage: ...
    def get_destination(self, destination_id: str) -> DestinationRecord | None: ...
    def get_map_points(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        resolution: str,
    ) -> tuple[MapPoint, ...]: ...
    def get_metadata(self, dataset_key: str | None) -> MetadataRecord: ...
