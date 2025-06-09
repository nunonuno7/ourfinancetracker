
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

# Built-in
import sys
import json
import hashlib
from io import BytesIO
from calendar import monthrange
from datetime import date, datetime
from typing import Any, Dict
from urllib.parse import urlencode

# 3rd party
import pandas as pd
import openpyxl
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter
from psycopg2.extras import execute_values

# Django core
from django.http import (
    HttpResponse, JsonResponse, Http404, HttpResponseForbidden
)
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.cache import cache_page
from django.utils.cache import patch_vary_headers
from django.utils.dateparse import parse_date
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.cache import cache
from django.db import connection, transaction as db_transaction
from django.db.models import Q, QuerySet, Sum, F
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator



# Django views
from django.views.generic import (
    CreateView, DeleteView, ListView, RedirectView, TemplateView,
    UpdateView, View
)

# App-specific
from .models import (
    Transaction, Account, AccountBalance, Category, Tag, DatePeriod
)
from .forms import (
    TransactionImportForm, TransactionForm, AccountForm,
    AccountBalanceFormSet, CategoryForm, CustomUserCreationForm
)

from core.mixins import UserInFormKwargsMixin


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from core.cache import TX_LAST

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

@method_decorator(cache_page(60 * 5), name='dispatch')
class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):
        self.object = form.save()
        if self.request.headers.get("HX-Request") == "true":
            # Responde com JSON simples para sucesso
            return JsonResponse({"success": True})
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            # Retorna erros JSON para o frontend processar e mostrar
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        print("\U0001f6d8 Formulário inválido:", form.errors)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("name")

        # Garante que a lista de categorias está disponível apenas para GET
        if self.request.method == "GET":
            context["category_list"] = list(
                Category.objects.filter(user=self.request.user).values_list("name", flat=True)
            )
        return context



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


@login_required
def transaction_clear_cache(request):
    user_id = request.user.id
    TX_LAST.pop(user_id, None)
    messages.success(request, "✅ Cache limpa. Os dados serão recarregados.")
    return redirect("transaction_list")

def parse_safe_date(value, fallback):
    """Tenta converter uma string para date com múltiplos formatos."""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    return fallback



