from fastapi import HTTPException, status


class AppException(HTTPException):
    def __init__(self, detail: str, status_code: int = 400, code: str | None = None):
        super().__init__(status_code=status_code, detail=detail)
        self.code = code


class RateLimitExceeded(AppException):
    def __init__(self):
        super().__init__(
            detail="Rate limit exceeded. Please wait before trying again.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
        )


class InvalidSession(AppException):
    def __init__(self):
        super().__init__(
            detail="Invalid or expired session.",
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_SESSION",
        )


class ServiceUnavailable(AppException):
    def __init__(self, service: str = "AI"):
        super().__init__(
            detail=f"{service} service is temporarily unavailable. Please try again later.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="SERVICE_UNAVAILABLE",
        )
