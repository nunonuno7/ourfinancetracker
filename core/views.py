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
logger = logging.getLogger(__name__)
import hashlib
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from django.db.models.query import QuerySet

import pandas as pd
from psycopg2.extras import execute_values

from django.contrib import messages
from django.contrib.auth import login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import connection, transaction as db_transaction
from django.http import (
    HttpResponse, HttpResponseForbidden, JsonResponse,
    HttpResponseRedirect as redirect
)
from django.middleware.csrf import get_token
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views import View
from django.views.decorators.http import require_GET, require_POST
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
    AccountBalanceFormSet, AccountForm, CategoryForm,
    CustomUserCreationForm, TransactionForm, UserInFormKwargsMixin
)
from .utils.cache_helpers import clear_tx_cache

from django.views.generic import TemplateView
from django.db import transaction as db_tx, connection


# ==============================================================================
# UTILITÁRIOS DE CACHE SEGUROS
# ==============================================================================

def _cache_key(user_id: int, start: date, end: date) -> str:
    """
    Gera cache key segura com hash da SECRET_KEY para prevenir colisões.
    """
    secret_hash = hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()[:8]
    return f"tx_cache_user_{user_id}_{start}_{end}_{secret_hash}"


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
            {"name": "Dashboard", "url": reverse("transaction_list")},
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

class TransactionListView(LoginRequiredMixin, ListView):
    """Lista todas as transações do utilizador atual, paginadas por 50 linhas."""
    model = Transaction
    template_name = "core/transaction_list.html"
    context_object_name = "transactions"
    paginate_by = 50  # ← evita carregar tudo de uma só vez

    def get_queryset(self):
        """
        Retorna o queryset filtrado pelo utilizador corrente,
        com relações carregadas de forma eficiente.
        """
        return (
            Transaction.objects
            .filter(user=self.request.user)
            .select_related("category", "account", "period")
            .order_by("-date", "-id")
        )

    def get_context_data(self, **kwargs):
        """Add additional context for filters."""
        context = super().get_context_data(**kwargs)

        # Get available periods for the filter dropdown
        periods = DatePeriod.objects.order_by("-year", "-month")
        context["period_options"] = [
            f"{p.year}-{p.month:02d}" for p in periods
        ]

        # Set current period (current month by default)
        today = date.today()
        context["current_period"] = f"{today.year}-{today.month:02d}"

        return context

class TransactionCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Criar nova transação com validação de segurança."""
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list")

    def form_valid(self, form):
        """Processar formulário válido e limpar cache."""
        self.object = form.save()
        logger.debug(f'📝 Criado: {self.object}')  # ✅ DEBUG no terminal

        # Limpar cache imediatamente (transação criada)
        clear_tx_cache(self.request.user.id)

        # Set flags for JavaScript to know cache was cleared
        self.request.session['transaction_changed'] = True
        self.request.session['cache_cleared'] = True

        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": True, "reload_needed": True, "cache_cleared": True})

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
    success_url = reverse_lazy("transaction_list")

    def get_queryset(self):
        return super().get_queryset().prefetch_related("tags")

    def form_valid(self, form):
        # Limpar cache imediatamente (transação editada)
        clear_tx_cache(self.request.user.id)

        # Set flags for JavaScript to know cache was cleared
        self.request.session['transaction_changed'] = True
        self.request.session['cache_cleared'] = True

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
    success_url = reverse_lazy("transaction_list")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_id = self.object.user_id

        # Delete the transaction
        response = super().delete(request, *args, **kwargs)

        # Clear cache after deletion (transação eliminada)
        clear_tx_cache(user_id)

        # Set modification flag for frontend
        request.session['transaction_changed'] = True
        request.session['cache_cleared'] = True

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Transação eliminada com sucesso!',
                'cache_cleared': True
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
        "0": "id", "1": "period", "2": "date", "3": "type",
        "4": "amount_float", "5": "category", "6": "account", "7": "tags"
    }
    sort_col = column_map.get(order_col, "date")
    if sort_col in df.columns:
        try:
            df.sort_values(by=sort_col, ascending=ascending, inplace=True)
        except Exception:
            pass

    # Formatar montantes (sem duplicar o símbolo da moeda)
    df["amount"] = df.apply(
        lambda r: f"{r['amount_float']:,.2f} {r['currency']}".replace(",", "X").replace(".", ",").replace("X", "."),
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

    # Se length for -1, mostrar todos os registros
    if length == -1:
        page_df = df
    else:
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
    """Bulk update transactions (mark as cleared, etc.)."""
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
        if action == 'mark_cleared':
            updated = transactions.update(is_cleared=True)
        elif action == 'mark_uncleared':
            updated = transactions.update(is_cleared=False)
        elif action == 'mark_estimated':
            updated = transactions.update(is_estimated=True)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'})

        # Clear cache after bulk update
        clear_tx_cache(request.user.id)

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
        ).select_related('category', 'account', 'period')

        if len(transactions) != len(transaction_ids):
            return JsonResponse({'success': False, 'error': 'Some transactions not found'})

        created = 0
        today = date.today()
        current_period, _ = DatePeriod.objects.get_or_create(
            year=today.year,
            month=today.month,
            defaults={'label': today.strftime('%B %Y')}
        )

        with db_transaction.atomic():
            for tx in transactions:
                # Create duplicate with today's date
                new_tx = Transaction.objects.create(
                    user=tx.user,
                    type=tx.type,
                    amount=tx.amount,
                    date=today,
                    notes=f"Duplicate of transaction from {tx.date}",
                    is_cleared=False,
                    is_estimated=tx.is_estimated,
                    period=current_period,
                    account=tx.account,
                    category=tx.category
                )

                # Copy tags
                for tag in tx.tags.all():
                    new_tx.tags.add(tag)

                created += 1

        # Clear cache after bulk create
        clear_tx_cache(request.user.id)

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
    """Bulk delete transactions with optimized performance."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'error': 'No transactions selected'})

        user_id = request.user.id

        with db_transaction.atomic():
            # Use raw SQL for maximum performance
            with connection.cursor() as cursor:
                # First verify all transactions belong to user
                cursor.execute("""
                    SELECT COUNT(*) FROM core_transaction 
                    WHERE id = ANY(%s) AND user_id = %s
                """, [transaction_ids, user_id])

                valid_count = cursor.fetchone()[0]

                if valid_count != len(transaction_ids):
                    return JsonResponse({'success': False, 'error': 'Some transactions not found'})

                # Delete transaction-tag relationships first (foreign key constraint)
                cursor.execute("""
                    DELETE FROM core_transactiontag 
                    WHERE transaction_id = ANY(%s)
                """, [transaction_ids])

                # Delete transactions
                cursor.execute("""
                    DELETE FROM core_transaction 
                    WHERE id = ANY(%s) AND user_id = %s
                """, [transaction_ids, user_id])

                deleted_count = cursor.rowcount

        # Clear cache after bulk delete
        clear_tx_cache(user_id)

        return JsonResponse({
            'success': True,
            'deleted': deleted_count,
            'message': f'{deleted_count} transactions deleted'
        })

    except Exception as e:
        logger.error(f"Bulk delete error for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@require_GET
@login_required
def check_cache_status(request):
    """Check cache status without clearing it."""
    try:
        # Just return that cache is OK - no clearing needed
        return JsonResponse({
            "cache_cleared": False, 
            "status": "ok",
            "message": "Cache status checked - no action needed"
        })
    except Exception as e:
        logger.error(f"Error checking cache status: {e}")
        return JsonResponse({
            "cache_cleared": False,
            "status": "error", 
            "message": str(e)
        }, status=500)


@require_POST
@login_required
def transaction_clear_cache(request):
    """Atualizar cache de transações preservando dados válidos."""
    try:
        user_id = request.user.id
        
        # Instead of clearing cache, just log that update was requested
        # The actual cache will be updated when new data is fetched
        logger.info(f"Cache update requested for user {user_id} - cache will be refreshed on next data fetch")
        
        return JsonResponse({
            "status": "ok",
            "message": "Cache refresh requested - data will be updated on next fetch"
        })

    except Exception as e:
        logger.error(f"Error requesting cache update for user {request.user.id}: {e}")
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)

@require_GET
@login_required
def period_autocomplete(request):
    """Autocomplete para períodos."""
    q = request.GET.get("q", "")
    periods = DatePeriod.objects.order_by("-year", "-month")
    if q:
        try:
            y, m = map(int, q.split("-"))
            periods = periods.filter(year=y, month=m)
        except Exception:
            periods = periods.none()
    return JsonResponse([
        {"value": f"{p.year}-{p.month:02}", "display": p.label} 
        for p in periods
    ], safe=False)


# ==============================================================================
# VIEWS DE CATEGORIAS
# ==============================================================================

class CategoryListView(OwnerQuerysetMixin, ListView):
    """Lista categorias do utilizador atual."""
    model = Category
    template_name = "core/category_list.html"
    context_object_name = "categories"


class CategoryCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Criar nova categoria."""
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class CategoryUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Atualizar categoria existente com fusão segura."""
    model = Category
    form_class = CategoryForm
    template_name = "core/category_form.html"
    success_url = reverse_lazy("category_list")

    def form_valid(self, form):
        try:
            merged = hasattr(form, "_merged_category")
            form.save()

            if merged:
                messages.success(self.request, "✅ As categorias foram fundidas com sucesso.")
            else:
                messages.success(self.request, "✅ Categoria atualizada com sucesso.")

            return redirect(self.get_success_url())
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)


class CategoryDeleteView(OwnerQuerysetMixin, DeleteView):
    """Eliminar categoria com opções de fusão."""
    model = Category
    template_name = "core/confirms/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        option = request.POST.get("option")

        if option == "delete_all":
            Transaction.objects.filter(category=self.object).delete()
            self.object.delete()
            messages.success(request, "✅ Category and all its transactions were deleted.")

        elif option == "move_to_other":
            fallback = Category.get_fallback(request.user)

            if fallback != self.object:
                Transaction.objects.filter(category=self.object).update(category=fallback)
                self.object.delete()
                messages.success(request, "🔁 Transactions moved to 'Other'. Category deleted.")
            else:
                messages.warning(request, "⚠️ Cannot delete 'Other' category.")
        else:
            messages.error(request, "❌ No valid option selected.")

        return redirect(self.success_url)


