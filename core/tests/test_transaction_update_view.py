from datetime import date
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from core.models import Transaction


@pytest.mark.django_db
def test_transaction_update_missing_redirects_back_to_list_with_message(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="update-user", password="p")
    client.force_login(user)

    response = client.get(reverse("transaction_update", args=[999999]), follow=True)

    assert response.redirect_chain == [(reverse("transaction_list_v2"), 302)]
    assert response.status_code == 200

    messages = [message.message for message in get_messages(response.wsgi_request)]
    assert any("no longer exists" in message for message in messages)
    assert "transaction_changed" not in client.session
    assert b"window.transactionListShouldForceRefresh = true;" in response.content


@pytest.mark.django_db
def test_transaction_update_missing_logs_diagnostic_context(
    client, django_user_model, caplog
):
    user = django_user_model.objects.create_user(username="update-log-user", password="p")
    client.force_login(user)

    with caplog.at_level("WARNING", logger="core.views"):
        client.get(reverse("transaction_update", args=[999999]))

    assert "Unavailable transaction edit access:" in caplog.text
    assert "'transaction_pk': 999999" in caplog.text
    assert "'exists_for_current_user': False" in caplog.text
    assert "'exists_for_other_user': False" in caplog.text


@pytest.mark.django_db
def test_transaction_update_missing_ajax_returns_redirect_url(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="update-ajax-user", password="p"
    )
    client.force_login(user)

    response = client.get(
        reverse("transaction_update", args=[999999]),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": "The transaction no longer exists or is no longer available.",
        "redirect_url": reverse("transaction_list_v2"),
    }


@pytest.mark.django_db
def test_transaction_update_other_users_transaction_logs_permission_context(
    client, django_user_model, caplog
):
    owner = django_user_model.objects.create_user(username="owner-log-user", password="p")
    other_user = django_user_model.objects.create_user(
        username="other-log-user", password="p"
    )
    transaction = Transaction.objects.create(
        user=owner,
        date=date(2024, 1, 10),
        amount=Decimal("20.00"),
        type=Transaction.Type.EXPENSE,
    )
    client.force_login(other_user)

    with caplog.at_level("WARNING", logger="core.views"):
        client.get(reverse("transaction_update", args=[transaction.pk]))

    assert "Unavailable transaction edit access:" in caplog.text
    assert f"'transaction_pk': {transaction.pk}" in caplog.text
    assert "'exists_for_current_user': False" in caplog.text
    assert "'exists_for_other_user': True" in caplog.text


@pytest.mark.django_db
def test_stale_list_edit_flow_redirects_and_forces_fresh_reload(
    client, django_user_model
):
    user = django_user_model.objects.create_user(
        username="stale-flow-user", password="p"
    )
    transaction = Transaction.objects.create(
        user=user,
        date=date(2024, 1, 10),
        amount=Decimal("45.67"),
        type=Transaction.Type.EXPENSE,
    )
    transaction_id = transaction.pk
    client.force_login(user)

    params = {"date_start": "2024-01-01", "date_end": "2024-12-31"}

    initial_list_response = client.get(reverse("transactions_json_v2"), params)
    assert initial_list_response.status_code == 200
    initial_ids = [tx["id"] for tx in initial_list_response.json()["transactions"]]
    assert transaction_id in initial_ids

    transaction.delete()

    stale_list_response = client.get(reverse("transactions_json_v2"), params)
    assert stale_list_response.status_code == 200
    stale_ids = [tx["id"] for tx in stale_list_response.json()["transactions"]]
    assert transaction_id in stale_ids

    edit_response = client.get(
        reverse("transaction_update", args=[transaction_id]),
        follow=True,
    )

    assert edit_response.redirect_chain == [(reverse("transaction_list_v2"), 302)]
    assert edit_response.status_code == 200
    assert b"window.transactionListShouldForceRefresh = true;" in edit_response.content

    forced_list_response = client.get(
        reverse("transactions_json_v2"),
        {**params, "force": "true"},
    )
    assert forced_list_response.status_code == 200
    forced_ids = [tx["id"] for tx in forced_list_response.json()["transactions"]]
    assert transaction_id not in forced_ids


@pytest.mark.django_db
def test_transaction_list_v2_consumes_transaction_changed_flag(
    client, django_user_model
):
    user = django_user_model.objects.create_user(username="list-user", password="p")
    Transaction.objects.create(
        user=user,
        date=date(2024, 1, 10),
        amount=Decimal("12.34"),
        type=Transaction.Type.EXPENSE,
    )
    client.force_login(user)

    session = client.session
    session["transaction_changed"] = True
    session.save()

    response = client.get(reverse("transaction_list_v2"))

    assert response.status_code == 200
    assert b"window.transactionListShouldForceRefresh = true;" in response.content
    assert "transaction_changed" not in client.session
