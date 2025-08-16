from decimal import Decimal

class EstimationService:
    """Service computing preview estimate based on actual totals."""

    def compute(self, scope, base_amount: Decimal) -> Decimal:
        # Currently simply returns the provided base amount.
        # Placeholder for more complex logic.
        return Decimal(base_amount)


class MissingAmountService:
    """Service computing missing amount for a scope.

    For now, this returns zero and acts as a placeholder for
    a future implementation that may consider budgets or other
    business rules.
    """

    def compute(self, scope, ignore_estimates: bool = False) -> Decimal:
        return Decimal("0")