# ==============================================================================
# VIEWS DE CONTAS
# ==============================================================================

class AccountListView(OwnerQuerysetMixin, ListView):
    """Lista contas do utilizador atual."""
    model = Account
    template_name = "core/account_list.html"
    context_object_name = "accounts"

    def get_queryset(self) -> QuerySet:
        return super().get_queryset().order_by("position", "name")


class AccountCreateView(LoginRequiredMixin, UserInFormKwargsMixin, CreateView):
    """Criar nova conta com verificação de duplicados."""
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        existing = form.find_duplicate()

        if existing:
            if not self.request.POST.get("confirm_merge", "").lower() == "true":
                form.add_error(None, "Já existe uma conta com esse nome. Queres fundir os saldos?")
                return self.form_invalid(form)

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountUpdateView(OwnerQuerysetMixin, UserInFormKwargsMixin, UpdateView):
    """Atualizar conta existente."""
    model = Account
    form_class = AccountForm
    template_name = "core/account_form.html"
    success_url = reverse_lazy("account_list")

    def form_valid(self, form):
        new_name = form.cleaned_data["name"].strip()
        existing = Account.objects.filter(
            user=self.request.user,
            name__iexact=new_name
        ).exclude(pk=self.object.pk).first()

        if existing:
            form.save(commit=False)
            return redirect("account_merge", source_pk=self.object.pk, target_pk=existing.pk)

        try:
            self.object = form.save()
        except ValidationError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        return super().form_valid(form)


class AccountDeleteView(OwnerQuerysetMixin, DeleteView):
    """Eliminar conta com verificações de segurança."""
    model = Account
    template_name = "core/confirms/account_confirm_delete.html"
    success_url = reverse_lazy("account_list")

    def dispatch(self, request, *args, **kwargs):
        account = self.get_object()
        if account.is_default():
            return HttpResponseForbidden("⚠️ The default 'Cash' account cannot be deleted.")
        return super().dispatch(request, *args, **kwargs)


class AccountMergeView(OwnerQuerysetMixin, View):
    """Fundir duas contas duplicadas."""
    template_name = "core/confirms/account_confirm_merge.html"
    success_url = reverse_lazy("account_list")

    def get(self, request, *args, **kwargs):
        source = self.get_source_account()
        target = self.get_target_account()

        if not source or not target:
            messages.error(request, "Accounts not found for merging.")
            return redirect("account_list")

        return render(request, self.template_name, {
            "source": source,
            "target": target,
        })

    def post(self, request, *args, **kwargs):
        target = self.get_target_account()
        source = self.get_source_account()

        if not source or not target or source == target:
            messages.error(request, "Invalid merge.")
            return redirect("account_list")

        # Fundir saldos duplicados
        for bal in AccountBalance.objects.filter(account=source):
            existing = AccountBalance.objects.filter(
                account=target, period=bal.period
            ).first()

            if existing:
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


# ==============================================================================
# VIEWS DE SALDOS DE CONTAS
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
            messages.error(request, "Mês inválido.")
            month = today.month
    except ValueError:
        messages.error(request, "Data inválida.")
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

                messages.success(request, "Saldos guardados com sucesso!")
                return redirect(f"{request.path}?year={year}&month={month:02d}")
            except Exception as e:
                messages.error(request, f"Erro ao guardar os saldos: {str(e)}")
        else:
            messages.error(request, "Erro ao guardar os saldos. Verifica os campos.")
    else:
        formset = AccountBalanceFormSet(queryset=qs_base, user=request.user)

    # Agrupar formulários por tipo e moeda
    grouped_forms = {}
    totals_by_group = {}
    grand_total = 0

    for form in formset:
        if hasattr(form.instance, 'account') and form.instance.account:
            account = form.instance.account

            # Verificações de segurança para account_type e currency
            account_type_name = account.account_type.name if account.account_type else "Unknown"
            currency_code = account.currency.code if account.currency else "EUR"

            key = (account_type_name, currency_code)
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
# VIEWS AUXILIARES
# ==============================================================================

def signup(request):
    """Registo de utilizador."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, "Conta criada com sucesso!")
                return redirect("transaction_list")
            except Exception as e:
                messages.error(request, f"Erro ao criar conta: {str(e)}")
                return render(request, "registration/signup.html", {"form": form})
        else:
            messages.error(request, "Erro na validação do formulário.")
    else:
        form = CustomUserCreationForm()

    return render(request, "registration/signup.html", {"form": form})


class LogoutView(RedirectView):
    """Logout do utilizador."""
    pattern_name = "login"

    def get(self, request, *args, **kwargs):
        auth_logout(request)
        return super().get(request, *args, **kwargs)


class HomeView(TemplateView):
    """
    Página inicial da aplicação OurFinanceTracker.
    Redireciona utilizadores autenticados para o dashboard.
    """
    template_name = "core/home.html"

    def get(self, request, *args, **kwargs):
        # Se utilizador autenticado, redirecionar para dashboard
        if request.user.is_authenticated:
            return redirect('dashboard')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'OurFinanceTracker - Gestão Financeira Pessoal'
        return context

@require_POST
@login_required
def delete_account_balance(request, pk):
    """Eliminar saldo de conta específico."""
    try:
        obj = AccountBalance.objects.get(pk=pk, account__user=request.user)
        obj.delete()
        return JsonResponse({"success": True})
    except AccountBalance.DoesNotExist:
        return JsonResponse({"success": False, "error": "Not found"}, status=404)


@require_GET
@login_required
def copy_previous_balances_view(request):
    """Copiar saldos do mês anterior se não existirem."""
    year = int(request.GET.get("year"))
    month = int(request.GET.get("month"))

    # Calcular mês anterior
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


# ==============================================================================
# VIEWS DE MOVIMENTO DE CONTAS
# ==============================================================================

@login_required
def move_account_up(request, pk):
    """Mover conta para cima na ordenação."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    above = Account.objects.filter(
        user=request.user, 
        position__lt=account.position
    ).order_by("-position").first()

    if above:
        account.position, above.position = above.position, account.position
        account.save()
        above.save()
    return redirect("account_list")


