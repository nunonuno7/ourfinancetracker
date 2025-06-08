
"""
Views for the *ourfinancetracker* core app.

The file was rewritten to:
• remove duplicated imports
• share common behaviour in mix‑ins (user injection & ownership filtering)
• add a dedicated ``AccountForm`` (see ``core/forms.py``) and reuse it in the account CBVs
• tighten querysets so a user can only access her own data
• add docstrings and type hints for easier maintenance
• introduce a MergeView for account fusion with confirmation
"""
from __future__ import annotations
from openpyxl import Workbook
from django.http import HttpResponse
from django.db import connection
from openpyxl import load_workbook
from calendar import monthrange
from datetime import date
from typing import Any, Dict
from .forms import TransactionImportForm
import logging
from django.views.decorators.http import require_POST
from datetime import datetime
import pandas as pd
from django.http import HttpResponse
from django.db import connection
from io import BytesIO
from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import QuerySet, Sum, F
from django.http import JsonResponse, Http404, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
import sys
from django.urls import reverse_lazy, reverse
from django.utils.functional import cached_property
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.views.generic import (
    CreateView, DeleteView, ListView, RedirectView, TemplateView,
    UpdateView, View
)


from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.cache import cache
from hashlib import md5
from .models import Transaction

from .forms import (
    AccountBalanceFormSet,
    AccountForm,
    CategoryForm,
    CustomUserCreationForm,
    TransactionForm,
)
from .models import Account, AccountBalance, Category, Transaction, Tag


from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from .models import Account
from django.contrib.auth.decorators import login_required
from .models import DatePeriod


from django.http import JsonResponse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET


import openpyxl
from openpyxl.utils import get_column_letter
from django.http import HttpResponse

import openpyxl
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import Transaction, Category, Tag, Account, DatePeriod
from django.utils.dateparse import parse_date
from datetime import date
from django.db import transaction as db_transaction

from django.contrib import messages
from django.db import connection, transaction
from django.utils.dateparse import parse_date
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
import pandas as pd
from psycopg2.extras import execute_values

from django.utils.timezone import now

################################################################################
#                               Menu config API                                #
################################################################################

print("✅ O ficheiro views.py foi carregado")

@login_required
def menu_config(request):
    return JsonResponse({
        "username": request.user.username,
        "links": [
            {"name": "Dashboard", "url": reverse("transaction_list")},
            {"name": "New Transaction", "url": reverse("transaction_create")},
            {"name": "Categories", "url": reverse("category_list")},
            {"name": "Account Balances", "url": reverse("account_balance")},
        ]
    })


################################################################################
#                               Shared mix‑ins                                 #
################################################################################


class UserInFormKwargsMixin:
    """Injects the current *request.user* into ModelForm kwargs."""

    def get_form_kwargs(self) -> Dict[str, Any]:  # type: ignore[override]
        kwargs: Dict[str, Any] = super().get_form_kwargs()  # type: ignore[misc]
        kwargs["user"] = self.request.user
        return kwargs


class OwnerQuerysetMixin(LoginRequiredMixin):
    """Limits queryset to objects owned by the current user."""

    def get_queryset(self) -> QuerySet:  # type: ignore[override]
        qs: QuerySet = super().get_queryset()  # type: ignore[misc]
        return qs.filter(user=self.request.user)




class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "core/dashboard.html"


################################################################################
#                             Transaction views                                #
################################################################################

class TransactionListView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = "core/transaction_list.html"
    context_object_name = "transactions"

    def get_queryset(self) -> QuerySet:
        return (
            super().get_queryset()
            .filter(user=self.request.user)
            .order_by("-date")
        )


class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """
    View para criar uma nova transação.

    Compatível tanto com o formulário padrão (transaction_form.html),
    como com o formulário inline na listagem (transaction_list.html).
    """
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("HX-Request") == "true":
            # Submissão via HTMX (opcional)
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        print("🚫 Form inválido:", form.errors)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """
        Adiciona contas do utilizador ao contexto se necessário
        (ex: para seleção no formulário ou rendering custom).
        """
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("name")
        return context


from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from django.db.models import Q
from django.http import JsonResponse
import hashlib

