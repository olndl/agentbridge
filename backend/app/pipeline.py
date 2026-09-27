from app.adapters import get_target_adapter
from app.mapper import apply_mapping
from app.models import Run, RunStatus
from app.store import Store


async def process_run(store: Store, run: Run) -> Run:
    integration = next(
        item
        for item in store.list_integrations()
        if item.id == run.integration_id
    )

    try:
        mapped = apply_mapping(run.raw_payload, integration.mapping)
        store.update_run(run.id, RunStatus.mapped, mapped_payload=mapped)

        adapter = get_target_adapter(integration.target)
        response = await adapter.deliver(mapped)
        return store.update_run(
            run.id,
            RunStatus.delivered,
            mapped_payload=mapped,
            delivery_response=response,
        )
    except Exception as exc:
        return store.update_run(run.id, RunStatus.failed, error=str(exc))
