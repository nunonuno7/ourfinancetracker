
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model
from decimal import Decimal
from collections import defaultdict

from core.models import Transaction, Account, AccountBalance, DatePeriod, AccountType, Currency

User = get_user_model()

class Command(BaseCommand):
    help = 'Sincroniza saldos da conta Cash baseado nas transações existentes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Sincronizar apenas para um utilizador específico'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Mostrar o que seria feito sem aplicar mudanças'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')
        dry_run = options.get('dry_run')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - Nenhuma mudança será aplicada'))
        
        users = User.objects.filter(id=user_id) if user_id else User.objects.all()
        
        for user in users:
            self.stdout.write(f'📊 Processando utilizador: {user.username}')
            self.sync_user_cash_balances(user, dry_run)
    
    def sync_user_cash_balances(self, user, dry_run=False):
        """Sincroniza saldos de Cash para um utilizador."""
        
        # Get or create Cash account
        cash_account = self.get_or_create_cash_account(user, dry_run)
        if not cash_account:
            return
        
        # Get all transactions grouped by period
        transactions = Transaction.objects.filter(user=user).select_related('period').order_by('date')
        
        period_balances = defaultdict(Decimal)
        
        # Calculate cash impact for each period
        for tx in transactions:
            if not tx.period:
                continue
                
            period_key = (tx.period.year, tx.period.month)
            
            if tx.type == Transaction.Type.INCOME:
                period_balances[period_key] += tx.amount
            elif tx.type == Transaction.Type.EXPENSE:
                period_balances[period_key] -= tx.amount
            elif tx.type == Transaction.Type.TRANSFER:
                period_balances[period_key] -= tx.amount  # Assume saída de cash
        
        # Update AccountBalance records
        updated_count = 0
        created_count = 0
        
        for (year, month), calculated_balance in period_balances.items():
            try:
                period = DatePeriod.objects.get(year=year, month=month)
            except DatePeriod.DoesNotExist:
                self.stdout.write(f'⚠️ Período {year}-{month:02d} não encontrado')
                continue
            
            if dry_run:
                self.stdout.write(
                    f'  📅 {year}-{month:02d}: Cash balance seria {calculated_balance}'
                )
            else:
                cash_balance, created = AccountBalance.objects.get_or_create(
                    account=cash_account,
                    period=period,
                    defaults={'reported_balance': calculated_balance}
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        f'  ✅ {year}-{month:02d}: Criado saldo Cash {calculated_balance}'
                    )
                else:
                    old_balance = cash_balance.reported_balance
                    cash_balance.reported_balance = calculated_balance
                    cash_balance.save()
                    updated_count += 1
                    self.stdout.write(
                        f'  🔄 {year}-{month:02d}: Cash {old_balance} → {calculated_balance}'
                    )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ {user.username}: {created_count} criados, {updated_count} atualizados'
                )
            )
    
    def get_or_create_cash_account(self, user, dry_run=False):
        """Get or create Cash account."""
        try:
            return Account.objects.get(user=user, name__iexact='Cash')
        except Account.DoesNotExist:
            if dry_run:
                self.stdout.write(f'  ⚠️ Conta Cash não existe para {user.username} (seria criada)')
                return None
            
            # Create Cash account
            account_type = AccountType.objects.filter(name__iexact='Savings').first()
            if not account_type:
                account_type = AccountType.objects.first()
            
            currency = Currency.objects.filter(code='EUR').first()
            if not currency:
                currency = Currency.objects.first()
            
            cash_account = Account.objects.create(
                user=user,
                name='Cash',
                account_type=account_type,
                currency=currency
            )
            
            self.stdout.write(f'  ✅ Conta Cash criada para {user.username}')
            return cash_account
