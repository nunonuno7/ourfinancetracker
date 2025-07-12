
"""
Django management command to estimate transactions for all users and periods.
Usage: python manage.py estimate_all_transactions [--user-id=X] [--period=YYYY-MM]
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import DatePeriod
from core.services.finance_estimation import FinanceEstimationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Estimate missing transactions for all users and periods'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Estimate only for specific user ID'
        )
        parser.add_argument(
            '--period',
            type=str,
            help='Estimate only for specific period (YYYY-MM format)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be estimated without creating transactions'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        period_str = options.get('period')
        dry_run = options.get('dry_run', False)

        self.stdout.write(
            self.style.SUCCESS('🧮 Starting transaction estimation process...')
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No transactions will be created')
            )

        # Get users to process
        users = User.objects.all()
        if user_id:
            users = users.filter(id=user_id)
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} not found')
                )
                return

        # Get periods to process
        periods = DatePeriod.objects.all().order_by('-year', '-month')
        if period_str:
            try:
                year, month = period_str.split('-')
                periods = periods.filter(year=int(year), month=int(month))
                if not periods.exists():
                    self.stdout.write(
                        self.style.ERROR(f'Period {period_str} not found')
                    )
                    return
            except ValueError:
                self.stdout.write(
                    self.style.ERROR('Invalid period format. Use YYYY-MM')
                )
                return

        total_users = users.count()
        total_periods = periods.count()
        
        self.stdout.write(f'Processing {total_users} users and {total_periods} periods...')

        estimated_count = 0
        error_count = 0

        for user in users:
            self.stdout.write(f'\n👤 Processing user: {user.username} (ID: {user.id})')
            
            estimation_service = FinanceEstimationService(user)
            
            for period in periods:
                try:
                    # Get estimation summary first
                    summary = estimation_service.get_estimation_summary(period)
                    
                    if summary['status'] == 'error':
                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⚠️  {period.label}: {summary["status_message"]}'
                            )
                        )
                        continue

                    estimated_amount = summary['estimated_amount']
                    
                    if estimated_amount == 0:
                        self.stdout.write(
                            f'  ✅ {period.label}: Already balanced (€0.00)'
                        )
                        continue

                    if dry_run:
                        self.stdout.write(
                            f'  🔍 {period.label}: Would estimate {summary["estimated_type"]} €{estimated_amount:.2f}'
                        )
                        estimated_count += 1
                    else:
                        # Run actual estimation
                        estimated_tx = estimation_service.estimate_transaction_for_period(period)
                        
                        if estimated_tx:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f'  ✅ {period.label}: Estimated {summary["estimated_type"]} €{estimated_amount:.2f} (TX ID: {estimated_tx.id})'
                                )
                            )
                            estimated_count += 1
                        else:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'  ⚠️  {period.label}: No transaction created'
                                )
                            )

                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ❌ {period.label}: Error - {str(e)}'
                        )
                    )
                    logger.error(f'Error estimating for user {user.id}, period {period}: {e}')

        # Summary
        self.stdout.write('\n' + '='*50)
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ DRY RUN COMPLETE: {estimated_count} transactions would be estimated'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ ESTIMATION COMPLETE: {estimated_count} transactions estimated'
                )
            )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'⚠️  {error_count} errors occurred')
            )

        self.stdout.write('Done!')
