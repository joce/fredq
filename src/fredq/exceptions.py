"""fredq-specific exception hierarchy."""

from __future__ import annotations


class FredqError(Exception):
    """Base exception for all fredq errors."""


class FredClientUsageError(FredqError):
    """Raised when the caller misuses the FredClient API."""


class FredApiKeyMissingError(FredqError):
    """Raised when no FRED API key can be located."""

    def __init__(self) -> None:
        """Initialize the missing-key error."""

        super().__init__(
            "FRED API key not found. Set the FRED_API_KEY environment variable "
            "or create a single-line file at ~/.fredq/api_key."
        )


class FredRequestError(FredqError):
    """Raised when FRED rejects an HTTP request."""

    def __init__(
        self,
        status_code: int,
        url: str,
        *,
        reason: str | None = None,
    ) -> None:
        """Initialize the request error."""

        message = f"FRED request rejected with HTTP {status_code} for {url}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.reason = reason


class FredUnavailableError(FredqError):
    """Raised when FRED cannot be reached due to transport failure."""

    def __init__(self, context: str) -> None:
        """Initialize the transport error."""

        super().__init__(f"FRED API unavailable while processing {context}")
        self.context = context
