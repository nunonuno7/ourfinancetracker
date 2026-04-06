
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from core.models import Transaction, Category
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = "Clean up duplicate automatic transactions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Clean up records for a specific user only",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would happen without applying changes",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")
        dry_run = options.get("dry_run")
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN - No changes will be applied")
            )
        
        users = User.objects.filter(id=user_id) if user_id else User.objects.all()
        
        total_cleaned = 0
        for user in users:
            cleaned = self.cleanup_user_duplicates(user, dry_run)
            total_cleaned += cleaned
            
        if total_cleaned > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Cleanup completed: {total_cleaned} duplicate transactions removed"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("✅ No duplicate transactions found")
            )
    
    def cleanup_user_duplicates(self, user, dry_run=False):
        """Clean up duplicate automatic transactions for a user."""
        
        try:
            system_category = Category.objects.get(user=user, name="System Adjustment")
        except Category.DoesNotExist:
            self.stdout.write(
                f"⚠️ {user.username}: Missing System Adjustment category"
            )
            return 0
        
        with connection.cursor() as cursor:
            # Find duplicate transactions for the same period, type, and amount
            cursor.execute("""
                SELECT period_id, type, amount, COUNT(*) as count, 
                       ARRAY_AGG(id ORDER BY created_at) as ids
                FROM core_transaction 
                WHERE user_id = %s 
                AND category_id = %s 
                AND is_system = TRUE
                GROUP BY period_id, type, amount
                HAVING COUNT(*) > 1
            """, [user.id, system_category.id])
            
            duplicates = cursor.fetchall()
            
        if not duplicates:
            self.stdout.write(f"✅ {user.username}: No duplicates found")
            return 0
        
        cleaned_count = 0
        
        if not dry_run:
            with transaction.atomic():
                for period_id, tx_type, amount, count, ids in duplicates:
                    # Keep the first transaction and remove the rest
                    ids_to_delete = ids[1:]  # Everything except the first one
                    
                    Transaction.objects.filter(id__in=ids_to_delete).delete()
                    cleaned_count += len(ids_to_delete)
                    
                    self.stdout.write(
                        f"🗑️ {user.username}: Removed {len(ids_to_delete)} duplicate transactions "
                        f"(period {period_id}, {tx_type}, EUR {amount})"
                    )
        else:
            for period_id, tx_type, amount, count, ids in duplicates:
                self.stdout.write(
                    f"🔍 {user.username}: Found {count - 1} duplicates "
                    f"(period {period_id}, {tx_type}, EUR {amount}) - would be removed"
                )
                cleaned_count += count - 1
        
        return cleaned_count
