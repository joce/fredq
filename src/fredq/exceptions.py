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
        body: str | None = None,
    ) -> None:
        """Initialize the request error."""

        message = f"FRED request rejected with HTTP {status_code} for {url}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.reason = reason
        # Raw response body (API-key material scrubbed by the client) so
        # error payload shapes can serve as corpus evidence.
        self.body = body


class FredUnavailableError(FredqError):
    """Raised when FRED cannot be reached due to transport failure."""

    def __init__(self, context: str) -> None:
        """Initialize the transport error."""

        super().__init__(f"FRED API unavailable while processing {context}")
        self.context = context


class FredApiError(FredqError):
    """Raised when FRED answers with its structured error payload.

    FRED reports every request-level failure — unknown ids, bad parameter
    values, unregistered API keys — as an HTTP 4xx/5xx whose JSON body is
    ``{"error_code": <int>, "error_message": <str>}``, with no structural
    difference between the causes (corpus evidence, 2026-07-05). There is
    deliberately no not-found subclass: distinguishing "does not exist"
    from other 400s would require matching message wording, which is
    forbidden by the error-mapping law.

    ``error_code`` is ``None`` only for the malformed-response contract
    (an HTTP 200 whose body is not a JSON object).
    """

    def __init__(
        self,
        *,
        error_message: str,
        error_code: int | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize the API error."""

        status_note = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"FRED API error{status_note}: {error_message}")
        self.error_code = error_code
        self.error_message = error_message
        self.status_code = status_code
