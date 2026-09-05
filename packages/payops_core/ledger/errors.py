class InjectedFailure(RuntimeError):
    """Raised inside an open transfer so the database transaction must roll back."""


class ConsistencyError(ValueError):
    """Invariant failed before or after applying debit/credit."""
