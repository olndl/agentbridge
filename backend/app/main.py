import os
from typing import Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.mapper import suggest_mapping
from app.models import (
    Integration,
    IntegrationCreate,
    MappingSuggestionRequest,
    MappingSuggestionResponse,
    Run,
    WebhookResponse,
)
from app.pipeline import process_run
from app.store import Store


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentBridge API",
        description="Integration runtime for AI-agent workflows.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    store = Store(os.getenv("AGENTBRIDGE_DB", "data/agentbridge.db"))
    store.seed()
    app.state.store = store

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/integrations", response_model=list[Integration])
    def list_integrations(store: Store = Depends(get_store)) -> list[Integration]:
        return list(store.list_integrations())

    @app.post("/integrations", response_model=Integration, status_code=201)
    def create_integration(
        payload: IntegrationCreate,
        store: Store = Depends(get_store),
    ) -> Integration:
        return store.create_integration(payload)

    @app.get("/runs", response_model=list[Run])
    def list_runs(store: Store = Depends(get_store)) -> list[Run]:
        return list(store.list_runs())

    @app.get("/runs/{run_id}", response_model=Run)
    def get_run(run_id: str, store: Store = Depends(get_store)) -> Run:
        run = store.get_run(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return run

    @app.post("/webhooks/{source}", response_model=WebhookResponse)
    async def receive_webhook(
        source: str,
        request: Request,
        x_idempotency_key: Optional[str] = Header(default=None),
        store: Store = Depends(get_store),
    ) -> WebhookResponse:
        integration = store.find_integration_for_source(source)
        if integration is None:
            raise HTTPException(
                status_code=404,
                detail=f"No enabled integration for source '{source}'",
            )

        payload = await request.json()
        run = store.create_run(
            integration=integration,
            raw_payload=payload,
            idempotency_key=x_idempotency_key or f"generated-{uuid4()}",
        )
        if run.status.value in {"delivered", "failed"}:
            return WebhookResponse(
                run_id=run.id,
                status=run.status,
                message="Duplicate webhook ignored because idempotency key was reused.",
            )

        processed = await process_run(store, run)
        return WebhookResponse(
            run_id=processed.id,
            status=processed.status,
            message="Webhook processed.",
        )

    @app.post("/mapping/suggest", response_model=MappingSuggestionResponse)
    def suggest_mapping_endpoint(
        payload: MappingSuggestionRequest,
    ) -> MappingSuggestionResponse:
        mapping, source_fields, target_fields = suggest_mapping(
            payload.sample_payload,
            payload.target_schema,
        )
        return MappingSuggestionResponse(
            mapping=mapping,
            source_fields=source_fields,
            target_fields=target_fields,
        )

    return app


def get_store(request: Request) -> Store:
    return request.app.state.store


app = create_app()
