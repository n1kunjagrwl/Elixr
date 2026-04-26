import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from elixir.domains.categorization.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategoryUpdate,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
)
from elixir.domains.categorization.services import CategorizationService
from elixir.runtime.dependencies import RequestCtx, get_db_session

# Two routers: categories (mounted at /categories) and rules (mounted at /categorization-rules)
router = APIRouter()
rules_router = APIRouter()


# ── Service factory ───────────────────────────────────────────────────────────

def get_categorization_service(
    request: Request,
    db=Depends(get_db_session),
) -> CategorizationService:
    return CategorizationService(
        db=db,
        settings=request.app.state.settings,
    )


CategorizationSvc = Annotated[CategorizationService, Depends(get_categorization_service)]


# ── Category Endpoints ────────────────────────────────────────────────────────

@router.get("", response_model=list[CategoryResponse])
async def get_categories(ctx: RequestCtx, svc: CategorizationSvc):
    """List all visible categories for the authenticated user (defaults + user custom)."""
    return await svc.list_categories(ctx.user_id)


@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    ctx: RequestCtx,
    svc: CategorizationSvc,
):
    """Create a custom category (kind must be 'expense' or 'income')."""
    return await svc.create_category(ctx.user_id, body)


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    ctx: RequestCtx,
    svc: CategorizationSvc,
):
    """Partially update a user-owned, non-default category."""
    return await svc.update_category(ctx.user_id, category_id, body)


# ── Rules Endpoints ───────────────────────────────────────────────────────────

@rules_router.get("", response_model=list[RuleResponse])
async def get_rules(ctx: RequestCtx, svc: CategorizationSvc):
    """List all categorization rules for the authenticated user (ordered by priority DESC)."""
    return await svc.list_rules(ctx.user_id)


@rules_router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: RuleCreate,
    ctx: RequestCtx,
    svc: CategorizationSvc,
):
    """Create a new categorization rule."""
    return await svc.create_rule(ctx.user_id, body)


@rules_router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: RuleUpdate,
    ctx: RequestCtx,
    svc: CategorizationSvc,
):
    """Partially update a categorization rule."""
    return await svc.update_rule(ctx.user_id, rule_id, body)


@rules_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: uuid.UUID,
    ctx: RequestCtx,
    svc: CategorizationSvc,
):
    """Delete a categorization rule."""
    await svc.delete_rule(ctx.user_id, rule_id)
