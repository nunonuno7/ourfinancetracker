import pytest
from django.urls import reverse
from django.core.cache import cache


@pytest.mark.django_db
def test_login_rate_limit(client, settings):
    """Blocks login after exceeding the attempt limit."""
    settings.AXES_ENABLED = False
    middleware = list(settings.MIDDLEWARE)
    idx = middleware.index("axes.middleware.AxesMiddleware")
    middleware.insert(idx, "core.middleware.rate_limiting.RateLimitMiddleware")
    settings.MIDDLEWARE = middleware
    cache.clear()
    url = reverse("accounts:login")
    data = {"username": "tester", "password": "wrong"}
    for _ in range(5):
        client.post(url, data)
    response = client.post(url, data)
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests"


@pytest.mark.django_db
def test_signup_rate_limit(client, settings):
    """Blocks signup after exceeding the attempt limit."""
    settings.AXES_ENABLED = False
    middleware = list(settings.MIDDLEWARE)
    idx = middleware.index("axes.middleware.AxesMiddleware")
    middleware.insert(idx, "core.middleware.rate_limiting.RateLimitMiddleware")
    settings.MIDDLEWARE = middleware
    cache.clear()
    url = reverse("accounts:signup")
    data = {}
    for _ in range(5):
        client.post(url, data)
    response = client.post(url, data)
    assert response.status_code == 429
    assert response.json()["detail"] == "Too many requests"
