import pytest
from django.urls import reverse

from core.models import DatePeriod


@pytest.mark.django_db
def test_menu_config_returns_username_and_links(client, django_user_model):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.force_login(user)
    response = client.get(reverse("menu_config"))
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "u"
    assert any(link["name"] == "Dashboard" for link in data["links"])


@pytest.mark.django_db
def test_period_autocomplete_returns_matching_periods(client, django_user_model):
    user = django_user_model.objects.create_user(username="u", password="p")
    DatePeriod.objects.create(year=2024, month=1, label="2024-01")
    client.force_login(user)
    response = client.get(reverse("period_autocomplete"), {"term": "2024"})
    assert response.status_code == 200
    assert response.json() == ["2024-01"]
