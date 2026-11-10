import hashlib
import json

from fastapi import APIRouter, Depends, Header, Request, Response

from app.admin.auth import DemoIdentity, current_identity, require_permission
from app.admin.repository import AdminRepository
from app.admin.schemas import (
    AcceptImport,
    AdminDestination,
    AuditResponse,
    DestinationCreate,
    DestinationEnvelope,
    DestinationPatch,
    DestinationsResponse,
    ImportCreate,
    ImportData,
    ImportEnvelope,
    ImportsResponse,
    MeResponse,
    ObservationCreate,
    ObservationEnvelope,
    PublicationCreate,
    PublicationEnvelope,
)
from app.core.config import get_settings
from app.core.errors import ApiError

router = APIRouter()
repository = AdminRepository(get_settings().admin_database)


def _etag(row) -> str:
    value = f"{row['id']}:{row['version']}"
    return f'"{hashlib.sha256(value.encode()).hexdigest()}"'


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _destination(row) -> dict:
    return dict(row)


def _import(row) -> dict:
    return dict(row)


def _observation(row) -> dict:
    return dict(row)


def _publication(row) -> dict:
    return dict(row)


@router.get("/me", response_model=MeResponse)
def me(identity: DemoIdentity = Depends(current_identity)) -> MeResponse:
    return MeResponse(
        subject=identity.subject,
        display_name=identity.display_name,
        permissions=sorted(identity.permissions),
        auth_mode="demo_header",
    )


@router.get("/destinations", response_model=DestinationsResponse)
def list_destinations(identity: DemoIdentity = Depends(require_permission("destinations:read"))):
    return DestinationsResponse(
        items=[
            AdminDestination.model_validate(_destination(row)) for row in repository.destinations()
        ]
    )


@router.post("/destinations", response_model=DestinationEnvelope, status_code=201)
def create_destination(
    request: Request,
    payload: DestinationCreate,
    response: Response,
    identity: DemoIdentity = Depends(require_permission("destinations:write")),
):
    row = repository.insert_destination(payload.model_dump())
    response.headers["etag"] = _etag(row)
    repository.audit(
        "destination.create",
        "destination",
        row["id"],
        identity.subject,
        _request_id(request),
        payload.change_reason,
    )
    return DestinationEnvelope(data=AdminDestination.model_validate(_destination(row)))


@router.patch("/destinations/{destination_id}", response_model=DestinationEnvelope)
def patch_destination(
    request: Request,
    destination_id: str,
    payload: DestinationPatch,
    response: Response,
    if_match: str | None = Header(default=None, alias="If-Match"),
    identity: DemoIdentity = Depends(require_permission("destinations:write")),
):
    if not if_match:
        raise ApiError(400, "IF_MATCH_REQUIRED", "If-Match is required for destination updates.")
    current = repository.destination(destination_id)
    if not current:
        raise ApiError(404, "NOT_FOUND", "Destination was not found.")
    try:
        expected = (
            int(if_match.strip('"').split(":")[-1])
            if ":" in if_match
            else current["version"]
            if if_match == _etag(current)
            else -1
        )
    except ValueError:
        expected = -1
    row = repository.update_destination(
        destination_id, payload.model_dump(exclude_none=True), expected
    )
    response.headers["etag"] = _etag(row)
    repository.audit(
        "destination.update",
        "destination",
        destination_id,
        identity.subject,
        _request_id(request),
        payload.change_reason,
    )
    return DestinationEnvelope(data=AdminDestination.model_validate(_destination(row)))


@router.delete("/destinations/{destination_id}", status_code=204)
def delete_destination(
    request: Request,
    destination_id: str,
    if_match: str | None = Header(default=None, alias="If-Match"),
    identity: DemoIdentity = Depends(require_permission("destinations:write")),
):
    if not if_match:
        raise ApiError(400, "IF_MATCH_REQUIRED", "If-Match is required for destination deletion.")
    current = repository.destination(destination_id)
    if not current:
        raise ApiError(404, "NOT_FOUND", "Destination was not found.")
    if if_match == _etag(current):
        expected = current["version"]
    elif ":" in if_match:
        try:
            expected = int(if_match.strip('"').split(":")[-1])
        except ValueError:
            expected = -1
    else:
        expected = -1
    repository.delete_destination(destination_id, expected)
    repository.audit(
        "destination.archive",
        "destination",
        destination_id,
        identity.subject,
        _request_id(request),
        "Destinasi diarsipkan dari katalog aktif",
    )
    return Response(status_code=204)


