# flake8: noqa
# isort: skip_file
# forms.py - Versão Corrigida
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.forms import BaseModelFormSet, modelformset_factory
from django.utils.translation import gettext_lazy as _

from .models import (
    ALLOWED_ACCOUNT_TYPE_NAMES,
    Account,
    AccountBalance,
    AccountType,
    Category,
    Currency,
    DatePeriod,
    RecurringTransaction,
    Tag,
    Transaction,
)

logger = logging.getLogger(__name__)


class UserAwareMixin:
    """Mixin to provide user information to forms."""

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)  # type: ignore


class UserInFormKwargsMixin:
    """
    View mixin that adds request.user to form kwargs on both
    get_form_kwargs() and get_form() methods. Most views just need one.
    """

    def get_form_kwargs(self):
        """Add request.user to form kwargs."""
        kwargs = super().get_form_kwargs()  # type: ignore[misc]
        kwargs["user"] = self.request.user  # type: ignore[misc]
        return kwargs


# core/forms.py


class TransactionForm(forms.ModelForm):
    """Form for creating or editing transactions."""

    period = forms.CharField(
        label=_("Period"),
        required=True,
        widget=forms.TextInput(
            attrs={"type": "month", "class": "form-control", "id": "id_period"}
        ),
    )

    tags_input = forms.CharField(
        label=_("Tags"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "id_tags_input",
                "placeholder": _("Optional tags…"),
            }
        ),
    )

    category = forms.CharField(
        label=_("Category"),
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "id": "id_category",
                "placeholder": _("Enter category…"),
                "data-category-list": "",
            }
        ),
    )

    direction = forms.ChoiceField(
        label=_("Investment Flow"),
        required=False,
        choices=(
            ("IN", _("Reinforcement")),
            ("OUT", _("Withdrawal")),
        ),
    )

    class Meta:
        model = Transaction
        fields = [
            "date",
            "type",
            "amount",
            "account",
            "category",
            "tags_input",
            "notes",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.TextInput(
                attrs={
                    "class": "form-control text-end",
                    "inputmode": "decimal",
                    "placeholder": "0.00",
                    "id": "id_amount",
                }
            ),
            "notes": forms.Textarea(
                attrs={"class": "form-control notes-textarea", "rows": "3"}
            ),
        }

    def __init__(self, *args, user: User = None, **kwargs):
        self._user = user
        super().__init__(*args, **kwargs)

        self.fields["account"].required = False
        self.fields["account"].empty_label = "— No account —"
        # Filtrar para excluir "System adjustment" (AJ) do formulário
        self.fields["type"].choices = [
            (value, label) for value, label in Transaction.Type.choices if value != "AJ"
        ]
        self.fields["type"].required = True

        if self._user:
            self.fields["account"].queryset = Account.objects.filter(
                user=self._user
            ).only("name")
        else:
            self.fields["account"].queryset = Account.objects.none()

        if self.instance and self.instance.pk:
            if self.instance.category:
                self.initial["category"] = self.instance.category.name
            if self.instance.tags.exists():
                self.initial["tags_input"] = ", ".join(
                    self.instance.tags.values_list("name", flat=True)
                )
            if self.instance.period:
                self.initial["period"] = (
                    f"{self.instance.period.year}-{self.instance.period.month:02d}"
                )

            # Garantir que a data está no formato correto (YYYY-MM-DD)
            if self.instance.date:
                self.initial["date"] = self.instance.date.strftime("%Y-%m-%d")

            if self.instance.amount is not None:
                if self.instance.type == Transaction.Type.INVESTMENT:
                    amount = self.instance.amount or Decimal("0.00")
                    self.initial["direction"] = "OUT" if amount < 0 else "IN"
                    self.initial["amount"] = abs(amount)
                else:
                    self.initial["amount"] = self.instance.amount
            elif self.data.get("amount"):
                self.initial["amount"] = self.data["amount"]
        else:
            today = date.today()
            if not self.initial.get("period"):
                self.initial["period"] = f"{today.year}-{today.month:02d}"
            if "amount" not in self.initial and not self.data:
                self.initial["amount"] = ""

        # Default investment flow to "Withdrawal" so users explicitly opt-in to reinforcement
        self.fields["direction"].initial = self.initial.get("direction", "OUT")

    def clean_amount(self) -> Decimal:
        raw = (self.data.get("amount") or "").strip()
        if raw == "":
            raise forms.ValidationError(_("This field is required."))

        normalized = raw.replace("\u00a0", "").replace(" ", "")
        if "," in normalized and "." in normalized:
            normalized = normalized.replace(".", "").replace(",", ".")
        elif "," in normalized:
            normalized = normalized.replace(",", ".")

        try:
            value = Decimal(normalized)
        except (InvalidOperation, ValueError):
            raise forms.ValidationError(_("Invalid number."))

        return value.quantize(Decimal("0.01"))

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount")
        type_ = cleaned_data.get("type")
        direction = cleaned_data.get("direction")

        if amount is not None and type_ != Transaction.Type.INVESTMENT and amount < 0:
            self.add_error("amount", _("Negative amounts are not allowed."))

        if type_ == Transaction.Type.INVESTMENT and direction not in {"IN", "OUT"}:
            self.add_error("direction", _("Investment flow is required."))

    def clean_category(self):
        name = (self.cleaned_data.get("category") or "").strip()
        if not name:
            raise forms.ValidationError(_("This field is required."))
        user = self._user or self.instance.user
        existing = Category.objects.filter(user=user, name__iexact=name).first()
        if existing:
            return existing
        return Category.objects.create(user=user, name=name)

    def clean_tags_input(self):
        return (self.cleaned_data.get("tags_input") or "").strip()

    def save(self, commit=True) -> Transaction:
        instance: Transaction = super().save(commit=False)

        # Assign DatePeriod
        year, month = map(int, self.cleaned_data["period"].split("-"))
        period, _ = DatePeriod.objects.get_or_create(year=year, month=month)
        instance.period = period

        if not instance.user_id and self._user:
            instance.user = self._user

        if not self.cleaned_data.get("account"):
            instance.account = None

        # Apply amount sign for investments
        if instance.type == Transaction.Type.INVESTMENT:
            direction = self.cleaned_data.get("direction", "IN")
            if direction == "OUT":
                instance.amount = -abs(instance.amount)
            else:
                instance.amount = abs(instance.amount)

        if commit:
            instance.save()

        # Tags
        tags_str = self.cleaned_data.get("tags_input", "")
        tag_names = {t.strip() for t in tags_str.split(",") if t.strip()}
        if commit:
            instance.tags.clear()
            if tag_names:
                tag_objs = [
                    Tag.objects.get_or_create(user=instance.user, name=name)[0]
                    for name in tag_names
                ]
                instance.tags.add(*tag_objs)

        return instance


