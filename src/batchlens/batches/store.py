"""The batches and their store: five tables in the app's own SQLite database.

| Table | Holds |
|---|---|
| ``batches`` | one row per batch: product, the reference flag |
| ``phase_executions`` | what happened on an asset (PlantCraft's ``asset_id``) between two instants |
| ``samples`` | an offline sample and when it was collected |
| ``assay_results`` | one analyte of one sample, with the time the result became available |
| ``pool_measurements`` | a pool's volume and concentration |

Assets, signals and online values stay in PlantCraft: a phase execution keeps only the asset's
id. Every instant is UTC text (``utc_iso``). ``SCHEMA`` is the tables as a new installation
makes them; once a version is installed somewhere, a change is a named step in ``MIGRATIONS``
(docs/data.md).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import astuple, fields
from datetime import datetime
from typing import Any

from plantcraft_sdk.server.store import Store
from plantcraft_sdk.utc import utc_iso

from batchlens.batches.models import (
    AssayResult,
    Batch,
    BatchRecord,
    PhaseExecution,
    PoolMeasurement,
    Sample,
)

BATCH_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
# Table and the column each record field is stored in ("end" is an SQL keyword).
TABLES: dict[type, str] = {
    Batch: "batches",
    PhaseExecution: "phase_executions",
    Sample: "samples",
    AssayResult: "assay_results",
    PoolMeasurement: "pool_measurements",
}
COLUMNS = {"start": "start_at", "end": "end_at"}
INSTANTS = {
    "created_at",
    "start_at",
    "end_at",
    "collected_at",
    "result_available_at",
    "measured_at",
}


def _columns(kind: type) -> list[str]:
    return [COLUMNS.get(field.name, field.name) for field in fields(kind)]


def _stored(value: Any) -> Any:
    return utc_iso(value) if isinstance(value, datetime) else value


def _row(kind: type, row: sqlite3.Row) -> Any:
    values = [
        datetime.fromisoformat(row[column]) if column in INSTANTS else row[column]
        for column in _columns(kind)
    ]
    if kind is Batch:
        values[2] = bool(values[2])
    return kind(*values)


class BatchStore(Store):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS batches (
        batch_id TEXT PRIMARY KEY,
        product TEXT NOT NULL,
        is_reference INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        provenance TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS phase_executions (
        phase_id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        kind TEXT NOT NULL,
        asset_id TEXT NOT NULL,
        start_at TEXT NOT NULL,
        end_at TEXT NOT NULL,
        provenance TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS phase_executions_batch ON phase_executions (batch_id, start_at);
    CREATE TABLE IF NOT EXISTS samples (
        sample_id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        collected_at TEXT NOT NULL,
        provenance TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS samples_batch ON samples (batch_id, collected_at);
    CREATE TABLE IF NOT EXISTS assay_results (
        result_id TEXT PRIMARY KEY,
        sample_id TEXT NOT NULL,
        analyte TEXT NOT NULL,
        value REAL NOT NULL,
        unit TEXT NOT NULL,
        method TEXT NOT NULL,
        result_available_at TEXT NOT NULL,
        validity TEXT NOT NULL,
        provenance TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS assay_results_sample ON assay_results (sample_id);
    CREATE TABLE IF NOT EXISTS pool_measurements (
        measurement_id TEXT PRIMARY KEY,
        batch_id TEXT NOT NULL,
        phase_id TEXT NOT NULL,
        pool TEXT NOT NULL,
        volume REAL NOT NULL,
        volume_unit TEXT NOT NULL,
        concentration REAL NOT NULL,
        concentration_unit TEXT NOT NULL,
        method TEXT NOT NULL,
        measured_at TEXT NOT NULL,
        result_available_at TEXT NOT NULL,
        provenance TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS pool_measurements_batch ON pool_measurements (batch_id, measured_at);
    """

    def save(self, record: BatchRecord) -> None:
        """The whole aggregate, replacing what was stored under the same batch id."""

        batch_id = record.batch.batch_id
        rows = [record.batch, *record.phases, *record.samples, *record.results, *record.pools]
        with self._lock, self._connect() as connection:
            connection.execute(
                "DELETE FROM assay_results WHERE sample_id IN "
                "(SELECT sample_id FROM samples WHERE batch_id = ?)",
                (batch_id,),
            )
            for table in ("pool_measurements", "samples", "phase_executions", "batches"):
                connection.execute(f"DELETE FROM {table} WHERE batch_id = ?", (batch_id,))
            for row in rows:
                columns = _columns(type(row))
                connection.execute(
                    f"INSERT INTO {TABLES[type(row)]} ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' * len(columns))})",
                    [_stored(value) for value in astuple(row)],
                )

    def summaries(self) -> list[tuple[Batch, tuple[PhaseExecution, ...]]]:
        """Every batch with its phase executions, oldest first."""

        with self._lock, self._connect() as connection:
            batches = connection.execute("SELECT * FROM batches ORDER BY created_at, batch_id")
            phases = connection.execute("SELECT * FROM phase_executions ORDER BY start_at")
            by_batch: dict[str, list[PhaseExecution]] = {}
            for row in phases.fetchall():
                by_batch.setdefault(row["batch_id"], []).append(_row(PhaseExecution, row))
            return [
                (_row(Batch, row), tuple(by_batch.get(row["batch_id"], ())))
                for row in batches.fetchall()
            ]

    def get(self, batch_id: str) -> BatchRecord | None:
        if not BATCH_ID.match(batch_id):
            return None
        with self._lock, self._connect() as connection:

            def rows(kind: type, where: str, order: str) -> tuple[Any, ...]:
                query = f"SELECT * FROM {TABLES[kind]} WHERE {where} ORDER BY {order}"
                return tuple(_row(kind, row) for row in connection.execute(query, (batch_id,)))

            batch = rows(Batch, "batch_id = ?", "batch_id")
            if not batch:
                return None
            return BatchRecord(
                batch[0],
                rows(PhaseExecution, "batch_id = ?", "start_at"),
                rows(Sample, "batch_id = ?", "collected_at"),
                rows(
                    AssayResult,
                    "sample_id IN (SELECT sample_id FROM samples WHERE batch_id = ?)",
                    "result_id",
                ),
                rows(PoolMeasurement, "batch_id = ?", "measured_at"),
            )

    def reference_id(self) -> str | None:
        """The batch the others are compared with (the oldest one marked as reference)."""

        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT batch_id FROM batches WHERE is_reference = 1 ORDER BY created_at LIMIT 1"
            ).fetchone()
        return row["batch_id"] if row else None
