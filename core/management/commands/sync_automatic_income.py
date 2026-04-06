
from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction
from django.contrib.auth.models import User
from core.views import _create_missing_income_transactions
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Sync missing automatic income transactions"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="Specific user ID (optional)",
        )
        parser.add_argument(
            "--all-users",
            action="store_true",
            help="Process all users",
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        all_users = options.get('all_users')

        if not user_id and not all_users:
            self.stdout.write(
                self.style.ERROR("You must specify --user-id or --all-users")
            )
            return

        if user_id:
            users = [user_id]
        else:
            users = User.objects.values_list('id', flat=True)

        total_created = 0
        total_users = len(users)

        self.stdout.write(
            f"🚀 Syncing automatic income for {total_users} user(s)..."
        )

        for user_id in users:
            try:
                with db_transaction.atomic():
                    created = _create_missing_income_transactions(user_id)
                    total_created += created
                    
                    if created > 0:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✅ User {user_id}: {created} transactions created/updated"
                            )
                        )
                    else:
                        self.stdout.write(
                            f"ℹ️ User {user_id}: No updates required"
                        )
                        
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Error for user {user_id}: {e}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"🎯 Completed! Total: {total_created} transactions processed"
            )
        )
