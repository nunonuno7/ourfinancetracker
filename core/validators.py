
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import date
import re

def validate_transaction_amount(value):
    """Valida montantes de transações"""
    if value == 0:
        raise ValidationError(_('Transaction amount cannot be zero.'))
    
    if abs(value) > Decimal('999999999.99'):
        raise ValidationError(_('Transaction amount is too large.'))
    
    # Verificar precisão decimal
    if value.as_tuple().exponent < -2:
        raise ValidationError(_('Amount cannot have more than 2 decimal places.'))

def validate_account_name(value):
    """Valida nomes de contas"""
    if not value or not value.strip():
        raise ValidationError(_('Account name cannot be empty.'))
    
    if len(value.strip()) < 2:
        raise ValidationError(_('Account name must be at least 2 characters long.'))
    
    # Verificar caracteres especiais problemáticos
    if re.search(r'[<>"\';]', value):
        raise ValidationError(_('Account name contains invalid characters.'))

def validate_category_name(value):
    """Valida nomes de categorias"""
    if not value or not value.strip():
        raise ValidationError(_('Category name cannot be empty.'))
    
    if len(value.strip()) > 50:
        raise ValidationError(_('Category name is too long (max 50 characters).'))
    
    # Verificar caracteres especiais
    if re.search(r'[<>"\';]', value):
        raise ValidationError(_('Category name contains invalid characters.'))

def validate_date_range(start_date, end_date):
    """Valida intervalos de datas"""
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(_('Start date cannot be after end date.'))
        
        # Verificar intervalo máximo (ex: 5 anos)
        max_days = 365 * 5
        if (end_date - start_date).days > max_days:
            raise ValidationError(_('Date range cannot exceed 5 years.'))

class TransactionValidator:
    """Validador complexo para transações"""
    
    @staticmethod
    def validate_transaction_data(transaction_data, user):
        """Valida dados completos de transação"""
        errors = {}
        
        # Validar tipo de transação
        tx_type = transaction_data.get('type')
        if tx_type not in ['IN', 'EX', 'IV', 'TR', 'AJ']:
            errors['type'] = 'Invalid transaction type.'
        
        # Validar conta pertence ao utilizador
        account_id = transaction_data.get('account')
        if account_id:
            from .models import Account
            try:
                Account.objects.get(id=account_id, user=user)
            except Account.DoesNotExist:
                errors['account'] = 'Invalid account for this user.'
        
        # Validar categoria pertence ao utilizador
        category_id = transaction_data.get('category')
        if category_id:
            from .models import Category
            try:
                Category.objects.get(id=category_id, user=user)
            except Category.DoesNotExist:
                errors['category'] = 'Invalid category for this user.'
        
        if errors:
            raise ValidationError(errors)
        
        return True
