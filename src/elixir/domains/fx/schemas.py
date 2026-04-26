from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class FXRateResponse(BaseModel):
    """Response schema for a single cached FX rate row."""

    model_config = ConfigDict(from_attributes=True)

    from_currency: str
    to_currency: str
    rate: Decimal
    fetched_at: datetime


class ConvertResponse(BaseModel):
    """Response schema for a currency conversion query."""

    model_config = ConfigDict(from_attributes=True)

    from_currency: str
    to_currency: str
    original_amount: Decimal
    converted_amount: Decimal
    rate_used: Decimal
    fetched_at: datetime
