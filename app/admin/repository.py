# ruff: noqa: E501

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.core.errors import ApiError


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AdminRepository:
    def __init__(self, database: str = ":memory:") -> None:
        if database != ":memory:":
            Path(database).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS destinations (
              id TEXT PRIMARY KEY, code TEXT UNIQUE NOT NULL, name TEXT NOT NULL, category TEXT NOT NULL,
              region_id TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL, description TEXT,
              status TEXT NOT NULL DEFAULT 'review', public_visible INTEGER NOT NULL DEFAULT 0,
              version INTEGER NOT NULL DEFAULT 1, source_label TEXT NOT NULL, dataset_version_id TEXT NOT NULL,
              created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observations (
              id TEXT PRIMARY KEY, destination_id TEXT, region_id TEXT, visitor_category TEXT NOT NULL,
              period_start TEXT NOT NULL, period_end TEXT NOT NULL, visitor_count INTEGER NOT NULL,
              data_class TEXT NOT NULL, validation_status TEXT NOT NULL, publication_status TEXT NOT NULL,
              dataset_version_id TEXT NOT NULL, source_label TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS imports (
              id TEXT PRIMARY KEY, dataset_version_id TEXT NOT NULL, source_label TEXT NOT NULL,
              period_start TEXT NOT NULL, period_end TEXT NOT NULL, status TEXT NOT NULL, total_rows INTEGER NOT NULL,
              accepted_rows INTEGER NOT NULL, rejected_rows INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS import_rows (
              id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
              destination_id TEXT NOT NULL, visitor_category TEXT NOT NULL
                CHECK (visitor_category IN ('domestic', 'international')),
              visitor_count INTEGER NOT NULL CHECK (visitor_count >= 0),
              period_start TEXT NOT NULL, period_end TEXT NOT NULL,
              UNIQUE (import_id, destination_id, visitor_category, period_start, period_end)
            );
            CREATE TABLE IF NOT EXISTS publications (
              id TEXT PRIMARY KEY, dataset_version_id TEXT NOT NULL, disclosure_scope TEXT NOT NULL,
              approval_note TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_logs (
              id TEXT PRIMARY KEY, action TEXT NOT NULL, resource_type TEXT NOT NULL, resource_id TEXT,
              actor_subject TEXT NOT NULL, request_id TEXT NOT NULL, reason TEXT NOT NULL, occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS idempotency (
              key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response_json TEXT NOT NULL, status_code INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_scenarios (
              id TEXT PRIMARY KEY, input_json TEXT NOT NULL, output_json TEXT NOT NULL,
              input_dataset_version_id TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS policy_recommendations (
              id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, snapshot_json TEXT NOT NULL,
              status TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reports (
              id TEXT PRIMARY KEY, template TEXT NOT NULL, resource_id TEXT NOT NULL,
              snapshot_json TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_destinations_public_name
              ON destinations(public_visible, name);
            CREATE INDEX IF NOT EXISTS idx_imports_dataset_status
              ON imports(dataset_version_id, status);
            CREATE INDEX IF NOT EXISTS idx_imports_created_at
              ON imports(created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_import_rows_import
              ON import_rows(import_id);
            CREATE INDEX IF NOT EXISTS idx_observations_destination_period
              ON observations(destination_id, period_start, period_end);
            CREATE INDEX IF NOT EXISTS idx_audit_logs_occurred_at
              ON audit_logs(occurred_at DESC);
            """
        )
        self._migrate_import_rows()
        self.db.commit()

    def _migrate_import_rows(self) -> None:
        columns = {row["name"] for row in self.db.execute("PRAGMA table_info(import_rows)")}
        if not columns or {"period_start", "period_end"}.issubset(columns):
            return
        self.db.execute("DROP INDEX IF EXISTS idx_import_rows_import")
        self.db.execute("ALTER TABLE import_rows RENAME TO import_rows_legacy")
        self.db.execute(
            """CREATE TABLE import_rows (
              id TEXT PRIMARY KEY, import_id TEXT NOT NULL REFERENCES imports(id) ON DELETE CASCADE,
              destination_id TEXT NOT NULL, visitor_category TEXT NOT NULL
                CHECK (visitor_category IN ('domestic', 'international')),
              visitor_count INTEGER NOT NULL CHECK (visitor_count >= 0),
              period_start TEXT NOT NULL, period_end TEXT NOT NULL,
              UNIQUE (import_id, destination_id, visitor_category, period_start, period_end)
            )"""
        )
        self.db.execute(
            """INSERT INTO import_rows
            (id, import_id, destination_id, visitor_category, visitor_count, period_start, period_end)
            SELECT r.id, r.import_id, r.destination_id, r.visitor_category, r.visitor_count,
                   i.period_start, i.period_end
            FROM import_rows_legacy r JOIN imports i ON i.id = r.import_id"""
        )
        self.db.execute("DROP TABLE import_rows_legacy")
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_import_rows_import ON import_rows(import_id)"
        )

    def close(self) -> None:
        self.db.close()

    def idempotent(self, key: str | None, payload: object):
        if not key:
            return None
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()
        row = self.db.execute("SELECT * FROM idempotency WHERE key = ?", (key,)).fetchone()
        if not row:
            return fingerprint
        if row["fingerprint"] != fingerprint:
            raise ApiError(
                409,
                "IDEMPOTENCY_KEY_REUSED",
                "The idempotency key was used with a different request.",
            )
        return json.loads(row["response_json"]), row["status_code"]

    def save_idempotency(
        self, key: str | None, fingerprint: str | None, response: object, status_code: int
    ) -> None:
        if key and fingerprint:
            self.db.execute(
                "INSERT INTO idempotency VALUES (?, ?, ?, ?)",
                (key, fingerprint, json.dumps(response, default=str), status_code),
            )
            self.db.commit()

    def audit(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None,
        actor: str,
        request_id: str,
        reason: str,
    ) -> None:
        self.db.execute(
            "INSERT INTO audit_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                action,
                resource_type,
                resource_id,
                actor,
                request_id,
                reason,
                utc_now(),
            ),
        )
        self.db.commit()

    def create_policy_scenario(self, payload: dict, output: dict, actor: str):
        scenario_id, created_at = str(uuid4()), utc_now()
        self.db.execute(
            "INSERT INTO policy_scenarios VALUES (?, ?, ?, ?, ?, ?)",
            (
                scenario_id,
                json.dumps(payload),
                json.dumps(output),
                payload["input_dataset_version_id"],
                actor,
                created_at,
            ),
        )
        self.db.commit()
        return self.policy_scenario(scenario_id)

    def policy_scenario(self, scenario_id: str):
        return self.db.execute(
            "SELECT * FROM policy_scenarios WHERE id = ?", (scenario_id,)
        ).fetchone()

    def policy_scenarios(self):
        return self.db.execute("SELECT * FROM policy_scenarios ORDER BY created_at DESC").fetchall()

    def delete_policy_scenario(self, scenario_id: str) -> bool:
        current = self.policy_scenario(scenario_id)
        if not current:
            return False
        # Recommendations are derived from the scenario and must not become
        # orphaned. Existing report snapshots remain available as history.
        self.db.execute("DELETE FROM policy_recommendations WHERE scenario_id = ?", (scenario_id,))
        self.db.execute("DELETE FROM policy_scenarios WHERE id = ?", (scenario_id,))
        self.db.commit()
        return True

    def create_recommendation(self, scenario_id: str, snapshot: dict, actor: str):
        record_id, created_at = str(uuid4()), utc_now()
        self.db.execute(
            "INSERT INTO policy_recommendations VALUES (?, ?, ?, 'draft', ?, ?)",
            (record_id, scenario_id, json.dumps(snapshot), actor, created_at),
        )
        self.db.commit()
        return self.recommendation(record_id)

    def recommendation(self, recommendation_id: str):
        return self.db.execute(
            "SELECT * FROM policy_recommendations WHERE id = ?", (recommendation_id,)
        ).fetchone()

    def create_report(self, template: str, resource_id: str, snapshot: dict, actor: str):
        report_id, created_at = str(uuid4()), utc_now()
        self.db.execute(
            "INSERT INTO reports VALUES (?, ?, ?, ?, ?, ?)",
            (report_id, template, resource_id, json.dumps(snapshot), actor, created_at),
        )
        self.db.commit()
        return self.report(report_id)

    def report(self, report_id: str):
        return self.db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    def reports(self):
        return self.db.execute("SELECT * FROM reports ORDER BY created_at DESC").fetchall()

    def destinations(self):
        return self.db.execute(
            "SELECT * FROM destinations WHERE public_visible = 1 ORDER BY name"
        ).fetchall()

    def destination(self, destination_id: str):
        return self.db.execute(
            "SELECT * FROM destinations WHERE id = ?", (destination_id,)
        ).fetchone()

    def insert_destination(self, data: dict) -> sqlite3.Row:
        now = utc_now()
        destination_id = str(uuid4())
        try:
            self.db.execute(
                "INSERT INTO destinations VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'review', 1, 1, ?, ?, ?, ?)",
                (
                    destination_id,
                    data["code"],
                    data["name"],
                    data["category"],
                    data["region_id"],
                    data["location"]["latitude"],
                    data["location"]["longitude"],
                    data.get("description"),
                    data["source_label"],
                    data["dataset_version_id"],
                    now,
                    now,
                ),
            )
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            raise ApiError(409, "CONFLICT", "The destination code already exists.") from exc
        return self.destination(destination_id)

    def update_destination(
        self, destination_id: str, data: dict, expected_version: int
    ) -> sqlite3.Row:
        current = self.destination(destination_id)
        if not current:
            raise ApiError(404, "NOT_FOUND", "Destination was not found.")
        if current["version"] != expected_version:
            raise ApiError(409, "VERSION_CONFLICT", "The destination was changed by another user.")
        fields, values = [], []
        for key, column in (
            ("name", "name"),
            ("category", "category"),
            ("description", "description"),
        ):
            if data.get(key) is not None:
                fields.append(f"{column} = ?")
                values.append(data[key])
        if data.get("location"):
            fields += ["latitude = ?", "longitude = ?"]
            values += [data["location"]["latitude"], data["location"]["longitude"]]
        if fields:
            values += [utc_now(), expected_version + 1, destination_id, expected_version]
            self.db.execute(
                f"UPDATE destinations SET {', '.join(fields)}, updated_at = ?, version = ? WHERE id = ? AND version = ?",
                values,
            )
            self.db.commit()
        return self.destination(destination_id)

    def delete_destination(self, destination_id: str, expected_version: int) -> None:
        current = self.destination(destination_id)
        if not current:
            raise ApiError(404, "NOT_FOUND", "Destination was not found.")
        if current["version"] != expected_version:
            raise ApiError(409, "VERSION_CONFLICT", "The destination was changed by another user.")
        self.db.execute(
            "UPDATE destinations SET public_visible = 0, status = 'archived', updated_at = ?, version = ? WHERE id = ? AND version = ?",
            (utc_now(), expected_version + 1, destination_id, expected_version),
        )
        self.db.commit()

    def insert_observation(self, data: dict) -> sqlite3.Row:
        observation_id = str(uuid4())
        now = utc_now()
        self.db.execute(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?, ?, ?, 'manual_entry', 'pending', 'draft', ?, ?, 1, ?)",
            (
                observation_id,
                data.get("destination_id"),
                data.get("region_id"),
                data["visitor_category"],
                str(data["period_start"]),
                str(data["period_end"]),
                data["visitor_count"],
                data["dataset_version_id"],
                data["source_label"],
                now,
            ),
        )
        self.db.commit()
        return self.observation(observation_id)

    def observation(self, observation_id: str):
        return self.db.execute(
            "SELECT * FROM observations WHERE id = ?", (observation_id,)
        ).fetchone()

    def insert_import(self, data: dict) -> sqlite3.Row:
        import_id = str(uuid4())
        valid, rejected = 0, 0
        for row in data["rows"]:
            is_valid = (
                row["visitor_count"] >= 0 and self.destination(row["destination_id"]) is not None
            )
            valid += is_valid
            rejected += not is_valid
        now = utc_now()
        status = "validated" if rejected == 0 else "received"
        try:
            self.db.execute(
                "INSERT INTO imports VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    import_id,
                    data["dataset_version_id"],
                    data["source_label"],
                    str(data["period_start"]),
                    str(data["period_end"]),
                    status,
                    len(data["rows"]),
                    valid,
                    rejected,
                    now,
                ),
            )
            self.db.executemany(
                "INSERT INTO import_rows VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        str(uuid4()),
                        import_id,
                        row["destination_id"],
                        row["visitor_category"],
                        row["visitor_count"],
                        str(row.get("period_start") or data["period_start"]),
                        str(row.get("period_end") or data["period_end"]),
                    )
                    for row in data["rows"]
                    if row["visitor_count"] >= 0
                    and self.destination(row["destination_id"]) is not None
                ],
            )
            self.db.commit()
        except sqlite3.IntegrityError as exc:
            self.db.rollback()
            raise ApiError(
                422, "INVALID_IMPORT", "CSV rows contain duplicate or invalid data."
            ) from exc
        return self.import_record(import_id)

    def import_record(self, import_id: str):
        return self.db.execute("SELECT * FROM imports WHERE id = ?", (import_id,)).fetchone()

    def imports(self):
        return self.db.execute("SELECT * FROM imports ORDER BY created_at DESC").fetchall()

    def set_import_status(self, import_id: str, status: str):
        current = self.import_record(import_id)
        if not current:
            raise ApiError(404, "NOT_FOUND", "Import batch was not found.")
        transitions = {"validated": {"pending", "received"}, "accepted": {"validated"}}
        if status not in transitions or current["status"] not in transitions[status]:
            raise ApiError(
                409, "INVALID_IMPORT_TRANSITION", "Import batch status transition is not allowed."
            )
        self.db.execute(
            "UPDATE imports SET status = ?, version = version + 1 WHERE id = ?", (status, import_id)
        )
        self.db.commit()
        return self.import_record(import_id)

    def delete_import(self, import_id: str) -> None:
        current = self.import_record(import_id)
        if not current:
            raise ApiError(404, "NOT_FOUND", "Import batch was not found.")
        publication = self.db.execute(
            "SELECT 1 FROM publications WHERE dataset_version_id = ? LIMIT 1",
            (current["dataset_version_id"],),
        ).fetchone()
        if publication:
            raise ApiError(
                409,
                "IMPORT_IN_USE",
                "Import batch cannot be deleted because its dataset is already published.",
            )
        try:
            self.db.execute("DELETE FROM imports WHERE id = ?", (import_id,))
            self.db.commit()
        except sqlite3.Error as exc:
            self.db.rollback()
            raise ApiError(
                500, "IMPORT_DELETE_FAILED", "Import batch could not be deleted."
            ) from exc

    def insert_publication(self, data: dict) -> sqlite3.Row:
        row = self.db.execute(
            "SELECT COUNT(*) AS count FROM imports WHERE dataset_version_id = ? AND status = 'accepted'",
            (data["dataset_version_id"],),
        ).fetchone()
        if row["count"] == 0:
            raise ApiError(
                409, "DATASET_NOT_ACCEPTED", "Only an accepted dataset can be published."
            )
        publication_id = str(uuid4())
        self.db.execute(
            "INSERT INTO publications VALUES (?, ?, ?, ?, 'approved_public', 1, ?)",
            (
                publication_id,
                data["dataset_version_id"],
                data["disclosure_scope"],
                data["approval_note"],
                utc_now(),
            ),
        )
        self.db.commit()
        return self.publication(publication_id)

    def publication(self, publication_id: str):
        return self.db.execute(
            "SELECT * FROM publications WHERE id = ?", (publication_id,)
        ).fetchone()

    def audits(self):
        return self.db.execute("SELECT * FROM audit_logs ORDER BY occurred_at DESC").fetchall()
