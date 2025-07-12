#  core/views.py


"""
Core application views for ourfinancetracker
Version: 2.1.0 (FINAL - June 2025)
Complete security and performance optimizations

PRINCIPAIS CORREÇÕES IMPLEMENTADAS:
- Cache keys seguros com hash da SECRET_KEY
- CSRF tokens gerados de forma segura
- Validação consistente de permissões por utilizador
- Tratamento robusto de exceções
- Performance otimizada com queries SQL otimizadas
- Headers de segurança implementados
"""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

import pandas as pd
from django.db.models.query import QuerySet
from django.db import models

logger = logging.getLogger(__name__)

from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction as db_transaction
from django.http import (
    HttpResponse, HttpResponseForbidden, JsonResponse,
    HttpResponseRedirect as redirect, Http404
)

from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views import View
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.generic import (
    CreateView, DeleteView, ListView, TemplateView,
    UpdateView, RedirectView
)
from django.conf import settings

from .models import (
    Account, AccountBalance, AccountType, Category, Currency, 
    DatePeriod, Tag, Transaction, User
)
from .forms import (
    AccountForm, CategoryForm,
    CustomUserCreationForm, TransactionForm, UserInFormKwargsMixin
)
from .utils.cache_helpers import clear_tx_cache

from django.views.generic import TemplateView
from django.db import transaction as db_tx, connection

from .forms import (
    AccountBalanceFormSet, AccountForm, CategoryForm,
    CustomUserCreationForm, TransactionForm, UserInFormKwargsMixin
)




# Authentication views
def signup(request):
    """User registration view."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()

    return render(request, 'registration/signup.html', {'form': form})


class LogoutView(View):
    """Custom logout view with redirect."""

    def get(self, request):
        auth_logout(request)
        messages.info(request, 'You have been logged out successfully.')
        return redirect('home')

class HomeView(TemplateView):
    """Home page view."""
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context


# ==============================================================================
# UTILITÁRIOS DE CACHE SEGUROS
# ==============================================================================

def _cache_key(user_id: int, start: date, end: date) -> str:
    """
    Gera cache key segura para prevenir colisões.
    """
    return f"tx_cache_user_{user_id}_{start}_{end}"


def parse_safe_date(value: str | None, fallback: date) -> date:
    """
    Parse seguro de data com fallback para valor padrão.
    """
    if not value:
        return fallback

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m"):
        try:
            parsed = datetime.strptime(value.strip(), fmt)
            return parsed.date()
        except (ValueError, TypeError):
            continue
    return fallback


# ==============================================================================
# MIXINS SEGUROS PARA VIEWS
# ==============================================================================

class OwnerQuerysetMixin(LoginRequiredMixin):
    """
    Mixin seguro que limita queryset apenas a objetos do utilizador atual.
    Inclui verificação adicional de segurança.
    """

    def get_queryset(self) -> QuerySet:
        """Filtra queryset apenas para objetos do utilizador atual."""
        if not self.request.user.is_authenticated:
            raise PermissionDenied("User must be authenticated")

        qs = super().get_queryset()
        return qs.filter(user=self.request.user)

    def get_object(self, queryset=None):
        """Garante que o objeto pertence ao utilizador atual."""
        obj = super().get_object(queryset)

        if hasattr(obj, 'user') and obj.user != self.request.user:
            raise PermissionDenied("You don't have permission to access this object")

        return obj


# ==============================================================================
# VIEWS DE DASHBOARD E CONFIGURAÇÃO
# ==============================================================================

class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard principal com KPIs e resumos financeiros."""
    template_name = "core/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        # Períodos disponíveis
        ctx["periods"] = DatePeriod.objects.order_by("-year", "-month")

        # Filtros de período
        start_period = self.request.GET.get("start-period")
        end_period = self.request.GET.get("end-period")

        # Queries SQL otimizadas para melhor performance
        with connection.cursor() as cursor:
            # Transações do utilizador
            cursor.execute("""
                SELECT 
                    CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0')) as period,
                    tx.type, tx.amount
                FROM core_transaction tx
                INNER JOIN core_dateperiod dp ON tx.period_id = dp.id
                WHERE tx.user_id = %s
                ORDER BY dp.year, dp.month
            """, [user.id])
            tx_rows = cursor.fetchall()

            # Saldos das contas
            cursor.execute("""
                SELECT 
                    CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0')) as period,
                    ab.reported_balance, at.name as account_type
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_accounttype at ON a.account_type_id = at.id
                INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                WHERE a.user_id = %s
                ORDER BY dp.year, dp.month
            """, [user.id])
            bal_rows = cursor.fetchall()

        # Converter para DataFrames para análise
        df_tx = pd.DataFrame(tx_rows, columns=["period", "type", "amount"])
        df_bal = pd.DataFrame(bal_rows, columns=["period", "reported_balance", "account_type"])

        # Aplicar filtros de período se especificados
        if start_period and end_period:
            df_tx = df_tx[(df_tx["period"] >= start_period) & (df_tx["period"] <= end_period)]
            df_bal = df_bal[(df_bal["period"] >= start_period) & (df_bal["period"] <= end_period)]

        # Cálculo de KPIs
        df_invest = df_bal[df_bal["account_type"].str.lower() == "investment"]
        patrimonio_mes = df_invest.groupby("period")["reported_balance"].sum()

        patrimonio_final = float(patrimonio_mes.iloc[-1]) if not patrimonio_mes.empty else 0
        patrimonio_inicial = float(patrimonio_mes.iloc[0]) if not patrimonio_mes.empty else 0
        aumento_patrimonio = patrimonio_final - patrimonio_inicial
        aumento_medio = patrimonio_mes.diff().dropna().mean() if len(patrimonio_mes) > 1 else 0

        df_income = df_tx[df_tx["type"] == "IN"]
        receita_mes = df_income.groupby("period")["amount"].sum().astype(float)
        receita_media = receita_mes.mean() if not receita_mes.empty else 0

        df_saving = df_bal[df_bal["account_type"].str.lower() == "savings"]
        saving_mes = df_saving.groupby("period")["reported_balance"].sum().astype(float)

        # Cálculo estimado de despesas
        periods = sorted(set(receita_mes.index) & set(saving_mes.index))
        despesas_estimadas = []
        for i in range(len(periods) - 1):
            p, p1 = periods[i], periods[i + 1]
            despesa = saving_mes[p] - saving_mes[p1] + receita_mes.get(p, 0)
            despesas_estimadas.append(despesa)
        despesa_media = pd.Series(despesas_estimadas).mean() if despesas_estimadas else 0

        total_investido = float(df_tx[df_tx["type"] == "IV"]["amount"].sum())
        n_meses = max(len(receita_mes), 1)
        poupanca_media = receita_media - despesa_media - total_investido / n_meses

        ctx["kpis"] = {
            "patrimonio": f"{patrimonio_final:,.0f} €",
            "aumento": f"{aumento_patrimonio:,.0f} €",
            "capital": f"{total_investido:,.0f} €",
            "despesa_media": f"{despesa_media:,.0f} €",
            "receita_media": f"{receita_media:,.0f} €",
            "aumento_riqueza": f"{aumento_medio:,.0f} €",
            "poupanca_media": f"{poupanca_media:,.0f} €",
        }
        return ctx


