import hashlib
import json
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response

from app.core.config import get_settings
from app.public.demo_repository import DemoPublicRepository
from app.public.schemas import (
    DestinationDetailResponse,
    DestinationsResponse,
    DistributionResponse,
    MapLayerResponse,
    MetadataResponse,
    OverviewResponse,
    RankingResponse,
    TrendsResponse,
)
from app.public.service import PublicTourismService

router = APIRouter()
service = PublicTourismService(DemoPublicRepository(get_settings().admin_database))

Region = Annotated[str, Query(pattern="^[a-z0-9-]+$", min_length=1, max_length=64)]
Category = Annotated[Literal["all", "domestic", "international"], Query()]
DateQuery = Annotated[date, Query()]
Limit = Annotated[int, Query(ge=1, le=100)]


def _etag(payload: object) -> str:
    encoded = json.dumps(payload, default=str, sort_keys=True).encode()
    return f'"{hashlib.sha256(encoded).hexdigest()}"'


def _conditional(response: Response, request: Request, payload: object) -> bool:
    etag = _etag(payload)
    response.headers["etag"] = etag
    if request.headers.get("if-none-match") == etag:
        return True
    return False


def _period(start: date | None, end: date | None) -> tuple[date, date]:
    resolved_start = start or date(2026, 1, 1)
    resolved_end = end or date(2026, 11, 30)
    if resolved_start > resolved_end:
        from app.core.errors import ApiError

        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "period_start must precede or equal period_end.",
            [{"field": "period_start", "reason": "must not be after period_end"}],
        )
    return resolved_start, resolved_end


@router.get("/overview", response_model=OverviewResponse)
def overview(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    period_start: date | None = None,
    period_end: date | None = None,
    visitor_category: Category = "all",
) -> OverviewResponse | None:
    start, end = _period(period_start, period_end)
    result = service.overview(region_id, start, end, visitor_category)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/visitor-distribution", response_model=DistributionResponse)
def visitor_distribution(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    period_start: date | None = None,
    period_end: date | None = None,
    visitor_category: Category = "all",
    limit: Limit = 25,
) -> DistributionResponse | None:
    start, end = _period(period_start, period_end)
    result = service.visitor_distribution(region_id, start, end, visitor_category, limit)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/trends", response_model=TrendsResponse)
def trends(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    period_start: date | None = None,
    period_end: date | None = None,
    visitor_category: Category = "all",
    grain: Literal["month", "quarter", "year"] = "month",
) -> TrendsResponse | None:
    start, end = _period(period_start, period_end)
    result = service.trends(region_id, start, end, visitor_category, grain)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/destinations", response_model=DestinationsResponse)
def destinations(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    search: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=50),
    status: Literal["good", "attention", "review"] | None = None,
    cursor: str | None = Query(default=None, pattern="^[0-9]+$"),
    limit: Limit = 25,
) -> DestinationsResponse | None:
    result = service.destinations(region_id, search, category, status, cursor, limit)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/destinations/ranking", response_model=RankingResponse)
def ranking(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    period_start: date | None = None,
    period_end: date | None = None,
    metric: Literal["visits"] = "visits",
    direction: Literal["asc", "desc"] = "desc",
    cursor: str | None = Query(default=None, pattern="^[0-9]+$"),
    limit: Limit = 25,
) -> RankingResponse | None:
    start, end = _period(period_start, period_end)
    result = service.ranking(region_id, start, end, metric, direction, cursor, limit)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/destinations/{destination_id}", response_model=DestinationDetailResponse)
def destination_detail(destination_id: str) -> DestinationDetailResponse:
    return service.destination_detail(destination_id)


@router.get("/map-layers/visits", response_model=MapLayerResponse)
def map_visits(
    request: Request,
    response: Response,
    region_id: Region = "surakarta",
    period_start: date | None = None,
    period_end: date | None = None,
    visitor_category: Category = "all",
    resolution: Literal["coarse", "medium"] = "coarse",
) -> MapLayerResponse | None:
    start, end = _period(period_start, period_end)
    result = service.map_visits(region_id, start, end, visitor_category, resolution)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result


@router.get("/metadata", response_model=MetadataResponse)
def metadata(
    request: Request,
    response: Response,
    dataset_key: str | None = Query(default=None, max_length=100),
) -> MetadataResponse | None:
    result = service.metadata(dataset_key)
    if _conditional(response, request, result.model_dump(mode="json")):
        return Response(status_code=304, headers={"etag": response.headers["etag"]})
    return result
