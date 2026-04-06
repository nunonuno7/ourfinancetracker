import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    "year,month,prev_year,prev_month,next_year,next_month",
    [
        (2026, 1, 2025, 12, 2026, 2),
        (2026, 12, 2026, 11, 2027, 1),
        (2026, 6, 2026, 5, 2026, 7),
    ],
)
def test_account_balance_prev_next_links_rollover_correctly(
    client,
    django_user_model,
    year,
    month,
    prev_year,
    prev_month,
    next_year,
    next_month,
):
    user = django_user_model.objects.create_user(username="u", password="p")
    client.force_login(user)

    response = client.get(reverse("account_balance"), {"year": year, "month": month})

    assert response.status_code == 200
    html = response.content.decode()
    assert f'href="?year={prev_year}&month={prev_month}"' in html
    assert f'href="?year={next_year}&month={next_month}"' in html


@pytest.mark.django_db
def test_account_balance_period_card_shows_first_day_of_selected_month(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="period-user", password="p")
    client.force_login(user)

    response = client.get(reverse("account_balance"), {"year": 2026, "month": 6})

    assert response.status_code == 200
    html = response.content.decode()
    assert '>1 Jun 2026<' in html
    assert 'type="month" id="selector" value="2026-06"' in html
