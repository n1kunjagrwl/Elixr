"""
ImportProcessingWorkflow orchestrates bulk historical transaction imports.

The human-in-the-loop mapping confirmation and row parsing work belong in
activities so the workflow stays deterministic.
"""

from temporalio import workflow


@workflow.defn
class ImportProcessingWorkflow:
    @workflow.run
    async def run(
        self,
        job_id: str,
        user_id: str,
        file_path: str,
        source_type: str,
    ) -> None:
        pass
