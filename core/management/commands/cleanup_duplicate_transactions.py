
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from core.models import Transaction, Category
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Limpa transações automáticas duplicadas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='Limpar apenas para um utilizador específico'
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
        
        total_cleaned = 0
        for user in users:
            cleaned = self.cleanup_user_duplicates(user, dry_run)
            total_cleaned += cleaned
            
        if total_cleaned > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Limpeza concluída: {total_cleaned} transações duplicadas removidas'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Nenhuma transação duplicada encontrada')
            )
    
    def cleanup_user_duplicates(self, user, dry_run=False):
        """Limpa transações automáticas duplicadas para um utilizador."""
        
        try:
            system_category = Category.objects.get(user=user, name="System Adjustment")
        except Category.DoesNotExist:
            self.stdout.write(f'⚠️ {user.username}: Sem categoria System Adjustment')
            return 0
        
        with connection.cursor() as cursor:
            # Encontrar transações duplicadas (mesmo período, tipo, montante)
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
            self.stdout.write(f'✅ {user.username}: Sem duplicados encontrados')
            return 0
        
        cleaned_count = 0
        
        if not dry_run:
            with transaction.atomic():
                for period_id, tx_type, amount, count, ids in duplicates:
                    # Manter apenas a primeira transação, eliminar as restantes
                    ids_to_delete = ids[1:]  # Todas exceto a primeira
                    
                    Transaction.objects.filter(id__in=ids_to_delete).delete()
                    cleaned_count += len(ids_to_delete)
                    
                    self.stdout.write(
                        f'🗑️ {user.username}: Removidas {len(ids_to_delete)} transações duplicadas '
                        f'(período {period_id}, {tx_type}, €{amount})'
                    )
        else:
            for period_id, tx_type, amount, count, ids in duplicates:
                self.stdout.write(
                    f'🔍 {user.username}: Encontradas {count-1} duplicações '
                    f'(período {period_id}, {tx_type}, €{amount}) - seriam removidas'
                )
                cleaned_count += count - 1
        
        return cleaned_count
