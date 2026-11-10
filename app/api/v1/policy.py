# ruff: noqa: E501

import csv
import io
import json
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html import escape
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, Request, Response

from app.admin.auth import DemoIdentity, require_permission
from app.api.v1.internal import repository
from app.core.errors import ApiError
from app.policy.calculator import score_recommendation, simulate_policy
from app.policy.models import RecommendationMetrics, ScenarioInput
from app.policy.schemas import RecommendationCreate, ReportCreate, ScenarioCreate

router = APIRouter()
DISCLAIMER = "Data demonstrasi — bukan statistik resmi"
REPORT_TIMEZONE = ZoneInfo("Asia/Jakarta")
MONTHS_ID = (
    "Januari",
    "Februari",
    "Maret",
    "April",
    "Mei",
    "Juni",
    "Juli",
    "Agustus",
    "September",
    "Oktober",
    "November",
    "Desember",
)

REPORT_TEMPLATES = {
    "tourism_overview": {
        "label": "Tourism Overview",
        "subtitle": "Ringkasan kondisi dan konteks pariwisata.",
    },
    "distribution": {
        "label": "Laporan Sebaran Kunjungan",
        "subtitle": "Ringkasan persebaran kunjungan berdasarkan wilayah dan destinasi.",
    },
    "performance_analysis": {
        "label": "Analisis Performa Destinasi",
        "subtitle": "Analisis performa destinasi berdasarkan data yang tersedia.",
    },
    "policy_simulation": {
        "label": "Hasil Simulasi Kebijakan",
        "subtitle": "Snapshot hasil simulasi dan asumsi model kebijakan.",
    },
    "policy_recommendation": {
        "label": "Rekomendasi Kebijakan",
        "subtitle": "Ringkasan rekomendasi, skor, dan faktor pendukung keputusan.",
    },
}


def scenario_data(row):
    return {
        "id": row["id"],
        **json.loads(row["input_json"]),
        "output": json.loads(row["output_json"]),
        "created_at": row["created_at"],
    }


def scenario_summary(row) -> dict[str, Any]:
    inputs = json.loads(row["input_json"])
    return {
        "id": row["id"],
        "destination_name": inputs["destination_name"],
        "period": inputs["period"],
        "input_dataset_version_id": row["input_dataset_version_id"],
        "created_at": row["created_at"],
    }


def format_number(value: Any, decimals: int = 1) -> str:
    """Format numeric report values using Indonesian separators.

    Decimal is constructed from the string representation to avoid exposing
    binary floating-point artifacts from the calculation layer.
    """
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return str(value)
    quantum = Decimal(1).scaleb(-decimals)
    rounded = number.quantize(quantum, rounding=ROUND_HALF_UP)
    formatted = f"{rounded:,.{decimals}f}"
    formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
    if "," in formatted:
        formatted = formatted.rstrip("0").rstrip(",")
    return formatted


def format_datetime_id(value: Any) -> str:
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        local = timestamp.astimezone(REPORT_TIMEZONE)
        return f"{local.day} {MONTHS_ID[local.month - 1]} {local.year}, {local:%H.%M} WIB"
    except (TypeError, ValueError):
        return str(value)


def format_report_value(label: str, value: Any) -> str | list[str]:
    """Return presentation values without changing the calculation snapshot."""
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, bool):
        return "Ya — kapasitas terbatas" if value else "Tidak — kapasitas tidak terbatas"
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        normalized_label = label.casefold()
        if "efisiensi biaya" in normalized_label:
            return f"{format_number(value, 8)} kunjungan/Rp"
        if "skor" in normalized_label:
            return format_number(value, 3)
        if "kunjungan" in normalized_label:
            return format_number(value, 1)
        return format_number(value, 3)
    return str(value)


def report_item(label: str, value: Any) -> dict[str, Any]:
    return {"label": label, "value": format_report_value(label, value)}


