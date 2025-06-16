from django.test import TestCase
from django.contrib.auth.models import User
from core.models import Account, Transaction, Category, DatePeriod
from decimal import Decimal

class ModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('testuser', 'test@test.com', 'pass123')

    def test_account_save_defaults(self):
        """Testar se Account.save() aplica defaults corretamente"""
        account = Account(name='Teste', user=self.user)
        account.save()
        
        self.assertIsNotNone(account.account_type)
        self.assertIsNotNone(account.currency)

    def test_dateperiod_month_validation(self):
        """Testar validação do mês em DatePeriod"""
        from django.core.exceptions import ValidationError
        
        # Mês válido
        period = DatePeriod(year=2025, month=6, label='Jun 2025')
        period.full_clean()  # Não deve levantar exceção
        
        # Mês inválido
        period_invalid = DatePeriod(year=2025, month=13, label='Invalid')
        with self.assertRaises(ValidationError):
            period_invalid.full_clean()
