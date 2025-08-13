import logging
from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.models import Sum, Q

from ..models import Account, AccountBalance, DatePeriod, Transaction, Category


logger = logging.getLogger(__name__)


class FinanceEstimationService:
    """Service for financial estimation and reconciliation."""

    def __init__(self, user):
        self.user = user

    def get_period_balances(self, period):
        """Return account balances grouped by account type for a period."""
        if not period:
            return {}

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT at.name, SUM(ab.reported_balance)
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_accounttype at ON a.account_type_id = at.id
                WHERE a.user_id = %s AND ab.period_id = %s
                GROUP BY at.name
                """,
                [self.user.id, period.id],
            )
            balances = {}
            for account_type, balance in cursor.fetchall():
                balances[account_type] = Decimal(str(balance or 0))
            return balances

    def get_next_period(self, period):
        """Return the DatePeriod immediately after the given period."""
        try:
            if period.month == 12:
                return DatePeriod.objects.get(year=period.year + 1, month=1)
            return DatePeriod.objects.get(year=period.year, month=period.month + 1)
        except DatePeriod.DoesNotExist:
            return None

    def get_estimation_summary(self, period):
        """Calculate estimation status for a period."""
        try:
            next_period = self.get_next_period(period)
            current_balances = self.get_period_balances(period)
            next_balances = (
                self.get_period_balances(next_period) if next_period else {}
            )

            real_tx = Transaction.objects.filter(
                user=self.user, period=period, is_estimated=False
            ).aggregate(
                income=Sum("amount", filter=Q(type="IN")) or Decimal("0"),
                expenses=Sum("amount", filter=Q(type="EX")) or Decimal("0"),
                investments=Sum("amount", filter=Q(type="IV")) or Decimal("0"),
            )

            income_inserted = real_tx["income"] or Decimal("0")
            expense_inserted = abs(real_tx["expenses"] or Decimal("0"))
            investment_inserted = real_tx["investments"] or Decimal("0")

            savings_current = current_balances.get("Savings", Decimal("0"))
            savings_next = next_balances.get("Savings", Decimal("0"))
            savings_diff = savings_next - savings_current

            estimated_expenses = income_inserted + savings_diff - investment_inserted
            missing_expenses = max(Decimal("0"), estimated_expenses - expense_inserted)
            missing_income = max(Decimal("0"), expense_inserted - estimated_expenses)

            status = "balanced"
            status_message = "All transactions reconciled"
            estimated_amount = Decimal("0")
            estimated_type = None

            if missing_expenses >= Decimal("1"):
                status = "missing_expenses"
                status_message = f"Missing €{missing_expenses:.2f} in expenses"
                estimated_amount = missing_expenses
                estimated_type = "EX"
            elif missing_income >= Decimal("1"):
                status = "missing_income"
                status_message = f"Missing €{missing_income:.2f} in income"
                estimated_amount = missing_income
                estimated_type = "IN"

            estimated_tx = Transaction.objects.filter(
                user=self.user, period=period, is_estimated=True
            ).first()

            # If a manual transaction exists for the missing type, treat as balanced
            if estimated_type and Transaction.objects.filter(
                user=self.user,
                period=period,
                type=estimated_type,
                is_estimated=False,
            ).exists():
                self.delete_estimated_transaction_by_period(period, estimated_type)
                status = "balanced"
                status_message = "All transactions reconciled"
                estimated_amount = Decimal("0")
                estimated_type = None
                estimated_tx = None

            return {
                "period_id": period.id,
                "period": period.label,
                "status": status,
                "status_message": status_message,
                "estimated_amount": float(estimated_amount),
                "estimated_type": estimated_type,
                "has_estimated_transaction": estimated_tx is not None,
                "estimated_transaction_id": estimated_tx.id if estimated_tx else None,
                "details": {
                    "income_inserted": float(income_inserted),
                    "expense_inserted": float(expense_inserted),
                    "investment_inserted": float(investment_inserted),
                    "savings_current": float(savings_current),
                    "savings_next": float(savings_next),
                    "estimated_expenses": float(estimated_expenses),
                    "missing_expenses": float(missing_expenses),
                    "missing_income": float(missing_income),
                },
            }
        except Exception as e:
            logger.error(
                "Error getting estimation summary for period %s: %s", period.id, e
            )
            return {
                "period_id": period.id,
                "period": period.label,
                "status": "error",
                "status_message": f"Error: {e}",
                "estimated_amount": 0,
                "estimated_type": None,
                "has_estimated_transaction": False,
                "estimated_transaction_id": None,
                "details": {},
            }

    def delete_estimated_transaction_by_period(self, period, tx_type=None):
        """Delete estimated transactions for a given period (optionally filtered by type)."""
        qs = Transaction.objects.filter(
            user=self.user, period=period, is_estimated=True
        )
        if tx_type:
            qs = qs.filter(type=tx_type)
        deleted, _ = qs.delete()
        if deleted:
            logger.info(
                "Deleted %s estimated transaction(s) for period %s", deleted, period.label
            )
        return deleted

    def estimate_transaction_for_period(self, period):
        """Create an estimated transaction if a period is missing data."""
        try:
            summary = self.get_estimation_summary(period)

            tx_type = summary.get("estimated_type")
            amount = Decimal(str(summary.get("estimated_amount", 0)))

            # Nothing missing -> ensure estimates removed and exit
            if summary["status"] == "balanced" or not tx_type or amount < Decimal("0.01"):
                if tx_type:
                    self.delete_estimated_transaction_by_period(period, tx_type)
                else:
                    self.delete_estimated_transaction_by_period(period)
                return None

            # Skip if a manual transaction already exists
            if Transaction.objects.filter(
                user=self.user,
                period=period,
                type=tx_type,
                is_estimated=False,
            ).exists():
                self.delete_estimated_transaction_by_period(period, tx_type)
                return None

            # Remove previous estimates for this period/type
            self.delete_estimated_transaction_by_period(period, tx_type)

            category, _ = Category.objects.get_or_create(
                name="Estimated Transaction", user=self.user
            )

            default_account = Account.objects.filter(
                user=self.user, name__icontains="checking"
            ).first() or Account.objects.filter(user=self.user).first()
            if not default_account:
                logger.error("No accounts found for user %s", self.user.id)
                return None

            estimated_tx = Transaction.objects.create(
                user=self.user,
                type=tx_type,
                amount=amount,
                date=period.get_last_day(),
                notes=f"Estimated {tx_type} transaction for {period.label}",
                is_estimated=True,
                period=period,
                account=default_account,
                category=category,
            )
            logger.info(
                "Created estimated transaction %s for period %s", estimated_tx.id, period.label
            )
            return estimated_tx
        except Exception as e:
            logger.error(
                "Error estimating transaction for period %s: %s", period.id, e
            )
            return None
