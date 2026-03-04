# core/admin.py

from django.contrib import admin
from .models import (
    Currency,
    AccountType,
    Account,
    AccountBalance,
    Category,
    Transaction,
    UserSettings,
)

# Registo simples
admin.site.register([Currency, AccountType, Account, AccountBalance, UserSettings])

# Registo personalizado para Category
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "position")
    list_filter = ("user",)
    search_fields = ("name",)

# Registo personalizado para Transaction
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "user", "type", "amount", "category", "is_estimated")
    list_filter = ("type", "user", "is_estimated")
    search_fields = ("notes",)
    autocomplete_fields = ("category",)