def report_content(template: str, period: str, resource_id: str, content: dict[str, Any] | None):
    definition = REPORT_TEMPLATES[template]
    if template == "policy_simulation" and content:
        output = content["output"]
        return {
            "title": definition["label"],
            "subtitle": definition["subtitle"],
            "executive_summary": (
                f"Simulasi untuk {content['destination_name']} menghasilkan "
                f"proyeksi {format_number(output['projected_visits'], 1)} kunjungan dengan "
                f"tambahan {format_number(output['incremental_visits'], 1)} kunjungan."
            ),
            "sections": [
                {
                    "title": "Identitas laporan",
                    "items": [
                        report_item("Destinasi", content["destination_name"]),
                        report_item("Periode", content["period"]),
                        report_item("Model", output["model_version"]),
                    ],
                },
                {
                    "title": "Hasil simulasi",
                    "items": [
                        report_item("Baseline kunjungan", content["baseline_visits"]),
                        report_item("Proyeksi kunjungan", output["projected_visits"]),
                        report_item("Kunjungan inkremental", output["incremental_visits"]),
                        report_item(
                            "Efisiensi biaya (kunjungan per Rp)", output["cost_efficiency"]
                        ),
                        report_item("Terbatas kapasitas", output["capacity_constrained"]),
                    ],
                },
                {
                    "title": "Asumsi dan metodologi",
                    "items": [
                        report_item("Asumsi", content["assumptions"]),
                        report_item("Metodologi", output["methodology"]),
                        report_item("Peringatan", output["warnings"]),
                    ],
                },
            ],
            "source_data": content,
        }
    if template == "policy_recommendation" and content:
        return {
            "title": definition["label"],
            "subtitle": definition["subtitle"],
            "executive_summary": (
                f"Rekomendasi berada pada prioritas {content['priority']} "
                f"dengan skor {content['score']}."
            ),
            "sections": [
                {
                    "title": "Keputusan",
                    "items": [
                        report_item("Judul", content["title"]),
                        report_item("Prioritas", content["priority"]),
                        report_item("Risiko", content["risk"]),
                        report_item("Skor", content["score"]),
                    ],
                },
                {
                    "title": "Komponen penilaian",
                    "items": [
                        report_item(key, value) for key, value in content["components"].items()
                    ],
                },
                {
                    "title": "Asumsi dan model",
                    "items": [
                        report_item("Model", content["model_version"]),
                        report_item("Asumsi", content["assumptions"]),
                    ],
                },
            ],
            "source_data": content,
        }
    return {
        "title": definition["label"],
        "subtitle": definition["subtitle"],
        "executive_summary": "Laporan dibuat sebagai snapshot dari data yang tersedia pada periode terpilih.",
        "sections": [
            {
                "title": "Ringkasan laporan",
                "items": [
                    report_item("Periode", period),
                    report_item("Resource", resource_id),
                    report_item("Ketersediaan data", "Snapshot demonstrasi"),
                ],
            },
            {
                "title": "Catatan interpretasi",
                "items": [
                    report_item(
                        "Catatan",
                        "Detail metrik untuk template ini belum tersedia pada sumber data laporan.",
                    ),
                ],
            },
        ],
    }


def flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        rows: list[tuple[str, Any]] = []
        for key, child in value.items():
            rows.extend(flatten(child, f"{prefix}.{key}" if prefix else key))
        return rows
    if isinstance(value, list):
        return [(prefix, " | ".join(str(item) for item in value))]
    return [(prefix, value)]


def html_value(value: Any) -> str:
    if isinstance(value, list):
        items = "".join(f"<li>{escape(str(item))}</li>" for item in value)
        return f"<ul>{items}</ul>"
    return escape(str(value))


