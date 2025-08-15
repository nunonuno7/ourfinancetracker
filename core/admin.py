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
    RecurringTransaction,
)

# Registo simples
admin.site.register([Currency, AccountType, AccountBalance, UserSettings])


# Registo personalizado para Account
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    search_fields = ("name", "user__username")

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


@admin.register(RecurringTransaction)
class RecurringTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "schedule", "amount", "next_run_at", "active")
    list_filter = ("schedule", "active")
    autocomplete_fields = ("category", "account")
