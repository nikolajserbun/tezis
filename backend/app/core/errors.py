from typing import Any


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: Any = None):
        super().__init__(message)
        self.message = message
        self.details = details


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class PaymentError(AppError):
    status_code = 402
    code = "payment_error"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"