class CategoryForm(UserAwareMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        if self.instance:
            self.instance.user = self.user

    # CORRIGIDO: Validação melhorada para "Other"
    def clean_name(self) -> str:
        name = self.cleaned_data.get("name", "").strip()

        # Impedir criação manual da categoria "Other" (e variantes)
        if name.lower() in ["other", "outro", "others"]:
            if not self.instance.pk:
                raise ValidationError(
                    "Reserved category names cannot be created manually."
                )

        # Verificar duplicados
        if (
            self.user
            and Category.objects.filter(user=self.user, name__iexact=name)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError("A category with this name already exists.")

        return name

    def save(self, commit: bool = True) -> Category:
        new_name = self.cleaned_data["name"].strip()
        self.cleaned_data["name"] = new_name
        self.instance.name = new_name
        self.instance.user = self.user

        # 🔁 Verificar se já existe uma categoria com esse nome
        existing = (
            Category.objects.filter(user=self.user, name__iexact=new_name)
            .exclude(pk=self.instance.pk)
            .first()
        )

        if existing:
            # ❌ Proibir fusão com "Other"
            if existing.name.strip().lower() == "other":
                raise ValidationError("You cannot merge another category into 'Other'.")

            # 🔁 Fundir: mover transações e apagar categoria atual
            Transaction.objects.filter(category=self.instance).update(category=existing)
            if self.instance.pk:
                self.instance.delete()

            # ✅ Guardar referência para feedback na view
            self._merged_category = existing
            return existing

        if commit:
            self.instance.save()
        return self.instance


class CustomUserCreationForm(UserCreationForm):
    username = forms.CharField(
        min_length=3,
        max_length=150,
        help_text="Required – between 3 and 150 characters.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. myusername"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "password1", "password2"]


class AccountBalanceForm(forms.ModelForm):
    account = forms.CharField(
        label="Account",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Account name"}
        ),
        max_length=70,
    )

    class Meta:
        model = AccountBalance
        fields = ["account", "reported_balance"]
        widgets = {
            "reported_balance": forms.NumberInput(
                attrs={
                    "class": "form-control text-end",
                    "step": "0.01",
                    "placeholder": "Enter balance",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance and getattr(self.instance, "account_id", None):
            self.initial["account"] = self.instance.account.name

    def clean_account(self):
        name = self.cleaned_data.get("account", "").strip()
        if not name:
            raise ValidationError("Account name is required.")
        if len(name) > 100:
            raise ValidationError("Account name cannot exceed 100 characters.")

        # Only allow selection of existing accounts for this user
        account_qs = Account.objects.filter(user=self.user, name__iexact=name)
        if account_qs.exists():
            return account_qs.first()
        raise ValidationError("Selected account does not exist.")

    def clean(self):
        cleaned = super().clean()
        account = cleaned.get("account")
        if isinstance(account, Account):
            self.cleaned_data["account"] = account
        return cleaned

    def save(self, commit=True):
        instance = self.instance

        if isinstance(self.cleaned_data.get("account"), Account):
            instance.account = self.cleaned_data["account"]

        # 🔐 Garante que o saldo é atualizado mesmo se já existir
        reported = self.cleaned_data.get("reported_balance")
        if reported is not None:
            instance.reported_balance = reported

        if commit:
            instance.save()
        return instance


class _BaseBalanceFormSet(BaseModelFormSet):
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["user"] = self.user
        return kwargs


AccountBalanceFormSet = modelformset_factory(
    AccountBalance,
    form=AccountBalanceForm,
    formset=_BaseBalanceFormSet,
    can_delete=True,
    extra=0,
)


class AccountForm(UserAwareMixin, forms.ModelForm):
    """
    Cria/edita contas. Se existir outra conta com mesmo nome (case-insensitive),
    pede confirmação para fundir saldos, desde que moeda e tipo coincidam.
    """

    # ✅ campo explícito em vez de olhar para request.POST["confirm_merge"]
    confirm_merge = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput,
        initial=False,
    )

    class Meta:
        model = Account
        fields = ("name", "account_type", "currency", "confirm_merge")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }

    # ------------------------------------------------------------------ #
    # INIT
    # ------------------------------------------------------------------ #
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        for name in ALLOWED_ACCOUNT_TYPE_NAMES:
            AccountType.objects.get_or_create(name=name)

        self.fields["account_type"].queryset = AccountType.objects.filter(
            name__in=ALLOWED_ACCOUNT_TYPE_NAMES
        ).order_by("name")
        self.fields["currency"].queryset = Currency.objects.order_by("code")

        if (
            not self.instance.pk
            and getattr(user, "settings", None)
            and user.settings.default_currency
        ):
            self.initial["currency"] = user.settings.default_currency

    # ------------------------------------------------------------------ #
    # CLEANERS
    # ------------------------------------------------------------------ #
    def clean_name(self):
        return self.cleaned_data["name"].strip()

    def clean(self):
        super().clean()

        name: str = self.cleaned_data.get("name", "").strip()
        account_type = self.cleaned_data.get("account_type")
        currency = self.cleaned_data.get("currency")
        confirm_merge = self.cleaned_data.get("confirm_merge")

        if not name or not account_type or not currency:
            return

        duplicate_qs = Account.objects.filter(
            user=self.user, name__iexact=name
        ).exclude(pk=self.instance.pk)

        if not duplicate_qs.exists():
            return  # → sem duplicados

        duplicate = duplicate_qs.first()

        # Não permitir fundir com conta especial “Cash” (regra de negócio)
        if duplicate.name.lower() == "cash":
            raise ValidationError(
                _("Merging with the ‘Cash’ account is not allowed."),
                code="merge_cash_forbidden",
            )

        # Moeda/tipo diferentes ⇒ bloqueio duro
        if (
            duplicate.account_type_id != account_type.id
            or duplicate.currency_id != currency.id
        ):
            raise ValidationError(
                _(
                    "Another account with this name already exists but with a "
                    "different type or currency. Merging is not possible."
                ),
                code="merge_incompatible",
            )

        # Alerta suave se ainda não confirmou
        if not confirm_merge:
            raise ValidationError(
                _(
                    "An account with this name already exists. "
                    "Tick ‘confirm_merge’ to merge balances."
                ),
                code="merge_confirmation_required",
            )

        # A partir daqui consideramos merge confirmado → guardamos ref.
        self._duplicate_to_merge: Account | None = duplicate  # type: ignore[attr-defined]

    # ------------------------------------------------------------------ #
    # SAVE
    # ------------------------------------------------------------------ #
    def save(self, commit=True):
        """
        - Guarda a nova/actual conta normalmente.
        - Se houver duplicado e confirm_merge, funde saldos de forma transacional.
        """
        name = self.cleaned_data["name"].strip()
        self.instance.name = name
        self.instance.user = self.user  # ← garante owner correcto

        duplicate = getattr(self, "_duplicate_to_merge", None)

        if duplicate:
            return self._merge_into(duplicate)

        if commit:
            conflict_qs = Account.objects.filter(
                user=self.user, name__iexact=name
            ).exclude(pk=self.instance.pk)
            if conflict_qs.exists():
                raise ValidationError(
                    _("An account with this name already exists."),
                    code="duplicate",
                )
            self.instance.save()
        return self.instance

    # ------------------------------------------------------------------ #
    # MERGE HELPER
    # ------------------------------------------------------------------ #
    def _merge_into(self, target):
        """
        Move saldos da `self.instance` para `target` (duplicado), somando
        reported_balance quando já existe o mesmo periodo.
        Tudo dentro de uma transacção atómica.
        """
        with transaction.atomic():
            # Salva/actualiza self.instance para obter FK consistentes
            if not self.instance.pk:
                self.instance.save()

            # 1) fundir saldos
            balances_qs = AccountBalance.objects.select_for_update().filter(
                account=self.instance
            )

            for bal in balances_qs:
                merged, created = AccountBalance.objects.get_or_create(
                    account=target,
                    period=bal.period,
                    defaults={"reported_balance": bal.reported_balance},
                )
                if not created:
                    merged.reported_balance = (
                        F("reported_balance") + bal.reported_balance
                    )
                    merged.save(update_fields=["reported_balance"])
                bal.delete()

            # 2) eliminar conta antiga, se existia na BD
            if self.instance.pk:
                self.instance.delete()

        return target


class TransactionImportForm(forms.Form):
    file = forms.FileField(
        label="Excel File",
        help_text="Select a .xlsx file with the transactions",
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )


class RecurringTransactionForm(UserAwareMixin, forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = [
            "schedule",
            "amount",
            "account",
            "category",
            "tags",
            "next_run_at",
            "active",
        ]
        widgets = {
            "schedule": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.TextInput(attrs={"class": "form-control text-end"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "tags": forms.SelectMultiple(attrs={"class": "form-select"}),
            "next_run_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
        }

    def __init__(self, *args, user: User | None = None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["account"].queryset = Account.objects.filter(user=self.user)
            self.fields["category"].queryset = Category.objects.filter(user=self.user)
            self.fields["tags"].queryset = Tag.objects.filter(user=self.user)