@login_required
@require_GET
def transactions_json(request):
    import logging
    import pandas as pd
    from core.cache import TX_LAST

    logging.getLogger("django.server").setLevel(logging.WARNING)
    user_id = request.user.id

    # 🗓️ Datas de início e fim
    raw_start = request.GET.get("date_start")
    raw_end = request.GET.get("date_end")
    start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
    end_date = parse_safe_date(raw_end, date.today())

    if not start_date or not end_date:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    print(f"📅 Intervalo: {start_date} → {end_date}")

    # 🧠 Verifica cache local

    cache_data = TX_LAST.get(user_id, {})
    cached_start = cache_data.get("start")
    cached_end = cache_data.get("end")

    if cached_start and cached_end and cached_start <= start_date and cached_end >= end_date:
        print("✅ Cache usada — a aplicar filtros e ordenação em memória")
        df = cache_data["df"].copy()
    else:
        print("📅 Query SQL nova (cache vazia ou expirada)")


        print("📅 Query SQL nova (cache vazia ou expirada)")
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                       COALESCE(cat.name, '') AS category,
                       COALESCE(acc.name, '') AS account,
                       COALESCE(curr.symbol, '') AS currency,
                       COALESCE(STRING_AGG(tag.name, ', '), '') AS tags
                FROM core_transaction tx
                LEFT JOIN core_category cat ON tx.category_id = cat.id
                LEFT JOIN core_account acc ON tx.account_id = acc.id
                LEFT JOIN core_currency curr ON acc.currency_id = curr.id
                LEFT JOIN core_dateperiod dp ON tx.period_id = dp.id
                LEFT JOIN core_transactiontag tt ON tt.transaction_id = tx.id
                LEFT JOIN core_tag tag ON tt.tag_id = tag.id
                WHERE tx.user_id = %s AND tx.date BETWEEN %s AND %s
                GROUP BY tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                         cat.name, acc.name, curr.symbol
                ORDER BY tx.id
            """, [user_id, start_date, end_date])
            rows = cursor.fetchall()

        df = pd.DataFrame(rows, columns=[
            "id", "date", "year", "month", "type", "amount",
            "category", "account", "currency", "tags"
        ])
        TX_LAST[user_id] = {"df": df.copy(), "start": start_date, "end": end_date}

    # 🧠 Preparar colunas
    df["date"] = df["date"].astype(str)
    df["period"] = df["year"].astype(str) + "-" + df["month"].astype(int).astype(str).str.zfill(2)
    df["type"] = df["type"].map(dict(Transaction.Type.choices)).fillna(df["type"])
    df["amount_float"] = df["amount"].astype(float)

    # 📊 Cópias para cada filtro (excluindo ele próprio)
    df_for_type = df.copy()
    df_for_category = df.copy()
    df_for_account = df.copy()
    df_for_period = df.copy()

    # 🪟 Filtros recebidos
    tx_type = request.GET.get("type", "").strip()
    category = request.GET.get("category", "").strip()
    account = request.GET.get("account", "").strip()
    period = request.GET.get("period", "").strip()
    search = request.GET.get("search[value]", "").strip()

    if tx_type:
        df = df[df["type"] == tx_type]
        df_for_category = df_for_category[df_for_category["type"] == tx_type]
        df_for_account = df_for_account[df_for_account["type"] == tx_type]
        df_for_period = df_for_period[df_for_period["type"] == tx_type]

    if category:
        df = df[df["category"].str.contains(category, case=False, na=False)]
        df_for_type = df_for_type[df_for_type["category"].str.contains(category, case=False, na=False)]
        df_for_account = df_for_account[df_for_account["category"].str.contains(category, case=False, na=False)]
        df_for_period = df_for_period[df_for_period["category"].str.contains(category, case=False, na=False)]

    if account:
        df = df[df["account"].str.contains(account, case=False, na=False)]
        df_for_type = df_for_type[df_for_type["account"].str.contains(account, case=False, na=False)]
        df_for_category = df_for_category[df_for_category["account"].str.contains(account, case=False, na=False)]
        df_for_period = df_for_period[df_for_period["account"].str.contains(account, case=False, na=False)]

    if period:
        try:
            y, m = map(int, period.split("-"))
            df = df[(df["year"] == y) & (df["month"] == m)]
            df_for_type = df_for_type[(df_for_type["year"] == y) & (df_for_type["month"] == m)]
            df_for_category = df_for_category[(df_for_category["year"] == y) & (df_for_category["month"] == m)]
            df_for_account = df_for_account[(df_for_account["year"] == y) & (df_for_account["month"] == m)]
        except Exception as e:
            print(f"❌ Erro no filtro por período: {e}")

    if search:
        df = df[
            df["category"].str.contains(search, case=False, na=False) |
            df["account"].str.contains(search, case=False, na=False) |
            df["type"].str.contains(search, case=False, na=False) |
            df["tags"].str.contains(search, case=False, na=False)
    ]
    # 🔢 Categorias e períodos com base nos dados visíveis (sem filtro próprio)
    unique_types = sorted(df_for_type["type"].dropna().unique())
    unique_categories = sorted(df_for_category["category"].dropna().unique())
    unique_accounts = sorted(df_for_account["account"].dropna().unique())
    available_periods = sorted(df_for_period["period"].dropna().unique(), reverse=True)

    # 🔄 Ordenação
    order_col = request.GET.get("order[0][column]", "1")
    order_dir = request.GET.get("order[0][dir]", "desc")
    ascending = order_dir != "desc"
    column_map = {
        "0": "period", "1": "date", "2": "type",
        "3": "amount_float", "4": "category", "5": "tags", "6": "account"
    }
    sort_col = column_map.get(order_col, "date")
    if sort_col in df.columns:
        try:
            df.sort_values(by=sort_col, ascending=ascending, inplace=True)
        except Exception as e:
            print(f"⚠️ Erro ao ordenar por {sort_col}: {e}")

    # 💶 Formatar montante
    df["amount"] = df.apply(lambda r: f"€ {r['amount_float']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {r['currency']}", axis=1)

    # 🏷️ Formatar tags HTML
    def format_tags(raw):
        if not raw or not isinstance(raw, str): return "–"
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        return " ".join(f"<span class='badge bg-secondary'>{t}</span>" for t in tags) if tags else "–"
    df["tags"] = df["tags"].astype(str).apply(format_tags)

    # 🔗 Ações HTML
    csrf = request.COOKIES.get("csrftoken", "")
    df["actions"] = df.apply(lambda r: f"""
        <div class='d-flex gap-2 justify-content-center'>
            <a href='/transactions/{r["id"]}/edit/' class='btn btn-sm btn-outline-primary btn-icon-fixed' title='Edit'>
            <span>✏️</span>
            </a>
            <form method='post' action='/transactions/{r["id"]}/delete/' class='delete-form d-inline' data-name='transaction on {r["date"]}'>
            <input type='hidden' name='csrfmiddlewaretoken' value='{csrf}'>
            <button type='submit' class='btn btn-sm btn-outline-danger btn-icon-fixed' title='Delete'>
                <span>🗑</span>
            </button>
            </form>
        </div>
    """, axis=1)

    # 📄 Paginação
    draw = int(request.GET.get("draw", "1"))
    start = int(request.GET.get("start", "0"))
    length = int(request.GET.get("length", "10"))
    total = len(df)
    df_page = df.iloc[start:start + length]

    return JsonResponse({
        "draw": draw,
        "recordsTotal": total,
        "recordsFiltered": total,
        "data": df_page[[ "period", "date", "type", "amount", "category", "tags", "account", "actions" ]].to_dict(orient="records"),
        "unique_types": unique_types,
        "unique_categories": unique_categories,
        "unique_accounts": unique_accounts,
        "available_periods": available_periods,
    })



class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def get_queryset(self):
        # Garante prefetch das tags para performance
        return super().get_queryset().prefetch_related("tags")

    def form_valid(self, form):
        messages.success(self.request, "Transação atualizada com sucesso!")
        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            # Renderiza o formulário atualizado (com mensagens)
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return response

    def form_invalid(self, form):
        if self.request.headers.get("HX-Request") == "true":
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_list"] = list(
            Category.objects.filter(user=self.request.user).values_list("name", flat=True)
        )
        return context


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

    def form_valid(self, form):
        merged = hasattr(form, "_merged_category")
        form.save()  # ⚠️ Pode devolver outra instância, mas ignoramos isso

        if merged:
            messages.success(self.request, "✅ The categories were merged successfully.")
        else:
            messages.success(self.request, "✅ Category updated successfully.")

        return redirect(self.get_success_url())
    
    
class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    model = Category
    template_name = "confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        option = request.POST.get("option")

        if option == "delete_all":
            # Apaga todas as transações associadas
            Transaction.objects.filter(category=self.object).delete()
            self.object.delete()
            messages.success(request, f"✅ Category and all its transactions were deleted.")
        elif option == "move_to_other":
            # Obter ou criar categoria 'Other'
            fallback = Category.get_fallback(request.user)

            # Fundir se já existir
            if fallback != self.object:
                Transaction.objects.filter(category=self.object).update(category=fallback)
                self.object.delete()
                messages.success(request, f"🔁 Transactions moved to 'Other'. Category deleted.")
            else:
                messages.warning(request, f"⚠️ Cannot delete 'Other' category.")
        else:
            messages.error(request, "❌ No valid option selected.")

        return redirect(self.success_url)


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
        """
        Adiciona as contas do utilizador e categorias ao contexto.
        """
        context = super().get_context_data(**kwargs)
        context["accounts"] = Account.objects.filter(user=self.request.user).order_by("name")
        Category.objects.filter(user=self.request.user).order_by("name").values_list("name", flat=True)


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
    # Limpa mensagens anteriores (ex: "Saldo guardado com sucesso")
    list(get_messages(request))

    # 🗓️ Determinar o mês/ano selecionado
    today = date.today()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))

    # 🔁 Obter ou criar o período correspondente
    period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    # 📥 Query base dos saldos do utilizador nesse período
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
                inst.period = period  # 🧠 já tínhamos o período acima

                if inst.account.user_id is None:
                    inst.account.user = request.user
                    inst.account.save()

                # Atualiza se já existir saldo para essa conta/período
                existing = AccountBalance.objects.filter(
                    account=inst.account,
                    period=period,
                ).first()

                if existing:
                    existing.reported_balance = inst.reported_balance
                    existing.save()
                else:
                    inst.save()

            # 🔄 Fundir contas duplicadas (por nome)
            _merge_duplicate_accounts(request.user)

            messages.success(request, "Balances saved!")
            return redirect(f"{request.path}?year={year}&month={month:02d}")

        messages.error(request, "Erro ao guardar os saldos. Verifica os campos.")
    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    # 🧮 Agrupar saldos por tipo/moeda e calcular totais
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

    # 📦 Enviar dados para o template
    context = {
        "formset": formset,
        "grouped_forms": grouped_forms,
        "totals_by_group": totals_by_group,
        "grand_total": grand_total,
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
    """Autocomplete de categorias filtradas por utilizador."""
    q = request.GET.get("q", "").strip()
    results = Category.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name")

    data = [{"name": c.name} for c in results]
    return JsonResponse(data, safe=False)

@login_required
def tag_autocomplete(request):
    """Autocomplete de tags globais do utilizador."""
    q = request.GET.get("q", "").strip()
    results = Tag.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name").values("name").distinct()

    return JsonResponse(list(results), safe=False)


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
            (
                SELECT STRING_AGG(tg.name, ', ')
                FROM core_transaction_tags tt
                JOIN core_tag tg ON tg.id = tt.tag_id
                WHERE tt.transaction_id = t.id
            ) AS Tags,
            COALESCE(a.name, '') AS Account,
            CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS Period
            FROM core_transaction t
            LEFT JOIN core_category c ON t.category_id = c.id
            LEFT JOIN core_account a ON t.account_id = a.id
            LEFT JOIN core_dateperiod p ON t.period_id = p.id
            WHERE t.user_id = %s
            GROUP BY t.id, t.date, t.type, t.amount, c.name, a.name, p.year, p.month
            ORDER BY t.date DESC
        """, [user_id])
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]



    # ⚙️ Criar DataFrame e exportar para Excel
    df = pd.DataFrame(rows, columns=columns)
    #print("📄 DataFrame criado com sucesso", flush=True)

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

        with connection.cursor() as cursor, db_transaction.atomic():
            cursor.execute("SELECT id FROM core_accounttype WHERE name ILIKE 'Savings' LIMIT 1")
            row = cursor.fetchone()
            if not row:
                raise Exception("Tipo de conta 'Savings' não existe.")
            default_account_type_id = row[0]

            for idx, row in df.iterrows():
                print(f"🔎 Linha {idx + 1}")
                date_val = parse_date(str(row["Date"]))
                if not date_val:
                    print(f"⚠️ Linha {idx + 1} ignorada: data inválida")
                    continue

                # Período
                key_period = (date_val.year, date_val.month)
                if key_period not in periods_cache:
                    cursor.execute("""
                        INSERT INTO core_dateperiod (year, month, label)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (year, month) DO NOTHING
                        RETURNING id
                    """, [date_val.year, date_val.month, date_val.strftime("%B %Y")])
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
                    user_id, date_val, row["Amount"], row["Type"], period_id,
                    category_id, account_id, "", False, True,
                    timestamp, timestamp
                ))

                # Tags
                raw_tags = str(row.get("Tags", "")).split(",")
                tags_cleaned = [t.strip() for t in raw_tags if t.strip()]
                for tag in tags_cleaned:
                    tag_links.append((len(transactions) - 1, tag))

            print(f"📝 Transações preparadas: {len(transactions)}")

            # Inserir transações
            def chunked(iterable, size=100):
                for i in range(0, len(iterable), size):
                    yield iterable[i:i + size]

            transaction_ids = []
            for chunk in chunked(transactions, 100):
                execute_values(cursor, """
                    INSERT INTO core_transaction
                    (user_id, date, amount, type, period_id, category_id, account_id,
                     notes, is_estimated, is_cleared, created_at, updated_at)
                    VALUES %s
                    RETURNING id
                """, chunk)
                transaction_ids.extend([row[0] for row in cursor.fetchall()])

            # Tags
            all_tag_names = sorted(set(tag for _, tag in tag_links))
            if all_tag_names:
                cursor.execute(
                    "SELECT id, name FROM core_tag WHERE name = ANY(%s) AND user_id = %s",
                    [all_tag_names, user_id]
                )
                for tag_id, tag_name in cursor.fetchall():
                    tag_cache[tag_name] = tag_id

                missing = [name for name in all_tag_names if name not in tag_cache]
                if missing:
                    execute_values(cursor, """
                        INSERT INTO core_tag (user_id, name, position)
                        VALUES %s
                        RETURNING id, name
                    """, [(user_id, name, 0) for name in missing])
                    for tag_id, tag_name in cursor.fetchall():
                        tag_cache[tag_name] = tag_id

            # Ligações tag-transação
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

        # 🧹 Limpar cache de transações do utilizador
        if request.user.id in TX_LAST:
            print(f"🧹 Limpar cache TX_LAST após importação (user_id={request.user.id})")
            del TX_LAST[request.user.id]

        # ✅ Mensagem de sucesso
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



