from __future__ import annotations

"""
Revised data‑model for *ourfinancetracker* (Phase 2‑MVP).

Principais mudanças
===================
1. **Defaults seguros** em `AccountType` e `Currency` para permitir a
   criação automática de contas a partir de texto‑livre (balance form).
2. `Account.currency` deixa de ser obrigatória na **DB layer**, mas um
   *default callable* assegura que é sempre preenchida com a moeda
   definida nas *user‑settings* (ou EUR quando inexistente).
3. Funções utilitárias de **lookup + fallback** partilhadas por views e
   forms (`get_default_currency`, `get_default_account_type`).
4. Pequenas melhorias de estilo/typing e *docstrings*.

Esta versão deve ser usada em conjunto com as refactorizações propostas
nos *forms* (ver `forms/account_utils.py`).
"""

from decimal import Decimal
from typing import Callable

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

User = get_user_model()

__all__ = [
    "Currency",
    "AccountType",
    "Account",
    "AccountBalance",
    "Category",
    "Transaction",
    "UserSettings",
    # helpers
    "get_default_currency",
    "get_default_account_type",
]

# ---------------------------------------------------------------------------
# Helpers (re‑used in defaults)
# ---------------------------------------------------------------------------

def get_default_currency() -> "Currency":
    """Return the default *EUR* currency (create if missing)."""
    from django.apps import apps

    Currency: type["Currency"] = apps.get_model("core", "Currency")  # type: ignore[name‑defined]
    obj, _ = Currency.objects.get_or_create(code="EUR", defaults={"symbol": "€", "decimals": 2})
    return obj


def get_default_account_type() -> "AccountType":
    """Return the fallback *Savings* account‑type (create if missing)."""
    from django.apps import apps

    AccountType: type["AccountType"] = apps.get_model("core", "AccountType")  # type: ignore[name‑defined]
    obj, _ = AccountType.objects.get_or_create(name="Savings")
    return obj


# ---------------------------------------------------------------------------
# Reference / lookup tables
# ---------------------------------------------------------------------------


class Currency(models.Model):
    """ISO‑4217 currency definition (e.g. EUR, USD)."""

    code = models.CharField(max_length=3, unique=True)
    symbol = models.CharField(max_length=5, blank=True)
    decimals = models.PositiveSmallIntegerField(default=2)

    class Meta:
        verbose_name_plural = "currencies"
        ordering = ("code",)

    def __str__(self) -> str:  # pragma: no cover
        return self.code


class AccountType(models.Model):
    """Type of financial account (e.g. current, savings, brokerage)."""

    name = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = "account type"
        verbose_name_plural = "account types"
        ordering = ("name",)

    def __str__(self) -> str:  # pragma: no cover
        return self.name


# ---------------------------------------------------------------------------
# Core objects
# ---------------------------------------------------------------------------


class Account(models.Model):
    """A bank or investment account owned by the user."""

    user: User = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")  # type: ignore[valid‑type]
    name = models.CharField(max_length=100)
    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        default=get_default_account_type,  # ← tentará usar "Savings"
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=get_default_currency,  # ← tentará usar "EUR"
    )
    created_at = models.DateField(auto_now_add=True)
    position = models.PositiveIntegerField(default=0)
    class Meta:
        unique_together = (("user", "name"),)
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} – {self.user}"

    def save(self, *args, **kwargs):
        """Ensure `account_type` and `currency` are not null when saving."""
        if not self.account_type_id:
            self.account_type = get_default_account_type() or AccountType.objects.first()
        if not self.currency_id:
            default_curr = getattr(getattr(self.user, "settings", None), "default_currency", None)
            self.currency = default_curr or get_default_currency()
        super().save(*args, **kwargs)

    def is_default(self) -> bool:
        """Returns True if this account is the default 'Cash' account."""
        return self.name.strip().lower() == "cash"

    


class AccountBalance(models.Model):
    """Snapshot of an account's balance for a given month."""

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="balances")
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()
    reported_balance = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = (("account", "year", "month"),)
        ordering = ("-year", "-month")

    def __str__(self) -> str:
        return f"{self.account} @ {self.year}-{self.month:02d}: {self.reported_balance}"
    

class Category(models.Model):
    """User‑specific tree of categories and sub‑categories."""

    user: User = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")  # type: ignore[valid‑type]
    name = models.CharField(max_length=64)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )

    class Meta:
        unique_together = (("user", "name", "parent"),)
        verbose_name_plural = "categories"
        ordering = ("parent__name", "name")

    # ------------------------------------------------------------ helpers

    @classmethod
    def get_default(cls, user: User) -> "Category":
        """Return (create if needed) *Geral / Não Classificado*."""
        with transaction.atomic():
            general, _ = cls.objects.get_or_create(user=user, name="Geral", parent=None)
            sub, _ = cls.objects.get_or_create(user=user, name="Não Classificado", parent=general)
        return sub

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.parent} / {self.name}" if self.parent else self.name


@receiver(post_save, sender=User)
def _create_cash_account(sender, instance: User, created: bool, **kwargs):
    if created:
        from django.apps import apps
        Account = apps.get_model("core", "Account")  # 👈 esta linha estava em falta
        if not Account.objects.filter(user=instance, name__iexact="Cash").exists():
            Account.objects.create(
                user=instance,
                name="Cash",
                account_type=get_default_account_type(),
                currency=getattr(instance.settings, "default_currency", None) or get_default_currency()
            )

# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class Transaction(models.Model):
    """Money movement. Expenses can be estimated if not recorded."""

    class Type(models.TextChoices):
        INCOME = "IN", "Income"
        EXPENSE = "EX", "Expense"
        INVESTMENT = "IV", "Investment"

    user: User = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")  # type: ignore[valid‑type]
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=2, choices=Type.choices)
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )
    notes = models.TextField(blank=True)
    is_estimated = models.BooleanField(default=False)
    is_cleared = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["user", "type"]),
        ]
        ordering = ("-date", "-id")

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.date} {self.get_type_display()} {self.amount}"

    # ------------------------------------------------------------ save/clean

    def save(self, *args, **kwargs):  # noqa: D401
        """Assign default category when missing."""
        if not self.category_id:
            self.category = Category.get_default(self.user)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# User settings – lightweight, avoids custom user model
# ---------------------------------------------------------------------------


class UserSettings(models.Model):
    user: User = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")  # type: ignore[valid‑type]
    default_currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    timezone = models.CharField(max_length=64, default="Europe/Lisbon")
    start_of_month = models.PositiveSmallIntegerField(
        default=1,
        help_text="Day of month considered the start for budgeting",
    )

    def __str__(self) -> str:  # pragma: no cover
        return f"Settings for {self.user}"


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


@receiver(post_save, sender=Account)
def _create_initial_balance_on_account_creation(sender, instance: Account, created: bool, **kwargs):
    if created:
        today = timezone.now().date()
        AccountBalance.objects.create(
            account=instance,
            year=today.year,
            month=today.month,
            reported_balance=Decimal("0.00"),
        )