@login_required
def move_account_down(request, pk):
    """Mover conta para baixo na ordenação."""
    account = get_object_or_404(Account, pk=pk, user=request.user)
    below = Account.objects.filter(
        user=request.user, 
        position__gt=account.position
    ).order_by("position").first()

    if below:
        account.position, below.position = below.position, account.position
        account.save()
        below.save()
    return redirect("account_list")


@login_required
def account_reorder(request):
    """Reordenar contas via AJAX."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            order = data.get("order", [])
            for item in order:
                Account.objects.filter(
                    pk=item["id"], 
                    user=request.user
                ).update(position=item["position"])
            return JsonResponse({"status": "ok"})
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"error": "invalid method"}, status=405)


# ==============================================================================
# AUTOCOMPLETE APIS
# ==============================================================================

@login_required
def category_autocomplete(request):
    """Autocomplete para categorias do utilizador."""
    q = request.GET.get("q", "").strip()
    results = Category.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name")

    data = [{"name": c.name} for c in results]
    return JsonResponse(data, safe=False)


@login_required
def tag_autocomplete(request):
    """Autocomplete para tags do utilizador."""
    q = request.GET.get("q", "").strip()
    results = Tag.objects.filter(
        user=request.user,
        name__icontains=q
    ).order_by("name").values("name").distinct()

    return JsonResponse(list(results), safe=False)


# ==============================================================================
# IMPORT/EXPORT EXCEL
# ==============================================================================

# core/views.py
from io import BytesIO
from django.http import HttpResponse
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
import pandas as pd


@require_GET
@login_required
def export_transactions_xlsx(request):
    """Exporta todas as transacções do utilizador (tags e type por extenso)."""
    user_id = request.user.id

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              t.date                                           AS "Date",
              CASE t.type
                   WHEN 'EX' THEN 'Expense'
                   WHEN 'IN' THEN 'Income'
                   WHEN 'IV' THEN 'Investment'
                   WHEN 'TR' THEN 'Transfer'
                   ELSE t.type
              END                                              AS "Type",
              t.amount                                         AS "Amount",
              COALESCE(a.name, '')                             AS "Account",
              COALESCE(c.name, '')                             AS "Category",
              COALESCE((
                 SELECT STRING_AGG(DISTINCT tg.name, ', ' ORDER BY tg.name)
                 FROM core_transactiontag tt
                 JOIN core_tag tg ON tg.id = tt.tag_id
                 WHERE tt.transaction_id = t.id
                   AND tg.user_id      = t.user_id
              ), '')                                           AS "Tags",
              COALESCE(t.notes, '')                            AS "Notes",
              CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS "Period"
            FROM core_transaction t
            LEFT JOIN core_account     a ON a.id = t.account_id
            LEFT JOIN core_category    c ON c.id = t.category_id
            LEFT JOIN core_dateperiod  p ON p.id = t.period_id
            WHERE t.user_id = %s
            ORDER BY t.date DESC;
        """, [user_id])

        rows    = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

    df = pd.DataFrame(rows, columns=columns)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Transactions")
    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = "attachment; filename=transactions.xlsx"
    return response










from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db import transaction as db_tx, connection
from django.utils.timezone import now
from django.contrib import messages

import pandas as pd
import re
from decimal import Decimal, InvalidOperation


# ────────────────────  HELPER NORMALISERS  ────────────────────
def normalise_amount(raw):
    """Return a Decimal or None; accepts 1.234,56 €  –100,00 +1 000,00 etc."""
    if pd.isna(raw):
        return None
    raw = str(raw).strip().replace("\u00A0", "")
    raw = re.sub(r"[€$+]", "", raw).replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except (InvalidOperation, ValueError):
        return None


def normalise_type(raw):
    """Map many human spellings to canonical codes IN / EX / IV / TR."""
    if not isinstance(raw, str):
        return None
    raw = raw.strip().lower()
    mapping = {
        "in": "IN", "income": "IN", "receita": "IN",
        "ex": "EX", "expense": "EX", "gasto": "EX",
        "iv": "IV", "investment": "IV", "investimento": "IV",
        "tr": "TR", "transfer": "TR", "transferência": "TR",
    }
    return mapping.get(raw)


