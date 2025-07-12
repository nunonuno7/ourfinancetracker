
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import Transaction
from collections import defaultdict

class Command(BaseCommand):
    help = 'Remove duplicate system adjustment transactions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Clean duplicates for specific user only'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options.get('user_id')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No changes will be made'))
        
        # Find duplicate system transactions
        filters = {'is_system': True, 'type': Transaction.Type.AJUSTE}
        if user_id:
            filters['user_id'] = user_id
            
        system_transactions = Transaction.objects.filter(**filters).order_by('user_id', 'date', 'id')
        
        # Group by user and date
        duplicates_by_user_date = defaultdict(list)
        for tx in system_transactions:
            key = (tx.user_id, tx.date)
            duplicates_by_user_date[key].append(tx)
        
        total_duplicates = 0
        total_kept = 0
        
        with transaction.atomic():
            for (user_id, date), transactions in duplicates_by_user_date.items():
                if len(transactions) > 1:
                    # Keep the first transaction (oldest ID)
                    to_keep = transactions[0]
                    to_delete = transactions[1:]
                    
                    self.stdout.write(
                        f'📅 {date} (User {user_id}): Keeping ID {to_keep.id}, '
                        f'deleting {len(to_delete)} duplicates'
                    )
                    
                    for tx in to_delete:
                        self.stdout.write(
                            f'   🗑️  Delete ID {tx.id}: {tx.amount}€ - {tx.notes}'
                        )
                        if not dry_run:
                            tx.delete()
                    
                    total_duplicates += len(to_delete)
                    total_kept += 1
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'🔍 Would delete {total_duplicates} duplicate transactions, '
                    f'keeping {total_kept} originals'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Deleted {total_duplicates} duplicate transactions, '
                    f'kept {total_kept} originals'
                )
            )