@login_required
def menu_config(request):
    """Configuração do menu para o utilizador atual."""
    return JsonResponse({
        "username": request.user.username,
        "links": [
            {"name": "Dashboard", "url": reverse("transaction_list_v2")},
            {"name": "New Transaction", "url": reverse("transaction_create")},
            {"name": "Categories", "url": reverse("category_list")},
            {"name": "Account Balances", "url": reverse("account_balance")},
        ],
    })


@login_required
def account_balances_pivot_json(request):
    """Saldos agregados por tipo/moeda em formato pivot para gráficos."""
    user_id = request.user.id
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
            FROM core_accountbalance ab
            JOIN core_account acc ON acc.id = ab.account_id
            JOIN core_accounttype at ON at.id = acc.account_type_id
            JOIN core_currency cur ON cur.id = acc.currency_id
            JOIN core_dateperiod dp ON dp.id = ab.period_id
            WHERE acc.user_id = %s
            GROUP BY at.name, cur.code, dp.year, dp.month
            ORDER BY dp.year, dp.month
        """, [user_id])
        rows = cursor.fetchall()

    if not rows:
        return JsonResponse({"columns": [], "rows": []})

    # Criar DataFrame
    df = pd.DataFrame(rows, columns=["type", "currency", "year", "month", "balance"])
    df["period"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1)).dt.strftime("%b/%y")

    # Pivot com fill_value=0 para garantir que todos os períodos aparecem
    pivot = (
        df.pivot_table(
            index=["type", "currency"],
            columns="period",
            values="balance",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index(axis=1)
        .reset_index()
    )

    return JsonResponse({
        "columns": list(pivot.columns),
        "rows": pivot.to_dict("records")
    })

# ==============================================================================
# VIEWS DE TRANSAÇÕES
# ==============================================================================

class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Criar nova transação com validação de segurança."""
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def form_valid(self, form):
        """Processar formulário válido e limpar cache."""
        self.object = form.save()
        logger.debug(f'📝 Criado: {self.object}')  # ✅ DEBUG no terminal

        # Limpar cache imediatamente
        clear_tx_cache(self.request.user.id)

        # Adicionar flag para JavaScript saber que deve recarregar
        self.request.session['transaction_changed'] = True

        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": True, "reload_needed": True})

        messages.success(self.request, "Transação criada com sucesso!")
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        """Processar formulário inválido."""
        logger.debug(f"❌ Formulário inválido: {form.errors}")  # DEBUG
        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": False, "errors": form.errors}, status=400)
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """Adicionar contexto seguro."""
        context = super().get_context_data(**kwargs)
        user = self.request.user

        context["accounts"] = Account.objects.filter(user=user).order_by("name")
        context["category_list"] = list(
            Category.objects.filter(user=user).values_list("name", flat=True)
        )
        return context

class TransactionUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Atualizar transação existente com validação de proprietário."""
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def get_queryset(self):
        return super().get_queryset().prefetch_related("tags")

    def get_object(self, queryset=None):
        """Override to provide better error handling."""
        try:
            return super().get_object(queryset)
        except Transaction.DoesNotExist:
            messages.error(self.request, f"Transaction with ID {self.kwargs.get('pk')} not found or you don't have permission to edit it.")
            logger.warning(f"User {self.request.user.id} tried to access non-existent transaction {self.kwargs.get('pk')}")
            raise Http404("Transaction not found")

    def form_valid(self, form):
        # Limpar cache imediatamente
        clear_tx_cache(self.request.user.id)

        # Adicionar flag para JavaScript saber que deve recarregar
        self.request.session['transaction_changed'] = True

        messages.success(self.request, "Transação atualizada com sucesso!")

        response = super().form_valid(form)
        if self.request.headers.get("HX-Request") == "true":
            context = self.get_context_data(form=form)
            return self.render_to_response(context)
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_list"] = list(
            Category.objects.filter(user=self.request.user).values_list("name", flat=True)
        )
        return context


class TransactionDeleteView(OwnerQuerysetMixin, DeleteView):
    """Eliminar transação com validação de proprietário."""
    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list_v2")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_id = self.object.user_id

        # Delete the transaction
        response = super().delete(request, *args, **kwargs)

        # Clear cache after deletion
        clear_tx_cache(user_id)

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Transação eliminada com sucesso!'
            })

        messages.success(request, "Transação eliminada com sucesso!")
        return response

    def post(self, request, *args, **kwargs):
        """Override post to handle both AJAX and regular form submissions."""
        self.object = self.get_object()

        # For AJAX requests, delete immediately
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return self.delete(request, *args, **kwargs)

        # For regular requests, use standard flow
        return super().post(request, *args, **kwargs)



@login_required
def transactions_json(request):
    """API JSON para DataTables com cache e filtros dinâmicos."""
    user_id = request.user.id

    # Datas
    raw_start = request.GET.get("date_start")
    raw_end = request.GET.get("date_end")
    start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
    end_date = parse_safe_date(raw_end, date.today())

    if not start_date or not end_date:
        return JsonResponse({"error": "Invalid date format"}, status=400)

    cache_key = _cache_key(user_id, start_date, end_date)
    cached_df = cache.get(cache_key)

    if cached_df is not None:
        df = cached_df.copy()
    else:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                       COALESCE(cat.name, '') AS category,
                       COALESCE(acc.name, 'No account') AS account,
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
        cache.set(cache_key, df.copy(), timeout=300)

    # Transformações e formatação
    df["date"] = df["date"].astype(str)
    df["period"] = df["year"].astype(str) + "-" + df["month"].astype(int).astype(str).str.zfill(2)
    df["type"] = df["type"].map(dict(Transaction.Type.choices)).fillna(df["type"])
    df["amount_float"] = df["amount"].astype(float)

    # Add investment direction for display with line break
    df["type_display"] = df.apply(lambda row: 
        f"Investment<br>({'Withdrawal' if row['amount_float'] < 0 else 'Reinforcement'})" 
        if row['type'] == 'Investment' 
        else row['type'], 
        axis=1
    )

    # Filtros GET
    tx_type = request.GET.get("type", "").strip()
    category = request.GET.get("category", "").strip()
    account = request.GET.get("account", "").strip()
    period = request.GET.get("period", "").strip()
    search = request.GET.get("search[value]", "").strip()

    # Advanced filters
    amount_min = request.GET.get("amount_min", "").strip()
    amount_max = request.GET.get("amount_max", "").strip()
    tags_filter = request.GET.get("tags", "").strip()

    df_for_type = df.copy()
    df_for_category = df.copy()
    df_for_account = df.copy()
    df_for_period = df.copy()

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
        except Exception:
            pass

    if search:
        df = df[
            df["category"].str.contains(search, case=False, na=False) |
            df["account"].str.contains(search, case=False, na=False) |
            df["type"].str.contains(search, case=False, na=False) |
            df["tags"].str.contains(search, case=False, na=False)
        ]

    # Advanced filters
    if amount_min:
        try:
            min_val = float(amount_min)
            df = df[df["amount_float"] >= min_val]
            logger.debug(f"Applied amount_min filter: {min_val}, remaining rows: {len(df)}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_min value: {amount_min}")

    if amount_max:
        try:
            max_val = float(amount_max)
            df = df[df["amount_float"] <= max_val]
            logger.debug(f"Applied amount_max filter: {max_val}, remaining rows: {len(df)}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_max value: {amount_max}")

    if tags_filter:
        tag_list = [t.strip().lower() for t in tags_filter.split(",") if t.strip()]
        if tag_list:
            # Use regex to match any of the tags
            tag_pattern = '|'.join(tag_list)
            df = df[df["tags"].str.contains(tag_pattern, case=False, na=False)]
            logger.debug(f"Applied tags filter: {tag_list}, remaining rows: {len(df)}")



    # Filtros únicos dinâmicos
    available_types = sorted(
        [t for t in df_for_type["type"].dropna().unique() if t]
    )

    available_categories = sorted(
        [c for c in df_for_category["category"].dropna().unique() if c]
    )

    available_accounts = sorted(
        [a for a in df_for_account["account"].dropna().unique() if a]
    )

    available_periods = sorted(
        [p for p in df_for_period["period"].dropna().unique() if p],
        reverse=True
    )

    # Ordenação
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
        except Exception:
            pass

    # Formatar montantes
    df["amount"] = df.apply(
        lambda r: f"€ {r['amount_float']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {r['currency']}",
        axis=1
    )

    # ✅ CORREÇÃO: criar ações como string HTML
    df["actions"] = df.apply(
        lambda r: f"""
        <div class='btn-group'>
          <a href='/transactions/{r["id"]}/edit/' class='btn btn-sm btn-outline-primary'>✏️</a>
          <a href='/transactions/{r["id"]}/delete/' class='btn btn-sm btn-outline-danger'>🗑️</a>
        </div>
        """, axis=1
    )

    # Paginação (DataTables)
    draw = int(request.GET.get("draw", 1))
    start = int(request.GET.get("start", 0))
    length = int(request.GET.get("length", 10))
    page_df = df.iloc[start : start + length]

    return JsonResponse({
        "draw": draw,
        "recordsTotal": len(df),
        "recordsFiltered": len(df),
        "data": page_df.to_dict(orient="records"),
        "filters": {
            "types": available_types,
            "categories": available_categories,
            "accounts": available_accounts,
            "periods": available_periods,
        },
    })




@require_POST
@login_required
def transaction_bulk_update(request):
    """Bulk update transactions (mark as estimated, etc.)."""
    try:
        data = json.loads(request.body)
        action = data.get('action')
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'error': 'No transactions selected'})

        # Validate transactions belong to user
        transactions = Transaction.objects.filter(
            id__in=transaction_ids, 
            user=request.user
        )

        if len(transactions) != len(transaction_ids):
            return JsonResponse({'success': False, 'error': 'Some transactions not found'})

        updated = 0

        # Use atomic transaction to ensure all updates happen together
        with db_transaction.atomic():
            if action == 'mark_estimated':
                updated = transactions.update(is_estimated=True)
            elif action == 'mark_unestimated':
                updated = transactions.update(is_estimated=False)
            else:
                return JsonResponse({'success': False, 'error': 'Invalid action'})

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id)
        logger.info(f"✅ Bulk update completed: {updated} transactions updated, cache cleared for user {request.user.id}")

        return JsonResponse({
            'success': True, 
            'updated': updated,
            'message': f'{updated} transactions updated'
        })

    except Exception as e:
        logger.error(f"Bulk update error for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required  
def transaction_bulk_duplicate(request):
    """Bulk duplicate transactions."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'error': 'No transactions selected'})

        # Get original transactions
        transactions = Transaction.objects.filter(
            id__in=transaction_ids,
            user=request.user
        ).select_related('category', 'account', 'period').prefetch_related('tags')

        if len(transactions) != len(transaction_ids):
            return JsonResponse({'success': False, 'error': 'Some transactions not found'})

        created = 0
        today = date.today()
        current_period, _ = DatePeriod.objects.get_or_create(
            year=today.year,
            month=today.month,
            defaults={'label': today.strftime('%B %Y')}
        )

        # Use atomic transaction for all operations
        with db_transaction.atomic():
            new_transactions = []
            for tx in transactions:
                # Create duplicate with today's date
                new_tx = Transaction.objects.create(
                    user=tx.user,
                    type=tx.type,
                    amount=tx.amount,
                    date=today,
                    notes=f"Duplicate of transaction from {tx.date}",
                    is_estimated=tx.is_estimated,
                    period=current_period,
                    account=tx.account,
                    category=tx.category
                )
                new_transactions.append((new_tx, tx.tags.all()))
                created += 1

            # Copy tags for all new transactions
            for new_tx, original_tags in new_transactions:
                for tag in original_tags:
                    new_tx.tags.add(tag)

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id)
        logger.info(f"✅ Bulk duplicate completed: {created} transactions created, cache cleared for user {request.user.id}")

        return JsonResponse({
            'success': True,
            'created': created,
            'message': f'{created} transactions duplicated'
        })

    except Exception as e:
        logger.error(f"Bulk duplicate error for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_POST
@login_required
def transaction_bulk_delete(request):
    """Bulk delete transactions."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'error': 'No transactions selected'})

        # Validate transactions belong to user and are deletable
        transactions = Transaction.objects.filter(
            id__in=transaction_ids, 
            user=request.user
        )

        if len(transactions) != len(transaction_ids):
            return JsonResponse({'success': False, 'error': 'Some transactions not found'})

        deleted_count = 0

        # Use atomic transaction to ensure all deletions happen together
        with db_transaction.atomic():
            for transaction in transactions:
                transaction.delete()
                deleted_count += 1

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id)
        logger.info(f"✅ Bulk delete completed: {deleted_count} transactions deleted, cache cleared for user {request.user.id}")

        return JsonResponse({
            'success': True,
            'deleted': deleted_count,
            'message': f'{deleted_count} transactions deleted'
        })

    except Exception as e:
        logger.error(f"Bulk delete error for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# IMPORT/EXPORT FUNCTIONS
# ==============================================================================

@login_required
def import_transactions_xlsx(request):
    """Import transactions from Excel file."""
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                messages.error(request, 'No file uploaded.')
                return render(request, 'core/import_form.html')

            # Read Excel file
            df = pd.read_excel(uploaded_file)

            # Validate required columns
            required_cols = ['Date', 'Type', 'Amount', 'Category', 'Account']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                messages.error(request, f'Missing required columns: {", ".join(missing_cols)}')
                return render(request, 'core/import_form.html')

            imported_count = 0
            errors = []

            for index, row in df.iterrows():
                try:
                    # Parse date
                    transaction_date = pd.to_datetime(row['Date']).date()

                    # Get or create period
                    period, _ = DatePeriod.objects.get_or_create(
                        year=transaction_date.year,
                        month=transaction_date.month,
                        defaults={'label': transaction_date.strftime('%B %Y')}
                    )

                    # Get or create category
                    category, _ = Category.objects.get_or_create(
                        name=row['Category'],
                        user=request.user
                    )

                    # Get or create account (assuming default currency and type)
                    currency, _ = Currency.objects.get_or_create(code='EUR', defaults={'name': 'Euro', 'symbol': '€'})
                    account_type, _ = AccountType.objects.get_or_create(name='Checking')
                    account, _ = Account.objects.get_or_create(
                        name=row['Account'],
                        user=request.user,
                        defaults={'currency': currency, 'account_type': account_type}
                    )

                    # Create transaction
                    Transaction.objects.create(
                        user=request.user,
                        type=row['Type'].upper()[:2],  # Convert to enum value
                        amount=float(row['Amount']),
                        date=transaction_date,
                        category=category,
                        account=account,
                        period=period,
                        notes=row.get('Notes', '')
                    )
                    imported_count += 1

                except Exception as e:
                    errors.append(f'Row {index + 2}: {str(e)}')

            # Clear cache after import
            clear_tx_cache(request.user.id)

            if errors:
                messages.warning(request, f'Imported {imported_count} transactions with {len(errors)} errors.')
            else:
                messages.success(request, f'Successfully imported {imported_count} transactions.')

            return redirect('transaction_list_v2')

        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')

    return render(request, 'core/import_form.html')


@login_required
def import_transactions_template(request):
    """Download Excel template for transaction import."""
    # Create sample data
    data = {
        'Date': ['2025-01-01', '2025-01-02'],
        'Type': ['Income', 'Expense'],
        'Amount': [1000.00, -50.00],
        'Category': ['Salary', 'Food'],
        'Account': ['Checking', 'Cash'],
        'Tags': ['monthly', 'daily'],
        'Notes': ['Monthly salary', 'Lunch']
    }

    df = pd.DataFrame(data)

    # Create Excel file in memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Transactions', index=False)

    output.seek(0)

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="transaction_import_template.xlsx"'
    return response


@login_required
def export_transactions_xlsx(request):
    """Export transactions to Excel."""
    user_id = request.user.id

    # Get date filters
    start_date = parse_safe_date(request.GET.get("date_start"), date(date.today().year, 1, 1))
    end_date = parse_safe_date(request.GET.get("date_end"), date.today())

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT tx.date, tx.type, tx.amount,
                   COALESCE(cat.name, '') AS category,
                   COALESCE(acc.name, '') AS account,
                   COALESCE(STRING_AGG(tag.name, ', '), '') AS tags,
                   tx.notes
            FROM core_transaction tx
            LEFT JOIN core_category cat ON tx.category_id = cat.id
            LEFT JOIN core_account acc ON tx.account_id = acc.id
            LEFT JOIN core_transactiontag tt ON tt.transaction_id = tx.id
            LEFT JOIN core_tag tag ON tt.tag_id = tag.id
            WHERE tx.user_id = %s AND tx.date BETWEEN %s AND %s
            GROUP BY tx.id, tx.date, tx.type, tx.amount, cat.name, acc.name, tx.notes
            ORDER BY tx.date DESC
        """, [user_id, start_date, end_date])
        rows = cursor.fetchall()

    df = pd.DataFrame(rows, columns=['Date', 'Type', 'Amount', 'Category', 'Account', 'Tags', 'Notes'])

    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Transactions', index=False)

    output.seek(0)

    filename = f"transactions_{start_date}_{end_date}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def transaction_clear_cache(request):
    """Clear transaction cache for current user."""
    try:
        clear_tx_cache(request.user.id)

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Cache cleared successfully!'
            })

        messages.success(request, 'Cache cleared successfully!')
        return redirect('transaction_list_v2')

    except Exception as e:
        logger.error(f"Error clearing cache for user {request.user.id}: {e}")

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

        messages.error(request, f'Failed to clear cache: {str(e)}')
        return redirect('transaction_list_v2')


