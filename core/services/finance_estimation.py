import logging
from decimal import Decimal
from django.db import connection
from django.db.models import Sum, Q
from ..models import DatePeriod, AccountBalance, Transaction, Account

logger = logging.getLogger(__name__)

class FinanceEstimationService:
    """Service for financial transaction estimation."""

    def __init__(self, user):
        self.user = user

    def estimate_transaction_for_period(self, period):
        """Estimate missing transaction for a specific period."""
        try:
            summary = self.get_estimation_summary(period)

            if summary['status'] == 'balanced':
                logger.info(f"Period {period.label} is already balanced")
                return None

            # Calculate missing amount
            missing_amount = summary['estimated_amount']
            if abs(missing_amount) < 0.01:  # Ignore very small amounts
                return None

            # Determine transaction type
            if summary['status'] == 'missing_expenses':
                tx_type = 'EX'
                amount = abs(missing_amount)
            elif summary['status'] == 'missing_income':
                tx_type = 'IN'
                amount = abs(missing_amount)
            else:
                return None

            # Get or create default account
            default_account = Account.objects.filter(
                user=self.user, 
                name__icontains='checking'
            ).first()

            if not default_account:
                default_account = Account.objects.filter(user=self.user).first()

            if not default_account:
                logger.error(f"No accounts found for user {self.user.id}")
                return None

            # Create estimated transaction
            estimated_tx = Transaction.objects.create(
                user=self.user,
                type=tx_type,
                amount=amount,
                date=period.get_last_day(),
                notes=f"Estimated {tx_type} transaction for {period.label}",
                is_estimated=True,
                period=period,
                account=default_account
            )

            logger.info(f"Created estimated transaction {estimated_tx.id} for period {period.label}")
            return estimated_tx

        except Exception as e:
            logger.error(f"Error estimating transaction for period {period.label}: {e}")
            return None

    def get_estimation_summary(self, period):
        """Get estimation summary for a period."""
        try:
            # Get next period
            next_period = self._get_next_period(period)

            # Get recorded transactions
            transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=False
            ).aggregate(
                income=Sum('amount', filter=Q(type='IN')) or Decimal('0'),
                expenses=Sum('amount', filter=Q(type='EX')) or Decimal('0'),
                investments=Sum('amount', filter=Q(type='IV')) or Decimal('0')
            )

            income_inserted = transactions['income'] or Decimal('0')
            expense_inserted = abs(transactions['expenses'] or Decimal('0'))
            investment_inserted = transactions['investments'] or Decimal('0')

            # Get account balances
            current_savings = self._get_savings_balance(period)
            next_savings = self._get_savings_balance(next_period) if next_period else current_savings

            # Calculate estimated expenses
            savings_diff = next_savings - current_savings
            estimated_expenses = income_inserted + savings_diff - investment_inserted

            # Calculate missing amounts
            missing_expenses = max(0, estimated_expenses - expense_inserted)
            missing_income = max(0, expense_inserted - estimated_expenses)

            # Determine status
            if abs(missing_expenses) < 1 and abs(missing_income) < 1:
                status = 'balanced'
                status_message = 'All transactions reconciled'
                estimated_amount = 0
                estimated_type = None
            elif missing_expenses > 1:
                status = 'missing_expenses'
                status_message = f'Missing €{missing_expenses:.2f} in expenses'
                estimated_amount = missing_expenses
                estimated_type = 'EX'
            else:
                status = 'missing_income'
                status_message = f'Missing €{missing_income:.2f} in income'
                estimated_amount = missing_income
                estimated_type = 'IN'

            # Check if estimated transaction exists
            estimated_tx = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True
            ).first()

            return {
                'period_id': period.id,
                'period': period.label,
                'status': status,
                'status_message': status_message,
                'estimated_amount': float(estimated_amount),
                'estimated_type': estimated_type,
                'has_estimated_transaction': estimated_tx is not None,
                'estimated_transaction_id': estimated_tx.id if estimated_tx else None,
                'details': {
                    'income_inserted': float(income_inserted),
                    'expense_inserted': float(expense_inserted),
                    'investment_inserted': float(investment_inserted),
                    'savings_current': float(current_savings),
                    'savings_next': float(next_savings),
                    'estimated_expenses': float(estimated_expenses),
                    'missing_expenses': float(missing_expenses),
                    'missing_income': float(missing_income)
                }
            }

        except Exception as e:
            logger.error(f"Error getting estimation summary for period {period.label}: {e}")
            return {
                'period_id': period.id,
                'period': period.label,
                'status': 'error',
                'status_message': f'Error: {str(e)}',
                'estimated_amount': 0,
                'estimated_type': None,
                'has_estimated_transaction': False,
                'estimated_transaction_id': None,
                'details': {}
            }

    def _get_next_period(self, period):
        """Get the next period after the given period."""
        try:
            if period.month == 12:
                next_year = period.year + 1
                next_month = 1
            else:
                next_year = period.year
                next_month = period.month + 1

            return DatePeriod.objects.filter(
                year=next_year,
                month=next_month
            ).first()

        except Exception:
            return None

    def _get_savings_balance(self, period):
        """Get total savings balance for a period."""
        if not period:
            return Decimal('0')

        try:
            balance = AccountBalance.objects.filter(
                account__user=self.user,
                account__account_type__name__icontains='savings',
                period=period
            ).aggregate(
                total=Sum('reported_balance')
            )['total']

            return balance or Decimal('0')

        except Exception as e:
            logger.error(f"Error getting savings balance for period {period.label}: {e}")
            return Decimal('0')
