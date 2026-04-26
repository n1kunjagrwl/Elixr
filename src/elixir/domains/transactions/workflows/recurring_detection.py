"""
RecurringTransactionDetectionWorkflow labels existing transactions as
`recurring_detected` when they match a recurring pattern.

The concrete scan/update logic belongs in activities so workflow code remains
deterministic.
"""

from temporalio import workflow


@workflow.defn
class RecurringTransactionDetectionWorkflow:
    @workflow.run
    async def run(self) -> None:
        pass


WORKFLOWS = [RecurringTransactionDetectionWorkflow]
ACTIVITIES: list = []
