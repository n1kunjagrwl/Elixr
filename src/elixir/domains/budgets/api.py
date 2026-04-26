import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from elixir.domains.budgets.schemas import (
    BudgetGoalCreate,
    BudgetGoalUpdate,
    BudgetGoalWithProgress,
)
from elixir.domains.budgets.services import BudgetsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ────────────────────────────────────────────────────────────

def get_budgets_service(
    db=Depends(get_db_session),
) -> BudgetsService:
    return BudgetsService(db=db)


BudgetsSvc = Annotated[BudgetsService, Depends(get_budgets_service)]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[BudgetGoalWithProgress])
async def get_budgets(ctx: RequestCtx, svc: BudgetsSvc):
    """List all active budget goals with current period progress."""
    return await svc.list_goals(ctx.user_id)


@router.post("", response_model=BudgetGoalWithProgress, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: BudgetGoalCreate,
    ctx: RequestCtx,
    svc: BudgetsSvc,
):
    """Create a new budget goal."""
    return await svc.create_goal(ctx.user_id, body)


@router.get("/{goal_id}", response_model=BudgetGoalWithProgress)
async def get_budget(
    goal_id: uuid.UUID,
    ctx: RequestCtx,
    svc: BudgetsSvc,
):
    """Get a single budget goal with current period progress."""
    return await svc.get_goal(ctx.user_id, goal_id)


@router.patch("/{goal_id}", response_model=BudgetGoalWithProgress)
async def edit_budget(
    goal_id: uuid.UUID,
    body: BudgetGoalUpdate,
    ctx: RequestCtx,
    svc: BudgetsSvc,
):
    """Partially update a budget goal."""
    return await svc.edit_goal(ctx.user_id, goal_id, body)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_budget(
    goal_id: uuid.UUID,
    ctx: RequestCtx,
    svc: BudgetsSvc,
):
    """Deactivate (soft-delete) a budget goal."""
    await svc.deactivate_goal(ctx.user_id, goal_id)