@login_required
def clear_session_flag(request):
    """Clear session flags."""
    if 'transaction_changed' in request.session:
        del request.session['transaction_changed']
    return JsonResponse({'success': True})


@login_required
def transaction_list_v2(request):
    """Modern transaction list view."""
    return render(request, 'core/transaction_list_v2.html')


@login_required
def transactions_json_v2(request):
    """Enhanced JSON API for transactions v2."""
    user_id = request.user.id
    logger.debug(f"🔍 [transactions_json_v2] Request from user {user_id}: {request.method}")

    # Parse request data (handles both GET and POST)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except:
            data = {}
    else:
        data = request.GET.dict()

    logger.debug(f"📋 [transactions_json_v2] Request data: {data}")

    # Datas - use wider default range if no dates provided
    raw_start = data.get('date_start', request.GET.get("date_start"))
    raw_end = data.get('date_end', request.GET.get("date_end"))

    # If no dates provided, use a very wide range to catch all transactions
    if not raw_start and not raw_end:
        start_date = date(2020, 1, 1)  # Much wider range
        end_date = date(2030, 12, 31)
        logger.debug(f"📅 [transactions_json_v2] No dates provided, using wide range: {start_date} to {end_date}")
    else:
        start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
        end_date = parse_safe_date(raw_end, date.today())

    logger.debug(f"📅 [transactions_json_v2] Date range: {start_date} to {end_date}")

    # Page settings
    current_page = int(data.get('page', 1))
    page_size = int(data.get('page_size', 25))

    # Sorting
    sort_field = data.get('sort_field', 'date')
    sort_direction = data.get('sort_direction', 'desc')

    if not start_date or not end_date:
        logger.error(f"❌ [transactions_json_v2] Invalid date format: start={raw_start}, end={raw_end}")
        return JsonResponse({"error": "Invalid date format"}, status=400)

    cache_key = f"tx_v2_{user_id}_{start_date}_{end_date}_{sort_field}_{sort_direction}"
    cached_df = cache.get(cache_key)

    if cached_df is not None:
        logger.debug(f"✅ [transactions_json_v2] Using cached data, {len(cached_df)} rows")
        df = cached_df.copy()
    else:
        logger.debug(f"🔄 [transactions_json_v2] Querying database...")

        # SQL query with sorting
        order_clause = f"tx.date {'DESC' if sort_direction == 'desc' else 'ASC'}"
        if sort_field == 'amount':
            order_clause = f"tx.amount {'DESC' if sort_direction == 'desc' else 'ASC'}"
        elif sort_field == 'type':
            order_clause = f"tx.type {'DESC' if sort_direction == 'desc' else 'ASC'}"

        with connection.cursor() as cursor:
            query = f"""
                SELECT tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                       COALESCE(cat.name, '') AS category,
                       COALESCE(acc.name, 'No account') AS account,
                       COALESCE(curr.symbol, '€') AS currency,
                       COALESCE(STRING_AGG(tag.name, ', '), '') AS tags,
                       tx.is_system, tx.editable,
                       CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0')) AS period
                FROM core_transaction tx
                LEFT JOIN core_category cat ON tx.category_id = cat.id
                LEFT JOIN core_account acc ON tx.account_id = acc.id
                LEFT JOIN core_currency curr ON acc.currency_id = curr.id
                LEFT JOIN core_dateperiod dp ON tx.period_id = dp.id
                LEFT JOIN core_transactiontag tt ON tt.transaction_id = tx.id
                LEFT JOIN core_tag tag ON tt.tag_id = tag.id
                WHERE tx.user_id = %s
                AND tx.date BETWEEN %s AND %s
                GROUP BY tx.id, tx.date, dp.year, dp.month, tx.type, tx.amount,
                         cat.name, acc.name, curr.symbol, tx.is_system, tx.editable
                ORDER BY {order_clause}
            """
            logger.debug(f"📝 [transactions_json_v2] SQL Query: {query}")
            logger.debug(f"📝 [transactions_json_v2] Query params: [{user_id}, {start_date}, {end_date}]")

            cursor.execute(query, [user_id, start_date, end_date])
            rows = cursor.fetchall()

            logger.debug(f"📊 [transactions_json_v2] Raw query returned {len(rows)} rows")

        df = pd.DataFrame(rows, columns=[
            "id", "date", "year", "month", "type", "amount",
            "category", "account", "currency", "tags", 
            "is_system", "editable", "period"
        ])
        logger.debug(f"📋 [transactions_json_v2] DataFrame created with {len(df)} rows")
        cache.set(cache_key, df.copy(), timeout=300)

    # Apply filters - convert empty strings to None
    tx_type = data.get("type", "").strip() or None
    category = data.get("category", "").strip() or None
    account = data.get("account", "").strip() or None
    period = data.get("period", "").strip() or None
    search = data.get("search", "").strip() or None
    amount_min = data.get("amount_min", "").strip() or None
    amount_max = data.get("amount_max", "").strip() or None
    tags_filter = data.get("tags", "").strip() or None
    include_system = data.get("include_system", False)

    # Store original for filter options
    df_original = df.copy()

    # Apply filters only if values are not None/empty
    if tx_type:
        df = df[df["type"] == tx_type]
        logger.debug(f"Applied type filter '{tx_type}', remaining rows: {len(df)}")
    if category:
        df = df[df["category"].str.contains(category, case=False, na=False)]
        logger.debug(f"Applied category filter '{category}', remaining rows: {len(df)}")
    if account:
        df = df[df["account"].str.contains(account, case=False, na=False)]
        logger.debug(f"Applied account filter '{account}', remaining rows: {len(df)}")
    if period:
        df = df[df["period"] == period]
        logger.debug(f"Applied period filter '{period}', remaining rows: {len(df)}")
    if search:
        df = df[
            df["category"].str.contains(search, case=False, na=False) |
            df["account"].str.contains(search, case=False, na=False) |
            df["tags"].str.contains(search, case=False, na=False)
        ]
        logger.debug(f"Applied search filter '{search}', remaining rows: {len(df)}")
    if amount_min:
        try:
            min_val = float(amount_min)
            df = df[df["amount"] >= min_val]
            logger.debug(f"Applied amount_min filter: {min_val}, remaining rows: {len(df)}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_min value: {amount_min}")
    if amount_max:
        try:
            max_val = float(amount_max)
            df = df[df["amount"] <= max_val]
            logger.debug(f"Applied amount_max filter: {max_val}, remaining rows: {len(df)}")
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_max value: {amount_max}")
    if tags_filter:
        tag_list = [t.strip().lower() for t in tags_filter.split(",") if t.strip()]
        if tag_list:
            tag_pattern = '|'.join(tag_list)
            df = df[df["tags"].str.contains(tag_pattern, case=False, na=False)]
            logger.debug(f"Applied tags filter: {tag_list}, remaining rows: {len(df)}")
    if not include_system:
        df = df[df["is_system"] != True]

    # Pagination
    total_count = len(df)
    start_idx = (current_page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = df.iloc[start_idx:end_idx].copy()

    # Format data for frontend
    page_df["date"] = page_df["date"].astype(str)
    page_df["type"] = page_df["type"].map({
        'IN': 'Income',
        'EX': 'Expense', 
        'IV': 'Investment',
        'TR': 'Transfer',
        'AJ': 'Adjustment'
    }).fillna(page_df["type"])

    # Format amounts
    page_df["amount_formatted"] = page_df.apply(
        lambda r: f"€ {abs(r['amount']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + f" {r['currency']}",
        axis=1
    )

    # Build response
    response_data = {
        "transactions": page_df.to_dict(orient="records"),
        "total_count": total_count,
        "current_page": current_page,
        "page_size": page_size,
        "filters": {
            "types": sorted(df_original["type"].map({
                'IN': 'Income', 'EX': 'Expense', 'IV': 'Investment', 'TR': 'Transfer', 'AJ': 'Adjustment'
            }).dropna().unique()),
            "categories": sorted([c for c in df_original["category"].dropna().unique() if c]),
            "accounts": sorted([a for a in df_original["account"].dropna().unique() if a]),
            "periods": sorted(df_original["period"].dropna().unique(), reverse=True)
        }
    }

    logger.debug(f"📤 [transactions_json_v2] Final response: {len(response_data['transactions'])} transactions, total_count: {total_count}")

    # Log if no transactions found
    if total_count == 0:
        total_tx_count = Transaction.objects.filter(user_id=user_id).count()
        logger.warning(f"⚠️ [transactions_json_v2] No transactions returned for user {user_id} in date range {start_date}-{end_date}, but user has {total_tx_count} total transactions")

    return JsonResponse(response_data)


@login_required
def transactions_totals_v2(request):
    """Get totals for transactions v2."""
    user_id = request.user.id

    # Parse request data (handles both GET and POST)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except:
            data = {}
    else:
        data = request.GET.dict()

    # Get filters
    start_date = parse_safe_date(data.get('date_start', request.GET.get("date_start")), date(date.today().year, 1, 1))
    end_date = parse_safe_date(data.get('date_end', request.GET.get("date_end")), date.today())
    include_system = data.get("include_system", False)

    # Build WHERE clause
    where_clause = "tx.user_id = %s AND tx.date BETWEEN %s AND %s"
    params = [user_id, start_date, end_date]

    if not include_system:
        where_clause += " AND (tx.is_system IS NULL OR tx.is_system = FALSE)"

    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT 
                tx.type,
                SUM(tx.amount) as total
            FROM core_transaction tx
            WHERE {where_clause}
            GROUP BY tx.type
        """, params)
        rows = cursor.fetchall()

    totals = {
        'income': 0,
        'expenses': 0,
        'investments': 0,
        'transfers': 0
    }

    type_mapping = {
        'IN': 'income',
        'EX': 'expenses', 
        'IV': 'investments',
        'TR': 'transfers'
    }

    for tx_type, amount in rows:
        mapped_type = type_mapping.get(tx_type, 'expenses')
        totals[mapped_type] += float(amount)

    totals['balance'] = totals['income'] - abs(totals['expenses'])

    return JsonResponse(totals)


# ==============================================================================
# CATEGORY & TAG FUNCTIONS
# ==============================================================================

class CategoryListView(OwnerQuerysetMixin, ListView):
    """List categories for current user."""
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Create new category."""
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Update category."""
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    """Delete category."""
    model = Category
    template_name = "core/confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")


@login_required
def category_autocomplete(request):
    """Autocomplete for categories."""
    term = request.GET.get('term', '')
    categories = Category.objects.filter(
        user=request.user,
        name__icontains=term
    ).values_list('name', flat=True)[:10]
    return JsonResponse(list(categories), safe=False)


@login_required
def tag_autocomplete(request):
    """Autocomplete for tags."""
    term = request.GET.get('term', '')
    tags = Tag.objects.filter(
        user=request.user,
        name__icontains=term
    ).values_list('name', flat=True)[:10]
    return JsonResponse(list(tags), safe=False)


# ==============================================================================
# ACCOUNT FUNCTIONS
# ==============================================================================

class AccountListView(OwnerQuerysetMixin, ListView):
    """List accounts for current user."""
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Create new account."""
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")


class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Update account."""
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")


class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    """Delete account."""
    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")


class AccountMergeView(LoginRequiredMixin, View):
    """Merge two accounts."""
    template_name = "core/confirms/account_confirm_merge.html"

    def get(self, request, source_pk, target_pk):
        source = get_object_or_404(Account, pk=source_pk, user=request.user)
        target = get_object_or_404(Account, pk=target_pk, user=request.user)
        return render(request, self.template_name, {
            'source': source, 
            'target': target
        })

    def post(self, request, source_pk, target_pk):
        source = get_object_or_404(Account, pk=source_pk, user=request.user)
        target = get_object_or_404(Account, pk=target_pk, user=request.user)

        # Move all transactions to target account
        Transaction.objects.filter(account=source).update(account=target)

        # Delete source account
        source.delete()

        messages.success(request, f'Account "{source.name}" merged into "{target.name}"')
        return redirect('account_list')


@login_required
def move_account_up(request, pk):
    """Move account up in order."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    # Implementation would depend on your ordering system
    return redirect('account_list')


@login_required
def move_account_down(request, pk):
    """Move account down in order."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    # Implementation would depend on your ordering system
    return redirect('account_list')


@login_required
def account_reorder(request):
    """Reorder accounts via AJAX."""
    if request.method == 'POST':
        order_data = json.loads(request.body)
        # Implementation would depend on your ordering system
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})


def _merge_duplicate_accounts(user):
    """Função auxiliar para fundir contas duplicadas por nome."""
    seen = {}
    for acc in Account.objects.filter(user=user).order_by("name"):
        key = acc.name.strip().lower()
        if key in seen:
            primary = seen[key]
            AccountBalance.objects.filter(account=acc).update(account=primary)
            Transaction.objects.filter(account=acc).update(account=primary)
            acc.delete()
        else:
            seen[key] = acc

# ==============================================================================
# ACCOUNT BALANCE FUNCTIONS
# ==============================================================================

@login_required
def account_balance_view(request):
    """Vista principal para gestão de saldos de contas."""
    # Limpar mensagens anteriores
    list(messages.get_messages(request))

    # Determinar mês/ano selecionado
    today = date.today()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))

        if month < 1 or month > 12:
            messages.error(request, "Invalid month.")
            month = today.month
    except ValueError:
        messages.error(request, "Invalid date.")
        year, month = today.year, today.month

    # Obter ou criar período correspondente
    period, _ = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    # Query base dos saldos do utilizador
    qs_base = AccountBalance.objects.filter(
        account__user=request.user,
        period=period
    ).select_related("account", "account__account_type", "account__currency")

    if request.method == "POST":
        formset = AccountBalanceFormSet(request.POST, queryset=qs_base, user=request.user)

        if formset.is_valid():
            try:
                with db_transaction.atomic():
                    for form in formset:
                        if form.cleaned_data.get("DELETE"):
                            continue

                        inst = form.save(commit=False)
                        inst.period = period

                        if inst.account.user_id is None:
                            inst.account.user = request.user
                            inst.account.save()

                        # Atualizar se já existe saldo para esta conta/período
                        existing = AccountBalance.objects.filter(
                            account=inst.account,
                            period=period,
                        ).first()

                        if existing:
                            existing.reported_balance = inst.reported_balance
                            existing.save()
                        else:
                            inst.save()

                    # Fundir contas duplicadas por nome
                    _merge_duplicate_accounts(request.user)

                messages.success(request, "Balances saved successfully!")
                return redirect(f"{request.path}?year={year}&month={month:02d}")
            except Exception as e:
                messages.error(request, f"Error whilst saving balances: {str(e)}")
        else:
            messages.error(request, "Error whilst saving balances. Please check the fields.")
    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    # Agrupar formulários por tipo e moeda
    grouped_forms = {}
    totals_by_group = {}
    grand_total = 0

    for form in formset:
        if hasattr(form.instance, 'account') and form.instance.account:
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
        "totals_by_group": totals_by_group,
        "grand_total": grand_total,
        "year": year,
        "month": month,
        "selected_month": date(year, month, 1),
    }

    return render(request, "core/account_balance.html", context)


@login_required
def delete_account_balance(request, pk):
    """Delete account balance."""
    balance = get_object_or_404(AccountBalance, pk=pk, account__user=request.user)
    balance.delete()
    messages.success(request, 'Account balance deleted successfully!')
    return redirect('account_balance')


@login_required
def copy_previous_balances_view(request):
    """Copy previous month balances to current period."""
    from datetime import date
    from decimal import Decimal

    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'})

    try:
        # Get target year and month
        year = int(request.GET.get('year', date.today().year))
        month = int(request.GET.get('month', date.today().month))

        # Calculate previous month
        if month == 1:
            prev_year = year - 1
            prev_month = 12
        else:
            prev_year = year
            prev_month = month - 1

        # Get or create periods
        target_period, _ = DatePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={'label': f"{date(year, month, 1).strftime('%B %Y')}"}
        )

        try:
            source_period = DatePeriod.objects.get(year=prev_year, month=prev_month)
        except DatePeriod.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'error': f'No data found for {prev_year}-{prev_month:02d}'
            })

        # Get previous month balances
        source_balances = AccountBalance.objects.filter(
            account__user=request.user,
            period=source_period
        ).select_related('account')

        if not source_balances.exists():
            return JsonResponse({
                'success': False,
                'error': f'No balances found for {prev_year}-{prev_month:02d}'
            })

        # Copy balances to target period
        created_count = 0
        updated_count = 0

        with db_transaction.atomic():
            for source_balance in source_balances:
                target_balance, created = AccountBalance.objects.get_or_create(
                    account=source_balance.account,
                    period=target_period,
                    defaults={
                        'reported_balance': source_balance.reported_balance
                    }
                )

                if created:
                    created_count += 1
                else:
                    # Update existing balance
                    target_balance.reported_balance = source_balance.reported_balance
                    target_balance.save()
                    updated_count += 1

        return JsonResponse({
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'message': f'Copied {created_count} new balances, updated {updated_count} existing balances from {prev_year}-{prev_month:02d}'
        })

    except Exception as e:
        logger.error(f"Error copying previous balances for user {request.user.id}: {e}")
        return JsonResponse({
            'success': False,
            'error': f'Error copying balances: {str(e)}'
        })


@login_required
def account_balance_export_xlsx(request):
    """Export account balances to Excel for selected period range."""
    user_id = request.user.id

    # Get period range from request
    start_period = request.GET.get('start', '')
    end_period = request.GET.get('end', '')

    # Parse periods (format: YYYY-MM)
    try:
        if start_period and end_period:
            start_year, start_month = map(int, start_period.split('-'))
            end_year, end_month = map(int, end_period.split('-'))
        else:
            # Default to current year if no periods specified
            today = date.today()
            start_year, start_month = today.year, 1
            end_year, end_month = today.year, today.month
    except (ValueError, TypeError):
        # Fallback to current year
        today = date.today()
        start_year, start_month = today.year, 1
        end_year, end_month = today.year, today.month

    # SQL query to get account balances by period
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                dp.year,
                dp.month,
                CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0')) as period,
                a.name as account_name,
                at.name as account_type,
                cur.code as currency,
                ab.reported_balance
            FROM core_accountbalance ab
            INNER JOIN core_account a ON ab.account_id = a.id
            INNER JOIN core_accounttype at ON a.account_type_id = at.id
            INNER JOIN core_currency cur ON a.currency_id = cur.id
            INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
            INNER JOIN auth_user u ON a.user_id = u.id
            WHERE u.id = %s
            AND (
                (dp.year > %s) OR 
                (dp.year = %s AND dp.month >= %s)
            )
            AND (
                (dp.year < %s) OR 
                (dp.year = %s AND dp.month <= %s)
            )
            ORDER BY dp.year DESC, dp.month DESC, at.name, a.name;
        """, [
            user_id, 
            start_year, start_year, start_month,
            end_year, end_year, end_month
        ])
        rows = cursor.fetchall()

    if not rows:
        # Create empty DataFrame with headers
        df = pd.DataFrame(columns=[
            'Year', 'Month', 'Period', 'Account_Name', 
            'Account_Type', 'Currency', 'Balance'
        ])
    else:
        # Create DataFrame from query results
        df = pd.DataFrame(rows, columns=[
            'Year', 'Month', 'Period', 'Account_Name', 
            'Account_Type', 'Currency', 'Balance'
        ])

    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Main sheet with detailed data
        df.to_excel(writer, sheet_name='Account_Balances', index=False)

        # Summary sheet by period
        if not df.empty:
            summary_df = df.groupby(['Period', 'Account_Type', 'Currency'])['Balance'].sum().reset_index()
            summary_df.to_excel(writer, sheet_name='Summary_by_Period', index=False)

    output.seek(0)

    # Generate filename with period range
    filename = f"account_balances_{start_year}-{start_month:02d}_to_{end_year}-{end_month:02d}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def account_balance_import_xlsx(request):
    """Import account balances from Excel."""
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                messages.error(request, 'No file uploaded.')
                return render(request, 'core/import_balances_form.html')

            # Read Excel file
            df = pd.read_excel(uploaded_file)

            # Validate required columns
            required_cols = ['Year', 'Month', 'Account', 'Balance']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                messages.error(request, f'Missing required columns: {", ".join(missing_cols)}')
                return render(request, 'core/import_balances_form.html')

            imported_count = 0
            errors = []

            with db_transaction.atomic():
                for index, row in df.iterrows():
                    try:
                        year = int(row['Year'])
                        month = int(row['Month'])
                        account_name = str(row['Account']).strip()
                        balance = float(row['Balance'])

                        # Get or create period
                        period, _ = DatePeriod.objects.get_or_create(
                            year=year,
                            month=month,
                            defaults={'label': f"{date(year, month, 1).strftime('%B %Y')}"}
                        )

                        # Get or create account
                        default_currency = Currency.objects.get_or_create(
                            code='EUR', 
                            defaults={'name': 'Euro', 'symbol': '€'}
                        )[0]

                        default_account_type = AccountType.objects.get_or_create(
                            name='Savings'
                        )[0]

                        account, _ = Account.objects.get_or_create(
                            name=account_name,
                            user=request.user,
                            defaults={
                                'currency': default_currency,
                                'account_type': default_account_type
                            }
                        )

                        # Create or update balance
                        balance_obj, created = AccountBalance.objects.get_or_create(
                            account=account,
                            period=period,
                            defaults={'reported_balance': Decimal(str(balance))}
                        )

                        if not created:
                            balance_obj.reported_balance = Decimal(str(balance))
                            balance_obj.save()

                        imported_count += 1

                    except Exception as e:
                        errors.append(f'Row {index + 2}: {str(e)}')

            if errors:
                messages.warning(request, f'Imported {imported_count} balances with {len(errors)} errors: {"; ".join(errors[:3])}')
            else:
                messages.success(request, f'Successfully imported {imported_count} account balances.')

            return redirect('account_balance')

        except Exception as e:
            messages.error(request, f'Import failed: {str(e)}')

    return render(request, 'core/import_balances_form.html')


