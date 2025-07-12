
from django.db import models
from decimal import Decimal

class MonthlySummary(models.Model):
    period = models.CharField(max_length=7, unique=True)   # 'YYYY-MM'
    investimentos      = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    despesas           = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    receitas_nao_lanc  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    despesas_ajustadas = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    updated_at         = models.DateTimeField(auto_now=True)
    is_dirty           = models.BooleanField(default=True)

    class Meta:
        ordering = ["period"]
        indexes  = [models.Index(fields=["is_dirty"])]

    def __str__(self):
        return f"Summary {self.period}"
