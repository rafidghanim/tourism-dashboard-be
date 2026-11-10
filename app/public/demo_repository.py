import sqlite3
from calendar import monthrange
from datetime import date, datetime, timezone

from .models import (
    DestinationPage,
    DestinationRecord,
    DistributionRecord,
    MapPoint,
    MetadataRecord,
    OverviewRecord,
    Period,
    Provenance,
    TrendRecord,
    VisitorCategory,
)

DEMO_PROVENANCE = Provenance(
    data_class="demonstration",
    dataset_version_id="demo-2026-11-08-v1",
    source_label="Data demonstrasi — bukan statistik resmi",
    last_updated=datetime(2026, 11, 8, 0, 32, tzinfo=timezone.utc),
    is_demo=True,
    warnings=("Fixture lokal untuk validasi UI; bukan statistik resmi.",),
)


class DemoPublicRepository:
    def __init__(self, admin_database: str | None = None) -> None:
        self.admin_database = admin_database
        self._last_import_meta: tuple[str, str, datetime] | None = None

    def _imported_destinations(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ):
        if not self.admin_database:
            return None
        try:
            with sqlite3.connect(self.admin_database) as db:
                db.row_factory = sqlite3.Row
                import_row = db.execute(
                    """SELECT id, dataset_version_id, source_label, created_at FROM imports
                    WHERE status = 'accepted' AND period_start <= ? AND period_end >= ?
                    ORDER BY created_at DESC LIMIT 1""",
                    (str(period_end), str(period_start)),
                ).fetchone()
                if not import_row:
                    self._last_import_meta = None
                    return None
                rows = db.execute(
                    """SELECT d.id, d.name, d.category, d.region_id, d.latitude, d.longitude,
                    SUM(r.visitor_count) AS visits FROM import_rows r
                    JOIN destinations d ON d.id = r.destination_id
                    WHERE r.import_id = ? AND d.region_id = ? AND d.public_visible = 1
                      AND r.period_start <= ? AND r.period_end >= ?
                      AND (? = 'all' OR r.visitor_category = ?)
                    GROUP BY d.id, d.name, d.category, d.region_id, d.latitude, d.longitude
                    ORDER BY visits DESC, d.name ASC""",
                    (
                        import_row["id"],
                        region_id,
                        str(period_end),
                        str(period_start),
                        visitor_category,
                        visitor_category,
                    ),
                ).fetchall()
                if not rows:
                    self._last_import_meta = None
                    return None
        except sqlite3.Error:
            return None
        self._last_import_meta = (
            import_row["dataset_version_id"],
            import_row["source_label"],
            datetime.fromisoformat(import_row["created_at"].replace("Z", "+00:00")),
        )
        return tuple(
            DestinationRecord(
                row["id"],
                row["name"],
                row["category"],
                row["region_id"],
                row["latitude"],
                row["longitude"],
                row["visits"],
                "good"
                if row["visits"] >= 12000
                else "attention"
                if row["visits"] >= 7000
                else "review",
            )
            for row in rows
        )

    def _sum_imported_category(
        self, region_id: str, period_start: date, period_end: date, category: str
    ) -> int:
        return sum(
            item.visits
            for item in self._imported_destinations(region_id, period_start, period_end, category)
            or ()
        )

    def _imported_provenance(self) -> Provenance:
        version, source, updated = self._last_import_meta or (
            "accepted-import",
            "Data import CSV",
            datetime.now(timezone.utc),
        )
        return Provenance("external_imported", version, source, updated, False)

    _destinations = (
        DestinationRecord(
            "keraton-kasunanan",
            "Keraton Kasunanan Surakarta",
            "Sejarah",
            "surakarta",
            -7.578238,
            110.825506,
            18420,
            "good",
        ),
        DestinationRecord(
            "pura-mangkunegaran",
            "Pura Mangkunegaran",
            "Sejarah",
            "surakarta",
            -7.566260,
            110.823100,
            13280,
            "good",
        ),
        DestinationRecord(
            "benteng-vastenburg",
            "Benteng Vastenburg",
            "Sejarah",
            "surakarta",
            -7.571900,
            110.830000,
            11860,
            "good",
        ),
        DestinationRecord(
            "taman-sriwedari",
            "Taman Sriwedari",
            "Rekreasi",
            "surakarta",
            -7.568452,
            110.813423,
            9460,
            "attention",
        ),
        DestinationRecord(
            "taman-balekambang",
            "Taman Balekambang",
            "Rekreasi",
            "surakarta",
            -7.557000,
            110.811000,
            7210,
            "attention",
        ),
        DestinationRecord(
            "museum-radya-pustaka",
            "Museum Radya Pustaka",
            "Sejarah",
            "surakarta",
            -7.568000,
            110.814000,
            6820,
            "good",
        ),
        DestinationRecord(
            "museum-batik-danar-hadi",
            "Museum Batik Danar Hadi",
            "Budaya",
            "surakarta",
            -7.568760,
            110.816370,
            6310,
            "good",
        ),
        DestinationRecord(
            "museum-keris-nusantara",
            "Museum Keris Nusantara",
            "Budaya",
            "surakarta",
            -7.568000,
            110.813000,
            5740,
            "attention",
        ),
        DestinationRecord(
            "museum-tumurun",
            "Museum Tumurun",
            "Seni",
            "surakarta",
            -7.567000,
            110.813000,
            5480,
            "good",
        ),
        DestinationRecord(
            "museum-lokananta",
            "Museum Lokananta",
            "Budaya",
            "surakarta",
            -7.559000,
            110.801000,
            4920,
            "attention",
        ),
        DestinationRecord(
            "monumen-pers-nasional",
            "Monumen Pers Nasional",
            "Sejarah",
            "surakarta",
            -7.565000,
            110.819000,
            4610,
            "attention",
        ),
        DestinationRecord(
            "kampung-batik-kauman",
            "Kampung Batik Kauman",
            "Budaya",
            "surakarta",
            -7.574000,
            110.828000,
            4380,
            "good",
        ),
        DestinationRecord(
            "kampung-batik-laweyan",
            "Kampung Batik Laweyan",
            "Budaya",
            "surakarta",
            -7.571000,
            110.801000,
            4210,
            "good",
        ),
        DestinationRecord(
            "pasar-klewer",
            "Pasar Klewer",
            "Belanja",
            "surakarta",
            -7.575000,
            110.828000,
            3980,
            "attention",
        ),
        DestinationRecord(
            "pasar-gede-hardjonagoro",
            "Pasar Gede Hardjonagoro",
            "Belanja",
            "surakarta",
            -7.569000,
            110.832000,
            3760,
            "attention",
        ),
        DestinationRecord(
            "pasar-antik-triwindu",
            "Pasar Antik Triwindu",
            "Belanja",
            "surakarta",
            -7.568000,
            110.825000,
            3540,
            "review",
        ),
        DestinationRecord(
            "alun-alun-utara",
            "Alun-Alun Utara Surakarta",
            "Ruang publik",
            "surakarta",
            -7.575000,
            110.827000,
            3320,
            "attention",
        ),
        DestinationRecord(
            "alun-alun-kidul",
            "Alun-Alun Kidul Surakarta",
            "Ruang publik",
            "surakarta",
            -7.580000,
            110.825000,
            3160,
            "attention",
        ),
        DestinationRecord(
            "taman-monumen-45",
            "Taman Monumen 45 Banjarsari",
            "Ruang publik",
            "surakarta",
            -7.558000,
            110.826000,
            2910,
            "review",
        ),
        DestinationRecord(
            "taman-tirtonadi",
            "Taman Tirtonadi",
            "Rekreasi",
            "surakarta",
            -7.556000,
            110.819000,
            2740,
            "attention",
        ),
        DestinationRecord(
            "taman-cerdas-jebres",
            "Taman Cerdas Jebres",
            "Rekreasi",
            "surakarta",
            -7.558000,
            110.847000,
            2520,
            "good",
        ),
        DestinationRecord(
            "taman-jayawijaya",
            "Taman Jayawijaya",
            "Rekreasi",
            "surakarta",
            -7.545000,
            110.856000,
            2310,
            "attention",
        ),
        DestinationRecord(
            "masjid-agung-surakarta",
            "Masjid Agung Surakarta",
            "Religi",
            "surakarta",
            -7.575000,
            110.827000,
            5120,
            "good",
        ),
        DestinationRecord(
            "gua-maria-mojosongo",
            "Gua Maria Mojosongo",
            "Religi",
            "surakarta",
            -7.540000,
            110.860000,
            1880,
            "review",
        ),
    )
    _monthly = (42000, 48000, 53000, 49000, 61000, 67000, 64000, 72000, 76000, 81000, 88000, None)

    def _factor(self, visitor_category: VisitorCategory) -> float:
        return {"all": 1.0, "domestic": 0.78, "international": 0.22}[visitor_category]

    def get_overview(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ) -> OverviewRecord:
        imported = self._imported_destinations(
            region_id, period_start, period_end, visitor_category
        )
        if imported is not None:
            total = sum(item.visits for item in imported)
            domestic = (
                self._sum_imported_category(region_id, period_start, period_end, "domestic")
                if visitor_category == "all"
                else total
                if visitor_category == "domestic"
                else 0
            )
            international = (
                self._sum_imported_category(region_id, period_start, period_end, "international")
                if visitor_category == "all"
                else total
                if visitor_category == "international"
                else 0
            )
            return OverviewRecord(
                total,
                domestic,
                international,
                len(imported),
                Period(period_start, period_end),
                self._imported_provenance(),
            )
        factor = self._factor(visitor_category)
        total = round(78120 * factor)
        domestic = (
            round(total * 0.78)
            if visitor_category == "all"
            else (total if visitor_category == "domestic" else 0)
        )
        international = total - domestic
        return OverviewRecord(
            total,
            domestic,
            international,
            len(self._destinations),
            Period(period_start, period_end),
            DEMO_PROVENANCE,
        )

    def get_distribution(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
    ) -> tuple[DistributionRecord, ...]:
        imported = self._imported_destinations(
            region_id, period_start, period_end, visitor_category
        )
        if imported is not None and visitor_category == "all":
            return (
                DistributionRecord(
                    "Domestik",
                    self._sum_imported_category(region_id, period_start, period_end, "domestic"),
                ),
                DistributionRecord(
                    "Mancanegara",
                    self._sum_imported_category(
                        region_id, period_start, period_end, "international"
                    ),
                ),
            )
        overview = self.get_overview(region_id, period_start, period_end, visitor_category)
        return (
            DistributionRecord("Domestik", overview.domestic_visits),
            DistributionRecord("Mancanegara", overview.international_visits),
        )

    def get_trends(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        grain: str,
    ) -> tuple[TrendRecord, ...]:
        imported = self._imported_destinations(
            region_id, period_start, period_end, visitor_category
        )
        if imported is not None:
            records = []
            month_cursor = date(period_start.year, period_start.month, 1)
            while month_cursor <= period_end:
                month_end = date(
                    month_cursor.year,
                    month_cursor.month,
                    monthrange(month_cursor.year, month_cursor.month)[1],
                )
                start = max(period_start, month_cursor)
                end = min(period_end, month_end)
                monthly = self._imported_destinations(region_id, start, end, visitor_category)
                records.append(
                    TrendRecord(start, end, sum(item.visits for item in monthly or ()), None)
                )
                month_cursor = date(
                    month_cursor.year + (month_cursor.month == 12), month_cursor.month % 12 + 1, 1
                )
            return tuple(records)
        if grain != "month":
            return (
                TrendRecord(
                    period_start,
                    period_end,
                    round(
                        sum(value or 0 for value in self._monthly) * self._factor(visitor_category)
                    ),
                    None,
                ),
            )
        factor = self._factor(visitor_category)
        records: list[TrendRecord] = []
        for month, raw_value in enumerate(self._monthly, 1):
            start = date(2026, month, 1)
            end = date(2026, month, monthrange(2026, month)[1])
            if start < period_start or start > period_end:
                continue
            value = round(raw_value * factor) if raw_value is not None else None
            comparison = round(value * 0.88) if value is not None else None
            records.append(TrendRecord(start, end, value, comparison))
        return tuple(records)

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
    ) -> DestinationPage:
        imported = self._imported_destinations(
            region_id, period_start or date(1900, 1, 1), period_end or date(2999, 12, 31), "all"
        )
        items = (
            list(imported)
            if imported is not None
            else [
                item
                for item in self._destinations
                if item.region_id == region_id and item.public_visible
            ]
        )
        if search:
            items = [item for item in items if search.lower() in item.name.lower()]
        if category:
            items = [item for item in items if item.category == category]
        if status:
            items = [item for item in items if item.status == status]
        items.sort(key=lambda item: item.name)
        start = int(cursor or "0")
        selected = items[start : start + limit]
        next_cursor = str(start + limit) if start + limit < len(items) else None
        return DestinationPage(tuple(selected), next_cursor, next_cursor is not None)

    def get_destination(self, destination_id: str) -> DestinationRecord | None:
        imported = self._imported_destinations(
            "surakarta", date(1900, 1, 1), date(2999, 12, 31), "all"
        )
        if imported is not None:
            return next((item for item in imported if item.id == destination_id), None)
        return next(
            (
                item
                for item in self._destinations
                if item.id == destination_id and item.public_visible
            ),
            None,
        )

    def get_map_points(
        self,
        region_id: str,
        period_start: date,
        period_end: date,
        visitor_category: VisitorCategory,
        resolution: str,
    ) -> tuple[MapPoint, ...]:
        imported = self._imported_destinations(
            region_id, period_start, period_end, visitor_category
        )
        if imported is not None:
            return tuple(
                MapPoint(
                    item.id,
                    item.name,
                    item.latitude,
                    item.longitude,
                    item.visits,
                )
                for item in imported
            )
        factor = self._factor(visitor_category)
        return tuple(
            MapPoint(
                item.id,
                item.name,
                item.latitude,
                item.longitude,
                round(item.visits * factor),
            )
            for item in self._destinations
            if item.region_id == region_id
        )

    def get_metadata(self, dataset_key: str | None) -> MetadataRecord:
        if self._last_import_meta:
            version, source, updated = self._last_import_meta
            return MetadataRecord(
                dataset_key or "tourism-overview",
                version,
                source,
                "external_imported",
                "Data berasal dari batch CSV yang telah diterima.",
                updated,
            )
        return MetadataRecord(
            dataset_key or "tourism-overview",
            DEMO_PROVENANCE.dataset_version_id,
            DEMO_PROVENANCE.source_label,
            DEMO_PROVENANCE.data_class,
            "Fixture sintetis untuk demonstrasi kontrak API; tidak mewakili statistik resmi.",
            DEMO_PROVENANCE.last_updated,
        )
