import logging

from django.http import HttpResponse
from django.test import override_settings
from django.urls import path
from django.conf import settings

from core.models import Currency


def nplus_one_view(request):
    ids = list(Currency.objects.values_list("id", flat=True))
    for i in ids:
        Currency.objects.get(id=i)
    return HttpResponse("ok")


urlpatterns = [path("nplus/", nplus_one_view)]


@override_settings(
    DEBUG=True,
    ROOT_URLCONF=__name__,
    MIDDLEWARE=[*settings.MIDDLEWARE, "core.middleware.performance.PerformanceMiddleware"],
)
def test_nplus_one_logging(client, caplog, db):
    Currency.objects.create(code="AAA")
    Currency.objects.create(code="BBB")

    with caplog.at_level(logging.WARNING, logger="core.performance"):
        response = client.get("/nplus/")
        assert response.status_code == 200

    assert any("N+1" in record.message for record in caplog.records)
