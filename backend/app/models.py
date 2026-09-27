from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

JsonObject = Dict[str, Any]


class RunStatus(str, Enum):
    received = "received"
    mapped = "mapped"
    delivered = "delivered"
    failed = "failed"


class IntegrationCreate(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    source: str = Field(min_length=2, max_length=40)
    target: str = Field(min_length=2, max_length=40)
    target_schema: JsonObject = Field(default_factory=dict)
    mapping: Dict[str, str] = Field(default_factory=dict)
    enabled: bool = True


class Integration(IntegrationCreate):
    id: str
    created_at: str


class Run(BaseModel):
    id: str
    integration_id: str
    idempotency_key: str
    source: str
    target: str
    status: RunStatus
    raw_payload: JsonObject
    mapped_payload: Optional[JsonObject] = None
    delivery_response: Optional[JsonObject] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str


class WebhookResponse(BaseModel):
    run_id: str
    status: RunStatus
    message: str


class MappingSuggestionRequest(BaseModel):
    sample_payload: JsonObject
    target_schema: JsonObject


class MappingSuggestionResponse(BaseModel):
    mapping: Dict[str, str]
    source_fields: List[str]
    target_fields: List[str]
