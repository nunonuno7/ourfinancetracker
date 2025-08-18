import string

import pytest
from django.urls import reverse
from hypothesis import HealthCheck, given, settings, strategies as st


@pytest.mark.django_db
@given(
    username=st.text(alphabet=string.ascii_letters + string.digits, max_size=20),
    password=st.text(alphabet=string.ascii_letters + string.digits, max_size=50),
)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_login_fuzz(client, settings, username, password):
    settings.SECURE_SSL_REDIRECT = False
    response = client.post(
        reverse("accounts:login"), {"username": username, "password": password}
    )
    assert response.status_code < 500


@pytest.mark.django_db
def test_login_sql_injection_attempt(client, settings):
    settings.SECURE_SSL_REDIRECT = False
    payload = "' OR '1'='1"
    response = client.post(reverse("accounts:login"), {"username": payload, "password": payload})
    assert response.status_code == 200
    assert client.session.get("_auth_user_id") is None