from django.views.decorators.cache import cache_page
from django.utils.cache import patch_vary_headers
from django.core.cache import cache
from django.db.models import Q
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from .models import Transaction

from urllib.parse import urlencode

@require_GET
@login_required
def period_autocomplete(request):
    q = request.GET.get("q", "")
    periods = DatePeriod.objects.all().order_by("-year", "-month")

    if q:
        try:
            year, month = map(int, q.split("-"))
            periods = periods.filter(year=year, month=month)
        except:
            periods = periods.none()

    results = [
        {
            "value": f"{p.year}-{p.month:02}",
            "display_name": f"{p.label}",
        }
        for p in periods
    ]
    return JsonResponse(results, safe=False)



@require_GET
@login_required
def transactions_json(request):
    print("🚨 ENTROU na transactions_json")

    # ⛔ Ocultar GET gigante no terminal
    logging.getLogger("django.server").setLevel(logging.WARNING)

    user = request.user
    params = request.GET.copy()
    params.pop("_", None)  # remove timestamp do DataTables
    query_string = urlencode(sorted(params.items()))

    raw_key = f"transactions_json_user_{user.id}_{query_string}"
    cache_key = "transactions_json_" + md5(raw_key.encode()).hexdigest()
    print(f"🔁 CHAVE DE CACHE: {cache_key}")

    # 📦 Tentar usar cache
    cached_response = cache.get(cache_key)
    if cached_response:
        print("✅ USOU CACHE")
        return cached_response

    print("❌ NÃO USOU CACHE — vai gerar a resposta")

    # 🧱 Colunas disponíveis
    columns = [
        'period', 'date', 'type', 'amount',
        'category__name', 'tags__name', 'account__name', 'id'
    ]

    # 🧩 Parâmetros do DataTables
    draw = int(request.GET.get('draw', '1'))
    start = int(request.GET.get('start', '0'))
    length = int(request.GET.get('length', '10'))
    search_value = request.GET.get('search[value]', '').strip()

    # 🎯 Filtros específicos
    filter_type = request.GET.get('type', '').strip()
    filter_account = request.GET.get('account', '').strip()
    filter_category = request.GET.get('category', '').strip()
    filter_period = request.GET.get('period', '').strip()

    # 🔽 Ordenação
    order_col_index = int(request.GET.get('order[0][column]', 1))
    order_dir = request.GET.get('order[0][dir]', 'desc')
    order_field = columns[order_col_index] if order_col_index < len(columns) else 'date'
    if order_dir == 'desc':
        order_field = '-' + order_field

    # 🔍 Base QuerySet
    qs = Transaction.objects.filter(user=user)

    # ⛳ Aplicar filtros
    if filter_type:
        qs = qs.filter(type=filter_type)
    if filter_account:
        qs = qs.filter(account__id=filter_account)
    if filter_category:
        qs = qs.filter(category__id=filter_category)
    if filter_period:
        try:
            year, month = map(int, filter_period.split('-'))
            qs = qs.filter(period__year=year, period__month=month)
        except ValueError:
            pass

    # 🔎 Filtro global
    if search_value:
        qs = qs.filter(
            Q(category__name__icontains=search_value) |
            Q(type__icontains=search_value) |
            Q(account__name__icontains=search_value)
        ).distinct()

    total_records = Transaction.objects.filter(user=user).count()
    filtered_records = qs.count()

    # 🧮 Ordenar corretamente por ano/mês
    if order_field.lstrip('-') == 'period':
        prefix = '-' if order_field.startswith('-') else ''
        qs = qs.order_by(f"{prefix}period__year", f"{prefix}period__month")
    else:
        qs = qs.order_by(order_field)

    # 📄 Paginação
    qs = qs[start:start + length]

    # 📦 Preparar JSON
    data = []
    for tx in qs:
        period_str = f"{tx.period.year}-{tx.period.month:02d}" if tx.period else ""
        data.append({
            "period": period_str,
            "date": tx.date.strftime("%Y-%m-%d") if tx.date else "",
            "type": tx.get_type_display(),
            "amount": f"{tx.amount:.2f}" if tx.amount is not None else "",
            "category": tx.category.name if tx.category else "–",
            "tags": [tag.name for tag in tx.tags.all()],
            "account": str(tx.account) if tx.account else "–",
            "id": tx.pk,
            "currency": tx.account.currency.symbol if tx.account and tx.account.currency else "",
        })

    response_data = {
        "draw": draw,
        "recordsTotal": total_records,
        "recordsFiltered": filtered_records,
        "data": data,
    }

    # 💾 Guardar no cache por 5 minutos
    response = JsonResponse(response_data)
    cache.set(cache_key, response, timeout=300)

    # 🧩 Guardar chave na lista do utilizador
    key_list_name = f"transactions_json_keys_user_{user.id}"
    key_list = cache.get(key_list_name, [])
    if cache_key not in key_list:
        key_list.append(cache_key)
        cache.set(key_list_name, key_list, timeout=300)

    return response


