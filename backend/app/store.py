import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional
from uuid import uuid4

from app.models import Integration, IntegrationCreate, Run, RunStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                create table if not exists integrations (
                  id text primary key,
                  name text not null,
                  source text not null,
                  target text not null,
                  target_schema text not null,
                  mapping text not null,
                  enabled integer not null,
                  created_at text not null
                );

                create table if not exists runs (
                  id text primary key,
                  integration_id text not null,
                  idempotency_key text not null,
                  source text not null,
                  target text not null,
                  status text not null,
                  raw_payload text not null,
                  mapped_payload text,
                  delivery_response text,
                  error text,
                  created_at text not null,
                  updated_at text not null,
                  unique(integration_id, idempotency_key)
                );
                """
            )

    def seed(self) -> None:
        if list(self.list_integrations()):
            return

        self.create_integration(
            IntegrationCreate(
                name="GitHub issues to customer success CRM",
                source="github",
                target="mock_crm",
                target_schema={
                    "external_id": "string",
                    "title": "string",
                    "customer": "string",
                    "priority": "string",
                    "url": "string",
                },
                mapping={
                    "external_id": "issue.id",
                    "title": "issue.title",
                    "customer": "repository.full_name",
                    "priority": "issue.labels.0.name",
                    "url": "issue.html_url",
                },
            )
        )
        self.create_integration(
            IntegrationCreate(
                name="Slack escalation to CRM note",
                source="slack",
                target="mock_crm",
                target_schema={
                    "external_id": "string",
                    "title": "string",
                    "customer": "string",
                    "priority": "string",
                    "url": "string",
                },
                mapping={
                    "external_id": "event.ts",
                    "title": "event.text",
                    "customer": "team.domain",
                    "priority": "event.priority",
                    "url": "event.permalink",
                },
            )
        )

    def create_integration(self, payload: IntegrationCreate) -> Integration:
        integration = Integration(
            id=f"int_{uuid4().hex[:12]}",
            created_at=utc_now(),
            **payload.model_dump(),
        )
        with self.connect() as connection:
            connection.execute(
                """
                insert into integrations
                (id, name, source, target, target_schema, mapping, enabled, created_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    integration.id,
                    integration.name,
                    integration.source,
                    integration.target,
                    json.dumps(integration.target_schema),
                    json.dumps(integration.mapping),
                    1 if integration.enabled else 0,
                    integration.created_at,
                ),
            )
        return integration

    def list_integrations(self) -> Iterable[Integration]:
        with self.connect() as connection:
            rows = connection.execute(
                "select * from integrations order by created_at asc"
            ).fetchall()
        return [self._integration_from_row(row) for row in rows]

    def find_integration_for_source(self, source: str) -> Optional[Integration]:
        with self.connect() as connection:
            row = connection.execute(
                """
                select * from integrations
                where source = ? and enabled = 1
                order by created_at asc
                limit 1
                """,
                (source,),
            ).fetchone()
        return self._integration_from_row(row) if row else None

    def create_run(
        self,
        integration: Integration,
        raw_payload: Dict[str, Any],
        idempotency_key: str,
    ) -> Run:
        existing = self.get_run_by_idempotency(integration.id, idempotency_key)
        if existing:
            return existing

        now = utc_now()
        run = Run(
            id=f"run_{uuid4().hex[:12]}",
            integration_id=integration.id,
            idempotency_key=idempotency_key,
            source=integration.source,
            target=integration.target,
            status=RunStatus.received,
            raw_payload=raw_payload,
            created_at=now,
            updated_at=now,
        )
        with self.connect() as connection:
            connection.execute(
                """
                insert into runs
                (id, integration_id, idempotency_key, source, target, status,
                 raw_payload, mapped_payload, delivery_response, error,
                 created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.integration_id,
                    run.idempotency_key,
                    run.source,
                    run.target,
                    run.status.value,
                    json.dumps(run.raw_payload),
                    None,
                    None,
                    None,
                    run.created_at,
                    run.updated_at,
                ),
            )
        return run

    def update_run(
        self,
        run_id: str,
        status: RunStatus,
        mapped_payload: Optional[Dict[str, Any]] = None,
        delivery_response: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> Run:
        with self.connect() as connection:
            connection.execute(
                """
                update runs
                set status = ?, mapped_payload = ?, delivery_response = ?,
                    error = ?, updated_at = ?
                where id = ?
                """,
                (
                    status.value,
                    json.dumps(mapped_payload) if mapped_payload is not None else None,
                    json.dumps(delivery_response)
                    if delivery_response is not None
                    else None,
                    error,
                    utc_now(),
                    run_id,
                ),
            )
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Run {run_id} not found after update")
        return run

    def get_run(self, run_id: str) -> Optional[Run]:
        with self.connect() as connection:
            row = connection.execute(
                "select * from runs where id = ?",
                (run_id,),
            ).fetchone()
        return self._run_from_row(row) if row else None

    def get_run_by_idempotency(
        self, integration_id: str, idempotency_key: str
    ) -> Optional[Run]:
        with self.connect() as connection:
            row = connection.execute(
                """
                select * from runs
                where integration_id = ? and idempotency_key = ?
                """,
                (integration_id, idempotency_key),
            ).fetchone()
        return self._run_from_row(row) if row else None

    def list_runs(self, limit: int = 50) -> Iterable[Run]:
        with self.connect() as connection:
            rows = connection.execute(
                "select * from runs order by created_at desc limit ?",
                (limit,),
            ).fetchall()
        return [self._run_from_row(row) for row in rows]

    def _integration_from_row(self, row: sqlite3.Row) -> Integration:
        return Integration(
            id=row["id"],
            name=row["name"],
            source=row["source"],
            target=row["target"],
            target_schema=json.loads(row["target_schema"]),
            mapping=json.loads(row["mapping"]),
            enabled=bool(row["enabled"]),
            created_at=row["created_at"],
        )

    def _run_from_row(self, row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            integration_id=row["integration_id"],
            idempotency_key=row["idempotency_key"],
            source=row["source"],
            target=row["target"],
            status=RunStatus(row["status"]),
            raw_payload=json.loads(row["raw_payload"]),
            mapped_payload=json.loads(row["mapped_payload"])
            if row["mapped_payload"]
            else None,
            delivery_response=json.loads(row["delivery_response"])
            if row["delivery_response"]
            else None,
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
