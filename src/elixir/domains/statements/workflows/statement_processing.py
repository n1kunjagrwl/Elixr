"""
Temporal workflow stub for statement processing.

This workflow orchestrates the following steps:
1. Parse the uploaded file (PDF/CSV) into raw rows
2. Classify each row via the AI categorisation agent
3. For low-confidence rows, send signals back to the frontend and await user input
4. On completion, publish ExtractionCompleted event to trigger the transactions domain
"""
from temporalio import workflow


@workflow.defn
class StatementProcessingWorkflow:
    """
    Durable workflow that processes a statement upload end-to-end.

    Stub implementation — activities and human-in-the-loop signals
    will be added in a future iteration.
    """

    @workflow.run
    async def run(self, job_id: str, upload_id: str) -> None:
        """Entry point — receives job_id and upload_id, drives the pipeline."""
        # Stub: real implementation will call parsing + classification activities
        pass
