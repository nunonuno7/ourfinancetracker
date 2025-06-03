"""
core/forms.py

Typed Django Forms for ourfinancetracker
----------------------------------------
Every form accepts an optional ``user=…`` kwarg so that query-sets and default
values are automatically scoped to the currently authenticated user.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, modelformset_factory

from .models import (
    Account,
    AccountBalance,
    AccountType,
    Category,
    Currency,
    Transaction,
)

User = get_user_model()

# ========================================================================== #
# Generic helper mix-ins                                                     #
# ========================================================================== #

class UserAwareMixin:
    """Inject the current ``request.user`` into a form instance."""

    def __init__(
        self,
        *args: Any,
        user: User | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.user: User | None = user

# ========================================================================== #
# Transaction                                                                #
# ========================================================================== #

class TransactionForm(UserAwareMixin, forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            "amount",
            "date",
            "type",
            "category",
            "account",
            "notes",
            "is_cleared",
        ]
        widgets = {
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "type": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "account": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 2}
            ),
            "is_cleared": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }

    def __init__(
        self,
        *args: Any,
        user: User | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["category"].queryset = Category.objects.filter(
                user=self.user
            ).order_by("name")
            self.fields["account"].queryset = Account.objects.filter(
                user=self.user
            ).order_by("name")

    def clean_amount(self) -> Decimal:
        amount: Decimal = self.cleaned_data["amount"]
        if amount == 0:
            raise ValidationError("Amount cannot be zero.")
        return amount

# ========================================================================== #
# Category                                                                   #
# ========================================================================== #

class CategoryForm(UserAwareMixin, forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=Category.objects.none(),
        required=False,
        label="Parent category",
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    class Meta:
        model = Category
        fields = ("name", "parent")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(
        self,
        *args: Any,
        user: User | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, user=user, **kwargs)
        self.instance.user = self.user

        qs = (
            Category.objects.filter(user=self.user).order_by(
                "parent__name", "name"
            )
            if self.user
            else Category.objects.none()
        )
        self.fields["parent"].queryset = qs

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        if (
            self.user
            and Category.objects.filter(
                user=self.user,
                name__iexact=cleaned.get("name"),
                parent=cleaned.get("parent"),
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise ValidationError(
                "A category with the same name already exists at this level."
            )
        return cleaned

    def save(self, commit: bool = True) -> Category:
        instance: Category = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance

# ========================================================================== #
# Registration                                                               #
# ========================================================================== #

class CustomUserCreationForm(UserCreationForm):
    """Friendlier sign-up form."""

    username = forms.CharField(
        min_length=3,
        max_length=150,
        help_text="Required – between 3 and 150 characters.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. myusername"}),
    )

    class Meta(UserCreationForm.Meta):  # type: ignore[misc]
        model = User
        fields = ["username", "password1", "password2"]

# ========================================================================== #
# Account Balances — NOVO FLUXO                                              #
# ========================================================================== #

class AccountBalanceForm(UserAwareMixin, forms.ModelForm):
    # O campo account deixa de ser ModelChoiceField!
    account = forms.CharField(
        label="Account",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Account name"}),
        max_length=150,
    )

    class Meta:
        model = AccountBalance
        fields = ["account", "reported_balance"]
        widgets = {
            "reported_balance": forms.NumberInput(attrs={
                "class": "form-control text-end",
                "step": "0.01",
                "placeholder": "Enter balance",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        # Nunca readonly — o user pode sempre editar ou fundir
        # Se quiseres bloquear em algum caso, podes adicionar lógica aqui

    def clean_account(self):
        """Valida (ou cria) a conta com este nome."""
        name = self.cleaned_data.get("account", "").strip()
        if not name:
            raise ValidationError("Account name is required.")

        # Busca a conta existente para este user, insensitive ao caso
        account_qs = Account.objects.filter(user=self.user, name__iexact=name)
        if account_qs.exists():
            return account_qs.first()  # devolve o Account instance
        else:
            # Cria com defaults: Savings/EUR (podes ajustar!)
            account_type = AccountType.objects.filter(name__iexact="Savings").first()
            currency = Currency.objects.filter(code__iexact="EUR").first()
            if not account_type:
                account_type = AccountType.objects.first()
            if not currency:
                currency = Currency.objects.first()
            account = Account.objects.create(
                user=self.user,
                name=name,
                account_type=account_type,
                currency=currency,
            )
            return account

    def clean(self):
        cleaned = super().clean()
        account = cleaned.get("account")
        if isinstance(account, Account):
            self.cleaned_data["account"] = account  # garante que será usado no save
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Garante que o campo account está como FK (não string)
        if isinstance(self.cleaned_data.get("account"), Account):
            instance.account = self.cleaned_data["account"]
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

# ========================================================================== #
# Account CRUD                                                               #
# ========================================================================== #

class AccountForm(UserAwareMixin, forms.ModelForm):
    class Meta:
        model = Account
        fields = ("name", "account_type", "currency")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(
        self,
        *args: Any,
        user: User | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, user=user, **kwargs)

        self.fields["account_type"].queryset = AccountType.objects.order_by("name")
        self.fields["currency"].queryset = Currency.objects.order_by("code")

        if (
            not self.instance.pk
            and getattr(user, "settings", None)
            and user.settings.default_currency
        ):
            self.initial["currency"] = user.settings.default_currency

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        # Permite duplicados porque agora ao fundir serão resolvidos!
        return name

    # ---------------------------------------------------------------- save
    def save(self, commit: bool = True) -> Account:
        """
        Se, ao gravar, já existir outra conta do utilizador com o mesmo nome
        (case-insensitive), funde-as:
          • todos os AccountBalance da conta actual passam para a conta destino
          • a conta duplicada é removida
        Caso contrário, grava normalmente.
        """
        new_name = self.cleaned_data["name"].strip()

        # Existe outra conta com o mesmo nome (ignorando maiúsc/minúsc)?
        clash_qs = Account.objects.filter(
            user=self.user,
            name__iexact=new_name,
        ).exclude(pk=self.instance.pk)

        if self.instance.pk and clash_qs.exists():
            # === Fusão ===
            primary = clash_qs.first()              # conta que vai ficar
            from .models import AccountBalance      # import local p/ evitar ciclos

            # Re-apontar saldos
            AccountBalance.objects.filter(account=self.instance) \
                                   .update(account=primary)

            # Remover a conta duplicada
            self.instance.delete()

            # Devolve a conta “ganhadora”
            return primary

        # --- criação ou alteração sem colisão ---
        account: Account = super().save(commit=False)
        account.user = self.user
        if commit:
            account.save()
        return account
