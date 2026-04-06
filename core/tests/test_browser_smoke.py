import os
import unittest
from datetime import date
from decimal import Decimal
from calendar import month_name
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.urls import reverse

RUN_BROWSER_SMOKE = os.environ.get("RUN_BROWSER_SMOKE") == "1"

if RUN_BROWSER_SMOKE:
    # Playwright's sync API keeps an event loop available on the current thread.
    # These smoke tests still exercise Django synchronously, so we relax the
    # async-safety guard for this test module only.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    playwright = pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import expect, sync_playwright  # noqa: E402
else:  # pragma: no cover - exercised only when browser smoke is disabled
    expect = None
    sync_playwright = None

from core.models import Account, AccountBalance, Category, DatePeriod, Transaction  # noqa: E402


@unittest.skipUnless(RUN_BROWSER_SMOKE, "browser smoke tests disabled")
class BrowserSmokeTests(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._playwright = sync_playwright().start()
        cls._browser = cls._playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls._browser.close()
        cls._playwright.stop()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.context = self._browser.new_context(
            base_url=self.live_server_url,
            viewport={"width": 1440, "height": 1080},
        )
        self.page = self.context.new_page()

    def tearDown(self):
        self.context.close()
        super().tearDown()

    def create_active_user(self, *, password="Pass12345!"):
        username = f"browser-{uuid4().hex[:8]}"
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password=password,
            is_active=True,
        )
        return user, password

    def create_transaction(
        self,
        *,
        user,
        account,
        category,
        period,
        amount,
        tx_type,
        tx_date=None,
    ):
        return Transaction.objects.create(
            user=user,
            account=account,
            category=category,
            period=period,
            date=tx_date or date(period.year, period.month, 1),
            amount=Decimal(str(amount)),
            type=tx_type,
        )

    def create_period(self, *, year, month, label=None):
        period, _ = DatePeriod.objects.get_or_create(
            year=year,
            month=month,
            defaults={"label": label or f"{month_name[month]} {year}"},
        )
        expected_label = label or f"{month_name[month]} {year}"
        if period.label != expected_label:
            period.label = expected_label
            period.save(update_fields=["label"])
        return period

    def set_account_balance(self, *, account, period, amount):
        balance, _ = AccountBalance.objects.update_or_create(
            account=account,
            period=period,
            defaults={"reported_balance": Decimal(str(amount))},
        )
        return balance

    def authenticate_browser(self, user):
        self.client.force_login(user)
        session_cookie = self.client.cookies[settings.SESSION_COOKIE_NAME]
        self.context.add_cookies(
            [
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session_cookie.value,
                    "url": self.live_server_url,
                }
            ]
        )

    def skip_if_sqlite_live_server_ajax(self, feature_name):
        if connection.vendor == "sqlite":
            self.skipTest(
                f"{feature_name} browser smoke test requires PostgreSQL because "
                "SQLite live-server runs are unstable with concurrent AJAX requests."
            )

    def test_transactions_page_filters_expenses(self):
        self.skip_if_sqlite_live_server_ajax("Transactions filter")

        user, password = self.create_active_user()
        account = Account.objects.create(user=user, name="Browser Wallet")
        expense_category = Category.objects.create(user=user, name="Groceries")
        income_category = Category.objects.create(user=user, name="Salary")
        period = DatePeriod.objects.create(year=2025, month=2, label="2025-02")

        self.create_transaction(
            user=user,
            account=account,
            category=expense_category,
            period=period,
            amount="45.00",
            tx_type=Transaction.Type.EXPENSE,
        )
        self.create_transaction(
            user=user,
            account=account,
            category=income_category,
            period=period,
            amount="2500.00",
            tx_type=Transaction.Type.INCOME,
            tx_date=date(2025, 2, 2),
        )

        self.authenticate_browser(user)
        self.page.goto(reverse("transaction_list_v2"))

        expect(self.page.locator("#transactions-tbody tr")).to_have_count(2)
        self.page.select_option("#filter-type", Transaction.Type.EXPENSE)
        expect(self.page.locator("#transactions-tbody tr")).to_have_count(1)

        body_text = self.page.locator("#transactions-tbody").inner_text()
        assert "Groceries" in body_text
        assert "Salary" not in body_text

    def test_account_balance_copy_previous_button_copies_balances(self):
        user, password = self.create_active_user()
        account = Account.objects.create(user=user, name="Browser Savings")
        previous_period = DatePeriod.objects.create(
            year=2025,
            month=1,
            label="January 2025",
        )
        AccountBalance.objects.create(
            account=account,
            period=previous_period,
            reported_balance=Decimal("1234.56"),
        )

        account_balance_path = f"{reverse('account_balance')}?year=2025&month=2"
        self.authenticate_browser(user)
        self.page.goto(account_balance_path)

        expect(self.page.locator("tr.form-row")).to_have_count(0)
        self.page.locator("#copy-previous-btn").click()
        expect(self.page.locator(".alert-success")).to_contain_text("Copied")
        expect(self.page.locator("tr.form-row")).to_have_count(1)
        expect(self.page.locator("tr.form-row")).to_contain_text("Browser Savings")

    def test_dashboard_period_link_opens_filtered_transactions(self):
        if connection.vendor == "sqlite":
            self.skipTest("Dashboard period smoke test requires PostgreSQL-backed SQL paths.")

        user, password = self.create_active_user()
        account = Account.objects.create(user=user, name="Browser Dashboard")
        category = Category.objects.create(user=user, name="Dining Out")
        period = DatePeriod.objects.create(year=2025, month=2, label="2025-02")

        self.create_transaction(
            user=user,
            account=account,
            category=category,
            period=period,
            amount="32.50",
            tx_type=Transaction.Type.EXPENSE,
        )

        dashboard_path = f"{reverse('dashboard')}?mode=period&period=2025-02"
        self.authenticate_browser(user)
        self.page.goto(dashboard_path)

        expect(self.page.get_by_text("Period Analysis")).to_be_visible()
        self.page.get_by_role("button", name="List").click()
        expect(self.page.locator("#list-view")).to_be_visible()
        self.page.get_by_role("link", name="View transactions").first.click()
        self.page.wait_for_url(lambda url: "/transactions/" in url)

        expect(self.page.locator("#filter-type")).to_have_value(Transaction.Type.EXPENSE)
        expect(self.page.locator("#filter-category")).to_have_value(str(category.id))
        expect(self.page.locator("#transactions-tbody tr")).to_have_count(1)
        expect(self.page.locator("#transactions-tbody")).to_contain_text("Dining Out")

    def test_estimation_page_can_create_an_estimated_transaction(self):
        self.skip_if_sqlite_live_server_ajax("Estimation")

        user, password = self.create_active_user()
        account = Account.objects.create(user=user, name="Browser Estimation Savings")
        period_march = self.create_period(year=2026, month=3)
        period_april = self.create_period(year=2026, month=4)

        self.set_account_balance(account=account, period=period_march, amount="1000")
        self.set_account_balance(account=account, period=period_april, amount="800")

        self.authenticate_browser(user)
        self.page.goto(reverse("estimate_transaction"))

        expect(self.page.locator("h2")).to_contain_text("Transaction Estimation")
        expect(self.page.locator("#year-filter")).to_have_value("2026")

        march_row = self.page.locator(f'tr[data-period-id="{period_march.id}"]')
        expect(march_row).to_contain_text("March 2026")
        expect(march_row).to_contain_text("Missing Expenses")

        self.page.evaluate("window.confirm = () => true;")
        march_row.locator(".estimate-btn").click()

        expect(self.page.locator(".toast")).to_contain_text(
            "Estimation completed for March 2026"
        )
        expect(march_row).to_contain_text("Balanced")
        expect(march_row.locator(".delete-estimated-btn")).to_have_count(1)

        assert Transaction.objects.filter(
            user=user,
            period=period_march,
            is_estimated=True,
            type=Transaction.Type.EXPENSE,
        ).exists()

    def test_import_button_opens_transaction_import_page(self):
        user, password = self.create_active_user()

        self.authenticate_browser(user)
        self.page.goto(reverse("transaction_list_v2"))
        self.page.locator("#import-btn").click()
        self.page.wait_for_url(lambda url: "import-excel" in url)

        expect(self.page.locator("h2")).to_contain_text("Import Transactions from Excel")
        expect(self.page.locator("#id_file")).to_be_visible()
        expect(self.page.get_by_role("link", name="Download Template")).to_be_visible()