def html_report(snapshot: dict[str, Any]) -> str:
    content = snapshot["content"]
    sections = []
    for section in content["sections"]:
        rows = "".join(
            f"<tr><th>{escape(str(item['label']))}</th><td>{html_value(item['value'])}</td></tr>"
            for item in section.get("items", [])
        )
        sections.append(
            f"<section><h2>{escape(section['title'])}</h2><table>{rows}</table></section>"
        )
    report = f"""<!doctype html>
<html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(content["title"])}</title><style>
:root {{ color-scheme: light; font-family: Inter, Arial, sans-serif; color: #102338; background: #f4f8f7; }}
body {{ margin: 0; padding: 40px 20px; }} .report {{ max-width: 920px; margin: auto; background: #fff; border: 1px solid #d7e7e4; box-shadow: 0 12px 36px #10233814; }}
header {{ padding: 36px 42px 30px; color: #fff; background: linear-gradient(120deg,#102338,#0b5256); }}
.eyebrow {{ margin: 0 0 10px; color: #a9ded6; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }}
h1 {{ margin: 0; font-size: 30px; letter-spacing: -.04em; }} .subtitle {{ margin: 10px 0 0; color: #d8efeb; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 22px; color: #d8efeb; font-size: 12px; }} main {{ padding: 30px 42px 42px; }}
.summary {{ padding: 18px 20px; color: #0b5256; background: #e9f5f2; border-left: 4px solid #168c8d; line-height: 1.6; }}
section {{ margin-top: 28px; }} h2 {{ margin: 0 0 11px; color: #0b5256; font-size: 17px; }} table {{ width: 100%; border-collapse: collapse; font-size: 13px; }} th,td {{ padding: 11px 13px; border-bottom: 1px solid #e7eeee; text-align: left; vertical-align: top; }} th {{ width: 34%; color: #617184; font-weight: 600; background: #f7faf9; }} td ul {{ margin: 0; padding-left: 18px; }} td li + li {{ margin-top: 4px; }}
footer {{ padding: 18px 42px; color: #617184; background: #f7faf9; border-top: 1px solid #e7eeee; font-size: 11px; }}
@media print {{ body {{ padding: 0; background: #fff; }} .report {{ border: 0; box-shadow: none; }} }}
</style></head><body><article class="report"><header><p class="eyebrow">Tourism Intelligence · Laporan</p><h1>{escape(content["title"])}</h1><p class="subtitle">{escape(content["subtitle"])}</p><div class="meta"><span>Periode: {escape(str(snapshot["period"]))}</span><span>Dibuat: {escape(format_datetime_id(snapshot["created_at"]))}</span></div></header><main><div class="summary"><strong>Ringkasan eksekutif</strong><br>{escape(content["executive_summary"])}</div>{"".join(sections)}</main><footer><strong>{escape(DISCLAIMER)}</strong><br>Data ini merupakan snapshot dan tidak menggantikan publikasi statistik resmi.</footer></article></body></html>"""

    return report.replace("Tourism Intelligence", "Tourism Decision Support System")


@router.post("/policy-scenarios", status_code=201)
def create_scenario(
    payload: ScenarioCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    identity: DemoIdentity = Depends(require_permission("policy:simulate")),
):
    data = payload.model_dump()
    fingerprint = repository.idempotent(idempotency_key, data)
    if isinstance(fingerprint, tuple):
        return Response(
            content=json.dumps(fingerprint[0]), status_code=200, media_type="application/json"
        )
    result = simulate_policy(
        ScenarioInput(**{key: data[key] for key in ScenarioInput.__dataclass_fields__})
    )
    output = {
        **result.__dict__,
        "warnings": ["Simulasi demonstrasi — bukan prediksi resmi."],
        "methodology": "Model elastisitas dengan batas kapasitas.",
    }
    row = repository.create_policy_scenario(data, output, identity.subject)
    body = {"data": scenario_data(row), "provenance": {"disclaimer": DISCLAIMER}}
    repository.save_idempotency(idempotency_key, fingerprint, body, 201)
    return body


@router.get("/policy-scenarios")
def list_policy_scenarios(identity: DemoIdentity = Depends(require_permission("policy:read"))):
    return {"items": [scenario_summary(row) for row in repository.policy_scenarios()]}


@router.delete("/policy-scenarios/{scenario_id}", status_code=204)
def delete_policy_scenario(
    request: Request,
    scenario_id: str,
    identity: DemoIdentity = Depends(require_permission("policy:simulate")),
):
    if not repository.delete_policy_scenario(scenario_id):
        raise ApiError(404, "NOT_FOUND", "Policy scenario was not found.")
    repository.audit(
        "policy_scenario.delete",
        "policy_scenario",
        scenario_id,
        identity.subject,
        getattr(request.state, "request_id", ""),
        "Skenario simulasi dihapus dari panel admin",
    )
    return Response(status_code=204)


@router.get("/policy-scenarios/{scenario_id}")
def get_scenario(
    scenario_id: str, identity: DemoIdentity = Depends(require_permission("policy:read"))
):
    row = repository.policy_scenario(scenario_id)
    if not row:
        raise ApiError(404, "NOT_FOUND", "Policy scenario was not found.")
    return {"data": scenario_data(row), "provenance": {"disclaimer": DISCLAIMER}}


