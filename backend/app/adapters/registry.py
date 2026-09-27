from app.adapters.base import TargetAdapter
from app.adapters.mock_crm import MockCrmAdapter

TARGET_ADAPTERS = {
    MockCrmAdapter.name: MockCrmAdapter,
}


def get_target_adapter(name: str) -> TargetAdapter:
    adapter = TARGET_ADAPTERS.get(name)
    if adapter is None:
        raise KeyError(f"Unknown target adapter: {name}")
    return adapter()
