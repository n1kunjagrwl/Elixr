class ElixirError(Exception):
    http_status: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str | None = None, **context):
        self.detail = detail or self.__class__.__name__
        self.context = context
        super().__init__(self.detail)


# ── Auth / Identity ──────────────────────────────────────────────────
class AuthError(ElixirError):
    http_status = 401
    error_code = "AUTH_ERROR"


class TokenExpiredError(AuthError):
    error_code = "TOKEN_EXPIRED"


class TokenInvalidError(AuthError):
    error_code = "TOKEN_INVALID"


class OTPExpiredError(AuthError):
    error_code = "OTP_EXPIRED"


class OTPInvalidError(AuthError):
    error_code = "OTP_INVALID"


class SessionRevokedError(AuthError):
    error_code = "SESSION_REVOKED"


class SessionExpiredError(AuthError):
    error_code = "SESSION_EXPIRED"


# ── Rate Limiting ────────────────────────────────────────────────────
class RateLimitError(ElixirError):
    http_status = 429
    error_code = "RATE_LIMIT_EXCEEDED"


class OTPLockedError(RateLimitError):
    error_code = "OTP_LOCKED"


# ── Domain / Business Errors ─────────────────────────────────────────
class NotFoundError(ElixirError):
    http_status = 404
    error_code = "NOT_FOUND"


class AccountNotFoundError(NotFoundError):
    error_code = "ACCOUNT_NOT_FOUND"


class TransactionNotFoundError(NotFoundError):
    error_code = "TRANSACTION_NOT_FOUND"


class UserNotFoundError(NotFoundError):
    error_code = "USER_NOT_FOUND"


class ForbiddenError(ElixirError):
    http_status = 403
    error_code = "FORBIDDEN"


class AccountBelongsToAnotherUserError(ForbiddenError):
    error_code = "ACCOUNT_BELONGS_TO_ANOTHER_USER"


class ConflictError(ElixirError):
    http_status = 409
    error_code = "CONFLICT"


class DuplicateTransactionError(ConflictError):
    error_code = "DUPLICATE_TRANSACTION"


class AccountHasLinkedTransactionsError(ConflictError):
    error_code = "ACCOUNT_HAS_LINKED_TRANSACTIONS"


class UnprocessableError(ElixirError):
    http_status = 422
    error_code = "UNPROCESSABLE"


class FXRateUnavailableError(UnprocessableError):
    error_code = "FX_RATE_UNAVAILABLE"


# ── Peers Errors ─────────────────────────────────────────────────────────────
class PeerContactNotFoundError(NotFoundError):
    error_code = "PEER_CONTACT_NOT_FOUND"


class PeerBalanceNotFoundError(NotFoundError):
    error_code = "PEER_BALANCE_NOT_FOUND"


class ContactHasOpenBalancesError(ConflictError):
    error_code = "CONTACT_HAS_OPEN_BALANCES"


class SettlementExceedsRemainingError(UnprocessableError):
    error_code = "SETTLEMENT_EXCEEDS_REMAINING"


# ── Categorization Errors ────────────────────────────────────────────────────
class CategoryNotFoundError(NotFoundError):
    error_code = "CATEGORY_NOT_FOUND"


class CannotEditDefaultCategoryError(ForbiddenError):
    error_code = "CANNOT_EDIT_DEFAULT_CATEGORY"


class DuplicateSlugError(ConflictError):
    error_code = "DUPLICATE_SLUG"


class InvalidRegexPatternError(UnprocessableError):
    error_code = "INVALID_REGEX_PATTERN"


class RuleNotFoundError(NotFoundError):
    error_code = "RULE_NOT_FOUND"


class CategoryKindForbiddenError(ForbiddenError):
    error_code = "CATEGORY_KIND_FORBIDDEN"


# ── Statements Errors ────────────────────────────────────────────────────────
class UploadNotFoundError(NotFoundError):
    error_code = "UPLOAD_NOT_FOUND"


class ExtractionJobNotFoundError(NotFoundError):
    error_code = "EXTRACTION_JOB_NOT_FOUND"


class RowNotFoundError(NotFoundError):
    error_code = "ROW_NOT_FOUND"


class RowAlreadyClassifiedError(ConflictError):
    error_code = "ROW_ALREADY_CLASSIFIED"


class ItemAmountMismatchError(UnprocessableError):
    error_code = "ITEM_AMOUNT_MISMATCH"


class FileTooLargeError(UnprocessableError):
    error_code = "FILE_TOO_LARGE"


class InvalidFileTypeError(UnprocessableError):
    error_code = "INVALID_FILE_TYPE"


# ── Import Errors ────────────────────────────────────────────────────────────
class ImportJobNotFoundError(NotFoundError):
    error_code = "IMPORT_JOB_NOT_FOUND"


class InvalidColumnMappingError(UnprocessableError):
    error_code = "INVALID_COLUMN_MAPPING"


class ImportJobStateError(ConflictError):
    error_code = "IMPORT_JOB_STATE_ERROR"


# ── Earnings Errors ──────────────────────────────────────────────────────────
class EarningNotFoundError(NotFoundError):
    error_code = "EARNING_NOT_FOUND"


class EarningSourceNotFoundError(NotFoundError):
    error_code = "EARNING_SOURCE_NOT_FOUND"


class TransactionAlreadyClassifiedError(ConflictError):
    error_code = "TRANSACTION_ALREADY_CLASSIFIED"


# ── Investments Errors ───────────────────────────────────────────────────────
class InstrumentNotFoundError(NotFoundError):
    error_code = "INSTRUMENT_NOT_FOUND"


class HoldingNotFoundError(NotFoundError):
    error_code = "HOLDING_NOT_FOUND"


class DuplicateHoldingError(ConflictError):
    error_code = "DUPLICATE_HOLDING"


class SIPNotFoundError(NotFoundError):
    error_code = "SIP_NOT_FOUND"


class FDDetailsRequiredError(UnprocessableError):
    error_code = "FD_DETAILS_REQUIRED"


class FDDetailsAlreadyExistError(ConflictError):
    error_code = "FD_DETAILS_ALREADY_EXIST"


# ── Budgets Errors ────────────────────────────────────────────────────────────
class BudgetGoalNotFoundError(NotFoundError):
    error_code = "BUDGET_GOAL_NOT_FOUND"


# ── Notifications Errors ──────────────────────────────────────────────────────
class NotificationNotFoundError(NotFoundError):
    error_code = "NOTIFICATION_NOT_FOUND"


class InvalidPeriodConfigError(UnprocessableError):
    error_code = "INVALID_PERIOD_CONFIG"


# ── Infrastructure Errors ────────────────────────────────────────────
class ExternalServiceError(ElixirError):
    http_status = 502
    error_code = "EXTERNAL_SERVICE_ERROR"


class TwilioError(ExternalServiceError):
    error_code = "TWILIO_ERROR"


class TemporalError(ExternalServiceError):
    error_code = "TEMPORAL_ERROR"
