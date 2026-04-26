from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class ImportBatchReady:
    event_type: ClassVar[str] = "import_.ImportBatchReady"

    job_id: uuid.UUID
    user_id: uuid.UUID
    rows: list[dict]

    def to_payload(self) -> dict:
        return {
            "job_id": str(self.job_id),
            "user_id": str(self.user_id),
            "rows": self.rows,
        }


@dataclass
class ImportCompleted:
    event_type: ClassVar[str] = "import_.ImportCompleted"

    job_id: uuid.UUID
    user_id: uuid.UUID
    imported_rows: int
    skipped_rows: int
    failed_rows: int

    def to_payload(self) -> dict:
        return {
            "job_id": str(self.job_id),
            "user_id": str(self.user_id),
            "imported_rows": self.imported_rows,
            "skipped_rows": self.skipped_rows,
            "failed_rows": self.failed_rows,
        }