class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")


class TransactionDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list")

################################################################################
#                               Category views                                 #
################################################################################


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().filter(user=self.request.user)  # type: ignore[misc]


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):  # type: ignore[override]
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "core/confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

################################################################################
#                               Account views                                  #
################################################################################





class AccountListView(LoginRequiredMixin, ListView):
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self) -> QuerySet:
        return (
            super()
            .get_queryset()
            .filter(user=self.request.user)
            .order_by("position", "name")
        )
# views.py
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Protege o acesso à relação OneToOne
        default_currency = getattr(user, "settings", None)
        context["default_currency"] = getattr(default_currency, "default_currency", "€")

        # (Resto da lógica permanece igual)
        return context


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        # Verificar se existe conta com o mesmo nome
        existing = form.find_duplicate()

        if existing:
            # Se a fusão ainda não foi confirmada, apenas mostrar erro no formulário
            if not self.request.POST.get("confirm_merge", "").lower() == "true":
                form.add_error(None, "Já existe uma conta com esse nome. Queres fundir os saldos?")
                return self.form_invalid(form)

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        # Verifica se há outra conta com o mesmo nome (ignorando maiúsculas/minúsculas)
        new_name = form.cleaned_data["name"].strip()
        existing = Account.objects.filter(
            user=self.request.user,
            name__iexact=new_name
        ).exclude(pk=self.object.pk).first()

        if existing:
            # Guarda o objeto editado para depois fundir
            form.save(commit=False)  # não guardamos já no DB
            return redirect(
                "account_merge",
                source_pk=self.object.pk,
                target_pk=existing.pk
            )

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")

    def dispatch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.name.lower() == "cash":
            return HttpResponseForbidden("Default account cannot be deleted.")
        return super().dispatch(request, *args, **kwargs)


class AccountMergeView(OwnerQuerysetMixin, View):
    template_name = "core/confirms/account_confirm_merge.html"
    success_url = reverse_lazy("account_list")

    def get(self, request, *args, **kwargs):
        self.source = self.get_source_account()
        self.target = self.get_target_account()

        if not self.source or not self.target:
            messages.error(request, "Accounts not found for merging.")
            return redirect("account_list")

        return render(request, self.template_name, {
            "source": self.source,
            "target": self.target,
        })


    def post(self, request, *args, **kwargs):
        target = self.get_target_account()
        source = self.get_source_account()

        if not source or not target or source == target:
            messages.error(request, "Invalid merge.")
            return redirect("account_list")

        # Reconciliar saldos duplicados
        for bal in AccountBalance.objects.filter(account=source):
            existing = AccountBalance.objects.filter(
                account=target, period=bal.period
            ).first()

            if existing:
                # Exemplo: somar os saldos
                existing.reported_balance += bal.reported_balance
                existing.save()
                bal.delete()
            else:
                bal.account = target
                bal.save()

        source.delete()
        messages.success(request, f"Merged account '{source.name}' into '{target.name}'")
        return redirect(self.success_url)


    def get_source_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["source_pk"]).first()

    def get_target_account(self):
        return Account.objects.filter(user=self.request.user, pk=self.kwargs["target_pk"]).first()

################################################################################
#                           Account balance view                               #
################################################################################

