"""Shared helpers for date and period parsing/formatting."""

from datetime import date, datetime

from dateutil.relativedelta import relativedelta


def period_str(dt) -> str:
    """Convert a date-like object to ``YYYY-MM``."""
    return dt.strftime("%Y-%m")


def period_key(year: int, month: int) -> str:
    """Build a ``YYYY-MM`` key from numeric year/month values."""
    return f"{int(year):04d}-{int(month):02d}"


def shift_period(period: str, delta_months: int = 1) -> str:
    """Shift a ``YYYY-MM`` period string by the requested number of months."""
    dt = datetime.strptime(period, "%Y-%m")
    return (dt + relativedelta(months=delta_months)).strftime("%Y-%m")


def add_one_month(period: str) -> str:
    """Backward-compatible alias for moving a period one month forward."""
    return shift_period(period, 1)


def period_label(year: int, month: int, fmt: str = "%b/%y") -> str:
    """Format a year/month pair using a strftime-compatible format."""
    return date(int(year), int(month), 1).strftime(fmt)


def parse_safe_date(value: str | None, fallback: date) -> date:
    """Safely parse a date and fall back to the provided default."""
    if not value:
        return fallback

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m"):
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.date()
        except (TypeError, ValueError):
            continue
    return fallback


def parse_optional_safe_date(value: str | None) -> date | None:
    """Safely parse a date and return ``None`` when it is missing or invalid."""
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m"):
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.date()
        except (TypeError, ValueError):
            continue
    return None
