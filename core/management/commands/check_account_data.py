
"""
Management command to check account data and periods
"""
from django.core.management.base import BaseCommand
from django.db import models
from core.models import Account, AccountBalance, DatePeriod, Transaction, AccountType
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Check account data and periods for debugging'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Checking account data...")
        
        # Check users
        users = User.objects.all()
        self.stdout.write(f"👥 Total users: {users.count()}")
        
        # Check account types
        account_types = AccountType.objects.all()
        self.stdout.write(f"🏦 Account types: {', '.join([at.name for at in account_types])}")
        
        # Check accounts
        accounts = Account.objects.all()
        self.stdout.write(f"💳 Total accounts: {accounts.count()}")
        
        for user in users:
            user_accounts = accounts.filter(user=user)
            if user_accounts.exists():
                self.stdout.write(f"  👤 {user.username}: {user_accounts.count()} accounts")
                for acc in user_accounts:
                    self.stdout.write(f"    - {acc.name} ({acc.account_type.name})")
        
        # Check periods
        periods = DatePeriod.objects.all().order_by('-year', '-month')
        self.stdout.write(f"📅 Total periods: {periods.count()}")
        if periods.exists():
            self.stdout.write(f"  Latest: {periods.first()}")
            self.stdout.write(f"  Earliest: {periods.last()}")
        
        # Check account balances
        balances = AccountBalance.objects.all()
        self.stdout.write(f"💰 Total account balances: {balances.count()}")
        
        # Check balances by period
        for period in periods[:5]:  # Show last 5 periods
            period_balances = balances.filter(period=period)
            if period_balances.exists():
                total = period_balances.aggregate(total=models.Sum('reported_balance'))['total']
                self.stdout.write(f"  📊 {period}: {period_balances.count()} balances, total €{total}")
        
        # Check transactions
        transactions = Transaction.objects.all()
        self.stdout.write(f"💸 Total transactions: {transactions.count()}")
        
        # Check system transactions
        system_txs = transactions.filter(is_system=True)
        self.stdout.write(f"🤖 System transactions: {system_txs.count()}")
        
        # Check by user
        for user in users:
            user_txs = transactions.filter(user=user)
            if user_txs.exists():
                user_system_txs = user_txs.filter(is_system=True)
                self.stdout.write(f"  👤 {user.username}: {user_txs.count()} transactions ({user_system_txs.count()} system)")