@login_required
def account_balance_view(request):
    list(get_messages(request))
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    if request.method == "GET":
        list(get_messages(request))

    period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        period=period
    ).select_related("account", "account__account_type", "account__currency")

    if request.method == "POST":
        formset = AccountBalanceFormSet(request.POST, queryset=qs_base, user=request.user)

        if formset.is_valid():
            instances = formset.save(commit=False)

            for form in formset:
                if form.cleaned_data.get("DELETE"):
                    continue

                inst = form.save(commit=False)

                period, _ = DatePeriod.objects.get_or_create(
                    year=year,
                    month=month,
                    defaults={"label": date(year, month, 1).strftime("%B %Y")},
                )
                inst.period = period

                if inst.account.user_id is None:
                    inst.account.user = request.user
                    inst.account.save()

                existing = AccountBalance.objects.filter(
                    account=inst.account,
                    period=period,
                ).first()

                if existing:
                    existing.reported_balance = inst.reported_balance
                    existing.save()
                else:
                    inst.save()

     
            _merge_duplicate_accounts(request.user)

            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")

        messages.error(request, "Erro ao guardar os saldos. Verifica os campos.")
    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    # 🔄 Agrupar e calcular totais
    grouped_forms = {}
    totals_by_group = {}
    grand_total = 0

    for form in formset:
        account = form.instance.account
        key = (account.account_type.name, account.currency.code)
        grouped_forms.setdefault(key, []).append(form)

    for key, forms in grouped_forms.items():
        subtotal = sum((f.instance.reported_balance or 0) for f in forms)
        totals_by_group[key] = subtotal
        grand_total += subtotal

    context = {
        "formset": formset,
        "grouped_forms": grouped_forms,
        "totals_by_group": totals_by_group,  # 👈 para subtotais no template
        "grand_total": grand_total,          # 👈 para total global no fim
        "year": year,
        "month": month,
        "selected_month": date(year, month, 1),
    }

    return render(request, "core/account_balance.html", context)


def _merge_duplicate_accounts(user):
    seen = {}
    for acc in Account.objects.filter(user=user).order_by("name"):
        name = acc.name.strip().lower()
        if name in seen:
            primary = seen[name]
            AccountBalance.objects.filter(account=acc).update(account=primary)
            acc.delete()
        else:
            seen[name] = acc

################################################################################
#                               Misc views                                     #
################################################################################

def signup(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("transaction_list")
    else:
        form = CustomUserCreationForm()
    return render(request, "registration/signup.html", {"form": form})


class LogoutView(RedirectView):
    pattern_name = "login"

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super().get(request, *args, **kwargs)


class HomeView(TemplateView):
    template_name = "core/home.html"


@require_POST
@csrf_exempt
@login_required
def delete_account_balance(request, pk):
    try:
        obj = AccountBalance.objects.get(pk=pk, account__user=request.user)
        obj.delete()
        return JsonResponse({"success": True})
    except AccountBalance.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)



@require_GET
@login_required
def copy_previous_balances_view(request):
    """Copies balances from the previous month if they do not already exist."""
    year = int(request.GET.get("year"))
    month = int(request.GET.get("month"))

    # Calcula mês anterior
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year

    user = request.user
    created_count = 0

    previous_period = DatePeriod.objects.filter(year=prev_year, month=prev_month).first()
    if not previous_period:
        return JsonResponse({"success": False, "error": "Previous period not found"}, status=404)

    target_period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    previous_balances = AccountBalance.objects.filter(
        account__user=user,
        period=previous_period
    ).select_related("account")

    for bal in previous_balances:
        exists = AccountBalance.objects.filter(
            account=bal.account,
            period=target_period
        ).exists()

        if not exists:
            AccountBalance.objects.create(
                account=bal.account,
                period=target_period,
                reported_balance=bal.reported_balance
            )
            created_count += 1

    return JsonResponse({"success": True, "created": created_count})



@login_required
def move_account_up(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    above = Account.objects.filter(user=request.user, position__lt=account.position).order_by("-position").first()
    if above:
        account.position, above.position = above.position, account.position
        account.save()
        above.save()
    return redirect("account_list")

@login_required
def move_account_down(request, pk):
    account = get_object_or_404(Account, pk=pk, user=request.user)
    below = Account.objects.filter(user=request.user, position__gt=account.position).order_by("position").first()
    if below:
        account.position, below.position = below.position, account.position
        account.save()
        below.save()
    return redirect("account_list")

@csrf_exempt  # Ou substitui por @login_required + token se estiver a funcionar corretamente
@login_required
def account_reorder(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order = data.get("order", [])
            for item in order:
                Account.objects.filter(pk=item["id"], user=request.user).update(position=item["position"])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "invalid method"}, status=405)