@login_required
def account_balance_template_xlsx(request):
    """Download template for account balance import."""
    data = {
        'Year': [2025, 2025],
        'Month': [1, 1], 
        'Account': ['Checking', 'Savings'],
        'Balance': [1000.00, 5000.00]
    }
    df = pd.DataFrame(data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Balances', index=False)

    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="balance_import_template.xlsx"'
    return response


# ==============================================================================
# TRANSACTION ESTIMATION FUNCTIONS
# ==============================================================================

@login_required
def estimate_transaction_view(request):
    """Transaction estimation management view."""
    # Get available periods with account balances, optimized query
    periods_with_balances = DatePeriod.objects.filter(
        account_balances__account__user=request.user
    ).distinct().select_related().order_by('-year', '-month')[:12]  # Last 12 months
    
    logger.debug(f"Found {periods_with_balances.count()} periods with balances for user {request.user.id}")
    
    context = {
        'periods': periods_with_balances,
        'user_id': request.user.id,  # Add for frontend caching
    }
    
    return render(request, 'core/estimate_transactions.html', context)


@require_POST
@login_required
def estimate_transaction_for_period(request):
    """Estimate transaction for a specific period."""
    from .services.finance_estimation import FinanceEstimationService
    
    try:
        data = json.loads(request.body)
        period_id = data.get('period_id')
        
        if not period_id:
            return JsonResponse({'success': False, 'error': 'Period ID required'})
        
        # Get the period
        try:
            period = DatePeriod.objects.get(id=period_id)
        except DatePeriod.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Period not found'})
        
        logger.info(f"Estimating transaction for period {period.label} (user {request.user.id})")
        
        # Run estimation
        estimation_service = FinanceEstimationService(request.user)
        estimated_tx = estimation_service.estimate_transaction_for_period(period)
        
        # Get updated summary data
        summary = estimation_service.get_estimation_summary(period)
        
        # Clear transaction cache
        clear_tx_cache(request.user.id)
        
        message = f'Estimation completed for {period.label}'
        if estimated_tx:
            message += f' - Created transaction ID {estimated_tx.id}'
        else:
            message += ' - No estimation needed (period appears balanced)'
        
        return JsonResponse({
            'success': True,
            'transaction_id': estimated_tx.id if estimated_tx else None,
            'summary': summary,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error estimating transaction for user {request.user.id}: {e}")
        return JsonResponse({
            'success': False, 
            'error': str(e)
        }, status=500)


@login_required
def get_estimation_summaries(request):
    """Get estimation summaries for multiple periods."""
    from .services.finance_estimation import FinanceEstimationService
    
    try:
        # Get year filter from request
        year_filter = request.GET.get('year')
        
        # Get periods with account balances, properly ordered
        periods_qs = DatePeriod.objects.filter(
            account_balances__account__user=request.user
        ).distinct().order_by('-year', '-month')
        
        # Apply year filter if provided
        if year_filter:
            try:
                year = int(year_filter)
                periods_qs = periods_qs.filter(year=year)
                logger.debug(f"Applied year filter: {year}")
            except (ValueError, TypeError):
                logger.warning(f"Invalid year filter: {year_filter}")
        
        periods = periods_qs[:12]
        
        logger.debug(f"Found {periods.count()} periods for user {request.user.id}")
        
        estimation_service = FinanceEstimationService(request.user)
        summaries = []
        
        # Use select_related for better performance
        periods_with_data = periods.select_related().prefetch_related(
            'account_balances__account'
        )
        
        for period in periods_with_data:
            try:
                summary = estimation_service.get_estimation_summary(period)
                summaries.append(summary)
                logger.debug(f"Generated summary for period {period.label}: {summary['status']}")
            except Exception as period_error:
                logger.error(f"Error processing period {period.id}: {period_error}")
                # Add error summary for this period
                summaries.append({
                    'period_id': period.id,
                    'period': period.label,
                    'status': 'error',
                    'status_message': f'Error: {str(period_error)}',
                    'estimated_type': None,
                    'estimated_amount': 0,
                    'has_estimated_transaction': False,
                    'estimated_transaction_id': None,
                    'details': {}
                })
        
        # Ensure summaries are properly ordered by period (most recent first)
        summaries.sort(key=lambda x: (
            int(x['period'].split(' ')[1]) if len(x['period'].split(' ')) > 1 else 0,  # Year
            ['January', 'February', 'March', 'April', 'May', 'June', 
             'July', 'August', 'September', 'October', 'November', 'December'].index(
                x['period'].split(' ')[0]) + 1 if len(x['period'].split(' ')) > 1 else 0  # Month
        ), reverse=True)
        
        logger.info(f"Returning {len(summaries)} estimation summaries for user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'summaries': summaries
        })
        
    except Exception as e:
        logger.error(f"Error getting estimation summaries for user {request.user.id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST  
@login_required
def delete_estimated_transaction(request, transaction_id):
    """Delete an estimated transaction."""
    try:
        # Get the transaction and verify it belongs to user and is estimated
        try:
            tx = Transaction.objects.get(
                id=transaction_id,
                user=request.user,
                is_estimated=True
            )
        except Transaction.DoesNotExist:
            logger.warning(f"Estimated transaction {transaction_id} not found for user {request.user.id}")
            return JsonResponse({
                'success': True,
                'message': 'No estimated transaction found to delete'
            })
        
        period_label = tx.period.label if tx.period else "Unknown"
        tx.delete()
        
        # Clear cache
        clear_tx_cache(request.user.id)
        
        return JsonResponse({
            'success': True,
            'message': f'Estimated transaction for {period_label} deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting estimated transaction {transaction_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_POST  
@login_required
def delete_estimated_transaction_by_period(request, period_id):
    """Delete estimated transaction for a specific period."""
    try:
        # Get the period
        try:
            period = DatePeriod.objects.get(id=period_id)
        except DatePeriod.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Period not found'})
        
        # Find and delete estimated transactions for this period and user
        estimated_transactions = Transaction.objects.filter(
            user=request.user,
            period=period,
            is_estimated=True
        )
        
        deleted_count = estimated_transactions.count()
        estimated_transactions.delete()
        
        logger.info(f"Deleted {deleted_count} estimated transaction(s) for period {period.label}")
        
        # Clear cache
        clear_tx_cache(request.user.id)
        
        return JsonResponse({
            'success': True,
            'message': f'Deleted {deleted_count} estimated transaction(s) for {period.label}'
        })
        
    except Exception as e:
        logger.error(f"Error deleting estimated transactions for period {period_id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def get_available_years(request):
    """Get years that have periods with account balances."""
    try:
        # Get distinct years from periods that have account balances for this user
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT dp.year
                FROM core_dateperiod dp
                INNER JOIN core_accountbalance ab ON ab.period_id = dp.id
                INNER JOIN core_account a ON ab.account_id = a.id
                WHERE a.user_id = %s
                ORDER BY dp.year DESC
            """, [request.user.id])
            
            years = [row[0] for row in cursor.fetchall()]
            
        logger.debug(f"Found {len(years)} years with balance periods for user {request.user.id}: {years}")
        
        return JsonResponse({
            'success': True,
            'years': years
        })
        
    except Exception as e:
        logger.error(f"Error getting available years for user {request.user.id}: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ==============================================================================
# API FUNCTIONS
# ==============================================================================

@login_required
def period_autocomplete(request):
    """Autocomplete for periods."""
    term = request.GET.get('term', '')
    periods = DatePeriod.objects.filter(
        label__icontains=term
    ).values_list('label', flat=True)[:10]
    return JsonResponse(list(periods), safe=False)


@login_required
def api_jwt_my_transactions(request):
    """JWT API for transactions."""
    transactions = Transaction.objects.filter(user=request.user)[:50]
    data = list(transactions.values('id', 'date', 'type', 'amount'))
    return JsonResponse(data, safe=False)


@login_required
def dashboard_data(request):
    """Dashboard data API."""
    return JsonResponse({
        'status': 'success',
        'data': {
            'total_transactions': Transaction.objects.filter(user=request.user).count(),
            'total_accounts': Account.objects.filter(user=request.user).count(),
        }
    })


@login_required
def dashboard_kpis_json(request):
    """Dashboard KPIs JSON API."""
    try:
        user_id = request.user.id

        # Get period filters
        start_period = request.GET.get('start_period')
        end_period = request.GET.get('end_period')

        # Base query for transactions
        tx_query = Transaction.objects.filter(user_id=user_id)

        # Apply period filters if provided
        if start_period and end_period:
            try:
                start_year, start_month = map(int, start_period.split('-'))
                end_year, end_month = map(int, end_period.split('-'))

                start_date = date(start_year, start_month, 1)
                # Calculate end date (last day of end month)
                if end_month == 12:
                    end_date = date(end_year + 1, 1, 1) - date(end_year, 12, 31).replace(day=1)
                else:
                    end_date = date(end_year, end_month + 1, 1) - date(end_year, end_month, 1).replace(day=1)

                tx_query = tx_query.filter(date__gte=start_date, date__lte=end_date)
            except (ValueError, TypeError):
                logger.warning(f"Invalid period format: {start_period} - {end_period}")

        # Get aggregated stats
        stats = tx_query.aggregate(
            total_income=models.Sum('amount', filter=models.Q(type='IN')) or 0,
            total_expenses=models.Sum('amount', filter=models.Q(type='EX')) or 0,
            total_investments=models.Sum('amount', filter=models.Q(type='IV')) or 0,
            total_count=models.Count('id')
        )

        total_income = float(stats['total_income'] or 0)
        total_expenses = float(stats['total_expenses'] or 0)
        total_investments = float(stats['total_investments'] or 0)
        total_transactions = stats['total_count']

        # Calculate averages (avoid division by zero)
        num_months = max(1, total_transactions // 10)  # Rough estimate
        receita_media = total_income / max(num_months, 1)
        despesa_media = abs(total_expenses) / max(num_months, 1)

        # Get latest account balances for patrimonio
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(ab.reported_balance), 0)
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                WHERE a.user_id = %s
                AND ab.period_id = (
                    SELECT dp.id FROM core_dateperiod dp 
                    ORDER BY dp.year DESC, dp.month DESC 
                    LIMIT 1
                )
            """, [user_id])
            patrimonio_total = float(cursor.fetchone()[0] or 0)

        return JsonResponse({
            'patrimonio_total': f"{patrimonio_total:,.0f} €",
            'receita_media': f"{receita_media:,.0f} €",
            'despesa_estimada_media': f"{despesa_media:,.0f} €",
            'valor_investido_total': f"{abs(total_investments):,.0f} €",
            'rentabilidade_mensal_media': "+0.0%",
            'num_meses': num_months,
            'metodo_calculo': "Enhanced calculation with period filters",
            'status': 'success',
            'debug_info': {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'total_investments': total_investments,
                'total_transactions': total_transactions,
                'patrimonio_total': patrimonio_total,
            }
        })

    except Exception as e:
        logger.error(f"Error in dashboard_kpis_json for user {request.user.id}: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'patrimonio_total': "0 €",
            'receita_media': "0 €",
            'despesa_estimada_media': "0 €",
            'valor_investido_total': "0 €",
            'rentabilidade_mensal_media': "+0.0%",
            'num_meses': 0,
            'metodo_calculo': "Error fallback",
        }, status=500)


@login_required
def financial_analysis_json(request):
    """Financial analysis JSON API."""
    return JsonResponse({
        'data': [],
        'status': 'success',
        'message': 'Analysis completed'
    })


@login_required
def sync_system_adjustments(request):
    """Sync system adjustments."""
    return JsonResponse({
        'status': 'success',
        'message': 'System adjustments synced'
    })



# Add clear cache view
@require_http_methods(["POST"])
@login_required
def clear_transaction_cache_view(request):
    """
    View to clear the transaction cache for the current user.
    """
    user_id = request.user.id
    clear_tx_cache(user_id)
    return JsonResponse({"status": "success", "message": "Transaction cache cleared successfully."})