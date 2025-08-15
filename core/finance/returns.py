from __future__ import annotations

"""Utilities for calculating investment returns."""

from decimal import Decimal


def portfolio_return(
    patrimonio: Decimal,
    patrimonio_first_day: Decimal,
    investments_period: Decimal,
) -> Decimal | None:
    """Compute the portfolio return percentage for a period.

    The formula is::

        (Patrimonio - (PatrimonioFirstDay + InvestimentosPeriodo))
        / (PatrimonioFirstDay + InvestimentosPeriodo)

    The result is multiplied by 100 to express a percentage. If the
    denominator is zero or negative, ``None`` is returned.
    """

    denom = patrimonio_first_day + investments_period
    if denom <= 0:
        return None
    return (patrimonio - (patrimonio_first_day + investments_period)) / denom * Decimal("100")