from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def category_autocomplete(request):
    q = request.GET.get("q", "")
    user = request.user
    results = Category.objects.filter(user=user, name__icontains=q).order_by("name")
    return JsonResponse([{"name": c.name} for c in results], safe=False)

@login_required
def tag_autocomplete(request):
    q = request.GET.get("q", "")
    results = Tag.objects.filter(name__icontains=q).order_by("name")
    return JsonResponse([{"name": t.name} for t in results], safe=False)



@login_required
def export_transactions_xlsx(request):

    user_id = request.user.id

    # 🧠 Query SQL otimizada com tags agregadas
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              t.date AS Date,
              t.type AS Type,
              t.amount AS Amount,
              COALESCE(c.name, '') AS Category,
              STRING_AGG(tag.name, ', ') AS Tags,
              COALESCE(a.name, '') AS Account,
              CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS Period
            FROM core_transaction t
            LEFT JOIN core_category c ON t.category_id = c.id
            LEFT JOIN core_account a ON t.account_id = a.id
            LEFT JOIN core_dateperiod p ON t.period_id = p.id
            LEFT JOIN core_transaction_tags tt ON t.id = tt.transaction_id
            LEFT JOIN core_tag tag ON tag.id = tt.tag_id
            WHERE t.user_id = %s
            GROUP BY t.id, t.date, t.type, t.amount, c.name, a.name, p.year, p.month
            ORDER BY t.date DESC
        """, [user_id])
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]



    # ⚙️ Criar DataFrame e exportar para Excel
    df = pd.DataFrame(rows, columns=columns)
    print("📄 DataFrame criado com sucesso", flush=True)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Transações")
    buffer.seek(0)


    # 📤 Enviar ficheiro para download
    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=transactions.xlsx'
    return response


@login_required

def import_transactions_xlsx(request):
    if request.method == "GET":
        print("🧾 [GET] A mostrar formulário de importação")
        return render(request, "core/import_form.html")

    print("🚀 [POST] Início da importação de transações via Excel")

    try:
        file = request.FILES["file"]
        df = pd.read_excel(file)
        print(f"📄 Ficheiro recebido com {len(df)} linhas")

        required = {"Date", "Type", "Amount", "Category", "Tags", "Account"}
        if not required.issubset(df.columns):
            missing = required - set(df.columns)
            print(f"❌ Faltam colunas: {missing}")
            messages.error(request, f"Missing columns: {', '.join(missing)}")
            return redirect("transaction_import_xlsx")

        user_id = request.user.id
        transactions = []
        tag_links = []
        periods_cache = {}
        category_cache = {}
        account_cache = {}
        tag_cache = {}

        timestamp = now()
        print(f"📌 Timestamp para created_at/updated_at: {timestamp}")

        with connection.cursor() as cursor, transaction.atomic():
            cursor.execute("SELECT id FROM core_accounttype WHERE name ILIKE 'Savings' LIMIT 1")
            row = cursor.fetchone()
            if not row:
                raise Exception("Tipo de conta 'Savings' não existe.")
            default_account_type_id = row[0]

            for idx, row in df.iterrows():
                date = parse_date(str(row["Date"]))
                if not date:
                    print(f"⚠️ Linha {idx+1} ignorada: data inválida")
                    continue

                # Período
                key_period = (date.year, date.month)
                if key_period not in periods_cache:
                    cursor.execute("""
                        INSERT INTO core_dateperiod (year, month, label)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (year, month) DO NOTHING
                        RETURNING id
                    """, [date.year, date.month, date.strftime("%B %Y")])
                    row_period = cursor.fetchone()
                    if not row_period:
                        cursor.execute("SELECT id FROM core_dateperiod WHERE year = %s AND month = %s", key_period)
                        row_period = cursor.fetchone()
                    periods_cache[key_period] = row_period[0]
                period_id = periods_cache[key_period]

                # Categoria
                cat_name = str(row["Category"]).strip()
                if cat_name not in category_cache:
                    cursor.execute("""
                        INSERT INTO core_category (user_id, name, position, created_at, updated_at)
                        VALUES (%s, %s, 0, %s, %s)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, cat_name, timestamp, timestamp])
                    row_cat = cursor.fetchone()
                    if not row_cat:
                        cursor.execute("SELECT id FROM core_category WHERE user_id = %s AND name = %s", [user_id, cat_name])
                        row_cat = cursor.fetchone()
                    category_cache[cat_name] = row_cat[0]
                category_id = category_cache[cat_name]

                # Conta
                acc_name = str(row["Account"]).strip()
                if acc_name not in account_cache:
                    cursor.execute("""
                        INSERT INTO core_account (user_id, name, account_type_id, currency_id, created_at, position)
                        VALUES (%s, %s, %s, NULL, %s, 0)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, acc_name, default_account_type_id, timestamp])
                    row_acc = cursor.fetchone()
                    if not row_acc:
                        cursor.execute("SELECT id FROM core_account WHERE user_id = %s AND name = %s", [user_id, acc_name])
                        row_acc = cursor.fetchone()
                    account_cache[acc_name] = row_acc[0]
                account_id = account_cache[acc_name]

                # Transação
                transactions.append((
                    user_id, date, row["Amount"], row["Type"], period_id,
                    category_id, account_id, "", False, True,
                    timestamp, timestamp
                ))

                # Tags associadas a esta transação
                raw_tags = str(row.get("Tags", "")).split(",")
                for tag in [t.strip() for t in raw_tags if t.strip()]:
                    tag_links.append((len(transactions) - 1, tag))

            print(f"📝 Transações preparadas: {len(transactions)}")
            print(f"🏷 Tags identificadas: {len(tag_links)}")

            # Inserir transações
            execute_values(cursor, """
                INSERT INTO core_transaction
                (user_id, date, amount, type, period_id, category_id, account_id,
                 notes, is_estimated, is_cleared, created_at, updated_at)
                VALUES %s
                RETURNING id
            """, transactions)
            transaction_ids = [row[0] for row in cursor.fetchall()]
            print(f"✅ Inseridas {len(transaction_ids)} transações")

            # Criar/obter Tags
            all_tag_names = sorted(set(tag for _, tag in tag_links))
            if all_tag_names:
                cursor.execute("SELECT id, name FROM core_tag WHERE name = ANY(%s)", [all_tag_names])
                for tag_id, tag_name in cursor.fetchall():
                    tag_cache[tag_name] = tag_id

                missing = [name for name in all_tag_names if name not in tag_cache]
                if missing:
                    execute_values(cursor, """
                        INSERT INTO core_tag (name, position)
                        VALUES %s
                        RETURNING id, name
                    """, [(name, 0) for name in missing])
                    for tag_id, tag_name in cursor.fetchall():
                        tag_cache[tag_name] = tag_id
                    print(f"➕ Criadas {len(missing)} novas tags")

            # Associar Tags às transações (com segurança)
            links = []
            for i, tx_id in enumerate(transaction_ids):
                for idx, tag_name in tag_links:
                    if idx == i:
                        tag_id = tag_cache.get(tag_name)
                        if tag_id:
                            links.append((tx_id, tag_id))

            if links:
                execute_values(cursor, """
                    INSERT INTO core_transactiontag (transaction_id, tag_id)
                    VALUES %s
                    ON CONFLICT DO NOTHING
                """, links)
                print(f"🔗 {len(links)} ligações tag-transação criadas")

        messages.success(request, f"✔ {len(transaction_ids)} transactions imported successfully!")

    except Exception as e:
        print("❌ Erro:", str(e))
        messages.error(request, f"❌ Import failed: {str(e)}")

    return redirect("transaction_list")




@login_required
def import_transactions_template(request):
    # Cabeçalhos da tabela
    columns = ["Date", "Type", "Amount", "Category", "Tags", "Account"]
    df = pd.DataFrame(columns=columns)

    # Criar ficheiro Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")

    output.seek(0)

    # Responder com download
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="transactions_template.xlsx"'
    return response