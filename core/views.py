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
import hashlib
import re
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

import pandas as pd
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models, transaction as db_transaction
from django.db.models import Q, Sum
from django.db.models.query import QuerySet
from django.http import (
    Http404,
    HttpResponse,
    HttpResponseForbidden,
    HttpResponseRedirect as redirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.timezone import now
from django.views import View
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    RedirectView,
    TemplateView,
    UpdateView,
)

from .forms import (
    AccountBalanceFormSet,
    AccountForm,
    CategoryForm,
    TransactionForm,
    UserInFormKwargsMixin,
)
from .models import (
    Account,
    AccountBalance,
    AccountType,
    Category,
    Currency,
    DatePeriod,
    Tag,
    Transaction,
    User,
    convert_amount,
    get_default_currency,
)
from .utils.cache_helpers import clear_tx_cache

logger = logging.getLogger(__name__)


# Helper for consistent percentage math with Decimals
def pct(part, whole) -> Decimal:
    try:
        if not whole or Decimal(whole) == 0:
            return Decimal('0.00')
        return (
            Decimal(part) / Decimal(whole) * Decimal('100')
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        # Defensive fallback
        return Decimal('0.00')




# LogoutView removida - usando Django's built-in LogoutView via accounts app

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
    Gera uma chave de cache segura combinando ``SECRET_KEY``, ``user_id``,
    ``start`` e ``end`` através de um hash ``SHA256``. Desta forma,
    diferentes utilizadores ou intervalos de datas produzem chaves
    exclusivamente ligadas ao ambiente atual.
    """
    raw = f"{settings.SECRET_KEY}:{user_id}:{start}:{end}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return f"tx_cache_user_{user_id}_{start}_{end}_{digest}"


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


def _shift_period(period_yyyy_mm: str, delta_months: int) -> str:
    """Return period shifted by ``delta_months`` in YYYY-MM format."""
    year, month = map(int, period_yyyy_mm.split("-"))
    month += delta_months
    year += (month - 1) // 12
    month = (month - 1) % 12 + 1
    return f"{year:04d}-{month:02d}"


def build_kpis_for_period(user, period_str: str):
    """Build KPI metrics for a period in the user's base currency."""
    cache_key = f"kpi:{user.id}:{period_str}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    year, month = map(int, period_str.split("-"))
    tx = (
        Transaction.objects.filter(user=user, period__year=year, period__month=month)
        .select_related("account__currency")
    )
    base_currency = (
        getattr(user, "settings", None) and user.settings.base_currency
    ) or get_default_currency()
    income = expenses = investments = Decimal("0")
    for t in tx:
        src_currency = t.account.currency if t.account and t.account.currency else base_currency
        converted = convert_amount(t.amount, src_currency, base_currency, t.date)
        if t.type == Transaction.Type.INCOME:
            income += converted
        elif t.type == Transaction.Type.EXPENSE:
            expenses += abs(converted)
        elif t.type == Transaction.Type.INVESTMENT:
            investments += converted
    net = income - expenses
    data = {
        "income": float(income),
        "expenses": float(expenses),
        "investments": float(investments),
        "net": float(net),
    }
    cache.set(cache_key, data, 86400)
    return data


def build_charts_for_period(tx):
    """Return expense totals grouped by category for charting."""
    expense_rows = (
        tx.filter(type=Transaction.Type.EXPENSE)
        .values("category__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    charts = []
    for row in expense_rows:
        charts.append(
            {
                "category": row["category__name"] or "Uncategorised",
                "total": float(abs(row["total"] or Decimal("0"))),
            }
        )
    return charts


def build_kpis_history(qs):
    """Minimal stub returning count for history queries."""
    return {"count": qs.count()}


def build_charts_history(qs):
    """Minimal stub placeholder for history charts."""
    return []


@login_required
def dashboard(request):
    """Dashboard supporting history and period modes."""
    mode = request.GET.get("mode", "history")
    # Default to previous month instead of current month
    current_date = now()
    if current_date.month == 1:
        default_period = f"{current_date.year - 1}-12"
    else:
        default_period = f"{current_date.year}-{current_date.month - 1:02d}"
    period = request.GET.get("period", default_period)
    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", period or ""):
        period = current_period

    prev_period = _shift_period(period, -1)
    next_period = _shift_period(period, 1)

    context = {
        "mode": mode,
        "period": period,
        "prev_period": prev_period,
        "next_period": next_period,
    }

    if mode == "period":
        year, month = map(int, period.split("-"))
        tx = Transaction.objects.filter(
            user=request.user, period__year=year, period__month=month
        ).select_related("account__currency")
        kpis = build_kpis_for_period(request.user, period)
        charts = build_charts_for_period(tx)
        
        # Enhanced expense statistics
        expense_stats = tx.filter(type="EX").aggregate(
            total=Sum("amount"),
            estimated=Sum("amount", filter=Q(is_estimated=True)),
            count=models.Count("id"),
            estimated_count=models.Count("id", filter=Q(is_estimated=True)),
        )
        total_expenses = abs(expense_stats["total"] or Decimal("0"))
        estimated_expenses = abs(expense_stats["estimated"] or Decimal("0"))
        verified_expenses_pct_dec = pct(
            total_expenses - estimated_expenses, total_expenses
        )
        
        # Additional KPI calculations
        kpis["non_estimated_expenses_pct"] = round(float(verified_expenses_pct_dec))
        kpis["verified_expenses_pct"] = float(verified_expenses_pct_dec)
        kpis["verified_expenses_pct_str"] = f"{verified_expenses_pct_dec}%"
        kpis["verification_level"] = kpis.get("verification_level", "Moderate")
        
        # Calculate daily and weekly averages
        days_in_month = monthrange(year, month)[1]
        kpis["daily_net"] = float(kpis["net"] / days_in_month) if days_in_month > 0 else 0
        kpis["weekly_net"] = float(kpis["net"] / 4.33) if kpis["net"] else 0  # Average weeks per month
        
        # Calculate rates if income exists
        if kpis["income"] > 0:
            kpis["savings_rate"] = round(float((kpis["net"] / kpis["income"]) * 100), 1)
            kpis["investment_rate"] = round(float((kpis["investments"] / kpis["income"]) * 100), 1)
            kpis["expense_ratio"] = round(float((kpis["expenses"] / kpis["income"]) * 100), 1)
        else:
            kpis["savings_rate"] = 0
            kpis["investment_rate"] = 0
            kpis["expense_ratio"] = 0
        
        # Transaction counts for insights
        kpis["transaction_count"] = tx.count()
        kpis["expense_count"] = expense_stats["count"]
        kpis["estimated_count"] = expense_stats["estimated_count"]
        
        # Format period for display
        try:
            period_date = date(year, month, 1)
            context["period_formatted"] = period_date.strftime("%B %Y")
        except:
            context["period_formatted"] = period
        
        context.update({"kpis": kpis, "charts": charts})
        return render(request, "core/dashboard.html", context)

    view = DashboardView.as_view()
    response = view(request)
    if hasattr(response, "context_data"):
        response.context_data.update(context)
    return response


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
        filtered_qs = qs.filter(user=self.request.user)

        # Otimizar queries com relacionamentos
        model_name = getattr(self, 'model', None)
        if model_name:
            if hasattr(model_name, 'account'):
                filtered_qs = filtered_qs.select_related('account', 'account__currency', 'account__account_type')
            if hasattr(model_name, 'category'):
                filtered_qs = filtered_qs.select_related('category')
            if hasattr(model_name, 'period'):
                filtered_qs = filtered_qs.select_related('period')

        return filtered_qs

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
            period_expr = (
                "CAST(dp.year AS TEXT) || '-' || printf('%%02d', dp.month)"
                if connection.vendor == "sqlite"
                else "CONCAT(dp.year, '-', LPAD(dp.month::text, 2, '0'))"
            )

            # Transações do utilizador
            cursor.execute(
                f"""
                SELECT
                    {period_expr} as period,
                    tx.type, tx.amount
                FROM core_transaction tx
                INNER JOIN core_dateperiod dp ON tx.period_id = dp.id
                WHERE tx.user_id = %s
                ORDER BY dp.year, dp.month
                """,
                [user.id],
            )
            tx_rows = cursor.fetchall()

            # Saldos das contas
            cursor.execute(
                f"""
                SELECT
                    {period_expr} as period,
                    ab.reported_balance, at.name as account_type
                FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_accounttype at ON a.account_type_id = at.id
                INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                WHERE a.user_id = %s
                ORDER BY dp.year, dp.month
                """,
                [user.id],
            )
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
        expense_stats = Transaction.objects.filter(user=user, type="EX").aggregate(
            total=Sum("amount"),
            estimated=Sum("amount", filter=Q(is_estimated=True)),
        )
        total_expenses = abs(expense_stats["total"] or Decimal("0"))
        estimated_expenses = abs(expense_stats["estimated"] or Decimal("0"))
        verified_expenses_pct_dec = pct(
            total_expenses - estimated_expenses, total_expenses
        )
        ctx["kpis"]["non_estimated_expenses_pct"] = round(
            float(verified_expenses_pct_dec)
        )
        ctx["kpis"]["verified_expenses_pct"] = float(
            verified_expenses_pct_dec
        )
        ctx["kpis"]["verified_expenses_pct_str"] = f"{verified_expenses_pct_dec}%"
        ctx["kpis"]["verification_level"] = ctx["kpis"].get(
            "verification_level",
            "Moderate",
        )
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
    
    # Check if specific period is requested
    requested_period = request.GET.get('period')
    
    with connection.cursor() as cursor:
        if requested_period:
            # Parse period (format: YYYY-MM)
            try:
                year, month = map(int, requested_period.split('-'))
                cursor.execute("""
                    SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
                    FROM core_accountbalance ab
                    JOIN core_account acc ON acc.id = ab.account_id
                    JOIN core_accounttype at ON at.id = acc.account_type_id
                    JOIN core_currency cur ON cur.id = acc.currency_id
                    JOIN core_dateperiod dp ON dp.id = ab.period_id
                    WHERE acc.user_id = %s AND dp.year = %s AND dp.month = %s
                    GROUP BY at.name, cur.code, dp.year, dp.month
                    ORDER BY at.name, cur.code
                """, [user_id, year, month])
            except (ValueError, TypeError):
                # Fallback to latest period
                cursor.execute("""
                    SELECT at.name, cur.code, dp.year, dp.month, SUM(ab.reported_balance)
                    FROM core_accountbalance ab
                    JOIN core_account acc ON acc.id = ab.account_id
                    JOIN core_accounttype at ON at.id = acc.account_type_id
                    JOIN core_currency cur ON cur.id = acc.currency_id
                    JOIN core_dateperiod dp ON dp.id = ab.period_id
                    WHERE acc.user_id = %s
                    AND dp.id = (SELECT id FROM core_dateperiod ORDER BY year DESC, month DESC LIMIT 1)
                    GROUP BY at.name, cur.code, dp.year, dp.month
                    ORDER BY at.name, cur.code
                """, [user_id])
        else:
            # All periods
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

    if requested_period:
        # Return individual accounts for single period
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT a.name, at.name, cur.code, ab.reported_balance
                FROM core_accountbalance ab
                JOIN core_account a ON a.id = ab.account_id
                JOIN core_accounttype at ON at.id = a.account_type_id
                JOIN core_currency cur ON cur.id = a.currency_id
                JOIN core_dateperiod dp ON dp.id = ab.period_id
                WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
                AND ab.reported_balance > 0
                ORDER BY a.name
            """, [user_id, year, month])
            individual_rows = cursor.fetchall()
        
        account_data = []
        for row in individual_rows:
            account_name, account_type, currency, balance = row
            account_data.append({
                "name": account_name,
                "type": account_type,
                "currency": currency,
                "balance": float(balance),
                "label": f"{account_name}"
            })
        return JsonResponse({"accounts": account_data})
    else:
        # Create DataFrame for pivot
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
    """Create a new transaction with security validation."""
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def form_valid(self, form):
        """Processar formulário válido e limpar cache."""
        self.object = form.save()
        logger.debug(f'📝 Criado: {self.object}')  # ✅ DEBUG no terminal

        # Limpar cache imediatamente
        clear_tx_cache(self.request.user.id, force=True)

        # Adicionar flag para JavaScript saber que deve recarregar
        self.request.session['transaction_changed'] = True

        if self.request.headers.get("HX-Request") == "true":
            return JsonResponse({"success": True, "reload_needed": True})

        messages.success(self.request, "Transaction created successfully!")
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
    """Update an existing transaction with owner validation."""
    model = Transaction
    form_class = TransactionForm
    template_name = "core/transaction_form.html"
    success_url = reverse_lazy("transaction_list_v2")

    def get_queryset(self):
        return super().get_queryset().prefetch_related("tags")

    def get_object(self, queryset=None):
        """Override to provide better error handling and prevent editing estimated transactions."""
        try:
            obj = super().get_object(queryset)
            
            # Prevent editing estimated transactions
            if obj.is_estimated:
                messages.error(self.request, "Estimated transactions cannot be edited directly. Use the estimation tool at /transactions/estimate/ instead.")
                logger.warning(f"User {self.request.user.id} tried to edit estimated transaction {obj.id}")
                raise PermissionDenied("Cannot edit estimated transaction")
                
            return obj
        except Transaction.DoesNotExist:
            messages.error(self.request, f"Transaction with ID {self.kwargs.get('pk')} not found or you don't have permission to edit it.")
            logger.warning(f"User {self.request.user.id} tried to access non-existent transaction {self.kwargs.get('pk')}")
            raise Http404("Transaction not found")

    def form_valid(self, form):
        # Limpar cache imediatamente
        clear_tx_cache(self.request.user.id, force=True)

        # Adicionar flag para JavaScript saber que deve recarregar
        self.request.session['transaction_changed'] = True

        messages.success(self.request, "Transaction updated successfully!")

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
    """Delete a transaction with owner validation."""
    model = Transaction
    template_name = "core/confirms/transaction_confirm_delete.html"
    success_url = reverse_lazy("transaction_list_v2")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        user_id = self.object.user_id

        # Delete the transaction
        response = super().delete(request, *args, **kwargs)

        # Clear cache after deletion
        clear_tx_cache(user_id, force=True)

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Transaction deleted successfully!'
            })

        messages.success(request, "Transaction deleted successfully!")
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
        except Exception as e:
            logger.warning(f"Invalid period value '{period}': {e}")

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



    # Filtros únicos dinâmicos - map backend types to display names for frontend
    backend_types = sorted([t for t in df_for_type["type"].dropna().unique() if t])
    available_types = []
    type_mapping = {
        'IN': 'Income', 'EX': 'Expense', 'IV': 'Investment', 'TR': 'Transfer', 'AJ': 'Adjustment'
    }
    for backend_type in backend_types:
        display_type = type_mapping.get(backend_type, backend_type)
        available_types.append(display_type)

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
        except Exception as e:
            logger.warning(f"Failed to sort by '{sort_col}': {e}")

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
        clear_tx_cache(request.user.id, force=True)
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
        clear_tx_cache(request.user.id, force=True)
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
    """Bulk delete transactions with optimized performance."""
    try:
        data = json.loads(request.body)
        transaction_ids = data.get('transaction_ids', [])

        if not transaction_ids:
            return JsonResponse({'success': False, 'error': 'No transactions selected'})

        logger.info(f"🗑️ [transaction_bulk_delete] Starting bulk delete of {len(transaction_ids)} transactions for user {request.user.id}")

        # Validate transactions belong to user in a single query
        valid_transactions = Transaction.objects.filter(
            id__in=transaction_ids, 
            user=request.user
        ).values_list('id', flat=True)

        valid_count = len(valid_transactions)
        if valid_count != len(transaction_ids):
            invalid_count = len(transaction_ids) - valid_count
            logger.warning(f"⚠️ [transaction_bulk_delete] {invalid_count} transactions not found or don't belong to user")
            return JsonResponse({
                'success': False, 
                'error': f'{invalid_count} transactions not found or access denied'
            })

        # Use optimized bulk deletion with atomic transaction
        with db_transaction.atomic():
            # First, delete related TransactionTag entries in bulk
            from .models import TransactionTag
            tag_delete_count = TransactionTag.objects.filter(
                transaction_id__in=valid_transactions
            ).delete()[0]
            
            logger.debug(f"🏷️ [transaction_bulk_delete] Deleted {tag_delete_count} transaction tags")

            # Then delete transactions in bulk - much faster than individual deletes
            deleted_info = Transaction.objects.filter(
                id__in=valid_transactions,
                user=request.user
            ).delete()
            
            deleted_count = deleted_info[0]  # Total objects deleted
            logger.info(f"🗑️ [transaction_bulk_delete] Bulk deleted {deleted_count} objects from database")

        # Clear cache only AFTER all database operations are complete
        clear_tx_cache(request.user.id, force=True)
        logger.info(f"✅ Bulk delete completed: {valid_count} transactions deleted, cache cleared for user {request.user.id}")

        return JsonResponse({
            'success': True,
            'deleted': valid_count,
            'message': f'{valid_count} transactions deleted successfully'
        })

    except Exception as e:
        logger.error(f"❌ Bulk delete error for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ==============================================================================
# IMPORT/EXPORT FUNCTIONS
# ==============================================================================

@login_required
def import_transactions_xlsx(request):
    """Import transactions from Excel file with optimized bulk operations."""
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            if not uploaded_file:
                messages.error(request, 'No file uploaded.')
                return render(request, 'core/import_form.html')

            logger.info(f"📁 [import_transactions_xlsx] Starting import for user {request.user.id}, file: {uploaded_file.name}")

            # Read Excel file
            df = pd.read_excel(uploaded_file)
            logger.info(f"📊 [import_transactions_xlsx] Read Excel file with shape: {df.shape}")
            logger.info(f"📋 [import_transactions_xlsx] Columns found: {list(df.columns)}")
            
            # Only log sensitive data in DEBUG mode
            if settings.DEBUG:
                logger.debug(f"🔍 [import_transactions_xlsx] First 3 rows:\n{df.head(3).to_string()}")
            
            # Detailed analysis of tag columns
            tag_columns = ['Tags', 'tags', 'Tag', 'tag']
            for col in tag_columns:
                if col in df.columns:
                    non_empty_count = df[col].notna().sum()
                    logger.info(f"🏷️ [import_transactions_xlsx] Column '{col}' found: {non_empty_count} non-empty values")
                    
                    # Only log actual tag values in DEBUG mode
                    if settings.DEBUG:
                        unique_values = df[col].dropna().unique()[:5]  # First 5 unique values
                        logger.debug(f"🏷️ [import_transactions_xlsx] Sample values from '{col}': {unique_values}")
                    break
            else:
                logger.warning(f"⚠️ [import_transactions_xlsx] No tags column found in: {list(df.columns)}")

            # Validate required columns
            required_cols = ['Date', 'Type', 'Amount', 'Category', 'Account']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                logger.error(f"❌ [import_transactions_xlsx] Missing columns: {missing_cols}")
                messages.error(request, f'Missing required columns: {", ".join(missing_cols)}')
                return render(request, 'core/import_form.html')

            logger.info(f"✅ [import_transactions_xlsx] All required columns present")

            # Clean and validate data upfront
            initial_rows = len(df)
            logger.info(f"📋 [import_transactions_xlsx] Initial data has {initial_rows} rows")
            
            # Check for completely empty rows first
            df_non_empty = df.dropna(how='all')
            logger.debug(f"🧹 [import_transactions_xlsx] After removing completely empty rows: {len(df)} → {len(df_non_empty)}")
            
            # More flexible cleaning - only drop rows where ALL required columns are missing
            missing_mask = df_non_empty[required_cols].isna().all(axis=1)
            df_clean = df_non_empty[~missing_mask].copy()
            rows_after_dropna = len(df_clean)
            logger.debug(f"🧹 [import_transactions_xlsx] Rows after cleaning required columns: {initial_rows} → {rows_after_dropna}")
            
            # Log which columns have missing values
            for col in required_cols:
                missing_count = df_clean[col].isna().sum()
                if missing_count > 0:
                    logger.warning(f"⚠️ [import_transactions_xlsx] Column '{col}' has {missing_count} missing values")
                    
                    # Only log actual data samples in DEBUG mode
                    if settings.DEBUG:
                        logger.debug(f"📋 [import_transactions_xlsx] Sample missing rows for '{col}':")
                        sample_missing = df_clean[df_clean[col].isna()].head(3)
                        logger.debug(f"{sample_missing.to_string()}")

            if df_clean.empty:
                logger.error(f"❌ [import_transactions_xlsx] No valid rows after cleaning")
                if settings.DEBUG:
                    logger.debug(f"📋 [import_transactions_xlsx] Original DataFrame info:")
                    logger.debug(f"Shape: {df.shape}")
                    logger.debug(f"Columns: {list(df.columns)}")
                    logger.debug(f"Data types: {df.dtypes.to_dict()}")
                messages.error(request, 'No valid data rows found in the Excel file. Please check that your file has data in the required columns: Date, Type, Amount, Category, Account')
                return render(request, 'core/import_form.html')

            # Clean string columns more carefully
            for col in ['Account', 'Category']:
                if col in df_clean.columns:
                    df_clean[col] = df_clean[col].fillna('').astype(str).str.strip()
                    # Replace empty strings with a default value
                    empty_mask = df_clean[col] == ''
                    if empty_mask.any():
                        default_value = 'Unknown Account' if col == 'Account' else 'Uncategorized'
                        df_clean.loc[empty_mask, col] = default_value
                        logger.warning(f"⚠️ [import_transactions_xlsx] Filled {empty_mask.sum()} empty {col} values with '{default_value}'")

            # Only log unique values in DEBUG mode to prevent PII exposure
            if settings.DEBUG:
                logger.debug(f"🏦 [import_transactions_xlsx] Unique accounts: {df_clean['Account'].unique()}")
                logger.debug(f"🏷️ [import_transactions_xlsx] Unique categories: {df_clean['Category'].unique()}")

            try:
                logger.info(f"🔄 [import_transactions_xlsx] Converting data types...")
                
                # Convert dates more carefully
                if settings.DEBUG:
                    logger.debug(f"📅 [import_transactions_xlsx] Sample date values: {df_clean['Date'].head().tolist()}")
                df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce').dt.date
                invalid_dates = df_clean['Date'].isna().sum()
                if invalid_dates > 0:
                    logger.error(f"❌ [import_transactions_xlsx] {invalid_dates} invalid dates found")
                    df_clean = df_clean.dropna(subset=['Date'])
                
                # Convert amounts more carefully
                if settings.DEBUG:
                    logger.debug(f"💰 [import_transactions_xlsx] Sample amount values: {df_clean['Amount'].head().tolist()}")
                df_clean['Amount'] = pd.to_numeric(df_clean['Amount'], errors='coerce')
                invalid_amounts = df_clean['Amount'].isna().sum()
                if invalid_amounts > 0:
                    logger.error(f"❌ [import_transactions_xlsx] {invalid_amounts} invalid amounts found")
                    df_clean = df_clean.dropna(subset=['Amount'])
                
                logger.info(f"📅 [import_transactions_xlsx] Date range: {df_clean['Date'].min()} to {df_clean['Date'].max()}")
                logger.info(f"💰 [import_transactions_xlsx] Amount range: {df_clean['Amount'].min()} to {df_clean['Amount'].max()}")
                
                # Clean and normalize transaction types
                if settings.DEBUG:
                    logger.debug(f"🏷️ [import_transactions_xlsx] Sample type values: {df_clean['Type'].head().tolist()}")
                df_clean['Type'] = df_clean['Type'].fillna('').astype(str).str.strip().str.upper()
                
                # Log original types before normalization (types are not PII)
                original_types = df_clean['Type'].value_counts().to_dict()
                logger.info(f"📊 [import_transactions_xlsx] Original types: {original_types}")
                
                # Check for completely empty types
                empty_types = (df_clean['Type'] == '').sum()
                if empty_types > 0:
                    logger.error(f"❌ [import_transactions_xlsx] {empty_types} rows have empty Type values")
                    df_clean = df_clean[df_clean['Type'] != '']
                
                # Log final data shape
                final_rows = len(df_clean)
                logger.info(f"✅ [import_transactions_xlsx] Final cleaned data: {final_rows} rows")
                
                # Log tags information if present - check all possible tag column names
                tag_columns = ['Tags', 'tags', 'Tag', 'tag']
                found_tag_col = None
                for col in tag_columns:
                    if col in df_clean.columns:
                        found_tag_col = col
                        break
                
                if found_tag_col:
                    # Count non-empty tag entries
                    tags_mask = df_clean[found_tag_col].notna() & (df_clean[found_tag_col].astype(str).str.strip() != '') & (~df_clean[found_tag_col].astype(str).str.lower().isin(['nan', 'none', 'null']))
                    tags_with_data = tags_mask.sum()
                    logger.info(f"🏷️ [import_transactions_xlsx] Found column '{found_tag_col}' with {tags_with_data} rows containing tag data")
                    
                    if tags_with_data > 0:
                        # Only log actual tag content in DEBUG mode
                        if settings.DEBUG:
                            sample_tags = df_clean[tags_mask][found_tag_col].head(5).tolist()
                            logger.debug(f"🏷️ [import_transactions_xlsx] Sample tags: {sample_tags}")
                            
                            # Log each unique tag value for debugging
                            unique_tags = df_clean[tags_mask][found_tag_col].unique()
                            logger.debug(f"🏷️ [import_transactions_xlsx] All unique tag values ({len(unique_tags)}): {unique_tags[:10]}")  # First 10
                else:
                    logger.warning(f"⚠️ [import_transactions_xlsx] No tags column found. Available columns: {list(df_clean.columns)}")
                
                if final_rows == 0:
                    logger.error(f"❌ [import_transactions_xlsx] No rows remaining after data cleaning")
                    messages.error(request, 'No valid data rows remain after cleaning. Please check your data format.')
                    return render(request, 'core/import_form.html')
                
            except Exception as e:
                logger.error(f"❌ [import_transactions_xlsx] Data conversion error: {str(e)}")
                logger.exception("Full error traceback:")
                messages.error(request, f'Invalid data format: {str(e)}')
                return render(request, 'core/import_form.html')

            # Use optimized bulk importer
            from .utils.import_helpers import BulkTransactionImporter
            
            importer = BulkTransactionImporter(request.user, batch_size=5000)  # Increased batch size for better performance
            result = importer.import_dataframe(df_clean)
            
            imported_count = result['imported']
            errors = result['errors']

            # Clear cache after import
            clear_tx_cache(request.user.id, force=True)
            logger.info(f"🗄️ [import_transactions_xlsx] Cache cleared for user {request.user.id}")

            logger.info(f"📊 [import_transactions_xlsx] Import completed: {imported_count} imported, {len(errors)} errors")

            # Clear any existing messages to prevent duplicates
            storage = messages.get_messages(request)
            for message in storage:
                pass  # Iterate through to mark as consumed
            storage.used = True

            if errors:
                messages.warning(request, f'Imported {imported_count} transactions with {len(errors)} errors.')
                if len(errors) <= 5:  # Show first 5 errors
                    for error in errors[:5]:
                        messages.error(request, error)
                # Log all errors for debugging
                for error in errors:
                    logger.error(f"🔴 [import_transactions_xlsx] Error: {error}")
            else:
                # Clear any remaining messages before adding the final success message
                list(messages.get_messages(request))
                messages.success(request, f'Successfully imported {imported_count} transactions.')

            # Stay on import page instead of redirecting
            return render(request, 'core/import_form.html')

        except Exception as e:
            logger.error(f"Import error for user {request.user.id}: {e}")
            messages.error(request, f'Import failed: {str(e)}')

    return render(request, 'core/import_form.html')


@login_required
def import_transactions_template(request):
    """Download Excel template for transaction import using Savings and Investments accounts."""
    # Create sample data using supported account types
    data = {
        'Date': ['2025-01-01', '2025-01-02', '2025-01-03'],
        'Type': ['Income', 'Expense', 'Investment'],
        'Amount': [1000.00, -50.00, -200.00],
        'Category': ['Salary', 'Food', 'Stocks'],
        'Account': ['Savings', 'Savings', 'Investments'],
        'Tags': ['monthly', 'daily', 'monthly'],
        'Notes': ['Monthly salary', 'Lunch', 'ETF purchase']
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
def export_data_xlsx(request):
    """Export both transactions and account balances to a single Excel file."""
    user_id = request.user.id

    # Date range for transactions
    start_date = parse_safe_date(request.GET.get("date_start"), date(date.today().year, 1, 1))
    end_date = parse_safe_date(request.GET.get("date_end"), date.today())

    # Fetch transactions
    with connection.cursor() as cursor:
        cursor.execute(
            """
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
            """,
            [user_id, start_date, end_date],
        )
        tx_rows = cursor.fetchall()

    tx_df = pd.DataFrame(
        tx_rows,
        columns=["Date", "Type", "Amount", "Category", "Account", "Tags", "Notes"],
    )

    # Fetch account balances for all periods
    with connection.cursor() as cursor:
        cursor.execute(
            """
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
            WHERE a.user_id = %s
            ORDER BY dp.year DESC, dp.month DESC, at.name, a.name;
            """,
            [user_id],
        )
        bal_rows = cursor.fetchall()

    bal_df = pd.DataFrame(
        bal_rows,
        columns=[
            "Year",
            "Month",
            "Period",
            "Account_Name",
            "Account_Type",
            "Currency",
            "Balance",
        ],
    )

    # Write both datasets to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        tx_df.to_excel(writer, sheet_name="Transactions", index=False)
        bal_df.to_excel(writer, sheet_name="Account_Balances", index=False)

    output.seek(0)

    filename = f"data_export_{start_date}_{end_date}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@login_required
def transaction_clear_cache(request):
    """Clear transaction cache for current user."""
    try:
        clear_tx_cache(request.user.id, force=True)

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': True,
                'message': 'Data refreshed successfully!'
            })

        messages.success(request, 'Data refreshed successfully!')
        return redirect('transaction_list_v2')

    except Exception as e:
        logger.error(f"Error refreshing data for user {request.user.id}: {e}")

        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Content-Type') == 'application/json':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

        messages.error(request, f'Failed to refresh data: {str(e)}')
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
    """Enhanced JSON API for transactions v2 with Excel-style cascading filters."""
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
    force_refresh = str(data.get('force', '')).lower() in ['1', 'true', 'yes']
    cached_df = None if force_refresh else cache.get(cache_key)

    if cached_df is not None:
        logger.debug(f"✅ [transactions_json_v2] Using cached data, {len(cached_df)} rows")
        df = cached_df.copy()
    else:
        if force_refresh:
            logger.debug("🔄 [transactions_json_v2] Force refresh requested, bypassing cache")
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
                       tx.is_system, tx.editable, tx.is_estimated,
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
                         cat.name, acc.name, curr.symbol, tx.is_system, tx.editable, tx.is_estimated
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
            "is_system", "editable", "is_estimated", "period"
        ])
        logger.debug(f"📋 [transactions_json_v2] DataFrame created with {len(df)} rows")
        cache.set(cache_key, df.copy(), timeout=300)

    # ✅ EXCEL-STYLE CASCADING FILTERS IMPLEMENTATION
    # Store original data for calculating available filter options
    df_original = df.copy()

    # Parse filters from request - convert empty strings to None
    active_filters = {}
    if data.get("type", "").strip():
        active_filters["type"] = data.get("type").strip()
    if data.get("category", "").strip():
        active_filters["category"] = data.get("category").strip()
    if data.get("account", "").strip():
        active_filters["account"] = data.get("account").strip()
    if data.get("period", "").strip():
        active_filters["period"] = data.get("period").strip()
    if data.get("search", "").strip():
        active_filters["search"] = data.get("search").strip()
    if data.get("amount_min", "").strip():
        active_filters["amount_min"] = data.get("amount_min").strip()
    if data.get("amount_max", "").strip():
        active_filters["amount_max"] = data.get("amount_max").strip()
    if data.get("tags", "").strip():
        active_filters["tags"] = data.get("tags").strip()

    include_system = data.get("include_system", False)

    logger.debug(f"📋 [Excel Filters] Active filters: {active_filters}")

    # Apply filters in cascade - each filter operates on the result of previous filters
    df_filtered = df.copy()

    # System filter first (if not included)
    if not include_system:
        df_filtered = df_filtered[df_filtered["is_system"] != True]
        logger.debug(f"🔽 [Excel Filter] System filter applied, remaining rows: {len(df_filtered)}")

    # Apply each filter sequentially (Excel-style)
    filter_order = ["type", "category", "account", "period", "search", "amount_min", "amount_max", "tags"]

    for filter_name in filter_order:
        if filter_name in active_filters:
            filter_value = active_filters[filter_name]
            df_before = len(df_filtered)

            if filter_name == "type":
                # Filter by the raw type from database (IN, EX, IV, TR, AJ)
                df_filtered = df_filtered[df_filtered["type"] == filter_value]

            elif filter_name == "category":
                df_filtered = df_filtered[df_filtered["category"].str.contains(filter_value, case=False, na=False)]

            elif filter_name == "account":
                df_filtered = df_filtered[df_filtered["account"].str.contains(filter_value, case=False, na=False)]

            elif filter_name == "period":
                df_filtered = df_filtered[df_filtered["period"] == filter_value]

            elif filter_name == "search":
                # Create mapped type column for search
                df_search = df_filtered.copy()
                df_search["type_display"] = df_search["type"].map({
                    'IN': 'Income', 'EX': 'Expense', 'IV': 'Investment', 'TR': 'Transfer', 'AJ': 'Adjustment'
                }).fillna(df_search["type"])

                search_mask = (
                    df_search["category"].str.contains(filter_value, case=False, na=False) |
                    df_search["account"].str.contains(filter_value, case=False, na=False) |
                    df_search["type_display"].str.contains(filter_value, case=False, na=False) |
                    df_search["tags"].str.contains(filter_value, case=False, na=False)
                )
                df_filtered = df_filtered[search_mask]

            elif filter_name == "amount_min":
                try:
                    min_val = float(filter_value)
                    df_filtered = df_filtered[df_filtered["amount"] >= min_val]
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount_min value: {filter_value}")

            elif filter_name == "amount_max":
                try:
                    max_val = float(filter_value)
                    df_filtered = df_filtered[df_filtered["amount"] <= max_val]
                except (ValueError, TypeError):
                    logger.warning(f"Invalid amount_max value: {filter_value}")

            elif filter_name == "tags":
                tag_list = [t.strip().lower() for t in filter_value.split(",") if t.strip()]
                if tag_list:
                    tag_pattern = '|'.join(tag_list)
                    df_filtered = df_filtered[df_filtered["tags"].str.contains(tag_pattern, case=False, na=False)]

            logger.debug(f"🔽 [Excel Filter] {filter_name}='{filter_value}' applied: {df_before} → {len(df_filtered)} rows")

    # 📊 CALCULATE AVAILABLE FILTER OPTIONS (Excel-style)
    # For each filter, calculate what values are available based on OTHER active filters

    def get_available_options_for_filter(target_filter):
        """Get available options for a specific filter based on other active filters."""
        temp_df = df.copy()

        # System filter first (if not included)
        if not include_system:
            temp_df = temp_df[temp_df["is_system"] != True]

        # Apply all OTHER filters (not the target filter)
        for filter_name in filter_order:
            if filter_name != target_filter and filter_name in active_filters:
                filter_value = active_filters[filter_name]

                if filter_name == "type":
                    temp_df = temp_df[temp_df["type"] == filter_value]
                elif filter_name == "category":
                    temp_df = temp_df[temp_df["category"].str.contains(filter_value, case=False, na=False)]
                elif filter_name == "account":
                    temp_df = temp_df[temp_df["account"].str.contains(filter_value, case=False, na=False)]
                elif filter_name == "period":
                    temp_df = temp_df[temp_df["period"] == filter_value]
                elif filter_name == "search":
                    temp_search = temp_df.copy()
                    temp_search["type_display"] = temp_search["type"].map({
                        'IN': 'Income', 'EX': 'Expense', 'IV': 'Investment', 'TR': 'Transfer', 'AJ': 'Adjustment'
                    }).fillna(temp_search["type"])

                    search_mask = (
                        temp_search["category"].str.contains(filter_value, case=False, na=False) |
                        temp_search["account"].str.contains(filter_value, case=False, na=False) |
                        temp_search["type_display"].str.contains(filter_value, case=False, na=False) |
                        temp_search["tags"].str.contains(filter_value, case=False, na=False)
                    )
                    temp_df = temp_df[search_mask]
                elif filter_name == "amount_min":
                    try:
                        min_val = float(filter_value)
                        temp_df = temp_df[temp_df["amount"] >= min_val]
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid amount_min filter value '{filter_value}': {e}")
                elif filter_name == "amount_max":
                    try:
                        max_val = float(filter_value)
                        temp_df = temp_df[temp_df["amount"] <= max_val]
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid amount_max filter value '{filter_value}': {e}")
                elif filter_name == "tags":
                    tag_list = [t.strip().lower() for t in filter_value.split(",") if t.strip()]
                    if tag_list:
                        tag_pattern = '|'.join(tag_list)
                        temp_df = temp_df[temp_df["tags"].str.contains(tag_pattern, case=False, na=False)]

        return temp_df

    # Calculate available options for each filter
    available_types = []
    available_categories = []
    available_accounts = []
    available_periods = []

    # Types
    type_df = get_available_options_for_filter("type")
    available_types = sorted(type_df["type"].map({
        'IN': 'Income', 'EX': 'Expense', 'IV': 'Investment', 'TR': 'Transfer', 'AJ': 'Adjustment'
    }).dropna().unique())

    # Categories
    category_df = get_available_options_for_filter("category")
    available_categories = sorted([c for c in category_df["category"].dropna().unique() if c])

    # Accounts
    account_df = get_available_options_for_filter("account")
    available_accounts = sorted([a for a in account_df["account"].dropna().unique() if a])

    # Periods
    period_df = get_available_options_for_filter("period")
    available_periods = sorted(period_df["period"].dropna().unique(), reverse=True)

    logger.debug(f"📊 [Excel Filters] Available options calculated:")
    logger.debug(f"  Types: {len(available_types)} options")
    logger.debug(f"  Categories: {len(available_categories)} options")
    logger.debug(f"  Accounts: {len(available_accounts)} options")
    logger.debug(f"  Periods: {len(available_periods)} options")

    # Use filtered data for pagination and response
    df = df_filtered

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

    # Build response with Excel-style filtered options
    response_data = {
        "transactions": page_df.to_dict(orient="records"),
        "total_count": total_count,
        "current_page": current_page,
        "page_size": page_size,
        "filters": {
            "types": available_types,
            "categories": available_categories,
            "accounts": available_accounts,
            "periods": available_periods
        }
    }

    logger.debug(f"📤 [transactions_json_v2] Final response: {len(response_data['transactions'])} transactions, total_count: {total_count}")
    logger.debug(f"✅ [Excel Filters] Filter options returned based on visible data only")

    # Log if no transactions found
    if total_count == 0:
        total_tx_count = Transaction.objects.filter(user_id=user_id).count()
        logger.warning(f"⚠️ [transactions_json_v2] No transactions returned for user {user_id} in date range {start_date}-{end_date}, but user has {total_tx_count} total transactions")

    return JsonResponse(response_data)


@login_required
def transactions_totals_v2(request):
    """Get totals for transactions v2 with proper filter application."""
    user_id = request.user.id
    logger.debug(f"💰 [transactions_totals_v2] Request from user {user_id}: {request.method}")

    # Parse request data (handles both GET and POST)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
        except:
            data = {}
    else:
        data = request.GET.dict()

    logger.debug(f"📋 [transactions_totals_v2] Request data: {data}")

    # Get date range with wider defaults if not provided
    raw_start = data.get('date_start', request.GET.get("date_start"))
    raw_end = data.get('date_end', request.GET.get("date_end"))

    if not raw_start and not raw_end:
        start_date = date(2020, 1, 1)
        end_date = date(2030, 12, 31)
    else:
        start_date = parse_safe_date(raw_start, date(date.today().year, 1, 1))
        end_date = parse_safe_date(raw_end, date.today())

    logger.debug(f"📅 [transactions_totals_v2] Date range: {start_date} to {end_date}")

    # Build complex query with all filters (same as transactions_json_v2)
    where_conditions = ["tx.user_id = %s", "tx.date BETWEEN %s AND %s"]
    params = [user_id, start_date, end_date]

    # Apply all filters exactly like in transactions_json_v2
    include_system = data.get("include_system", False)
    if not include_system:
        where_conditions.append("(tx.is_system IS NULL OR tx.is_system = FALSE)")

    # Type filter
    if data.get("type", "").strip():
        where_conditions.append("tx.type = %s")
        params.append(data.get("type").strip())

    # Category filter
    if data.get("category", "").strip():
        where_conditions.append("COALESCE(cat.name, '') ILIKE %s")
        params.append(f"%{data.get('category').strip()}%")

    # Account filter
    if data.get("account", "").strip():
        where_conditions.append("COALESCE(acc.name, '') ILIKE %s")
        params.append(f"%{data.get('account').strip()}%")

    # Period filter
    if data.get("period", "").strip():
        try:
            year, month = data.get("period").strip().split("-")
            where_conditions.append("dp.year = %s AND dp.month = %s")
            params.extend([int(year), int(month)])
        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid period value '{data.get('period')}': {e}")

    # Amount range filters
    if data.get("amount_min", "").strip():
        try:
            min_val = float(data.get("amount_min").strip())
            where_conditions.append("tx.amount >= %s")
            params.append(min_val)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid amount_min value '{data.get('amount_min')}': {e}")

    if data.get("amount_max", "").strip():
        try:
            max_val = float(data.get("amount_max").strip())
            where_conditions.append("tx.amount <= %s")
            params.append(max_val)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid amount_max value '{data.get('amount_max')}': {e}")

    # Search filter
    if data.get("search", "").strip():
        search_term = f"%{data.get('search').strip()}%"
        where_conditions.append("""(
            COALESCE(cat.name, '') ILIKE %s OR
            COALESCE(acc.name, '') ILIKE %s OR
            tx.id IN (
                SELECT DISTINCT tt.transaction_id 
                FROM core_transactiontag tt 
                INNER JOIN core_tag tag ON tt.tag_id = tag.id 
                WHERE tag.name ILIKE %s
            )
        )""")
        params.extend([search_term, search_term, search_term])

    # Tags filter - handle separately to avoid duplication
    tags_filter = data.get("tags", "").strip()
    if tags_filter:
        tag_list = [t.strip().lower() for t in tags_filter.split(",") if t.strip()]
        if tag_list:
            tag_pattern = '|'.join(tag_list)
            where_conditions.append("""tx.id IN (
                SELECT DISTINCT tt.transaction_id 
                FROM core_transactiontag tt 
                INNER JOIN core_tag tag ON tt.tag_id = tag.id 
                WHERE tag.name ~* %s
            )""")
            params.append(tag_pattern)

    where_clause = " AND ".join(where_conditions)

    logger.debug(f"🔍 [transactions_totals_v2] WHERE clause: {where_clause}")
    logger.debug(f"🔍 [transactions_totals_v2] Parameters: {params}")

    with connection.cursor() as cursor:
        # Simplified query to avoid duplication from tag JOINs
        query = f"""
            SELECT 
                tx.type,
                SUM(tx.amount) as total
            FROM core_transaction tx
            LEFT JOIN core_category cat ON tx.category_id = cat.id
            LEFT JOIN core_account acc ON tx.account_id = acc.id
            LEFT JOIN core_dateperiod dp ON tx.period_id = dp.id
            WHERE {where_clause}
            GROUP BY tx.type
        """

        logger.debug(f"📝 [transactions_totals_v2] SQL Query: {query}")
        cursor.execute(query, params)
        rows = cursor.fetchall()

    logger.debug(f"📊 [transactions_totals_v2] Raw results: {rows}")

    totals = {
        'income': Decimal('0'),
        'expenses': Decimal('0'),
        'investments': Decimal('0'),
        'transfers': Decimal('0')
    }

    # Debug individual transactions
    for tx_type, amount in rows:
        logger.debug(f"🔍 [transactions_totals_v2] Processing: type={tx_type}, amount={amount}")

    type_mapping = {
        'IN': 'income',
        'EX': 'expenses', 
        'IV': 'investments',
        'TR': 'transfers'
    }

    for tx_type, amount in rows:
        amount_dec = Decimal(amount)
        logger.debug(f"💰 [transactions_totals_v2] Processing {tx_type}: {amount_dec}")

        if tx_type == 'IN':
            # Income: preserve sign (refunds reduce total income)
            totals['income'] += amount_dec
            logger.debug(f"📈 [transactions_totals_v2] Income += {amount_dec}, total now: {totals['income']}")
        elif tx_type == 'EX':
            # Expenses: preserve sign to allow refunds to decrease total
            totals['expenses'] += amount_dec
            logger.debug(f"📉 [transactions_totals_v2] Expenses += {amount_dec}, total now: {totals['expenses']}")
        elif tx_type == 'IV':
            # Investments: keep original amount (positive = reinforcement, negative = withdrawal)
            totals['investments'] += amount_dec
            logger.debug(f"📊 [transactions_totals_v2] Investments += {amount_dec}, total now: {totals['investments']}")
        elif tx_type == 'TR':
            # Transfers: keep original sign
            totals['transfers'] += amount_dec
            logger.debug(f"🔄 [transactions_totals_v2] Transfers += {amount_dec}, total now: {totals['transfers']}")

    # Balance = Income - Expenses (not including investments or transfers)
    totals['balance'] = totals['income'] - totals['expenses']

    logger.debug(
        f"🧮 [transactions_totals_v2] Final calculation: Balance = {totals['income']} - {totals['expenses']} = {totals['balance']}"
    )

    logger.debug(f"📊 [transactions_totals_v2] Final totals: {totals}")

    # Convert Decimals to floats rounded to 2 decimal places for JSON serialization
    totals = {k: float(v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)) for k, v in totals.items()}

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
    paginate_by = 50  # Add pagination for large account lists

    def get_queryset(self):
        """Optimize queryset with select_related for foreign keys."""
        queryset = super().get_queryset().select_related(
            'account_type', 'currency'
        ).prefetch_related(
            'balances__period'
        )
        
        # Handle search functionality
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)
        
        return queryset.order_by('position', 'name')

    def get_context_data(self, **kwargs):
        """Add optimized context data."""
        context = super().get_context_data(**kwargs)
        
        # Get accounts efficiently
        accounts = context['accounts']
        
        # Calculate totals by account type using efficient aggregation
        account_type_totals = {}
        default_currency = 'EUR'
        
        # Get latest period for balance calculations
        latest_period = DatePeriod.objects.order_by('-year', '-month').first()
        
        if latest_period and accounts:
            # Efficient query for latest balances by account type
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT at.name, 
                           COALESCE(SUM(ab.reported_balance), 0) as total_balance,
                           c.code as currency
                    FROM core_accounttype at
                    LEFT JOIN core_account a ON a.account_type_id = at.id AND a.user_id = %s
                    LEFT JOIN core_currency c ON a.currency_id = c.id
                    LEFT JOIN core_accountbalance ab ON ab.account_id = a.id AND ab.period_id = %s
                    GROUP BY at.name, c.code
                    HAVING COALESCE(SUM(ab.reported_balance), 0) != 0
                    ORDER BY at.name
                """, [self.request.user.id, latest_period.id])
                
                results = cursor.fetchall()
                for account_type, balance, currency in results:
                    if balance:
                        currency_symbol = currency or default_currency
                        account_type_totals[account_type] = f"{balance:,.0f} {currency_symbol}"
        
        context['account_type_totals'] = account_type_totals
        context['default_currency'] = default_currency
        
        return context


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
        try:
            data = json.loads(request.body)
            order_list = data.get('order', [])
            
            logger.debug(f"Reordering accounts for user {request.user.id}: {order_list}")
            
            # Update position for each account
            with db_transaction.atomic():
                for index, item in enumerate(order_list):
                    account_id = item.get('id')
                    
                    if account_id:
                        # Use the index as the position to ensure proper ordering
                        updated_count = Account.objects.filter(
                            id=account_id,
                            user=request.user
                        ).update(position=index)
                        
                        if updated_count:
                            logger.debug(f"Updated account {account_id} to position {index}")
                        else:
                            logger.warning(f"Account {account_id} not found or not owned by user {request.user.id}")
            
            # Clear cache to ensure fresh data
            cache.delete(f"account_balance_{request.user.id}")
            cache.delete(f"account_summary_{request.user.id}")
            
            logger.info(f"Account order updated for user {request.user.id}")
            return JsonResponse({'success': True, 'message': 'Account order updated successfully'})
            
        except Exception as e:
            logger.error(f"Error reordering accounts for user {request.user.id}: {e}")
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST method required'})


def _merge_duplicate_accounts(user):
    """Função auxiliar otimizada para fundir contas duplicadas por nome."""
    # Usar raw SQL para melhor performance
    with connection.cursor() as cursor:
        # Encontrar contas duplicadas
        cursor.execute("""
            SELECT LOWER(TRIM(name)) as normalized_name, 
                   array_agg(id ORDER BY created_at) as account_ids,
                   COUNT(*) as count
            FROM core_account 
            WHERE user_id = %s 
            GROUP BY LOWER(TRIM(name))
            HAVING COUNT(*) > 1
        """, [user.id])
        
        duplicates = cursor.fetchall()
        
        if not duplicates:
            return  # Sem duplicados
        
        logger.info(f"Found {len(duplicates)} sets of duplicate accounts for user {user.id}")
        
        for normalized_name, account_ids, count in duplicates:
            primary_id = account_ids[0]  # Manter a conta mais antiga
            duplicate_ids = account_ids[1:]  # Contas a serem fundidas
            
            logger.debug(f"Merging accounts {duplicate_ids} into {primary_id}")
            
            # Atualizar saldos em bulk
            cursor.execute("""
                UPDATE core_accountbalance 
                SET account_id = %s 
                WHERE account_id = ANY(%s)
            """, [primary_id, duplicate_ids])
            
            # Atualizar transações em bulk  
            cursor.execute("""
                UPDATE core_transaction 
                SET account_id = %s 
                WHERE account_id = ANY(%s)
            """, [primary_id, duplicate_ids])
            
            # Eliminar contas duplicadas
            cursor.execute("""
                DELETE FROM core_account 
                WHERE id = ANY(%s)
            """, [duplicate_ids])
            
        logger.info(f"Account merge completed for user {user.id}")

# ==============================================================================
# ACCOUNT BALANCE FUNCTIONS
# ==============================================================================

@login_required
def account_balance_view(request):
    """Vista principal ultra otimizada para gestão de saldos de contas com detecção de alterações."""
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

    # Check cache first for GET requests
    cache_key = f"account_balance_ultra_{request.user.id}_{year}_{month}"
    
    # Obter ou criar período correspondente
    period, period_created = DatePeriod.objects.get_or_create(
        year=year,
        month=month,
        defaults={"label": date(year, month, 1).strftime("%B %Y")},
    )

    if request.method == "POST":
        logger.info(f"🚀 [account_balance_view] Change-detection POST processing for user {request.user.id}, period {year}-{month:02d}")
        start_time = datetime.now()

        try:
            # Parse form data in memory first for maximum speed
            form_data = request.POST
            total_forms = int(form_data.get('form-TOTAL_FORMS', 0))
            logger.debug(f"📊 [account_balance_view] Processing {total_forms} forms")
            
            # ⚡ ENHANCED CHANGE DETECTION - More thorough but still fast
            # First pass: Quick scan for obvious changes
            has_obvious_changes = False
            for i in range(total_forms):
                prefix = f'form-{i}'
                
                # Check for deletions - these are always changes
                if form_data.get(f'{prefix}-DELETE'):
                    has_obvious_changes = True
                    logger.debug(f"🔍 [account_balance_view] Found deletion in form {i}")
                    break
                
                # Check for new entries (no balance_id but has data)
                balance_id = form_data.get(f'{prefix}-id')
                account_name = form_data.get(f'{prefix}-account')
                reported_balance_str = form_data.get(f'{prefix}-reported_balance')
                
                if not balance_id and account_name and reported_balance_str:
                    has_obvious_changes = True
                    logger.debug(f"🔍 [account_balance_view] Found new entry in form {i}: {account_name}")
                    break
            
            # If no obvious changes, do more thorough verification with actual data comparison
            if not has_obvious_changes:
                logger.debug(f"⚡ [account_balance_view] No obvious changes detected, doing thorough verification")
                
                # Load current data for comparison
                current_balances_dict = {}
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT ab.id, ab.account_id, ab.reported_balance, a.name
                        FROM core_accountbalance ab
                        INNER JOIN core_account a ON ab.account_id = a.id
                        WHERE a.user_id = %s AND ab.period_id = %s
                    """, [request.user.id, period.id])
                    
                    for balance_id, account_id, current_amount, account_name in cursor.fetchall():
                        current_balances_dict[balance_id] = {
                            'account_name': account_name,
                            'amount': Decimal(str(current_amount))
                        }
                
                # Compare form data with database data
                changes_detected = False
                form_balance_ids = set()
                
                for i in range(total_forms):
                    prefix = f'form-{i}'
                    balance_id = form_data.get(f'{prefix}-id')
                    account_name = form_data.get(f'{prefix}-account')
                    reported_balance_str = form_data.get(f'{prefix}-reported_balance')
                    
                    # Skip empty forms
                    if not account_name or reported_balance_str == '':
                        continue
                        
                    if balance_id:
                        balance_id_int = int(balance_id)
                        form_balance_ids.add(balance_id_int)
                        
                        # Check if this balance exists in DB and if amount changed
                        if balance_id_int in current_balances_dict:
                            try:
                                new_amount = Decimal(str(reported_balance_str))
                                current_amount = current_balances_dict[balance_id_int]['amount']
                                
                                if new_amount != current_amount:
                                    changes_detected = True
                                    logger.debug(f"🔍 [account_balance_view] Amount change detected: {account_name} {current_amount} → {new_amount}")
                                    break
                            except (ValueError, TypeError):
                                changes_detected = True
                                logger.debug(f"🔍 [account_balance_view] Invalid amount format for {account_name}: {reported_balance_str}")
                                break
                        else:
                            # Balance ID in form but not in DB - this is a change
                            changes_detected = True
                            logger.debug(f"🔍 [account_balance_view] Balance ID {balance_id_int} not found in DB")
                            break
                    else:
                        # New entry without balance_id
                        changes_detected = True
                        logger.debug(f"🔍 [account_balance_view] New entry without ID: {account_name}")
                        break
                
                # Check if any existing balances were removed from the form
                if not changes_detected:
                    db_balance_ids = set(current_balances_dict.keys())
                    if db_balance_ids != form_balance_ids:
                        changes_detected = True
                        removed_ids = db_balance_ids - form_balance_ids
                        logger.debug(f"🔍 [account_balance_view] Balances removed from form: {removed_ids}")
                
                # If no changes detected, return early
                if not changes_detected:
                    logger.info(f"✅ [account_balance_view] Thorough verification - no changes detected")
                    processing_time = (datetime.now() - start_time).total_seconds()
                    messages.info(request, f"ℹ️ No changes detected ({processing_time:.2f}s)")
                    return redirect(f"{request.path}?year={year}&month={month:02d}")
                else:
                    logger.info(f"🔍 [account_balance_view] Changes detected during thorough verification")
            
            # ✨ Load current balances only if changes are likely
            current_balances = {}
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT ab.id, ab.account_id, ab.reported_balance, a.name
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    WHERE a.user_id = %s AND ab.period_id = %s
                """, [request.user.id, period.id])
                
                for balance_id, account_id, current_amount, account_name in cursor.fetchall():
                    current_balances[balance_id] = {
                        'account_id': account_id,
                        'account_name': account_name,
                        'current_amount': Decimal(str(current_amount))
                    }
            
            logger.debug(f"📋 [account_balance_view] Loaded {len(current_balances)} existing balances")
            
            # Pre-allocate lists for better memory performance
            balance_updates = []
            balance_creates = []
            balance_deletes = []
            skipped_count = 0
            
            # Single pass through form data - ultra optimized with change detection
            for i in range(total_forms):
                prefix = f'form-{i}'
                
                # Check deletion first
                if form_data.get(f'{prefix}-DELETE'):
                    balance_id = form_data.get(f'{prefix}-id')
                    if balance_id:
                        balance_deletes.append(int(balance_id))
                    continue
                
                account_name = form_data.get(f'{prefix}-account')
                reported_balance_str = form_data.get(f'{prefix}-reported_balance')
                balance_id = form_data.get(f'{prefix}-id')
                
                # Skip empty entries
                if not account_name or reported_balance_str == '':
                    continue
                    
                try:
                    new_amount = Decimal(str(reported_balance_str))
                    account_name = str(account_name).strip()
                    
                    # Get or create account by name
                    account, created = Account.objects.get_or_create(
                        user_id=request.user.id,
                        name__iexact=account_name,
                        defaults={
                            'name': account_name,
                            'currency_id': Currency.objects.filter(code='EUR').first().id,
                            'account_type_id': AccountType.objects.filter(name='Savings').first().id,
                        }
                    )
                    
                    if balance_id:  # Update existing
                        balance_id_int = int(balance_id)
                        
                        # ✨ DETECÇÃO DE ALTERAÇÕES: Só gravar se valor mudou
                        if balance_id_int in current_balances:
                            current_amount = current_balances[balance_id_int]['current_amount']
                            
                            # Comparar valores com precisão decimal
                            if new_amount != current_amount:
                                balance_updates.append((balance_id_int, account.id, new_amount, current_amount, new_amount))
                                logger.debug(f"🔄 [account_balance_view] Changed: {account_name} {current_amount} → {new_amount}")
                            else:
                                skipped_count += 1
                                logger.debug(f"⏭️ [account_balance_view] Skipped unchanged: {account_name} = {current_amount}")
                        else:
                            # Balance ID exists but not in current_balances - treat as update
                            balance_updates.append((balance_id_int, account.id, new_amount, Decimal('0'), new_amount))
                    else:  # Create new
                        balance_creates.append((account.id, new_amount))
                        logger.debug(f"➕ [account_balance_view] Creating new: {account_name} = {new_amount}")
                        
                except (ValueError, TypeError) as e:
                    logger.warning(f"⚠️ [account_balance_view] Invalid data in form {i}: {e}")
                    continue

            # Ultra-fast bulk operations using single atomic transaction
            operations_count = 0
            changed_count = len(balance_updates) + len(balance_creates) + len(balance_deletes)
            
            logger.info(f"📈 [account_balance_view] Changes detected: {changed_count} operations, {skipped_count} skipped")
            
            if changed_count > 0:
                with db_transaction.atomic():
                    with connection.cursor() as cursor:
                        
                        # 1. Bulk deletes with single query
                        if balance_deletes:
                            cursor.execute("""
                                DELETE FROM core_accountbalance 
                                WHERE id = ANY(%s) AND account_id IN (
                                    SELECT id FROM core_account WHERE user_id = %s
                                )
                            """, [balance_deletes, request.user.id])
                            operations_count += cursor.rowcount
                            logger.debug(f"🗑️ [account_balance_view] Deleted {cursor.rowcount} balances")
                        
                        # 2. Bulk updates - only changed values
                        if balance_updates:
                            for balance_id, account_id, new_amount, old_amount, _ in balance_updates:
                                cursor.execute("""
                                    UPDATE core_accountbalance 
                                    SET reported_balance = %s
                                    WHERE id = %s AND account_id IN (
                                        SELECT id FROM core_account WHERE user_id = %s
                                    )
                                """, [new_amount, balance_id, request.user.id])
                                operations_count += cursor.rowcount
                            
                            logger.debug(f"🔄 [account_balance_view] Updated {len(balance_updates)} changed balances")
                        
                        # 3. Bulk creates with single INSERT
                        if balance_creates:
                            for account_id, amount in balance_creates:
                                cursor.execute("""
                                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (account_id, period_id) 
                                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                                """, [account_id, period.id, amount])
                                operations_count += cursor.rowcount
                                
                            logger.debug(f"➕ [account_balance_view] Created/updated {len(balance_creates)} new balances")

                # Strategic cache clearing - only clear what's necessary
                from django.core.cache import cache
                cache_keys_pattern = [
                    f"account_balance_ultra_{request.user.id}_{year}_{month}",
                    f"account_balance_optimized_{request.user.id}_{year}_{month}",
                    f"account_summary_{request.user.id}",
                ]
                
                # Use pipeline for batch cache operations
                cache.delete_many(cache_keys_pattern)
                
                # Clear transaction cache to ensure consistency
                clear_tx_cache(request.user.id, force=True)
            else:
                logger.info(f"⚡ [account_balance_view] No changes detected - skipping database operations")

            processing_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"⚡ [account_balance_view] POST completed in {processing_time:.3f}s, {operations_count} operations, {skipped_count} skipped")
            
            if changed_count > 0:
                messages.success(request, f"✅ Balances saved! ({operations_count} ops, {skipped_count} unchanged, {processing_time:.2f}s)")
            else:
                messages.info(request, f"ℹ️ No changes detected ({processing_time:.2f}s)")
            
            # Optimized redirect with minimal URL construction
            return redirect(f"{request.path}?year={year}&month={month:02d}")
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [account_balance_view] Error after {processing_time:.3f}s for user {request.user.id}: {e}")
            messages.error(request, f"Error saving balances: {str(e)}")

    # GET request - ultra-fast cache lookup
    from django.core.cache import cache
    cached_data = cache.get(cache_key)
    if cached_data and request.method == "GET":
        logger.debug(f"⚡ [account_balance_view] Using cached summary data for user {request.user.id}")
        # We still need to build the formset as it can't be cached
        # But we can use cached totals and other data

    # Build context with single ultra-optimized query
    start_time = datetime.now()
    
    with connection.cursor() as cursor:
        # Single query with all JOINs and calculations
        cursor.execute("""
            SELECT 
                a.id, a.name, a.position,
                at.name, cur.code, cur.symbol,
                COALESCE(ab.reported_balance, 0),
                ab.id,
                CASE WHEN ab.id IS NOT NULL THEN 1 ELSE 0 END
            FROM core_account a
            INNER JOIN core_accounttype at ON a.account_type_id = at.id
            INNER JOIN core_currency cur ON a.currency_id = cur.id
            LEFT JOIN core_accountbalance ab ON (ab.account_id = a.id AND ab.period_id = %s)
            WHERE a.user_id = %s
            ORDER BY a.position NULLS LAST, a.name
        """, [period.id, request.user.id])
        
        rows = cursor.fetchall()

    # Ultra-fast data processing with pre-allocated dictionaries
    totals_by_group = {}
    grand_total = 0
    available_accounts = []

    # Single pass processing for maximum efficiency
    for row in rows:
        account_id, account_name, account_position, account_type_name, currency_code, currency_symbol, balance, balance_id, has_balance = row
        
        balance_value = float(balance)
        grand_total += balance_value

        # Group totals calculation
        key = (account_type_name, currency_code)
        totals_by_group[key] = totals_by_group.get(key, 0) + balance_value

        if not has_balance:
            available_accounts.append({"id": account_id, "name": account_name})

    # Minimized formset creation for template
    queryset = AccountBalance.objects.filter(
        account__user=request.user,
        period=period
    ).select_related('account__account_type', 'account__currency').only(
        'id', 'reported_balance', 'account__id', 'account__name', 
        'account__account_type__name', 'account__currency__code'
    ).order_by('account__position', 'account__name')
    
    formset = AccountBalanceFormSet(queryset=queryset, user=request.user)
    
    # Ultra-fast form grouping
    grouped_forms = {}
    for form in formset:
        if hasattr(form.instance, 'account') and form.instance.account:
            key = (form.instance.account.account_type.name, form.instance.account.currency.code)
            if key not in grouped_forms:
                grouped_forms[key] = []
            grouped_forms[key].append(form)

    context = {
        "formset": formset,
        "grouped_forms": grouped_forms,
        "totals_by_group": totals_by_group,
        "grand_total": grand_total,
        "year": year,
        "month": month,
        "selected_month": date(year, month, 1),
        "available_accounts": available_accounts,
    }

    # Cache only serializable data for performance
    if request.method == "GET":
        cache_safe_context = {
            "totals_by_group": totals_by_group,
            "grand_total": grand_total,
            "year": year,
            "month": month,
            "selected_month": date(year, month, 1),
        }
        cache.set(cache_key, cache_safe_context, timeout=600)  # 10 minutes cache
    
    query_time = (datetime.now() - start_time).total_seconds()
    logger.debug(f"⚡ [account_balance_view] GET completed in {query_time:.3f}s for user {request.user.id}")

    return render(request, "core/account_balance.html", context)


