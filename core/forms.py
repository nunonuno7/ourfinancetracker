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





class UserAwareMixin:
    def __init__(
        self,
        *args: Any,
        user: User | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.user: User | None = user


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
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "type": forms.Select(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "account": forms.Select(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "is_cleared": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        if self.user:
            self.fields["category"].queryset = Category.objects.filter(user=self.user).order_by("name")
            self.fields["account"].queryset = Account.objects.filter(user=self.user).order_by("name")

    def clean_amount(self) -> Decimal:
        amount: Decimal = self.cleaned_data["amount"]
        if amount == 0:
            raise ValidationError("Amount cannot be zero.")
        return amount


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
        widgets = {"name": forms.TextInput(attrs={"class": "form-control"})}

    def __init__(self, *args: Any, user: User | None = None, **kwargs: Any) -> None:
        super().__init__(*args, user=user, **kwargs)
        self.instance.user = self.user
        qs = Category.objects.filter(user=self.user).order_by("parent__name", "name") if self.user else Category.objects.none()
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
            raise ValidationError("A category with the same name already exists at this level.")
        return cleaned

    def save(self, commit: bool = True) -> Category:
        instance: Category = super().save(commit=False)
        instance.user = self.user
        if commit:
            instance.save()
        return instance


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
        super().__init__(*args, **kwargs)
        self.user = user
        if self.instance and getattr(self.instance, 'account_id', None):
            self.initial['account'] = self.instance.account.name

    def clean_account(self):
        name = self.cleaned_data.get("account", "").strip()
        if not name:
            raise ValidationError("Account name is required.")

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
        instance.reported_balance = self.cleaned_data["reported_balance"]

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
    can_delete=True,  # 👈 este é o ponto importante
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

    def save(self, commit: bool = True) -> Account:
        from .models import AccountBalance

        new_name = self.cleaned_data["name"].strip()
        self.cleaned_data["name"] = new_name
        self.instance.name = new_name
        self.instance.user = self.user

        # Procurar conta com o mesmo nome (ignorando maiúsculas)
        existing_qs = Account.objects.filter(
            user=self.user,
            name__iexact=new_name
        ).exclude(pk=self.instance.pk)

        if existing_qs.exists():
            existing = existing_qs.first()

            # ⚠️ Impedir fusão com conta 'Cash'
            if existing.name.strip().lower() == "cash":
                raise ValidationError("Não é permitido fundir com a conta 'Cash'.")

            # ⚠️ Incompatível se tiver moeda ou tipo diferente
            if (
                existing.currency_id != self.cleaned_data["currency"].id or
                existing.account_type_id != self.cleaned_data["account_type"].id
            ):
                raise ValidationError("Já existe uma conta com esse nome, mas com tipo ou moeda diferente. Não é possível fundir.")

            # ⚠️ Verificar se o utilizador confirmou
            confirm_merge = self.data.get("confirm_merge", "").lower() == "true"
            if not confirm_merge:
                self.add_error(None, "Já existe uma conta com esse nome. Queres fundir os saldos?")
                return self.instance  # Não salvar ainda

            # ✅ Fundir saldos: combinar valores por (ano, mês)
            for balance in AccountBalance.objects.filter(account=self.instance):
                existing_balance = AccountBalance.objects.filter(
                    account=existing,
                    year=balance.year,
                    month=balance.month
                ).first()

                if existing_balance:
                    existing_balance.amount += balance.amount
                    existing_balance.save()
                    balance.delete()
                else:
                    balance.account = existing
                    balance.save()

            # Se estiver a editar uma conta existente, apagar após a fusão
            if self.instance.pk:
                self.instance.delete()

            return existing

        # ✅ Sem conflito — guardar normalmente
        if commit:
            self.instance.save()
        return self.instance
