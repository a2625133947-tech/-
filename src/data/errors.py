"""Typed data-layer errors, independent of presentation."""


class DataLayerError(Exception):
    pass


class UnsupportedCapability(DataLayerError):
    pass


class ProviderFailure(DataLayerError):
    pass


class RateLimited(ProviderFailure):
    pass


class SchemaChanged(ProviderFailure):
    pass


class InvalidData(DataLayerError):
    pass


class NotPublished(DataLayerError):
    pass


class MissingData(DataLayerError):
    pass


class Conflict(DataLayerError):
    pass


def classify_provider_error(exc: Exception) -> ProviderFailure:
    """Keep public diagnostics typed without copying upstream URLs or credentials."""
    if isinstance(exc, ProviderFailure):
        return exc
    message = str(exc).lower()
    if "429" in message or "rate limit" in message or "too many requests" in message:
        return RateLimited(f"request limited ({type(exc).__name__})")
    return ProviderFailure(f"request failed ({type(exc).__name__})")
