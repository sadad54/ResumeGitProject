import uuid

from proofhire_contracts import ProfileFactType
from pydantic import BaseModel


class ProfileFactPublic(BaseModel):
    id: uuid.UUID
    type: ProfileFactType
    value_json: dict
    source: str
    immutable: bool
    confirmed: bool

    model_config = {"from_attributes": True}


class ProfileFactPatch(BaseModel):
    confirmed: bool | None = None
    value_json: dict | None = None
