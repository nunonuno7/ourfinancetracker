from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal
from core.models import Transaction, AccountBalance, DatePeriod
from core.models_monthly import MonthlySummary
from core.utils.date_helpers import add_one_month
from django import models


class Command(BaseCommand):
    help = "Sync monthly summaries - basic version without adjustments"

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process all dirty summaries (back-fill)",
        )
        parser.add_argument(
            "--period",
            type=str,
            help="Process a specific period (YYYY-MM format)",
        )

    def handle(self, *args, **options):
        if options.get("period"):
            # Process a specific period
            self.process_period(options["period"])
            self.stdout.write(
                self.style.SUCCESS(f'Processed period {options["period"]}')
            )
            return

        limit = None if options["all"] else 100

        # Get dirty summaries
        dirty_summaries = MonthlySummary.objects.filter(is_dirty=True)
        if limit:
            dirty_summaries = dirty_summaries[:limit]

        processed = 0

        with transaction.atomic():
            for summary in dirty_summaries:
                self.process_period(summary.period)
                processed += 1

        self.stdout.write(
            self.style.SUCCESS(f'Processed {processed} monthly summaries')
        )

    def process_period(self, period):
        """Process a single period for basic summary statistics."""

        self.stdout.write(f'📊 Processing period {period}')

        # Parse period
        year, month = map(int, period.split('-'))
        next_period = add_one_month(period)
        next_year, next_month = map(int, next_period.split('-'))

        # Get period objects
        try:
            current_period = DatePeriod.objects.get(year=year, month=month)
        except DatePeriod.DoesNotExist:
            current_period = DatePeriod.objects.create(
                year=year, 
                month=month, 
                label=f"{month:02d}/{year}"
            )

        try:
            next_period_obj = DatePeriod.objects.get(year=next_year, month=next_month)
        except DatePeriod.DoesNotExist:
            next_period_obj = None

        # Update the global monthly summary
        self.update_monthly_summary(period, current_period, next_period_obj)

    def update_monthly_summary(self, period, current_period, next_period_obj):
        """Update the global monthly summary."""

        # Calculate global totals for the summary
        current_total_balance = AccountBalance.objects.filter(
            period=current_period
        ).aggregate(total=models.Sum("reported_balance"))["total"] or Decimal("0")

        if next_period_obj:
            next_total_balance = AccountBalance.objects.filter(
                period=next_period_obj
            ).aggregate(total=models.Sum("reported_balance"))["total"] or Decimal("0")
        else:
            next_total_balance = Decimal("0")

        total_income = Transaction.objects.filter(
            period=current_period,
            type=Transaction.Type.INCOME,
            is_system=False,
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

        total_investments = Transaction.objects.filter(
            period=current_period,
            type=Transaction.Type.INVESTMENT,
            is_system=False,
        ).aggregate(total=models.Sum("amount"))["total"] or Decimal("0")

        estimated_expenses = (
            current_total_balance
            - next_total_balance
            + total_income
            - total_investments
        )
        unposted_income = max(Decimal("0"), -estimated_expenses)
        adjusted_expenses = max(estimated_expenses, Decimal("0"))

        # Update MonthlySummary using English aliases
        summary, _ = MonthlySummary.objects.get_or_create(period=period)
        summary.investments = total_investments
        summary.estimated_expenses = estimated_expenses
        summary.unposted_income = unposted_income
        summary.adjusted_expenses = adjusted_expenses
        summary.is_dirty = False
        summary.save()

        self.stdout.write(f'📊 Global summary {period}: basic stats updated')
