from decimal import Decimal
from django.db import models
from django.core.cache import cache
from . import Currency, get_default_currency


class FxRate(models.Model):
    """Daily FX rate between two currencies."""

    date = models.DateField()
    base = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="fx_base_rates")
    quote = models.ForeignKey(Currency, on_delete=models.CASCADE, related_name="fx_quote_rates")
    rate = models.DecimalField(max_digits=20, decimal_places=6)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["date", "base", "quote"], name="unique_fx_rate")
        ]
        ordering = ("-date", "base__code", "quote__code")

    def __str__(self):
        return f"{self.date} {self.base.code}/{self.quote.code} {self.rate}"

    @classmethod
    def get_rate(cls, date, base: Currency, quote: Currency) -> Decimal:
        """Retrieve FX rate for given date and currency pair.

        Falls back to EUR intermediate conversions when direct pair is missing.
        Results are cached for a day.
        """
        if base == quote:
            return Decimal("1")

        cache_key = f"fx:{date}:{base.code}:{quote.code}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        eur = get_default_currency()
        if base == eur:
            obj = cls.objects.get(date=date, base=eur, quote=quote)
            rate = obj.rate
        elif quote == eur:
            obj = cls.objects.get(date=date, base=eur, quote=base)
            rate = Decimal("1") / obj.rate
        else:
            rate = cls.get_rate(date, base, eur) * cls.get_rate(date, eur, quote)

        cache.set(cache_key, rate, 86400)
        return rate


def convert_amount(amount: Decimal, from_currency: Currency, to_currency: Currency, date) -> Decimal:
    """Convert an amount between currencies using FxRate."""
    if from_currency == to_currency or amount == 0:
        return amount
    rate = FxRate.get_rate(date, from_currency, to_currency)
    return (amount * rate).quantize(Decimal("0.01"))