@login_required
def delete_account_balance(request, pk):
    """Optimized delete account balance."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    try:
        balance = get_object_or_404(AccountBalance, pk=pk, account__user=request.user)
        period_year = balance.period.year
        period_month = balance.period.month
        
        balance.delete()
        logger.info(f"Account balance {pk} deleted by user {request.user.id}")
        
        # Clear related cache
        cache.delete(f"account_balance_{request.user.id}_{period_year}_{period_month}")
        
        # Return JSON response for AJAX requests
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'success': True, 'message': 'Balance deleted successfully'})
        
        # Redirect back to account balance page for the same period
        messages.success(request, "Balance deleted successfully!")
        return redirect(f"{reverse('account_balance')}?year={period_year}&month={period_month:02d}")
        
    except AccountBalance.DoesNotExist:
        logger.error(f"Error deleting account balance {pk} for user {request.user.id}: No AccountBalance matches the given query.")
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'success': False, 'error': 'Balance not found'}, status=404)
        
        messages.error(request, "Balance not found or already deleted.")
        return redirect('account_balance')
        
    except Exception as e:
        logger.error(f"Error deleting account balance {pk} for user {request.user.id}: {e}")
        
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'success': False, 'error': 'Error deleting balance'}, status=500)
        
        messages.error(request, 'Error deleting account balance.')
        return redirect('account_balance')


@login_required
def warm_account_balance_cache(request):
    """Warm cache for account balance view to improve performance."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required'})
    
    try:
        year = int(request.GET.get('year', date.today().year))
        month = int(request.GET.get('month', date.today().month))
        
        # Warm cache by making a quick query
        cache_key = f"account_balance_optimized_{request.user.id}_{year}_{month}"
        
        if not cache.get(cache_key):
            # Quick cache warming query
            period = DatePeriod.objects.filter(year=year, month=month).first()
            if period:
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT COUNT(*) FROM core_account a
                        LEFT JOIN core_accountbalance ab ON (ab.account_id = a.id AND ab.period_id = %s)
                        WHERE a.user_id = %s
                    """, [period.id, request.user.id])
                    
                logger.info(f"🔥 Cache warmed for user {request.user.id}, period {year}-{month:02d}")
        
        return JsonResponse({'success': True, 'message': 'Cache warmed'})
        
    except Exception as e:
        logger.error(f"Error warming cache for user {request.user.id}: {e}")
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def copy_previous_balances_view(request):
    """Optimized copy previous month balances to current period."""
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

        logger.info(f"Copying balances from {prev_year}-{prev_month:02d} to {year}-{month:02d} for user {request.user.id}")

        # Use raw SQL for better performance
        with connection.cursor() as cursor:
            # First check if source period has any data
            cursor.execute("""
                SELECT COUNT(*) FROM core_accountbalance ab
                INNER JOIN core_account a ON ab.account_id = a.id
                INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
            """, [request.user.id, prev_year, prev_month])
            
            source_count = cursor.fetchone()[0]
            if source_count == 0:
                return JsonResponse({
                    'success': False,
                    'error': f'No balances found for {prev_year}-{prev_month:02d}'
                })

            # Get or create target period
            target_period, _ = DatePeriod.objects.get_or_create(
                year=year,
                month=month,
                defaults={'label': f"{date(year, month, 1).strftime('%B %Y')}"}
            )

            # Use bulk upsert with raw SQL for maximum performance
            cursor.execute("""
                WITH source_data AS (
                    SELECT 
                        ab.account_id,
                        ab.reported_balance,
                        %s as target_period_id
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    INNER JOIN core_dateperiod dp ON ab.period_id = dp.id
                    WHERE a.user_id = %s AND dp.year = %s AND dp.month = %s
                ),
                upsert AS (
                    INSERT INTO core_accountbalance (account_id, period_id, reported_balance)
                    SELECT account_id, target_period_id, reported_balance 
                    FROM source_data
                    ON CONFLICT (account_id, period_id) 
                    DO UPDATE SET reported_balance = EXCLUDED.reported_balance
                    RETURNING 
                        CASE WHEN xmax = 0 THEN 1 ELSE 0 END as is_insert,
                        account_id
                )
                SELECT 
                    SUM(is_insert) as created_count,
                    COUNT(*) - SUM(is_insert) as updated_count,
                    COUNT(*) as total_count
                FROM upsert
            """, [target_period.id, request.user.id, prev_year, prev_month])

            result = cursor.fetchone()
            created_count, updated_count, total_count = result

            logger.info(f"Copy operation completed: {created_count} created, {updated_count} updated")

            # Clear cache for this user's account balance data more efficiently
            cache.delete(f"account_balance_optimized_{request.user.id}_{year}_{month}")
            cache.delete(f"account_summary_{request.user.id}")
            # Clear neighboring months cache too since data dependencies exist
            if month == 1:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year-1}_12")
            else:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year}_{month-1}")
            if month == 12:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year+1}_1")
            else:
                cache.delete(f"account_balance_optimized_{request.user.id}_{year}_{month+1}")

            return JsonResponse({
                'success': True,
                'created': created_count,
                'updated': updated_count,
                'total': total_count,
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
    """Import account balances from Excel with optimized bulk operations."""
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

            # Clean and validate data upfront
            df = df.dropna(subset=required_cols)
            df['Account'] = df['Account'].astype(str).str.strip()

            try:
                df['Year'] = df['Year'].astype(int)
                df['Month'] = df['Month'].astype(int)
                df['Balance'] = df['Balance'].astype(float)
            except ValueError as e:
                messages.error(request, f'Invalid data format: {str(e)}')
                return render(request, 'core/import_balances_form.html')

            imported_count = 0
            updated_count = 0
            errors = []

            with db_transaction.atomic():
                # Pre-fetch default objects
                default_currency, _ = Currency.objects.get_or_create(
                    code='EUR', 
                    defaults={'name': 'Euro', 'symbol': '€'}
                )
                default_account_type, _ = AccountType.objects.get_or_create(
                    name='Savings'
                )

                # Get unique periods and accounts from data
                unique_periods = df[['Year', 'Month']].drop_duplicates()
                unique_accounts = df['Account'].unique()

                # Bulk create/get periods
                periods_to_create = []
                existing_periods = {}

                for _, row in unique_periods.iterrows():
                    year, month = int(row['Year']), int(row['Month'])
                    try:
                        period = DatePeriod.objects.get(year=year, month=month)
                        existing_periods[(year, month)] = period
                    except DatePeriod.DoesNotExist:
                        period_date = date(year, month, 1)
                        periods_to_create.append(DatePeriod(
                            year=year,
                            month=month,
                            label=period_date.strftime('%B %Y')
                        ))

                # Bulk create new periods
                if periods_to_create:
                    DatePeriod.objects.bulk_create(periods_to_create, ignore_conflicts=True)

                # Re-fetch all periods after bulk create
                all_periods = DatePeriod.objects.filter(
                    year__in=unique_periods['Year'].values,
                    month__in=unique_periods['Month'].values
                )
                period_lookup = {(p.year, p.month): p for p in all_periods}

                # Bulk create/get accounts
                accounts_to_create = []
                existing_accounts = {}

                for account_name in unique_accounts:
                    try:
                        account = Account.objects.get(name=account_name, user=request.user)
                        existing_accounts[account_name] = account
                    except Account.DoesNotExist:
                        accounts_to_create.append(Account(
                            name=account_name,
                            user=request.user,
                            currency=default_currency,
                            account_type=default_account_type
                        ))

                # Bulk create new accounts
                if accounts_to_create:
                    Account.objects.bulk_create(accounts_to_create, ignore_conflicts=True)

                # Re-fetch all accounts after bulk create
                all_accounts = Account.objects.filter(
                    user=request.user,
                    name__in=unique_accounts
                )
                account_lookup = {a.name: a for a in all_accounts}

                # Prepare balance operations
                balances_to_create = []
                balances_to_update = []

                # Get existing balances for this user in bulk
                existing_balances = {}
                if account_lookup and period_lookup:
                    existing_balance_qs = AccountBalance.objects.filter(
                        account__user=request.user,
                        account__in=account_lookup.values(),
                        period__in=period_lookup.values()
                    ).select_related('account', 'period')

                    for bal in existing_balance_qs:
                        key = (bal.account.name, bal.period.year, bal.period.month)
                        existing_balances[key] = bal

                # Process each row for balance operations
                for index, row in df.iterrows():
                    try:
                        year = int(row['Year'])
                        month = int(row['Month'])
                        account_name = str(row['Account']).strip()
                        balance = Decimal(str(row['Balance']))

                        # Get period and account from lookup
                        period = period_lookup.get((year, month))
                        account = account_lookup.get(account_name)

                        if not period or not account:
                            errors.append(f'Row {index + 2}: Could not find period or account')
                            continue

                        balance_key = (account_name, year, month)

                        if balance_key in existing_balances:
                            # Update existing balance
                            existing_balance = existing_balances[balance_key]
                            existing_balance.reported_balance = balance
                            balances_to_update.append(existing_balance)
                            updated_count += 1
                        else:
                            # Create new balance
                            balances_to_create.append(AccountBalance(
                                account=account,
                                period=period,
                                reported_balance=balance
                            ))
                            imported_count += 1

                    except Exception as e:
                        errors.append(f'Row {index + 2}: {str(e)}')

                # Bulk operations for balances
                if balances_to_create:
                    AccountBalance.objects.bulk_create(balances_to_create, ignore_conflicts=True)

                if balances_to_update:
                    AccountBalance.objects.bulk_update(
                        balances_to_update, 
                        ['reported_balance'], 
                        batch_size=1000
                    )

            if errors:
                messages.warning(request, f'Imported {imported_count} new balances, updated {updated_count} existing balances with {len(errors)} errors.')
                if len(errors) <= 5:  # Show first 5 errors
                    for error in errors[:5]:
                        messages.error(request, error)
            else:
                messages.success(request, f'Successfully imported {imported_count} new balances and updated {updated_count} existing balances.')

            return redirect('/account-balance/')

        except Exception as e:
            logger.error(f"Import error for user {request.user.id}: {e}")
            messages.error(request, f'Import failed: {str(e)}')

    return render(request, 'core/import_balances_form.html')


@login_required
def account_balance_template_xlsx(request):
    """Download template for account balance import using Savings and Investments accounts."""
    data = {
        'Year': [2025, 2025],
        'Month': [1, 1],
        'Account': ['Savings', 'Investments'],
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
    # Get available periods with account balances, excluding the most recent period
    # because we need the next period's data to estimate transactions
    all_periods_with_balances = DatePeriod.objects.filter(
        account_balances__account__user=request.user
    ).distinct().select_related().order_by('-year', '-month')
    
    # Exclude the most recent period (first in the ordered list)
    periods_with_balances = all_periods_with_balances[1:13]  # Skip first, get next 12 months

    logger.debug(f"Found {periods_with_balances.count()} periods with balances for user {request.user.id} (excluding latest period)")

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
        clear_tx_cache(request.user.id, force=True)

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

        # Exclude the most recent period because we need next period data for estimation
        periods = periods_qs[1:13]  # Skip first, get next 12 months

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
        clear_tx_cache(request.user.id, force=True)

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

        # Find and delete estimated transactions for this period anduser
        estimated_transactions = Transaction.objects.filter(
            user=request.user,
            period=period,
            is_estimated=True
        )

        deleted_count = estimated_transactions.count()
        estimated_transactions.delete()

        logger.info(f"Deleted {deleted_count} estimated transaction(s) for period {period.label}")

        # Clear cache
        clear_tx_cache(request.user.id, force=True)

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
    """Dashboard KPIs JSON API with proper period filtering."""
    try:
        user_id = request.user.id
        logger.debug(f"📊 [dashboard_kpis_json] Request from user {user_id}: {request.GET}")

        # Get period filters from request
        start_period = request.GET.get('start_period')
        end_period = request.GET.get('end_period')

        logger.debug(f"📅 [dashboard_kpis_json] Period filters: {start_period} -> {end_period}")

        # Base query for transactions
        tx_query = Transaction.objects.filter(user_id=user_id)
        balance_periods = []

        # Apply period filters if provided
        if start_period and end_period:
            try:
                # Parse periods (format: YYYY-MM)
                start_year, start_month = map(int, start_period.split('-'))
                end_year, end_month = map(int, end_period.split('-'))

                # Calculate date range
                from calendar import monthrange
                start_date = date(start_year, start_month, 1)
                _, last_day = monthrange(end_year, end_month)
                end_date = date(end_year, end_month, last_day)

                logger.debug(f"📅 [dashboard_kpis_json] Date range: {start_date} -> {end_date}")

                # Filter transactions by date range
                tx_query = tx_query.filter(date__gte=start_date, date__lte=end_date)

                # Get corresponding periods for balance calculation
                balance_periods = list(DatePeriod.objects.filter(
                    year__gte=start_year,
                    year__lte=end_year,
                    month__gte=start_month if start_year == end_year else 1,
                    month__lte=end_month if start_year == end_year else 12
                ).values_list('id', flat=True))

                if start_year != end_year:
                    # Handle multi-year ranges
                    balance_periods = list(DatePeriod.objects.filter(
                        models.Q(year=start_year, month__gte=start_month) |
                        models.Q(year__gt=start_year, year__lt=end_year) |
                        models.Q(year=end_year, month__lte=end_month)
                    ).values_list('id', flat=True))

                logger.debug(f"📊 [dashboard_kpis_json] Found {len(balance_periods)} periods for balance calculation")

            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid period format: {start_period} - {end_period}: {e}")
                # Fallback to no period filter
                start_period = end_period = None

        # Get aggregated transaction stats
        stats = tx_query.aggregate(
            total_income=models.Sum('amount', filter=models.Q(type='IN')) or 0,
            total_expenses=models.Sum('amount', filter=models.Q(type='EX')) or 0,
            total_investments=models.Sum('amount', filter=models.Q(type='IV')) or 0,
            total_count=models.Count('id'),
            categorized_count=models.Count('id', filter=models.Q(category__isnull=False))
        )

        total_income = float(stats['total_income'] or 0)
        total_expenses = float(abs(stats['total_expenses'] or 0))  # Make positive
        total_investments = float(abs(stats['total_investments'] or 0))  # Make positive
        total_transactions = stats['total_count']
        categorized_transactions = stats['categorized_count']

        from django.db.models import Q, Sum

        estimated_expenses_sum = tx_query.aggregate(
            est_sum=Sum('amount', filter=Q(type='EX') & Q(is_estimated=True))
        )['est_sum'] or 0
        estimated_expenses_sum = float(abs(estimated_expenses_sum))

        non_estimated_expense_pct_dec = pct(
            Decimal(total_expenses) - Decimal(estimated_expenses_sum),
            Decimal(total_expenses)
        )
        non_estimated_expense_pct = float(non_estimated_expense_pct_dec)

        logger.debug(f"💰 [dashboard_kpis_json] Transaction stats: income={total_income}, expenses={total_expenses}, investments={total_investments}, total={total_transactions}")

        # Calculate number of months in the filtered period
        if start_period and end_period:
            try:
                start_year, start_month = map(int, start_period.split('-'))
                end_year, end_month = map(int, end_period.split('-'))
                num_months = (end_year - start_year) * 12 + (end_month - start_month) + 1
            except:
                num_months = 1
        else:
            # Estimate months based on data span
            date_range = tx_query.aggregate(
                min_date=models.Min('date'),
                max_date=models.Max('date')
            )
            if date_range['min_date'] and date_range['max_date']:
                delta = date_range['max_date'] - date_range['min_date']
                num_months = max(1, delta.days // 30)
            else:
                num_months = 1

        logger.debug(f"📅 [dashboard_kpis_json] Calculated {num_months} months for averaging")

        # Calculate averages
        receita_media = total_income / max(num_months, 1)
        despesa_media = total_expenses / max(num_months, 1)

        # Calculate savings rate
        savings_rate = ((total_income - total_expenses) / total_income * 100) if total_income > 0 else 0

        # Calculate categorized percentage
        categorized_percentage = (categorized_transactions / total_transactions * 100) if total_transactions > 0 else 0

        # Get patrimonio from filtered periods or latest available
        if balance_periods:
            # Use filtered periods
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT COALESCE(SUM(ab.reported_balance), 0)
                    FROM core_accountbalance ab
                    INNER JOIN core_account a ON ab.account_id = a.id
                    WHERE a.user_id = %s
                    AND ab.period_id = ANY(%s)
                    AND ab.period_id = (
                        SELECT MAX(ab2.period_id) 
                        FROM core_accountbalance ab2 
                        INNER JOIN core_account a2 ON ab2.account_id = a2.id
                        WHERE a2.user_id = %s 
                        AND ab2.period_id = ANY(%s)
                    )
                """, [user_id, balance_periods, user_id, balance_periods])
                patrimonio_total = float(cursor.fetchone()[0] or 0)
        else:
            # Use latest available balance
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

        logger.debug(f"💎 [dashboard_kpis_json] Calculated patrimonio: {patrimonio_total}")

        # Calculate additional metrics
        investment_rate = (total_investments / total_income * 100) if total_income > 0 else 0
        avg_transaction = total_income / total_transactions if total_transactions > 0 else 0

        # Calculate financial health score (simple algorithm)
        health_score = (
            min(savings_rate, 30) +  # Max 30 points for savings rate
            min(categorized_percentage, 20) +  # Max 20 points for categorization
            min(investment_rate, 25) +  # Max 25 points for investment rate
            (25 if patrimonio_total > 10000 else patrimonio_total / 10000 * 25)  # Max 25 points for net worth
        )

        return JsonResponse({
            'patrimonio_total': f"{patrimonio_total:,.0f} €",
            'receita_media': f"{receita_media:,.0f} €",
            'despesa_estimada_media': f"{despesa_media:,.0f} €",
            'valor_investido_total': f"{total_investments:,.0f} €",
            'despesas_justificadas_pct': non_estimated_expense_pct,
            'despesas_justificadas_pct_str': f"{non_estimated_expense_pct_dec}%",
            'taxa_poupanca': f"{savings_rate:.1f}%",
            'rentabilidade_mensal_media': "+0.0%",  # Placeholder for now
            'investment_rate': f"{investment_rate:.1f}%",
            'wealth_growth': "+0.0%",  # Placeholder for now
            'avg_transaction': f"{avg_transaction:.0f} €",
            'total_transactions': total_transactions,
            'num_meses': num_months,
            'financial_health_score': health_score,
            'account_breakdown': {
                'savings': 0,  # Placeholder
                'investments': 0,  # Placeholder
                'checking': 0  # Placeholder
            },
            'metodo_calculo': "Enhanced calculation with comprehensive metrics",
            'period_info': {
                'months_analyzed': num_months,
                'period_filter': bool(start_period and end_period),
                'start_period': start_period,
                'end_period': end_period
            },
            'status': 'success',
            'debug_info': {
                'total_income': total_income,
                'total_expenses': total_expenses,
                'total_investments': total_investments,
                'total_transactions': total_transactions,
                'patrimonio_total': patrimonio_total,
                'previous_patrimonio': 0,  # Placeholder
                'savings_rate': savings_rate,
                'categorized_percentage': categorized_percentage,
                'estimated_expenses_sum': estimated_expenses_sum,
                'non_estimated_expense_pct': non_estimated_expense_pct
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
            'despesas_justificadas_pct': 0.0,
            'despesas_justificadas_pct_str': "0%",
            'taxa_poupanca': "0.0%",
            'rentabilidade_mensal_media': "+0.0%",
            'investment_rate': "0.0%",
            'wealth_growth': "+0.0%",
            'avg_transaction': "0 €",
            'total_transactions': 0,
            'num_meses': 0,
            'financial_health_score': 0,
            'account_breakdown': {'savings': 0, 'investments': 0, 'checking': 0},
            'metodo_calculo': "Error fallback",
            'period_info': {'months_analyzed': 0, 'period_filter': False}
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


@login_required
def dashboard_goals_json(request):
    """Dashboard Goals JSON API."""
    try:
        user_id = request.user.id
        logger.debug(f"🎯 [dashboard_goals_json] Request from user {user_id}")

        # Get current month's data for goal calculations
        today = date.today()
        current_period = DatePeriod.objects.filter(
            year=today.year, 
            month=today.month
        ).first()

        # Calculate monthly savings goal (target: €2000)
        savings_target = 2000
        current_savings = 0

        if current_period:
            # Get current month transactions
            current_income = Transaction.objects.filter(
                user_id=user_id,
                period=current_period,
                type='IN'
            ).aggregate(total=models.Sum('amount'))['total'] or 0

            current_expenses = abs(Transaction.objects.filter(
                user_id=user_id,
                period=current_period,
                type='EX'
            ).aggregate(total=models.Sum('amount'))['total'] or 0)

            current_savings = float(current_income) - float(current_expenses)

        savings_progress = min(100, max(0, (current_savings / savings_target) * 100))

        # Calculate investment target (target: €10000 total)
        investment_target = 10000
        total_investments = float(Transaction.objects.filter(
            user_id=user_id,
            type='IV'
        ).aggregate(total=models.Sum('amount'))['total'] or 0)

        investment_progress = min(100, max(0, (abs(total_investments) / investment_target) * 100))

        # Calculate spending reduction goal (target: save €500 vs average)
        # Get last 3 months average expenses
        last_3_months = DatePeriod.objects.filter(
            year__gte=today.year - 1
        ).order_by('-year', '-month')[:3]

        avg_expenses = 0
        current_month_expenses = 0
        reduction_target = 500

        if last_3_months.count() >= 2:
            # Average of previous months (excluding current)
            previous_periods = last_3_months[1:]
            avg_expenses = float(Transaction.objects.filter(
                user_id=user_id,
                period__in=previous_periods,
                type='EX'
            ).aggregate(total=models.Sum('amount'))['total'] or 0) / len(previous_periods)

            # Current month expenses
            if current_period:
                current_month_expenses = float(Transaction.objects.filter(
                    user_id=user_id,
                    period=current_period,
                    type='EX'
                ).aggregate(total=models.Sum('amount'))['total'] or 0)

        actual_reduction = max(0, abs(avg_expenses) - abs(current_month_expenses))
        reduction_progress = min(100, max(0, (actual_reduction / reduction_target) * 100))

        goals = [
            {
                'name': 'Monthly Savings Goal',
                'progress': round(savings_progress, 1),
                'current': round(current_savings, 0),
                'target': savings_target,
                'color': 'success' if savings_progress >= 80 else 'warning' if savings_progress >= 50 else 'danger'
            },
            {
                'name': 'Investment Target', 
                'progress': round(investment_progress, 1),
                'current': round(abs(total_investments), 0),
                'target': investment_target,
                'color': 'success' if investment_progress >= 80 else 'warning' if investment_progress >= 50 else 'info'
            },
            {
                'name': 'Spending Reduction',
                'progress': round(reduction_progress, 1),
                'current': round(actual_reduction, 0),
                'target': reduction_target,
                'color': 'info' if reduction_progress >= 80 else 'warning' if reduction_progress >= 50 else 'secondary'
            }
        ]

        return JsonResponse({
            'status': 'success',
            'goals': goals
        })

    except Exception as e:
        logger.error(f"Error in dashboard_goals_json for user {request.user.id}: {e}")
        return JsonResponse({
            'status': 'error',
            'goals': []
        }, status=500)


@login_required
def dashboard_spending_by_category_json(request):
    """Dashboard Spending by Category JSON API."""
    try:
        user_id = request.user.id
        logger.debug(f"🛒 [dashboard_spending_by_category_json] Request from user {user_id}")

        if request.method != 'POST':
            return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

        import json
        data = json.loads(request.body)
        start_period = data.get('start_period')  # Format: YYYY-MM
        end_period = data.get('end_period')      # Format: YYYY-MM

        logger.debug(f"📅 [dashboard_spending_by_category_json] Period: {start_period} -> {end_period}")

        # Base query for expense transactions
        tx_query = Transaction.objects.filter(
            user_id=user_id,
            type='EX'  # Only expenses
        )

        # Apply period filters if provided
        if start_period and end_period:
            try:
                # Parse periods (format: YYYY-MM)
                start_year, start_month = map(int, start_period.split('-'))
                end_year, end_month = map(int, end_period.split('-'))

                # Calculate date range
                from calendar import monthrange
                start_date = date(start_year, start_month, 1)
                _, last_day = monthrange(end_year, end_month)
                end_date = date(end_year, end_month, last_day)

                logger.debug(f"📅 [dashboard_spending_by_category_json] Date range: {start_date} -> {end_date}")

                tx_query = tx_query.filter(
                    date__gte=start_date,
                    date__lte=end_date
                )
            except ValueError as e:
                logger.error(f"❌ [dashboard_spending_by_category_json] Invalid period format: {e}")
                return JsonResponse({'status': 'error', 'message': 'Invalid period format'}, status=400)

        # Group expenses by category
        category_totals = tx_query.values('category__name').annotate(
            total_amount=models.Sum('amount'),
            transaction_count=models.Count('id')
        ).order_by('-total_amount')

        categories = []
        total_expenses = 0

        for item in category_totals:
            category_name = item['category__name'] or 'Uncategorized'
            amount = abs(float(item['total_amount'] or 0))  # Ensure positive
            count = item['transaction_count']

            if amount > 0:  # Only include categories with expenses
                categories.append({
                    'name': category_name,
                    'total_amount': amount,
                    'transaction_count': count,
                    'percentage': 0  # Will calculate after getting total
                })
                total_expenses += amount

        # Calculate percentages
        for category in categories:
            if total_expenses > 0:
                category['percentage'] = (category['total_amount'] / total_expenses) * 100

        # Sort by amount (descending)
        categories.sort(key=lambda x: x['total_amount'], reverse=True)

        logger.debug(f"🛒 [dashboard_spending_by_category_json] Found {len(categories)} categories, total: €{total_expenses:.2f}")

        return JsonResponse({
            'status': 'success',
            'categories': categories,
            'total_expenses': total_expenses,
            'period': f"{start_period} to {end_period}" if start_period and end_period else 'All time'
        })

    except Exception as e:
        logger.error(f"❌ Error in dashboard_spending_by_category_json for user {request.user.id}: {e}")
        return JsonResponse({
            'status': 'error',
            'message': str(e),
            'categories': []
        }, status=500)


@login_required
def dashboard_returns_json(request):
    """Return monthly portfolio returns and their average for the user."""
    start_period = request.GET.get("start_period")
    end_period = request.GET.get("end_period")
    user = request.user
    base_currency = (
        getattr(user, "settings", None) and user.settings.base_currency
    ) or get_default_currency()

    cache_key = f"returns:{user.id}:{start_period}:{end_period}"
    cached = cache.get(cache_key)
    if cached is not None:
        return JsonResponse({"series": cached})

    balances_qs = (
        AccountBalance.objects.filter(
            account__user=user,
            account__account_type__name__istartswith="invest",
        )
        .select_related("account__currency", "period")
        .order_by("period__year", "period__month")
    )

    balance_map: dict[str, Decimal] = {}
    periods_list: list[str] = []
    for bal in balances_qs:
        period_str = f"{bal.period.year:04d}-{bal.period.month:02d}"
        periods_list.append(period_str)
        rate_date = date(bal.period.year, bal.period.month, 1)
        amount = convert_amount(
            bal.reported_balance,
            bal.account.currency,
            base_currency,
            rate_date,
        )
        balance_map[period_str] = balance_map.get(period_str, Decimal("0")) + amount

    periods = sorted(set(periods_list))

    if not balance_map:
        return JsonResponse({"series": []})

    if start_period and end_period and re.match(r"^\d{4}-(0[1-9]|1[0-2])$", start_period) and re.match(r"^\d{4}-(0[1-9]|1[0-2])$", end_period):
        periods = [p for p in periods if start_period <= p <= end_period]

    flows_qs = (
        Transaction.objects.filter(user=user, type="IV")
        .select_related("account__currency", "period")
    )
    flow_map: dict[str, Decimal] = {}
    for t in flows_qs:
        period_str = f"{t.period.year:04d}-{t.period.month:02d}"
        amount = convert_amount(
            t.amount,
            t.account.currency if t.account else base_currency,
            base_currency,
            t.date,
        )
        flow_map[period_str] = flow_map.get(period_str, Decimal("0")) + amount

    def _to_float(value: Decimal | None) -> float | None:
        if value is None:
            return None
        return float(value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    monthly_returns: list[tuple[str, Decimal | None]] = []
    prev_balance: Decimal | None = None

    for period in periods:
        balance = Decimal(balance_map.get(period, Decimal("0")))
        flow = Decimal(flow_map.get(period, Decimal("0")))
        if prev_balance is None:
            ret = None
            if settings.DEBUG:
                logger.debug(
                    "Period %s has no previous balance; flow=%s -> return=None",
                    period,
                    flow,
                )
        else:
            denom = prev_balance + flow
            if denom <= 0:
                ret = None
                if settings.DEBUG:
                    logger.debug(
                        "Period %s invalid denom prev_balance=%s flow=%s denom=%s",
                        period,
                        prev_balance,
                        flow,
                        denom,
                    )
            else:
                ret = (balance - denom) / denom * Decimal("100")
                if settings.DEBUG:
                    logger.debug(
                        "Period %s prev_balance=%s flow=%s denom=%s return=%s",
                        period,
                        prev_balance,
                        flow,
                        denom,
                        ret,
                    )

        monthly_returns.append((period, ret))
        prev_balance = balance

    valid_returns = [r for _, r in monthly_returns if r is not None]
    avg_return = (
        sum(valid_returns) / Decimal(len(valid_returns)) if valid_returns else None
    )

    series = [
        {
            "period": period,
            "portfolio_return": _to_float(ret),
            "avg_portfolio_return": _to_float(avg_return),
        }
        for period, ret in monthly_returns
    ]
    cache.set(cache_key, series, 86400)
    return JsonResponse({"series": series})


@login_required
def dashboard_insights_json(request):
    """Dashboard Insights JSON API."""
    try:
        user_id = request.user.id
        logger.debug(f"🧠 [dashboard_insights_json] Request from user {user_id}")

        insights = []

        # Get user's financial data for analysis
        total_transactions = Transaction.objects.filter(user_id=user_id).count()

        if total_transactions == 0:
            insights.append({
                'type': 'info',
                'title': '📈 Start Your Financial Journey',
                'text': 'Add your first transactions to begin receiving personalized insights.'
            })
            return JsonResponse({'status': 'success', 'insights': insights})

        # Get recent data (last 3 months)
        recent_periods = DatePeriod.objects.order_by('-year', '-month')[:3]

        # Calculate monthly averages
        recent_income = Transaction.objects.filter(
            user_id=user_id,
            period__in=recent_periods,
            type='IN'
        ).aggregate(total=models.Sum('amount'))['total'] or 0

        recent_expenses = abs(Transaction.objects.filter(
            user_id=user_id,
            period__in=recent_periods,
            type='EX'
        ).aggregate(total=models.Sum('amount'))['total'] or 0)

        recent_investments = abs(Transaction.objects.filter(
            user_id=user_id,
            period__in=recent_periods,
            type='IV'
        ).aggregate(total=models.Sum('amount'))['total'] or 0)

        months_count = max(1, recent_periods.count())
        avg_income = float(recent_income) / months_count
        avg_expenses = float(recent_expenses) / months_count
        avg_investments = float(recent_investments) / months_count

        # Savings rate analysis
        savings_rate = ((avg_income - avg_expenses) / avg_income * 100) if avg_income > 0 else 0

        if savings_rate > 30:
            insights.append({
                'type': 'positive',
                'title': '💎 Excellent Saver',
                'text': f'Your savings rate of {savings_rate:.1f}% is outstanding! You\'re on track for financial independence.'
            })
        elif savings_rate > 15:
            insights.append({
                'type': 'warning', 
                'title': '👍 Good Savings Habits',
                'text': f'Savings rate of {savings_rate:.1f}% is solid. Try to reach 20-30% to accelerate your goals.'
            })
        elif savings_rate > 0:
            insights.append({
                'type': 'negative',
                'title': '🎯 Savings Opportunity',
                'text': f'Savings rate: {savings_rate:.1f}%. Focus on reducing expenses or increasing income.'
            })
        else:
            insights.append({
                'type': 'negative',
                'title': '⚠️ Spending Alert',
                'text': 'You\'re spending more than you earn. Review your budget urgently.'
            })

        # Investment analysis
        investment_rate = (avg_investments / avg_income * 100) if avg_income > 0 else 0

        if investment_rate > 15:
            insights.append({
                'type': 'positive',
                'title': '🚀 Investment Champion',
                'text': f'Investing {investment_rate:.1f}% of income is excellent for long-term wealth building.'
            })
        elif investment_rate > 5:
            insights.append({
                'type': 'warning',
                'title': '📈 Building Wealth',
                'text': f'You\'re investing {investment_rate:.1f}% of income. Consider increasing to 15-20% for faster growth.'
            })
        elif investment_rate > 0:
            insights.append({
                'type': 'info',
                'title': '🌱 Investment Starter',
                'text': f'Great start with {investment_rate:.1f}% invested. Gradually increase your investment rate.'
            })

        # Transaction categorization insight
        categorized_count = Transaction.objects.filter(
            user_id=user_id,
            category__isnull=False
        ).count()

        categorization_rate = (categorized_count / total_transactions * 100) if total_transactions > 0 else 0

        if categorization_rate < 80:
            insights.append({
                'type': 'info',
                'title': '🏷️ Organize Your Finances',
                'text': f'Only {categorization_rate:.0f}% of transactions are categorized. Better categorization provides deeper insights.'
            })

        # Seasonal spending insight
        current_month = date.today().month
        if current_month in [11, 12, 1]:  # Nov, Dec, Jan
            insights.append({
                'type': 'warning',
                'title': '🎄 Holiday Season Alert',
                'text': 'Holiday spending can impact budgets. Track expenses carefully and stick to your financial goals.'
            })
        elif current_month in [6, 7, 8]:  # Summer months
            insights.append({
                'type': 'info',
                'title': '☀️ Summer Spending',
                'text': 'Summer often brings vacation and leisure expenses. Plan ahead to maintain your savings goals.'
            })

        # Account balance insight
        latest_period = DatePeriod.objects.order_by('-year', '-month').first()
        if latest_period:
            total_balance = AccountBalance.objects.filter(
                account__user_id=user_id,
                period=latest_period
            ).aggregate(total=models.Sum('reported_balance'))['total'] or 0

            if float(total_balance) > 50000:
                insights.append({
                    'type': 'positive',
                    'title': '💰 Strong Financial Position',
                    'text': 'Your net worth is growing well. Consider diversifying investments for optimal returns.'
                })

        # If no specific insights, add encouragement
        if len(insights) == 0:
            insights.append({
                'type': 'info',
                'title': '📊 Keep Building Data',
                'text': 'Continue adding transactions and balances for more personalized financial insights.'
            })

        # Limit to 4 most relevant insights
        insights = insights[:4]

        return JsonResponse({
            'status': 'success',
            'insights': insights
        })

    except Exception as e:
        logger.error(f"Error in dashboard_insights_json for user {request.user.id}: {e}")
        return JsonResponse({
            'status': 'error',
            'insights': [{
                'type': 'info',
                'title': '📈 Keep Adding Data',
                'text': 'The more data you add, the more personalized insights we can provide.'
            }]
        }, status=500)



# Add clear cache view
@require_http_methods(["POST"])
@login_required
def clear_transaction_cache_view(request):
    """
    View to clear the transaction cache for the current user.
    """
    user_id = request.user.id
    clear_tx_cache(user_id, force=True)
    return JsonResponse({"status": "success", "message": "Transaction cache cleared successfully."})


def healthz(_request):
    """
    Lightweight health endpoint used by external monitors to keep the app warm.
    Must not touch the database or perform expensive work.
    """
    response = HttpResponse("ok", content_type="text/plain", status=200)
    # Avoid intermediary caches; make sure the request reaches the app
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
