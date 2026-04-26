"""
Temporal activity stubs for statement processing.

Activities are the side-effectful steps called by the workflow.
They are retried automatically on failure by Temporal.
"""
from temporalio import activity


class StatementActivities:
    """
    Activity implementations for statement processing.

    Each method decorated with @activity.defn represents one retryable step.
    """

    @activity.defn
    async def parse_statement(self, job_id: str, file_path: str, file_type: str) -> int:
        """
        Parse a bank/credit card statement file and insert RawExtractedRow records.
        Returns the total number of rows parsed.

        Stub — real implementation will call a PDF/CSV parser.
        """
        raise NotImplementedError("parse_statement activity not yet implemented")

    @activity.defn
    async def classify_rows(self, job_id: str) -> int:
        """
        Run AI classification over all pending rows in the job.
        Returns the count of rows that were auto-classified with high confidence.

        Stub — real implementation will call the Google ADK categorisation agent.
        """
        raise NotImplementedError("classify_rows activity not yet implemented")

    @activity.defn
    async def mark_job_completed(self, job_id: str, upload_id: str) -> None:
        """
        Finalise the job and publish ExtractionCompleted outbox event.

        Stub — real implementation will write status + outbox event in one transaction.
        """
        raise NotImplementedError("mark_job_completed activity not yet implemented")