@router.post("/recommendations", status_code=201)
def create_recommendation(
    payload: RecommendationCreate,
    identity: DemoIdentity = Depends(require_permission("recommendations:write")),
):
    scenario = repository.policy_scenario(payload.scenario_id)
    if not scenario:
        raise ApiError(404, "NOT_FOUND", "Policy scenario was not found.")
    record = scenario_data(scenario)
    output = record["output"]
    headroom = max(
        0, (record["capacity_limit"] - output["projected_visits"]) / record["capacity_limit"]
    )
    metrics = RecommendationMetrics(
        growth_opportunity=min(1, output["incremental_visits"] / max(1, record["baseline_visits"])),
        cost_efficiency=min(1, output["cost_efficiency"] * 100_000),
        capacity_headroom=headroom,
        data_quality=0.70,
    )
    score = score_recommendation(metrics)
    snapshot = {
        "title": payload.title,
        "risk": payload.risk,
        "priority": score.priority,
        "score": score.score,
        "components": score.components,
        "scenario_id": payload.scenario_id,
        "data_class": "derived",
        "model_version": output["model_version"],
        "assumptions": record["assumptions"],
        "disclaimer": DISCLAIMER,
    }
    row = repository.create_recommendation(payload.scenario_id, snapshot, identity.subject)
    return {"data": {"id": row["id"], **snapshot, "status": row["status"]}}


@router.post("/reports", status_code=201)
def create_report(
    payload: ReportCreate, identity: DemoIdentity = Depends(require_permission("reports:create"))
):
    if payload.template == "policy_simulation":
        resource = repository.policy_scenario(payload.resource_id)
        content = scenario_data(resource) if resource else None
    elif payload.template == "policy_recommendation":
        resource = repository.recommendation(payload.resource_id)
        content = json.loads(resource["snapshot_json"]) if resource else None
    else:
        content = {"period": payload.period, "summary": "Template laporan demonstrasi."}
    if content is None:
        raise ApiError(404, "NOT_FOUND", "Selected report resource was not found.")
    snapshot = {
        "template": payload.template,
        "period": payload.period,
        "resource_id": payload.resource_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_at_display": format_datetime_id(datetime.now(timezone.utc).isoformat()),
        "content": report_content(payload.template, payload.period, payload.resource_id, content),
        "provenance": {"data_class": "derived", "disclaimer": DISCLAIMER},
    }
    row = repository.create_report(
        payload.template, payload.resource_id, snapshot, identity.subject
    )
    return {
        "data": {
            "id": row["id"],
            "template": row["template"],
            "created_at": row["created_at"],
            "snapshot": snapshot,
        }
    }


@router.get("/reports")
def list_reports(identity: DemoIdentity = Depends(require_permission("reports:read"))):
    return {
        "items": [
            {"id": row["id"], "template": row["template"], "created_at": row["created_at"]}
            for row in repository.reports()
        ]
    }


@router.get("/reports/{report_id}/download")
def download_report(
    report_id: str,
    format: str = "html",
    identity: DemoIdentity = Depends(require_permission("reports:read")),
):
    row = repository.report(report_id)
    if not row:
        raise ApiError(404, "NOT_FOUND", "Report was not found.")
    if format not in {"html", "csv", "json"}:
        raise ApiError(400, "UNSUPPORTED_FORMAT", "Supported formats are html, csv, and json.")
    snapshot = json.loads(row["snapshot_json"])
    filename = f"tourism-report-{snapshot['template']}-{row['id']}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if format == "json":
        return Response(
            json.dumps(snapshot, indent=2, ensure_ascii=False),
            media_type="application/json; charset=utf-8",
            headers=headers,
        )
    if format == "csv":
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["section", "metric", "value"])
        writer.writerow(["Metadata", "Template", snapshot["content"]["title"]])
        writer.writerow(["Metadata", "Periode", snapshot["period"]])
        writer.writerow(["Metadata", "Dibuat", format_datetime_id(snapshot["created_at"])])
        writer.writerow(
            ["Ringkasan eksekutif", "Ringkasan", snapshot["content"]["executive_summary"]]
        )
        for section in snapshot["content"]["sections"]:
            for item in section.get("items", []):
                value = item["value"]
                if isinstance(value, list):
                    value = " • ".join(str(item) for item in value)
                writer.writerow([section["title"], item["label"], value])
        return Response(stream.getvalue(), media_type="text/csv; charset=utf-8", headers=headers)
    return Response(html_report(snapshot), media_type="text/html; charset=utf-8", headers=headers)
