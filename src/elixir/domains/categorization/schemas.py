from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ── Category Schemas ──────────────────────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str
    slug: str
    kind: str  # validated in service: only expense|income allowed from API
    icon: str | None = None
    parent_id: uuid.UUID | None = None


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    is_active: bool | None = None


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    kind: str
    icon: str | None
    is_default: bool
    parent_id: uuid.UUID | None
    user_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


# ── Rule Schemas ───────────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    pattern: str
    match_type: str  # contains|starts_with|exact|regex
    category_id: uuid.UUID
    priority: int = 0


class RuleUpdate(BaseModel):
    pattern: str | None = None
    match_type: str | None = None
    category_id: uuid.UUID | None = None
    priority: int | None = None
    is_active: bool | None = None


class RuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    pattern: str
    match_type: str
    category_id: uuid.UUID
    priority: int
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


# ── Suggestion Schemas ────────────────────────────────────────────────────────

class CategorySuggestion(BaseModel):
    category_id: uuid.UUID | None
    category_name: str | None
    confidence: float
    source: Literal["rule", "ai", "none"]
    item_suggestions: list[str] = []