@router.post("/visitor-statistics", response_model=ObservationEnvelope, status_code=201)
def create_observation(
    request: Request,
    payload: ObservationCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: DemoIdentity = Depends(require_permission("observations:write")),
):
    fingerprint = repository.idempotent(idempotency_key, payload.model_dump(mode="json"))
    if isinstance(fingerprint, tuple):
        return Response(
            content=json.dumps(fingerprint[0]), status_code=200, media_type="application/json"
        )
    if payload.destination_id and not repository.destination(payload.destination_id):
        raise ApiError(404, "NOT_FOUND", "Destination was not found.")
    row = repository.insert_observation(payload.model_dump())
    result = ObservationEnvelope(data=_observation(row))
    body = result.model_dump(mode="json")
    repository.save_idempotency(idempotency_key, fingerprint, body, 201)
    response.headers["etag"] = _etag(row)
    repository.audit(
        "observation.create",
        "observation",
        row["id"],
        identity.subject,
        _request_id(request),
        payload.rationale,
    )
    return result


@router.post("/imports", response_model=ImportEnvelope, status_code=201)
def create_import(
    request: Request,
    payload: ImportCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: DemoIdentity = Depends(require_permission("imports:create")),
):
    fingerprint = repository.idempotent(idempotency_key, payload.model_dump(mode="json"))
    if isinstance(fingerprint, tuple):
        return Response(
            content=json.dumps(fingerprint[0]), status_code=200, media_type="application/json"
        )
    row = repository.insert_import(payload.model_dump())
    result = ImportEnvelope(data=_import(row))
    repository.save_idempotency(idempotency_key, fingerprint, result.model_dump(mode="json"), 201)
    repository.audit(
        "import.create",
        "import",
        row["id"],
        identity.subject,
        _request_id(request),
        "Batch import diterima",
    )
    return result


@router.get("/imports", response_model=ImportsResponse)
def list_imports(
    identity: DemoIdentity = Depends(require_permission("imports:read")),
):
    return ImportsResponse(
        items=[ImportData.model_validate(_import(row)) for row in repository.imports()]
    )


@router.post("/imports/{import_id}/validate", response_model=ImportEnvelope)
def validate_import(
    request: Request,
    import_id: str,
    identity: DemoIdentity = Depends(require_permission("imports:validate")),
):
    row = repository.set_import_status(import_id, "validated")
    repository.audit(
        "import.validate",
        "import",
        import_id,
        identity.subject,
        _request_id(request),
        "Validasi deterministik",
    )
    return ImportEnvelope(data=_import(row))


@router.delete("/imports/{import_id}", status_code=204)
def delete_import(
    request: Request,
    import_id: str,
    identity: DemoIdentity = Depends(require_permission("imports:delete")),
):
    repository.delete_import(import_id)
    repository.audit(
        "import.delete",
        "import",
        import_id,
        identity.subject,
        _request_id(request),
        "Batch CSV dihapus dari panel admin",
    )
    return Response(status_code=204)


@router.post("/imports/{import_id}/accept", response_model=ImportEnvelope)
def accept_import(
    request: Request,
    import_id: str,
    payload: AcceptImport,
    identity: DemoIdentity = Depends(require_permission("imports:approve")),
):
    row = repository.set_import_status(import_id, "accepted")
    repository.audit(
        "import.accept",
        "import",
        import_id,
        identity.subject,
        _request_id(request),
        payload.review_note,
    )
    return ImportEnvelope(data=_import(row))


@router.post("/publications", response_model=PublicationEnvelope, status_code=201)
def create_publication(
    request: Request,
    payload: PublicationCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: DemoIdentity = Depends(require_permission("publication:approve")),
):
    fingerprint = repository.idempotent(idempotency_key, payload.model_dump(mode="json"))
    if isinstance(fingerprint, tuple):
        return Response(
            content=json.dumps(fingerprint[0]), status_code=200, media_type="application/json"
        )
    row = repository.insert_publication(payload.model_dump())
    result = PublicationEnvelope(data=_publication(row))
    repository.save_idempotency(idempotency_key, fingerprint, result.model_dump(mode="json"), 201)
    repository.audit(
        "publication.approve",
        "publication",
        row["id"],
        identity.subject,
        _request_id(request),
        payload.approval_note,
    )
    return result


@router.get("/audit-logs", response_model=AuditResponse)
def audit_logs(identity: DemoIdentity = Depends(require_permission("audit:read"))):
    return AuditResponse(items=[dict(row) for row in repository.audits()])
