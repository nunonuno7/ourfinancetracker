# forms.py - Versão Corrigida

import re
from typing import Any
from datetime import datetime
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, modelformset_factory
from decimal import Decimal

from core.models import (
    Transaction,
    Category,
    Account,
    AccountBalance,
    DatePeriod,
    AccountType,
    Currency,
    Tag,
)


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


class TransactionForm(UserAwareMixin, forms.ModelForm):
    """Form for Transaction creation/editing."""

    date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        required=False,
    )

    period = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "YYYY-MM",
                "data-autocomplete": "periods",
            }
        ),
    )

    category = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Category",
                "data-autocomplete": "categories",
            }
        ),
    )

    tags_input = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Tags (comma-separated)",
                "data-autocomplete": "tags",
            }
        ),
    )

    class Meta:
        model = Transaction
        fields = [
            "date",
            "period",
            "type",
            "amount",
            "account",
            "category",
            "tags_input",
            "notes",
            "is_cleared",
        ]
        widgets = {
            "type": forms.Select(attrs={"class": "form-select"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "account": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(
                attrs={"class": "form-control", "rows": "3", "style": "height: 5em;"}
            ),
            "is_cleared": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)

        # Define available accounts
        if user:
            self.fields["account"].queryset = Account.objects.filter(user=user)

        # For edit: preencher campos transient
        if self.instance and self.instance.pk:
            if self.instance.category:
                self.initial["category"] = self.instance.category.name

            if self.instance.tags.exists():
                self.initial["tags_input"] = ", ".join(
                    self.instance.tags.values_list("name", flat=True)
                )

            if self.instance.period:
                self.initial["period"] = f"{self.instance.period.year}-{self.instance.period.month:02d}"

    def clean_amount(self) -> Decimal:
        amount = self.cleaned_data["amount"]
        if amount == 0:
            raise ValidationError("Amount cannot be zero.")
        return amount

    # CORRIGIDO: Melhoria no tratamento de exceções na validação do período
    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("type")
        category_name = (cleaned.get("category") or "").strip()

        if tipo == "TR":
            cleaned["category"] = None
            self.cleaned_data["tags_input"] = self.cleaned_data.get("tags_input", "")
        elif category_name:
            category = Category.objects.filter(user=self.user, name__iexact=category_name).first()
            if not category:
                category = Category.objects.create(user=self.user, name=category_name)
            cleaned["category"] = category
        else:
            self.add_error("category", "You must provide a category.")
            cleaned["category"] = None

        period_str = self.data.get("period", "").strip()
        if period_str:
            try:
                dt = datetime.strptime(period_str, "%Y-%m")
                if dt.month < 1 or dt.month > 12:
                    raise ValueError("Invalid month")
                
                # Add year validation to prevent unreasonable dates
                current_year = datetime.now().year
                if dt.year < 1900 or dt.year > current_year + 10:
                    raise ValueError(f"Year must be between 1900 and {current_year + 10}")
                    
                period, _ = DatePeriod.objects.get_or_create(
                    year=dt.year,
                    month=dt.month,
                    defaults={"label": dt.strftime("%B %Y")},
                )
                cleaned["period"] = period
            except ValueError as e:
                self.add_error("period", f"Invalid period format: {str(e)}")
            except Exception as e:
                self.add_error("period", f"Error processing period: {str(e)}")
        elif not cleaned.get("date"):
            # If neither date nor period is provided, add an error
            self.add_error(None, "Either date or period must be provided")
        
        return cleaned

    def save(self, commit=True) -> Transaction:
        instance = super().save(commit=False)
        instance.user = self.user
        instance.category = self.cleaned_data.get("category", instance.category)

        if commit:
            instance.save()

        # Guardar tags (seguro mesmo se tags_input não existir)
        raw_tags = self.cleaned_data.get("tags_input", "")
        tag_names = [t.strip() for t in raw_tags.split(",") if t.strip()]
        tags = []
        for name in tag_names:
            tag, _ = Tag.objects.get_or_create(user=self.user, name=name)
            tags.append(tag)

        instance.tags.set(tags)
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
        if name.lower() in ['other', 'outro', 'others']:
            if not self.instance.pk:
                raise ValidationError("Reserved category names cannot be created manually.")

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
        existing = Category.objects.filter(
            user=self.user,
            name__iexact=new_name
        ).exclude(pk=self.instance.pk).first()

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
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Account name"}),
        max_length=70,
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
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance and getattr(self.instance, 'account_id', None):
            self.initial['account'] = self.instance.account.name

    def clean_account(self):
        name = self.cleaned_data.get("account", "").strip()
        if not name:
            raise ValidationError("Account name is required.")
        if len(name) > 100:
            raise ValidationError("Account name cannot exceed 100 characters.")

        account_qs = Account.objects.filter(user=self.user, name__iexact=name)
        if account_qs.exists():
            return account_qs.first()
        else:
            account_type = AccountType.objects.filter(name__iexact="Savings").first() or AccountType.objects.first()
            currency = Currency.objects.filter(code__iexact="EUR").first() or Currency.objects.first()
            return Account.objects.create(
                user=self.user,
                name=name,
                account_type=account_type,
                currency=currency,
            )

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
    class Meta:
        model = Account
        fields = ("name", "account_type", "currency")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "account_type": forms.Select(attrs={"class": "form-control"}),
            "currency": forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)

        self.fields["account_type"].queryset = AccountType.objects.order_by("name")
        self.fields["currency"].queryset = Currency.objects.order_by("code")

        if not self.instance.pk and getattr(user, "settings", None) and user.settings.default_currency:
            self.initial["currency"] = user.settings.default_currency

    def clean_name(self) -> str:
        return self.cleaned_data["name"].strip()

    def find_duplicate(self) -> Account | None:
        """Returns an existing account with the same name (case-insensitive), if any."""
        name = self.cleaned_data.get("name", "").strip()
        return Account.objects.filter(
            user=self.user,
            name__iexact=name
        ).exclude(pk=self.instance.pk).first()

    def save(self, commit: bool = True) -> Account:
        new_name = self.cleaned_data["name"].strip()
        self.cleaned_data["name"] = new_name
        self.instance.name = new_name
        self.instance.user = self.user

        existing_qs = Account.objects.filter(
            user=self.user,
            name__iexact=new_name
        ).exclude(pk=self.instance.pk)

        if existing_qs.exists():
            existing = existing_qs.first()

            if existing.name.strip().lower() == "cash":
                raise ValidationError("Merging with 'Cash' account is not allowed.")

            if (
                existing.currency_id != self.cleaned_data["currency"].id or
                existing.account_type_id != self.cleaned_data["account_type"].id
            ):
                raise ValidationError("Já existe uma conta com esse nome, mas com tipo ou moeda diferente. Não é possível fundir.")

            confirm_merge = self.data.get("confirm_merge", "").lower() == "true"
            if not confirm_merge:
                self.add_error(None, "Já existe uma conta com esse nome. Queres fundir os saldos?")
                return self.instance  # ⚠️ Voltar para form_invalid sem crash

            # Fundir saldos
            for balance in AccountBalance.objects.filter(account=self.instance):
                existing_balance = AccountBalance.objects.filter(
                    account=existing,
                    period=balance.period
                ).first()

                if existing_balance:
                    # Fix: use reported_balance instead of amount
                    existing_balance.reported_balance += balance.reported_balance
                    existing_balance.save()
                    balance.delete()
                else:
                    balance.account = existing
                    balance.save()
            

            if self.instance.pk:
                self.instance.delete()

            return existing

        if commit:
            self.instance.save()
        return self.instance


class TransactionImportForm(forms.Form):
    file = forms.FileField(
        label="Ficheiro Excel",
        help_text="Seleciona um ficheiro .xlsx com as transações",
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control"
        })
    )