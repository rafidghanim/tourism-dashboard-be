from datetime import date, datetime, timezone

from app.core.errors import ApiError

from .models import VisitorCategory
from .repository import PublicTourismRepository
from .schemas import (
    DestinationDetailResponse,
    DestinationDto,
    DestinationsResponse,
    DistributionItemDto,
    DistributionResponse,
    MapFeatureDto,
    MapLayerResponse,
    MetadataResponse,
    MetaDto,
    MetricDto,
    OverviewDataDto,
    OverviewResponse,
    PageDto,
    PeriodDto,
    ProvenanceDto,
    RankingItemDto,
    RankingResponse,
    TrendPointDto,
    TrendsResponse,
)


class PublicTourismService:
    def __init__(self, repository: PublicTourismRepository) -> None:
        self.repository = repository

    @staticmethod
    def _provenance(value) -> ProvenanceDto:
        return ProvenanceDto(
            data_class=value.data_class,
            dataset_version_id=value.dataset_version_id,
            source_label=value.source_label,
            last_updated=value.last_updated,
            is_demo=value.is_demo,
            warnings=list(value.warnings),
        )

    @staticmethod
    def _period(value) -> PeriodDto:
        return PeriodDto(start=value.start, end=value.end)

    def overview(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ) -> OverviewResponse:
        value = self.repository.get_overview(region_id, period_start, period_end, visitor_category)
        return OverviewResponse(
            data=OverviewDataDto(
                total_visits=value.total_visits,
                domestic_visits=value.domestic_visits,
                international_visits=value.international_visits,
                destination_count=value.destination_count,
            ),
            period=self._period(value.period),
            provenance=self._provenance(value.provenance),
            availability="available",
            is_demo=value.provenance.is_demo,
        )

    def visitor_distribution(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        limit: int,
    ) -> DistributionResponse:
        items = self.repository.get_distribution(
            region_id, period_start, period_end, visitor_category
        )[:limit]
        denominator = sum(item.count for item in items)
        return DistributionResponse(
            items=[
                DistributionItemDto(
                    label=item.label,
                    count=item.count,
                    percentage=round(item.count / denominator * 100, 2) if denominator else 0,
                )
                for item in items
            ],
            denominator=denominator,
            period=PeriodDto(start=period_start, end=period_end),
            provenance=self._provenance(
                self.repository.get_overview(
                    region_id, period_start, period_end, visitor_category
                ).provenance
            ),
            availability="available" if denominator else "no_data",
            methodology="Persentase dihitung dari denominator kategori yang dikembalikan API.",
        )

    def trends(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        grain: str,
    ) -> TrendsResponse:
        series = self.repository.get_trends(
            region_id, period_start, period_end, visitor_category, grain
        )
        provenance = self.repository.get_overview(
            region_id, period_start, period_end, visitor_category
        ).provenance
        return TrendsResponse(
            grain=grain,
            series=[
                TrendPointDto(
                    period_start=item.period_start,
                    period_end=item.period_end,
                    value=item.value,
                    comparison_value=item.comparison_value,
                )
                for item in series
            ],
            period=PeriodDto(start=period_start, end=period_end),
            provenance=self._provenance(provenance),
            availability="partial" if any(item.value is None for item in series) else "available",
            methodology=(
                "Periode tanpa observasi dikembalikan sebagai null; "
                "tidak diisi nol atau diinterpolasi."
            ),
        )

    def destinations(
        self,
        region_id: str,
        search: str | None,
        category: str | None,
        status: str | None,
        cursor: str | None,
        limit: int,
    ) -> DestinationsResponse:
        page = self.repository.list_destinations(region_id, search, category, status, cursor, limit)
        provenance = self.repository.get_metadata(None)
        return DestinationsResponse(
            items=[
                DestinationDto.model_validate(item, from_attributes=True) for item in page.items
            ],
            page=PageDto(next_cursor=page.next_cursor, has_more=page.has_more),
            meta=MetaDto(generated_at=datetime.now(timezone.utc)),
            provenance=ProvenanceDto(
                data_class=provenance.data_class,
                dataset_version_id=provenance.dataset_version_id,
                source_label=provenance.source_label,
                last_updated=provenance.last_updated,
                is_demo=True,
                warnings=[],
            ),
        )

    def destination_detail(self, destination_id: str) -> DestinationDetailResponse:
        item = self.repository.get_destination(destination_id)
        if item is None:
            raise ApiError(404, "NOT_FOUND", "Destination was not found.")
        metadata = self.repository.get_metadata(None)
        return DestinationDetailResponse(
            data=DestinationDto.model_validate(item, from_attributes=True),
            period=PeriodDto(start=date(2026, 1, 1), end=date(2026, 11, 30)),
            provenance=ProvenanceDto(
                data_class=metadata.data_class,
                dataset_version_id=metadata.dataset_version_id,
                source_label=metadata.source_label,
                last_updated=metadata.last_updated,
                is_demo=True,
                warnings=[],
            ),
            availability="available",
        )

    def ranking(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        metric: str,
        direction: str,
        cursor: str | None,
        limit: int,
    ) -> RankingResponse:
        page = self.repository.list_destinations(
            region_id, None, None, None, cursor, 100, period_start, period_end
        )
        items = sorted(
            page.items,
            key=lambda item: ((-item.visits if direction == "desc" else item.visits), item.name),
        )
        start = int(cursor or "0")
        selected = items[start : start + limit]
        provenance = self.repository.get_metadata(None)
        return RankingResponse(
            items=[
                RankingItemDto(
                    **DestinationDto.model_validate(item, from_attributes=True).model_dump(),
                    rank=start + index + 1,
                    metric_value=item.visits,
                )
                for index, item in enumerate(selected)
            ],
            page=PageDto(
                next_cursor=str(start + limit) if start + limit < len(items) else None,
                has_more=start + limit < len(items),
            ),
            meta=MetaDto(generated_at=datetime.now(timezone.utc)),
            period=PeriodDto(start=period_start, end=period_end),
            metric=MetricDto(
                code="visits",
                name="Total kunjungan",
                unit="visitor_count",
                formula_version="demo-v1",
            ),
            direction=direction,
            tie_breaker="destination_name_ascending",
            provenance=ProvenanceDto(
                data_class=provenance.data_class,
                dataset_version_id=provenance.dataset_version_id,
                source_label=provenance.source_label,
                last_updated=provenance.last_updated,
                is_demo=True,
                warnings=[],
            ),
        )

    def map_visits(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        resolution: str,
    ) -> MapLayerResponse:
        provenance = self.repository.get_overview(
            region_id, period_start, period_end, visitor_category
        ).provenance
        features = [
            MapFeatureDto(
                id=item.id,
                geometry={"type": "Point", "coordinates": [item.longitude, item.latitude]},
                properties={"name": item.name, "visits": item.visits},
            )
            for item in self.repository.get_map_points(
                region_id, period_start, period_end, visitor_category, resolution
            )
        ]
        return MapLayerResponse(
            features=features,
            period=PeriodDto(start=period_start, end=period_end),
            provenance=self._provenance(provenance),
            availability="available",
            resolution=resolution,
            disclosure_note="Koordinat berasal dari katalog destinasi publik.",
        )

    def metadata(self, dataset_key: str | None) -> MetadataResponse:
        value = self.repository.get_metadata(dataset_key)
        return MetadataResponse(
            dataset_key=value.dataset_key,
            dataset_version_id=value.dataset_version_id,
            source_label=value.source_label,
            data_class=value.data_class,
            methodology_note=value.methodology_note,
            last_updated=value.last_updated,
            is_demo=True,
        )