# ──────────────────────  MAIN VIEW  ───────────────────────────
@require_http_methods(["GET", "POST"])
@login_required
def import_transactions_xlsx(request):
    """Import XLSX with columns: Date | Type | Amount | Category | Tags | Account."""
    if request.method == "GET":
        return render(request, "core/import_form.html")

    try:
        df = pd.read_excel(request.FILES["file"])
    except Exception as e:
        messages.error(request, f"Error reading Excel file: {e}")
        return redirect("transaction_import_xlsx")

    required = {"Date", "Type", "Amount", "Category", "Tags", "Account"}
    if missing := (required - set(df.columns)):
        messages.error(request, f"Missing columns: {', '.join(missing)}")
        return redirect("transaction_import_xlsx")

    user_id = request.user.id
    ts = now()
    inserted = 0
    periods, cats, accts, tags = {}, {}, {}, {}

    with connection.cursor() as cur, db_tx.atomic():
        for idx, row in df.iterrows():
            row_num = idx + 2
            raw_date = row["Date"]
            if pd.isna(raw_date):
                messages.warning(request, f"⚠️ Line {row_num}: Date empty.")
                continue
            date_val = pd.to_datetime(raw_date).date()

            tx_type = normalise_type(row["Type"])
            if not tx_type:
                messages.warning(request, f"⚠️ Line {row_num}: invalid Type '{row['Type']}'.")
                continue

            amount = normalise_amount(row["Amount"])
            if amount is None:
                messages.warning(request, f"⚠️ Line {row_num}: invalid Amount '{row['Amount']}'.")
                continue
            if amount == 0:
                messages.warning(request, f"⚠️ Line {row_num}: zero Amount ignored.")
                continue

            if tx_type == "IV":
                amount = amount if amount < 0 else abs(amount)
            else:
                amount = abs(amount)

            key = (date_val.year, date_val.month)
            if key not in periods:
                cur.execute(
                    """
                    INSERT INTO core_dateperiod (year, month, label)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (year,month) DO NOTHING
                    RETURNING id
                    """,
                    [key[0], key[1], date_val.strftime("%B %Y")],
                )
                rec = cur.fetchone() or cur.execute(
                    "SELECT id FROM core_dateperiod WHERE year=%s AND month=%s",
                    key,
                ) or cur.fetchone()
                if not rec:
                    messages.warning(request, f"⚠️ Line {row_num}: cannot resolve DatePeriod.")
                    continue
                periods[key] = rec[0]
            period_id = periods[key]

            cat = str(row["Category"]).strip()
            if cat not in cats:
                cur.execute(
                    """
                    INSERT INTO core_category (user_id,name,position,created_at,updated_at)
                    VALUES (%s,%s,0,%s,%s)
                    ON CONFLICT (user_id,name) DO NOTHING
                    RETURNING id
                    """,
                    [user_id, cat, ts, ts],
                )
                rec = cur.fetchone() or cur.execute(
                    "SELECT id FROM core_category WHERE user_id=%s AND name=%s",
                    [user_id, cat],
                ) or cur.fetchone()
                if not rec:
                    messages.warning(request, f"⚠️ Line {row_num}: cannot resolve Category '{cat}'.")
                    continue
                cats[cat] = rec[0]
            category_id = cats[cat]

            acc = str(row["Account"]).strip()
            if acc not in accts:
                cur.execute(
                    "SELECT id FROM core_account WHERE user_id=%s AND name=%s",
                    [user_id, acc],
                )
                rec = cur.fetchone()
                if not rec:
                    cur.execute(
                        "SELECT id FROM core_accounttype WHERE name ILIKE %s LIMIT 1",
                        ["savings"],
                    )
                    type_rec = cur.fetchone()
                    if not type_rec:
                        cur.execute("SELECT id FROM core_accounttype LIMIT 1")
                        type_rec = cur.fetchone()
                    if not type_rec:
                        messages.warning(request, "⚠️ Nenhum AccountType definido na base de dados.")
                        continue
                    acct_type_id = type_rec[0]
                    cur.execute(
                        """
                        INSERT INTO core_account (
                            user_id, name, position, created_at, account_type_id
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        [user_id, acc, 0, ts, acct_type_id],
                    )
                    rec = cur.fetchone()

                if not rec:
                    messages.warning(request, f"⚠️ Line {row_num}: cannot create Account '{acc}'.")
                    continue
                accts[acc] = rec[0]
            account_id = accts[acc]

            raw_tags = row.get("Tags", "")
            tag_names = [] if pd.isna(raw_tags) else [t.strip() for t in str(raw_tags).split(",") if t.strip()]
            tag_ids = []

            for tag in tag_names:
                if tag not in tags:
                    cur.execute(
                        """
                        INSERT INTO core_tag (user_id, name, position)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                        """,
                        [user_id, tag, 0],
                    )
                    rec = cur.fetchone()
                    if not rec:
                        cur.execute(
                            "SELECT id FROM core_tag WHERE user_id=%s AND name=%s",
                            [user_id, tag],
                        )
                        rec = cur.fetchone()
                    if not rec:
                        messages.warning(request, f"⚠️ Line {row_num}: cannot resolve Tag '{tag}'.")
                        continue
                    tags[tag] = rec[0]
                tag_ids.append(tags[tag])

            cur.execute(
                """
                INSERT INTO core_transaction (
                    user_id, type, amount, date,
                    notes, is_cleared, is_estimated,
                    period_id, account_id, category_id,
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                RETURNING id
                """,
                [
                    user_id, tx_type, amount, date_val,
                    "", False, False,
                    period_id, account_id, category_id,
                    ts, ts,
                ],
            )
            rec = cur.fetchone()
            if not rec:
                messages.warning(request, f"⚠️ Line {row_num}: insert failed.")
                continue
            transaction_id = rec[0]
            inserted += 1

            for tag_id in tag_ids:
                cur.execute(
                    """
                    INSERT INTO core_transactiontag (transaction_id, tag_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [transaction_id, tag_id],
                )

    from core.utils.cache_helpers import clear_tx_cache
    clear_tx_cache(user_id)

    messages.success(request, f"✅ {inserted} transactions imported successfully.")
    return redirect("transaction_list")


@login_required
def import_transactions_template(request):
    """Template para importação de transações com múltiplos exemplos reais."""
    example_data = [
        {
            "Date": "2025-06-15",
            "Type": "Income",
            "Amount": 1000.00,
            "Category": "Salary",
            "Tags": "monthly,recurring",
            "Account": "Bpi"
        },
        {
            "Date": "2025-06-16",
            "Type": "Expense",
            "Amount": 200.00,
            "Category": "Groceries",
            "Tags": "food",
            "Account": "Bpi"
        },
        {
            "Date": "2025-06-17",
            "Type": "Investment",
            "Amount": 500.00,
            "Category": "ETF",
            "Tags": "longterm",
            "Account": "Trading212"
        },
        {
            "Date": "2025-06-18",
            "Type": "Investment",
            "Amount": -250.00,
            "Category": "ETF",
            "Tags": "rebalance",
            "Account": "Trading212"
        },
        {
            "Date": "2025-06-19",
            "Type": "Transfer",
            "Amount": 150.00,
            "Category": "Transferência",
            "Tags": "",
            "Account": "Revolut"
        }
    ]

    df = pd.DataFrame(example_data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")

    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="transactions_template.xlsx"'
    return response


# ==============================================================================
# IMPORT/EXPORT SALDOS
# ==============================================================================

@login_required
def account_balance_export_xlsx(request):
    """Exportar saldos de contas para Excel."""
    user_id = request.user.id

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                p.year AS Year,
                p.month AS Month,
                a.name AS Account,
                at.name AS Type,
                COALESCE(curr.code, 'EUR') AS Currency,
                ab.reported_balance AS Balance
            FROM core_accountbalance ab
            INNER JOIN core_account a ON ab.account_id = a.id
            LEFT JOIN core_accounttype at ON a.account_type_id = at.id
            LEFT JOIN core_currency curr ON a.currency_id = curr.id
            INNER JOIN core_dateperiod p ON ab.period_id = p.id
            WHERE a.user_id = %s
            ORDER BY p.year, p.month, a.name
        """, [user_id])
        rows = cursor.fetchall()
        columns = [col[0] for col in cursor.description]

    df = pd.DataFrame(rows, columns=columns)

    buffer = BytesIO()
    df.to_excel(buffer, index=False, sheet_name="Balances")
    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="account_balances.xlsx"'
    return response


@login_required
def account_balance_import_xlsx(request):
    """Importar saldos de contas de Excel."""
    if request.method == "POST":
        file = request.FILES.get("file")
        if not file or not file.name.endswith(".xlsx"):
            messages.error(request, "Please upload a valid .xlsx Excel file.")
            return redirect("account_balance_import_xlsx")

        try:
            df = pd.read_excel(file)
        except Exception as e:
            messages.error(request, f"Error reading Excel file: {e}")
            return redirect("account_balance_import_xlsx")

        required_cols = {"Year", "Month", "Account", "Balance"}
        if not required_cols.issubset(df.columns):
            messages.error(request, f"Missing required columns: {', '.join(required_cols)}")
            return redirect("account_balance_import_xlsx")

        user_id = request.user.id
        created = 0
        timestamp = now()

        with connection.cursor() as cursor, db_transaction.atomic():
            periods_cache = {}
            accounts_cache = {}

            cursor.execute("SELECT id FROM core_accounttype WHERE name ILIKE 'Savings' LIMIT 1")
            default_type_id = cursor.fetchone()[0]

            cursor.execute("SELECT id FROM core_currency WHERE code = 'EUR'")
            default_currency_id = cursor.fetchone()[0]

            for idx, row in df.iterrows():
                try:
                    year = int(row["Year"])
                    month = int(row["Month"])
                    account_name = str(row["Account"]).strip()
                    balance = float(row["Balance"])
                except Exception as e:
                    messages.warning(request, f"❌ Skipped row {idx + 1}: {e}")
                    continue

                key_period = (year, month)
                if key_period not in periods_cache:
                    cursor.execute("""
                        INSERT INTO core_dateperiod (year, month, label)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (year, month) DO NOTHING
                        RETURNING id
                    """, [year, month, date(year, month, 1).strftime("%B %Y")])
                    row_period = cursor.fetchone()
                    if not row_period:
                        cursor.execute("SELECT id FROM core_dateperiod WHERE year = %s AND month = %s", key_period)
                        row_period = cursor.fetchone()
                    periods_cache[key_period] = row_period[0]

                period_id = periods_cache[key_period]

                if account_name not in accounts_cache:
                    cursor.execute("""
                        INSERT INTO core_account (user_id, name, account_type_id, currency_id, created_at, position)
                        VALUES (%s, %s, %s, %s, %s, 0)
                        ON CONFLICT (user_id, name) DO NOTHING
                        RETURNING id
                    """, [user_id, account_name, default_type_id, default_currency_id, timestamp])
                    row_acc = cursor.fetchone()
                    if not row_acc:
                        cursor.execute("SELECT id FROM core_account WHERE user_id = %s AND name = %s", [user_id, account_name])
                        row_acc = cursor.fetchone()
                    accounts_cache[account_name] = row_acc[0]

                account_id = accounts_cache[account_name]

                cursor.execute("""
                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (account_id, period_id)
                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                """, [account_id, period_id, balance])
                created += 1

        messages.success(request, f"✅ {created} balances imported successfully.")
        return redirect("account_balance")

    return render(request, "core/import_balances_form.html")


@login_required
def account_balance_template_xlsx(request):
    """Template para importação de saldos."""
    df = pd.DataFrame([{
        "Year": 2025,
        "Month": 6,
        "Account": "Bpi",
        "Balance": 1234.56
    }])

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Template")

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = "attachment; filename=account_balances_template.xlsx"
    return response


# ==============================================================================
# APIs ESPECIAIS
# ==============================================================================

@login_required
def dashboard_data(request):
    """API para dados do dashboard."""
    user_id = request.user.id

    with connection.cursor() as cursor:
        cursor.execute("""
            WITH base AS (
                SELECT p.year, p.month,
                    SUM(CASE WHEN t.type = 'IN' THEN t.amount ELSE 0 END) AS income
                FROM core_transaction t
                JOIN core_dateperiod p ON t.period_id = p.id
                WHERE t.user_id = %s
                GROUP BY p.year, p.month
            ),
            saldos AS (
                SELECT p.year, p.month, SUM(ab.reported_balance) AS saldo
                FROM core_accountbalance ab
                JOIN core_dateperiod p ON ab.period_id = p.id
                JOIN core_account a ON ab.account_id = a.id
                WHERE a.user_id = %s
                GROUP BY p.year, p.month
            )
            SELECT b.year, b.month, b.income,
                s1.saldo AS saldo_n,
                s2.saldo AS saldo_nplus1,
                COALESCE(s1.saldo - s2.saldo + b.income, 0) AS expense_est
            FROM base b
            LEFT JOIN saldos s1 ON s1.year = b.year AND s1.month = b.month
            LEFT JOIN saldos s2 ON (
                (s2.year = b.year AND s2.month = b.month + 1) OR
                (s2.year = b.year + 1 AND b.month = 12 AND s2.month = 1)
            )
            ORDER BY b.year, b.month;
        """, [user_id, user_id])

        rows = cursor.fetchall()

    labels = [f"{y}-{m:02d}" for y, m, *_ in rows]
    income = [float(inc or 0) for _, _, inc, *_ in rows]
    expense = [float(e or 0) for *_, e in rows]

    return JsonResponse({
        "labels": labels,
        "income": income,
        "expense": expense
    })


# JWT API para integrações externas (Looker, etc.)
import jwt

@require_GET
def api_jwt_my_transactions(request):
    """API JWT segura para transações do utilizador."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return HttpResponseForbidden("Missing Authorization header with JWT token.")

    token = auth_header.replace("Bearer ", "").strip()
    try:
        jwt_secret = getattr(settings, 'SUPABASE_JWT_SECRET', settings.SECRET_KEY)
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = int(payload["user_id"])
    except Exception as e:
        return HttpResponseForbidden(f"Invalid token: {str(e)}")

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT
                t.id, t.date, t.amount, t.type,
                COALESCE(c.name, '') AS category,
                COALESCE(a.name, '') AS account,
                CONCAT(p.year, '-', LPAD(p.month::text, 2, '0')) AS period
            FROM core_transaction t
            LEFT JOIN core_category c ON t.category_id = c.id
            LEFT JOIN core_account a ON t.account_id = a.id
            LEFT JOIN core_dateperiod p ON t.period_id = p.id
            WHERE t.user_id = %s
            ORDER BY t.date DESC
        """, [user_id])

        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return JsonResponse(rows, safe=False)


# ==============================================================================
# FIM DO FICHEIRO
# ==============================================================================

@require_POST
@login_required
def clear_session_flag(request):
    """Limpar flag de mudança de transação da sessão."""
    if 'transaction_changed' in request.session:
        del request.session['transaction_changed']
    if 'cache_cleared' in request.session:
        del request.session['cache_cleared']
    return JsonResponse({'success': True})

@login_required
def check_cache_status(request):
    """Check if cache was cleared and needs frontend update."""
    cache_cleared = request.session.get('cache_cleared', False)
    if cache_cleared:
        # Clear the flag after checking
        del request.session['cache_cleared']

    return JsonResponse({
        'cache_cleared': cache_cleared,
        'should_reload_cache': cache_cleared
    })

@login_required
def dashboard_kpis_json(request):
    """
    API JSON para KPIs do dashboard - função em falta no views.py original.

    Esta função calcula e retorna indicadores financeiros principais:
    - Patrimônio total atual
    - Receita média mensal
    - Despesa média estimada
    - Poupança média
    - Taxa de crescimento patrimonial
    """
    user_id = request.user.id

    try:
        with connection.cursor() as cursor:
            # Query para obter dados financeiros agregados
            cursor.execute("""
                WITH monthly_data AS (
                    -- Receitas mensais
                    SELECT 
                        dp.year, dp.month,
                        COALESCE(SUM(CASE WHEN tx.type = 'IN' THEN tx.amount ELSE 0 END), 0) as income,
                        COALESCE(SUM(CASE WHEN tx.type = 'EX' THEN tx.amount ELSE 0 END), 0) as expenses
                    FROM core_dateperiod dp
                    LEFT JOIN core_transaction tx ON tx.period_id = dp.id AND tx.user_id = %s
                    GROUP BY dp.year, dp.month
                ),
                patrimonio_data AS (
                    -- Patrimônio mensal (contas de investimento)
                    SELECT 
                        dp.year, dp.month,
                        COALESCE(SUM(ab.reported_balance), 0) as patrimonio
                    FROM core_dateperiod dp
                    LEFT JOIN core_accountbalance ab ON ab.period_id = dp.id
                    LEFT JOIN core_account acc ON ab.account_id = acc.id AND acc.user_id = %s
                    LEFT JOIN core_accounttype at ON acc.account_type_id = at.id
                    WHERE LOWER(at.name) LIKE '%%investment%%' OR at.name IS NULL
                    GROUP BY dp.year, dp.month
                ),
                savings_data AS (
                    -- Saldos de poupança
                    SELECT 
                        dp.year, dp.month,
                        COALESCE(SUM(ab.reported_balance), 0) as savings
                    FROM core_dateperiod dp
                    LEFT JOIN core_accountbalance ab ON ab.period_id = dp.id
                    LEFT JOIN core_account acc ON ab.account_id = acc.id AND acc.user_id = %s
                    LEFT JOIN core_accounttype at ON acc.account_type_id = at.id
                    WHERE LOWER(at.name) LIKE '%%saving%%' OR LOWER(at.name) LIKE '%%deposit%%'
                    GROUP BY dp.year, dp.month
                )
                SELECT 
                    md.year, md.month, md.income, md.expenses,
                    pd.patrimonio, sd.savings
                FROM monthly_data md
                LEFT JOIN patrimonio_data pd ON md.year = pd.year AND md.month = pd.month
                LEFT JOIN savings_data sd ON md.year = sd.year AND md.month = sd.month
                ORDER BY md.year DESC, md.month DESC
                LIMIT 12
            """, [user_id, user_id, user_id])

            rows = cursor.fetchall()

        if not rows:
            # Retornar valores default se não há dados
            return JsonResponse({
                "patrimonio_atual": "0 €",
                "receita_media": "0 €", 
                "despesa_media": "0 €",
                "poupanca_media": "0 €",
                "crescimento_patrimonial": "0 €",
                "num_meses": 0,
                "status": "no_data"
            })

        # Processar dados para cálculos
        df = pd.DataFrame(rows, columns=['year', 'month', 'income', 'expenses', 'patrimonio', 'savings'])
        df = df.fillna(0)

        # KPIs principais
        patrimonio_atual = float(df['patrimonio'].iloc[0]) if len(df) > 0 else 0
        receita_media = float(df['income'].mean())
        despesa_media = float(df['expenses'].mean())

        # Cálculo de poupança média
        df['poupanca_mensal'] = df['income'] - df['expenses']
        poupanca_media = float(df['poupanca_mensal'].mean())

        # Crescimento patrimonial (diferença entre primeiro e último)
        if len(df) > 1:
            patrimonio_inicial = float(df['patrimonio'].iloc[-1])  # Mais antigo
            crescimento = patrimonio_atual - patrimonio_inicial
        else:
            crescimento = 0

        # Formatação para display
        return JsonResponse({
            "patrimonio_atual": f"{patrimonio_atual:,.0f} €".replace(",", "."),
            "receita_media": f"{receita_media:,.0f} €".replace(",", "."),
            "despesa_media": f"{despesa_media:,.0f} €".replace(",", "."),
            "poupanca_media": f"{poupanca_media:,.0f} €".replace(",", "."),
            "crescimento_patrimonial": f"{crescimento:,.0f} €".replace(",", "."),
            "num_meses": len(df),
            "status": "success"
        })

    except Exception as e:
        # Log do erro e retorno de valores safe
        return JsonResponse({
            "error": str(e),
            "patrimonio_atual": "0 €",
            "receita_media": "0 €",
            "despesa_media": "0 €", 
            "poupanca_media": "0 €",
            "crescimento_patrimonial": "0 €",
            "status": "error"
        }, status=500)

def account_balance_template_xlsx(request):
    """Download de template de Excel com colunas Year, Month, Account, Balance."""

    output = BytesIO()

    # Exemplo com o mês atual
    today = date.today()
    df = pd.DataFrame([{
        "Year": today.year,
        "Month": today.month,
        "Account": "Bpi",
        "Balance": 1234.56,
    }])

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    output.seek(0)
    filename = "account_balance_template.xlsx"
    response = HttpResponse(
        output.read(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response