from abc import ABC, abstractmethod
from typing import Any, Dict


class TargetAdapter(ABC):
    name: str

    @abstractmethod
    async def deliver(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver a normalized payload to a target system."""
