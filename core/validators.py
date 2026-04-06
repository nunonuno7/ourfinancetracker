
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import date
import re

def validate_transaction_amount(value):
    """Validate transaction amounts."""
    if value == 0:
        raise ValidationError(_('Transaction amount cannot be zero.'))
    
    if abs(value) > Decimal('999999999.99'):
        raise ValidationError(_('Transaction amount is too large.'))
    
    # Check decimal precision
    if value.as_tuple().exponent < -2:
        raise ValidationError(_('Amount cannot have more than 2 decimal places.'))

def validate_account_name(value):
    """Validate account names."""
    if not value or not value.strip():
        raise ValidationError(_('Account name cannot be empty.'))
    
    if len(value.strip()) < 2:
        raise ValidationError(_('Account name must be at least 2 characters long.'))
    
    # Check for problematic special characters
    if re.search(r'[<>"\';]', value):
        raise ValidationError(_('Account name contains invalid characters.'))

def validate_category_name(value):
    """Validate category names."""
    if not value or not value.strip():
        raise ValidationError(_('Category name cannot be empty.'))
    
    if len(value.strip()) > 50:
        raise ValidationError(_('Category name is too long (max 50 characters).'))
    
    # Check for invalid special characters
    if re.search(r'[<>"\';]', value):
        raise ValidationError(_('Category name contains invalid characters.'))

def validate_date_range(start_date, end_date):
    """Validate date ranges."""
    if start_date and end_date:
        if start_date > end_date:
            raise ValidationError(_('Start date cannot be after end date.'))
        
        # Check maximum supported range (for example, 5 years)
        max_days = 365 * 5
        if (end_date - start_date).days > max_days:
            raise ValidationError(_('Date range cannot exceed 5 years.'))

class TransactionValidator:
    """Higher-level validator for transactions."""
    
    @staticmethod
    def validate_transaction_data(transaction_data, user):
        """Validate the full transaction payload."""
        errors = {}
        
        # Validate transaction type
        tx_type = transaction_data.get('type')
        if tx_type not in ['IN', 'EX', 'IV', 'TR', 'AJ']:
            errors['type'] = 'Invalid transaction type.'
        
        # Validate that the account belongs to the current user
        account_id = transaction_data.get('account')
        if account_id:
            from .models import Account
            try:
                Account.objects.get(id=account_id, user=user)
            except Account.DoesNotExist:
                errors['account'] = 'Invalid account for this user.'
        
        # Validate that the category belongs to the current user
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
