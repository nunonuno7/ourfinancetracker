# models.py - Versão Corrigida

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.db.models import UniqueConstraint
from datetime import date
from django.dispatch import receiver
from django.db.models.signals import post_save


def get_default_currency_id() -> int:
    return get_default_currency().pk


def get_default_account_type_id() -> int:
    return get_default_account_type().pk


def get_default_currency() -> "Currency":
    """Return the default *EUR* currency (create if missing)."""
    from django.apps import apps

    Currency: type["Currency"] = apps.get_model("core", "Currency")  # type: ignore[name-defined]
    obj, _ = Currency.objects.get_or_create(code="EUR", defaults={"symbol": "€", "decimals": 2})
    return obj


def get_default_account_type() -> "AccountType":
    """Return the fallback *Savings* account-type (create if missing)."""
    from django.apps import apps

    AccountType: type["AccountType"] = apps.get_model("core", "AccountType")  # type: ignore[name-defined]
    obj, _ = AccountType.objects.get_or_create(name="Savings")
    return obj


# --------------------------------------------------------------------------------
# Reference / lookup tables
# --------------------------------------------------------------------------------

class Currency(models.Model):
    """ISO-4217 currency definition (e.g. EUR, USD)."""

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


# --------------------------------------------------------------------------------
# Core objects
# --------------------------------------------------------------------------------

class Account(models.Model):
    """A bank or investment account owned by the user."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="accounts")
    name = models.CharField(max_length=100)

    account_type = models.ForeignKey(
        AccountType,
        on_delete=models.PROTECT,
        default=get_default_account_type_id,
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        default=get_default_currency_id,
    )

    created_at = models.DateField(auto_now_add=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("name",)
        constraints = [
            UniqueConstraint(fields=["user", "name"], name="unique_account_user_name")
        ]

    def __str__(self) -> str:
        return f"{self.name} – {self.user}"

    # CORRIGIDO: Account.save() com tratamento de exceções
    def save(self, *args, **kwargs):
        """Ensure `account_type` and `currency` are not null when saving."""
        if not self.account_type_id:
            self.account_type = get_default_account_type() or AccountType.objects.first()
        
        if not self.currency_id:
            try:
                user_settings = getattr(self.user, "settings", None)
                default_curr = getattr(user_settings, "default_currency", None)
                self.currency = default_curr or get_default_currency()
            except AttributeError:
                self.currency = get_default_currency()
        
        super().save(*args, **kwargs)

    def is_default(self) -> bool:
        """Returns True if this account is the default 'Cash' account."""
        return self.name.strip().lower() == "cash"


class AccountBalance(models.Model):
    """Snapshot of an account's balance for a given month."""

    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="balances")
    period = models.ForeignKey("DatePeriod", on_delete=models.CASCADE, related_name="account_balances")
    reported_balance = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        ordering = ("-period__year", "-period__month")
        constraints = [
            UniqueConstraint(fields=["account", "period"], name="unique_accountbalance_account_period")
        ]

    def __str__(self) -> str:
        return f"{self.account} @ {self.period}: {self.reported_balance}"

    # CORRIGIDO: merge_into() corrigido para AccountBalance
    def merge_into(self, target: 'AccountBalance') -> None:
        """Merge this balance into target balance for the same period."""
        if self.pk == target.pk:
            return
        
        # Verificar se são do mesmo período
        if self.period != target.period:
            raise ValueError("Cannot merge balances from different periods")
        
        # Somar os saldos
        target.reported_balance += self.reported_balance
        target.save()
        self.delete()


