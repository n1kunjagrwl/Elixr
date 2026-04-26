import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    type: str
    title: str
    body: str
    route: str
    primary_entity_id: uuid.UUID | None
    secondary_entity_id: uuid.UUID | None
    period_start: date | None
    read_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
