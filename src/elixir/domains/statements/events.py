from typing import ClassVar


class StatementUploaded:
    event_type: ClassVar[str] = "statements.StatementUploaded"

    def __init__(
        self,
        upload_id: str,
        user_id: str,
        account_id: str,
        file_type: str,
    ) -> None:
        self.upload_id = upload_id
        self.user_id = user_id
        self.account_id = account_id
        self.file_type = file_type

    def to_payload(self) -> dict:
        return {
            "upload_id": self.upload_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "file_type": self.file_type,
        }


class ExtractionCompleted:
    event_type: ClassVar[str] = "statements.ExtractionCompleted"

    def __init__(
        self,
        job_id: str,
        upload_id: str,
        user_id: str,
        account_id: str,
        account_kind: str,
        classified_rows: list,
    ) -> None:
        self.job_id = job_id
        self.upload_id = upload_id
        self.user_id = user_id
        self.account_id = account_id
        self.account_kind = account_kind
        self.classified_rows = classified_rows

    def to_payload(self) -> dict:
        return {
            "job_id": self.job_id,
            "upload_id": self.upload_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "account_kind": self.account_kind,
            "classified_rows": self.classified_rows,
        }


class ExtractionPartiallyCompleted:
    event_type: ClassVar[str] = "statements.ExtractionPartiallyCompleted"

    def __init__(
        self,
        job_id: str,
        upload_id: str,
        user_id: str,
        account_id: str,
        account_kind: str,
        classified_rows: list,
        discarded_from_date: str | None,
        discarded_to_date: str | None,
    ) -> None:
        self.job_id = job_id
        self.upload_id = upload_id
        self.user_id = user_id
        self.account_id = account_id
        self.account_kind = account_kind
        self.classified_rows = classified_rows
        self.discarded_from_date = discarded_from_date
        self.discarded_to_date = discarded_to_date

    def to_payload(self) -> dict:
        return {
            "job_id": self.job_id,
            "upload_id": self.upload_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "account_kind": self.account_kind,
            "classified_rows": self.classified_rows,
            "discarded_from_date": self.discarded_from_date,
            "discarded_to_date": self.discarded_to_date,
        }