class Category(models.Model):
    """User-defined flat category (no hierarchy)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="categories")  # type: ignore[valid-type]
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "name")
        verbose_name_plural = "categories"
        constraints = [
            UniqueConstraint(fields=["user", "name"], name="unique_category_user_name")
        ]

    def __str__(self) -> str:
        return self.name

    # -------------------- helpers ----------------------

    @classmethod
    def get_fallback(cls, user: User) -> "Category":
        """
        Garante que existe a categoria 'Other' (em inglês),
        usada como fallback ao eliminar ou fundir categorias.
        """
        return cls.objects.get_or_create(user=user, name="Other")[0]

    @classmethod
    def get_default(cls, user: User) -> "Category":
        """
        🔁 Compatibilidade retroativa com código antigo que usava 'Geral'.
        Agora redireciona para 'Other'.
        """
        return cls.get_fallback(user)

    def merge_into(self, target: 'Category') -> None:
        """Merge this category into target category."""
        if self.pk == target.pk:
            return
        from core.models import Transaction
        Transaction.objects.filter(category=self).update(category=target)
        self.delete()


# --------------------------------------------------------------------------------
# Transactions
# --------------------------------------------------------------------------------

class Transaction(models.Model):
    """Money movement. Expenses can be estimated if not recorded."""

    class Type(models.TextChoices):
        EXPENSE = "EX", "Expense"
        INCOME = "IN", "Income"
        INVESTMENT = "IV", "Investment"
        TRANSFER = "TR", "Transfer"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    type = models.CharField(max_length=2, choices=Type.choices)

    period = models.ForeignKey(
        "DatePeriod",
        on_delete=models.PROTECT,
        related_name="transactions",
        null=True,
        blank=True,
        help_text="Reference period (e.g. June 2025)",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transactions",
    )

    tags = models.ManyToManyField(
        "Tag",
        through="TransactionTag",  # 🔗 ligação explícita
        blank=True,
        related_name="transactions"
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

    def __str__(self) -> str:
        return f"{self.date} {self.get_type_display()} {self.amount}"

    def save(self, *args, **kwargs):
        """Aplica defaults à transação antes de guardar."""

        # 🚫 Garante que pelo menos um dos dois está definido
        if not self.date and not self.period:
            raise ValueError("Transaction must have either a date or a period defined.")

        # 🔁 Preenche período com base na data
        if not self.period and self.date:
            self.period, _ = DatePeriod.objects.get_or_create(
                year=self.date.year,
                month=self.date.month,
                defaults={"label": self.date.strftime("%B %Y")}
            )

        # 🔁 Preenche data com base no período
        if not self.date and self.period:
            self.date = date(self.period.year, self.period.month, 1)

        # Tipo default
        if not self.type:
            self.type = self.Type.EXPENSE

        # Atribui categoria mais usada se não houver
        if not self.pk and not self.category_id:
            most_used = (
                Category.objects.filter(user=self.user)
                .annotate(num=models.Count("transactions"))
                .order_by("-num")
                .first()
            )
            self.category = most_used or Category.get_default(self.user)

        super().save(*args, **kwargs)


# --------------------------------------------------------------------------------
# User settings – lightweight, avoids custom user model
# --------------------------------------------------------------------------------

class UserSettings(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="settings")

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


class TransactionAttachment(models.Model):
    transaction = models.ForeignKey("Transaction", on_delete=models.CASCADE, related_name="attachments")
    file_path = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Attachment for transaction {self.transaction_id}"


class Budget(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="budgets")
    category = models.ForeignKey("Category", on_delete=models.CASCADE, related_name="budgets")
    start_date = models.DateField()
    end_date = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    rollover = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category} budget ({self.start_date} – {self.end_date})"


class RecurringTransaction(models.Model):
    class Frequency(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recurring_transactions")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    frequency = models.CharField(max_length=10, choices=Frequency.choices)
    next_occurrence = models.DateField()

    end_period = models.ForeignKey(
        "DatePeriod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurring_transactions",
        help_text="Optional period when recurrence ends",
    )

    is_active = models.BooleanField(default=True)
    template_transaction = models.ForeignKey(
        "Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recurrence_templates"
    )
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} – {self.amount} ({self.frequency})"


class ImportLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        PARTIAL = "partial", "Partial"
        ERROR = "error", "Error"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="import_logs")
    source = models.CharField(max_length=80)
    imported_at = models.DateTimeField(auto_now_add=True)
    num_records = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class ExchangeRate(models.Model):
    from_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_from")
    to_currency = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="rates_to")
    rate = models.DecimalField(max_digits=20, decimal_places=6)
    rate_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["from_currency", "to_currency", "rate_date"],
                name="unique_exchangerate_from_to_date"
            )
        ]

    def __str__(self):
        return f"{self.from_currency} → {self.to_currency} @ {self.rate_date}: {self.rate}"


# CORRIGIDO: DatePeriod com validação de mês
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

class DatePeriod(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(12)
        ]
    )
    label = models.CharField(max_length=20)

    class Meta:
        unique_together = ('year', 'month')
        ordering = ['-year', '-month']

    def clean(self):
        super().clean()
        if DatePeriod.objects.exclude(pk=self.pk).filter(year=self.year, month=self.month).exists():
            raise ValidationError("The period with this year and month already exists.")

    def __str__(self):
        return self.label


class Tag(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tags")
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    # 💡 NOVO: ligação opcional à categoria
    category = models.ForeignKey(
        "Category",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tags",
        help_text="(Opcional) Categoria associada a esta tag"
    )

    class Meta:
        ordering = ("position", "name")
        verbose_name_plural = "tags"
        constraints = [
            UniqueConstraint(fields=["user", "name"], name="unique_tag_user_name")
        ]

    def __str__(self):
        return self.name


class TransactionTag(models.Model):
    transaction = models.ForeignKey("Transaction", on_delete=models.CASCADE, related_name="tag_links")
    tag = models.ForeignKey("Tag", on_delete=models.CASCADE, related_name="transaction_links")

    class Meta:
        verbose_name = "Transaction Tag"
        verbose_name_plural = "Transaction Tags"
        constraints = [
            UniqueConstraint(fields=["transaction", "tag"], name="unique_transactiontag_tx_tag")
        ]

    def __str__(self):
        return f"{self.transaction_id} → {self.tag.name}"


# --------------------------------------------------------------------------------
# Signals
# --------------------------------------------------------------------------------

@receiver(post_save, sender=Account)
def _create_initial_balance_on_account_creation(sender, instance, created, **kwargs):
    if created:
        today = date.today()
        period, _ = DatePeriod.objects.get_or_create(
            year=today.year,
            month=today.month,
            defaults={"label": today.strftime("%B %Y")}
        )
        AccountBalance.objects.create(
            account=instance,
            period=period,
            reported_balance=0
        )