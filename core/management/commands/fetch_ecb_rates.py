from datetime import date
from decimal import Decimal
import requests
from django.core.management.base import BaseCommand
from core.models import Currency, FxRate, get_default_currency


class Command(BaseCommand):
    help = "Fetch daily FX rates from the European Central Bank"

    def handle(self, *args, **options):
        base = get_default_currency()
        resp = requests.get("https://api.exchangerate.host/latest", params={"base": base.code})
        resp.raise_for_status()
        payload = resp.json()
        rate_date = date.fromisoformat(payload["date"])
        created = 0
        for code, rate in payload["rates"].items():
            if code == base.code:
                continue
            quote, _ = Currency.objects.get_or_create(code=code)
            FxRate.objects.update_or_create(
                date=rate_date,
                base=base,
                quote=quote,
                defaults={"rate": Decimal(str(rate))},
            )
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Fetched {created} rates for {rate_date}"))
