
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import AccountType, Account


class Command(BaseCommand):
    help = 'Remove Checking account type and migrate accounts to Savings'

    def handle(self, *args, **options):
        with transaction.atomic():
            try:
                # Get the account types
                checking_type = AccountType.objects.get(name="Checking")
                savings_type = AccountType.objects.get(name="Savings")
                
                # Count accounts using Checking type
                checking_accounts = Account.objects.filter(account_type=checking_type)
                count = checking_accounts.count()
                
                if count > 0:
                    self.stdout.write(f"🔄 Migrating {count} accounts from Checking to Savings...")
                    # Migrate all accounts from Checking to Savings
                    checking_accounts.update(account_type=savings_type)
                    self.stdout.write(f"✅ Migrated {count} accounts to Savings type")
                
                # Delete the Checking account type
                checking_type.delete()
                self.stdout.write("✅ Removed 'Checking' account type from database")
                
            except AccountType.DoesNotExist:
                self.stdout.write("ℹ️ 'Checking' account type not found in database")
            except Exception as e:
                self.stdout.write(f"❌ Error: {e}")
                raise
