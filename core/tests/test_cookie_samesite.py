import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_session_and_csrf_cookies_use_samesite_strict():
    user = User.objects.create_user('user', password='secret')
    client = Client(enforce_csrf_checks=True)

    login_url = reverse('accounts:login')
    resp = client.get(login_url)
    assert resp.cookies['csrftoken']['samesite'] == 'Strict'
    csrf_token = resp.cookies['csrftoken'].value

    resp = client.post(
        login_url,
        {'username': 'user', 'password': 'secret', 'csrfmiddlewaretoken': csrf_token},
        HTTP_REFERER='http://testserver/',
    )
    # login sets the session cookie
    assert resp.cookies['sessionid']['samesite'] == 'Strict'

