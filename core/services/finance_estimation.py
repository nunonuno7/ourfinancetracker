import logging
from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.models import Q, Sum

from ..models import Account, Category, DatePeriod, Transaction

logger = logging.getLogger(__name__)


class FinanceEstimationService:
    """Service for financial estimation and reconciliation."""

    MIN_ESTIMATION_AMOUNT = Decimal("10")

    def __init__(self, user):
        self.user = user

    def get_estimation_summary(self, period):
        """Get estimation summary for a specific period."""
        try:
            balance_start_period = period
            balance_end_period = self.get_next_period(period)

            # January reconciles against the previous December balance.
            if period.month == 1:
                previous_december = DatePeriod.objects.filter(
                    year=period.year - 1,
                    month=12,
                ).first()
                if previous_december:
                    balance_start_period = previous_december
                    balance_end_period = period

            current_balances = self.get_period_balances(balance_start_period)
            next_balances = (
                self.get_period_balances(balance_end_period)
                if balance_end_period
                else {}
            )

            real_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=False,
            ).aggregate(
                income=Sum("amount", filter=Q(type=Transaction.Type.INCOME))
                or Decimal("0"),
                expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE))
                or Decimal("0"),
                investments=Sum("amount", filter=Q(type=Transaction.Type.INVESTMENT))
                or Decimal("0"),
            )

            estimated_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True,
            ).aggregate(
                income=Sum("amount", filter=Q(type=Transaction.Type.INCOME))
                or Decimal("0"),
                expenses=Sum("amount", filter=Q(type=Transaction.Type.EXPENSE))
                or Decimal("0"),
                investments=Sum("amount", filter=Q(type=Transaction.Type.INVESTMENT))
                or Decimal("0"),
            )

            savings_current = current_balances.get("Savings", Decimal("0"))
            savings_next = next_balances.get("Savings", Decimal("0"))
            savings_diff = savings_next - savings_current

            income_inserted = abs(real_transactions["income"] or Decimal("0"))
            expense_inserted = abs(real_transactions["expenses"] or Decimal("0"))
            investment_inserted = real_transactions["investments"] or Decimal("0")

            estimated_expenses = income_inserted - savings_diff - investment_inserted
            missing_expenses = max(Decimal("0"), estimated_expenses - expense_inserted)
            missing_income = max(Decimal("0"), expense_inserted - estimated_expenses)

            estimated_expense_tx = abs(
                estimated_transactions["expenses"] or Decimal("0")
            )
            estimated_income_tx = abs(
                estimated_transactions["income"] or Decimal("0")
            )

            missing_expenses_after = max(
                Decimal("0"),
                missing_expenses - estimated_expense_tx,
            )
            missing_income_after = max(
                Decimal("0"),
                missing_income - estimated_income_tx,
            )

            estimated_tx = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True,
            ).first()

            status = "balanced"
            status_message = "Period is balanced"
            estimated_type = None
            estimated_amount = Decimal("0")

            if missing_expenses > self.MIN_ESTIMATION_AMOUNT:
                status = "missing_expenses"
                status_message = f"Missing \u20ac{missing_expenses:.0f} in expenses"
                estimated_type = Transaction.Type.EXPENSE
                estimated_amount = missing_expenses
            elif missing_income > self.MIN_ESTIMATION_AMOUNT:
                status = "missing_income"
                status_message = f"Missing \u20ac{missing_income:.0f} in income"
                estimated_type = Transaction.Type.INCOME
                estimated_amount = missing_income

            if (
                status == "missing_expenses"
                and estimated_expense_tx == missing_expenses
                and missing_income <= self.MIN_ESTIMATION_AMOUNT
            ) or (
                status == "missing_income"
                and estimated_income_tx == missing_income
                and missing_expenses <= self.MIN_ESTIMATION_AMOUNT
            ):
                status = "balanced"
                status_message = "Period is balanced"
                estimated_type = None
                estimated_amount = Decimal("0")

            existing_estimate_amount = (
                estimated_expense_tx
                if estimated_expense_tx > 0
                else estimated_income_tx
            )
            currently_estimating = (
                existing_estimate_amount
                if existing_estimate_amount > 0
                else estimated_amount
            )

            return {
                "period_id": period.id,
                "period": period.label,
                "status": status,
                "status_message": status_message,
                "estimated_type": estimated_type,
                "estimated_amount": float(estimated_amount),
                "has_estimated_transaction": estimated_tx is not None,
                "estimated_transaction_id": estimated_tx.id if estimated_tx else None,
                "details": {
                    "income_inserted": float(income_inserted),
                    "expense_inserted": float(expense_inserted),
                    "investment_inserted": float(investment_inserted),
                    "savings_current": float(savings_current),
                    "savings_next": float(savings_next),
                    "estimated_expenses": float(estimated_expenses),
                    "missing_expenses": float(missing_expenses_after),
                    "missing_income": float(missing_income_after),
                    "currently_estimating": float(currently_estimating),
                    "real_income": float(abs(real_transactions["income"] or Decimal("0"))),
                    "real_expenses": float(
                        abs(real_transactions["expenses"] or Decimal("0"))
                    ),
                    "real_investments": float(
                        real_transactions["investments"] or Decimal("0")
                    ),
                    "estimated_income": float(
                        abs(estimated_transactions["income"] or Decimal("0"))
                    ),
                    "estimated_expenses_tx": float(estimated_expense_tx),
                    "estimated_investments": float(
                        estimated_transactions["investments"] or Decimal("0")
                    ),
                },
            }
        except Exception as e:
            logger.error(
                "Error getting estimation summary for period %s: %s",
                period.id,
                e,
            )
            return {
                "period_id": period.id,
                "period": period.label,
                "status": "error",
                "status_message": f"Error: {str(e)}",
                "estimated_type": None,
                "estimated_amount": 0,
                "has_estimated_transaction": False,
                "estimated_transaction_id": None,
                "details": {},
            }

    def get_period_balances(self, period):
        """Get account balances for a period grouped by account type."""
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
        """Get the next period after the given period."""
        try:
            if period.month == 12:
                return DatePeriod.objects.get(year=period.year + 1, month=1)
            return DatePeriod.objects.get(year=period.year, month=period.month + 1)
        except DatePeriod.DoesNotExist:
            return None

    def delete_estimated_transaction_by_period(self, period):
        """Delete estimated transactions for a specific period."""
        try:
            estimated_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True,
            )
            deleted_count = estimated_transactions.count()
            estimated_transactions.delete()
            logger.info(
                "Deleted %s estimated transaction(s) for period %s",
                deleted_count,
                period.label,
            )
            return deleted_count
        except Exception as e:
            logger.error(
                "Error deleting estimated transactions for period %s: %s",
                period.id,
                e,
            )
            raise

    def estimate_transaction_for_period(self, period):
        """Create or update an estimated transaction for a period."""
        summary = self.get_estimation_summary(period)

        if (
            summary["status"] == "error"
            or Decimal(str(summary["estimated_amount"])) <= self.MIN_ESTIMATION_AMOUNT
        ):
            return None

        self.delete_estimated_transaction_by_period(period)

        category, _ = Category.objects.get_or_create(
            name="Estimated Transaction",
            user=self.user,
            defaults={"blocked": True},
        )
        if not category.blocked:
            category.blocked = True
            category.save(update_fields=["blocked"])

        account = Account.objects.filter(user=self.user).first()
        if not account:
            raise Exception("No account found for user")

        estimated_tx = Transaction.objects.create(
            user=self.user,
            type=summary["estimated_type"],
            amount=Decimal(str(summary["estimated_amount"])),
            date=date(period.year, period.month, 15),
            notes=f"Estimated {summary['estimated_type']} for {period.label}",
            is_estimated=True,
            period=period,
            account=account,
            category=category,
        )

        logger.info(
            "Created estimated transaction %s for period %s",
            estimated_tx.id,
            period.label,
        )
        return estimated_tx
