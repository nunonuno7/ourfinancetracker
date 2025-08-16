import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_login_logout_csrf_flow():
    user = User.objects.create_user('user', password='secret')
    client = Client(enforce_csrf_checks=True)
    login_url = reverse('accounts:login')
    resp = client.get(login_url)
    csrf_token = resp.cookies['csrftoken'].value
    resp = client.post(login_url, {'username': 'user', 'password': 'secret'})
    assert resp.status_code == 403
    resp = client.post(login_url, {'username': 'user', 'password': 'secret', 'csrfmiddlewaretoken': csrf_token}, HTTP_REFERER='http://testserver/')
    assert resp.status_code in (302, 303)
    csrf_token = client.cookies['csrftoken'].value
    logout_url = reverse('accounts:logout')
    resp = client.post(logout_url, {'csrfmiddlewaretoken': csrf_token}, HTTP_REFERER='http://testserver/')
    assert resp.status_code in (302, 303)


@pytest.mark.django_db
def test_anonymous_redirected_from_protected_page(client):
    resp = client.get(reverse('accounts:profile'))
    assert resp.status_code == 302
    assert reverse('accounts:login') in resp['Location']
