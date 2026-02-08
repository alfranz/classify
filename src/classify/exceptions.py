"""Exception types for classify SDK."""


class ClassifyError(Exception):
    """Base exception for classify SDK errors."""


class ClassifyTimeoutError(ClassifyError):
    """Raised when a batch job exceeds the specified timeout."""