import logging
from decimal import Decimal
from datetime import date
from django.db.models import Sum, Q
from django.db import connection
from ..models import Transaction, DatePeriod, AccountBalance, Account

logger = logging.getLogger(__name__)


class FinanceEstimationService:
    """Service for financial estimation and reconciliation."""

    def __init__(self, user):
        self.user = user

    def get_estimation_summary(self, period):
        """Get estimation summary for a specific period."""
        try:
            # Get account balances for current and next period
            current_balances = self.get_period_balances(period)
            next_period = self.get_next_period(period)
            next_balances = self.get_period_balances(next_period) if next_period else {}

            # Get recorded transactions for the period - separated by estimated vs real
            real_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=False
            ).aggregate(
                income=Sum('amount', filter=Q(type='IN')) or Decimal('0'),
                expenses=Sum('amount', filter=Q(type='EX')) or Decimal('0'),
                investments=Sum('amount', filter=Q(type='IV')) or Decimal('0')
            )

            estimated_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True
            ).aggregate(
                income=Sum('amount', filter=Q(type='IN')) or Decimal('0'),
                expenses=Sum('amount', filter=Q(type='EX')) or Decimal('0'),
                investments=Sum('amount', filter=Q(type='IV')) or Decimal('0')
            )

            # Combined totals for calculations
            transactions = {
                'income': (real_transactions['income'] or Decimal('0')) + (estimated_transactions['income'] or Decimal('0')),
                'expenses': (real_transactions['expenses'] or Decimal('0')) + (estimated_transactions['expenses'] or Decimal('0')),
                'investments': (real_transactions['investments'] or Decimal('0')) + (estimated_transactions['investments'] or Decimal('0'))
            }

            # Calculate savings difference
            savings_current = current_balances.get('Savings', Decimal('0'))
            savings_next = next_balances.get('Savings', Decimal('0'))
            savings_diff = savings_next - savings_current

            # Estimate missing expenses based on savings change
            income_inserted = abs(transactions['income'] or Decimal('0'))
            expense_inserted = abs(transactions['expenses'] or Decimal('0'))
            investment_inserted = transactions['investments'] or Decimal('0')

            # Calculate expected expenses
            estimated_expenses = income_inserted - savings_diff - investment_inserted
            missing_expenses = max(Decimal('0'), estimated_expenses - expense_inserted)
            missing_income = max(Decimal('0'), -estimated_expenses) if estimated_expenses < 0 else Decimal('0')

            # Check if there's an estimated transaction
            estimated_tx = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True
            ).first()

            # Determine status
            status = 'balanced'
            status_message = 'Period is balanced'
            estimated_type = None
            estimated_amount = Decimal('0')

            if missing_expenses > 10:  # Threshold for missing expenses
                status = 'missing_expenses'
                status_message = f'Missing €{missing_expenses:.0f} in expenses'
                estimated_type = 'EX'
                estimated_amount = missing_expenses
            elif missing_income > 10:  # Threshold for missing income
                status = 'missing_income'
                status_message = f'Missing €{missing_income:.0f} in income'
                estimated_type = 'IN'
                estimated_amount = missing_income

            return {
                'period_id': period.id,
                'period': period.label,
                'status': status,
                'status_message': status_message,
                'estimated_type': estimated_type,
                'estimated_amount': float(estimated_amount),
                'has_estimated_transaction': estimated_tx is not None,
                'estimated_transaction_id': estimated_tx.id if estimated_tx else None,
                'details': {
                    'income_inserted': float(income_inserted),
                    'expense_inserted': float(expense_inserted),
                    'investment_inserted': float(investment_inserted),
                    'savings_current': float(savings_current),
                    'savings_next': float(savings_next),
                    'estimated_expenses': float(estimated_expenses),
                    'missing_expenses': float(missing_expenses),
                    'missing_income': float(missing_income),
                    # Real vs Estimated breakdown
                    'real_income': float(abs(real_transactions['income'] or Decimal('0'))),
                    'real_expenses': float(abs(real_transactions['expenses'] or Decimal('0'))),
                    'real_investments': float(abs(real_transactions['investments'] or Decimal('0'))),
                    'estimated_income': float(abs(estimated_transactions['income'] or Decimal('0'))),
                    'estimated_expenses_tx': float(abs(estimated_transactions['expenses'] or Decimal('0'))),
                    'estimated_investments': float(abs(estimated_transactions['investments'] or Decimal('0')))
                }
            }

        except Exception as e:
            logger.error(f"Error getting estimation summary for period {period.id}: {e}")
            return {
                'period_id': period.id,
                'period': period.label,
                'status': 'error',
                'status_message': f'Error: {str(e)}',
                'estimated_type': None,
                'estimated_amount': 0,
                'has_estimated_transaction': False,
                'estimated_transaction_id': None,
                'details': {}
            }

    def get_period_balances(self, period):
        """Get account balances for a period grouped by account type."""
        if not period:
            return {}

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT at.name, SUM(ab.reported_balance)
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_accounttype at ON a.account_type_id = at.id
                WHERE a.user_id = %s AND ab.period_id = %s
                GROUP BY at.name
            """, [self.user.id, period.id])

            balances = {}
            for account_type, balance in cursor.fetchall():
                balances[account_type] = Decimal(str(balance or 0))

            return balances

    def get_next_period(self, period):
        """Get the next period after the given period."""
        try:
            if period.month == 12:
                return DatePeriod.objects.get(year=period.year + 1, month=1)
            else:
                return DatePeriod.objects.get(year=period.year, month=period.month + 1)
        except DatePeriod.DoesNotExist:
            return None

    def delete_estimated_transaction_by_period(self, period):
        """Delete estimated transactions for a specific period."""
        try:
            # Find and delete estimated transactions for this period and user
            estimated_transactions = Transaction.objects.filter(
                user=self.user,
                period=period,
                is_estimated=True
            )

            deleted_count = estimated_transactions.count()
            estimated_transactions.delete()

            logger.info(f"Deleted {deleted_count} estimated transaction(s) for period {period.label}")
            return deleted_count

        except Exception as e:
            logger.error(f"Error deleting estimated transactions for period {period.id}: {e}")
            raise

    def estimate_transaction_for_period(self, period):
        """Create or update estimated transaction for a period."""
        try:
            summary = self.get_estimation_summary(period)

            if summary['status'] == 'error' or summary['estimated_amount'] <= 10:
                return None

            # Delete existing estimated transaction using the service method
            self.delete_estimated_transaction_by_period(period)

            # Create new estimated transaction
            from ..models import Category

            # Get or create estimation category
            category, _ = Category.objects.get_or_create(
                name='Estimated Transaction',
                user=self.user
            )

            # Get default account
            account = Account.objects.filter(user=self.user).first()
            if not account:
                raise Exception("No account found for user")

            estimated_tx = Transaction.objects.create(
                user=self.user,
                type=summary['estimated_type'],
                amount=Decimal(str(summary['estimated_amount'])),
                date=date(period.year, period.month, 15),  # Mid-month
                notes=f"Estimated {summary['estimated_type']} for {period.label}",
                is_estimated=True,
                period=period,
                account=account,
                category=category
            )

            logger.info(f"Created estimated transaction {estimated_tx.id} for period {period.label}")
            return estimated_tx

        except Exception as e:
            logger.error(f"Error estimating transaction for period {period.id}: {e}")
            raise