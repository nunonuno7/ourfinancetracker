from django.urls import reverse
import pytest

@pytest.mark.django_db
def test_get_goals_requires_login(client):
    r = client.get(reverse("kpi_goals_get"))
    assert r.status_code in (302, 403)

@pytest.mark.django_db
def test_update_goals_happy_path(client, django_user_model):
    user = django_user_model.objects.create_user("u","u@x.com","p")
    client.force_login(user)
    r = client.post(reverse("kpi_goals_update"), {"kpi_key":"avg_income","goal":"2500","mode":"closest"})
    assert r.status_code == 200
    assert r.json()["kpi_goals"]["avg_income"]["goal"] == 2500.0
