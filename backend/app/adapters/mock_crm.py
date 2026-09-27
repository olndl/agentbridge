from typing import Any, Dict
from uuid import uuid4

from app.adapters.base import TargetAdapter


class MockCrmAdapter(TargetAdapter):
    name = "mock_crm"

    async def deliver(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "remote_id": f"crm_{uuid4().hex[:10]}",
            "system": self.name,
            "accepted": True,
            "record": payload,
        }
