from unittest.mock import patch
import smtplib
import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.core import mail
from django.core.mail import BadHeaderError
from django.urls import reverse

from core.utils.email_helpers import (
    send_account_activation_email,
    send_template_email,
)


@pytest.mark.django_db
def test_send_template_email_failure():
    with patch("core.utils.email_helpers.render_to_string", return_value="body"):
        with patch(
            "core.utils.email_helpers.send_mail",
            side_effect=smtplib.SMTPException("fail"),
        ):
            success = send_template_email(
                "subject", "template.html", {}, ["to@example.com"], fail_silently=True
            )
    assert not success


@pytest.mark.django_db
def test_send_account_activation_email_failure():
    user = User.objects.create(username="u", email="u@example.com")
    request = RequestFactory().get("/")
    with patch("core.utils.email_helpers.render_to_string", return_value="body"):
        with patch(
            "core.utils.email_helpers.reverse", return_value="/activate/"
        ):
            with patch(
                "core.utils.email_helpers.send_mail",
                side_effect=BadHeaderError("bad"),
            ):
                success = send_account_activation_email(user, request)
    assert not success


@pytest.mark.django_db
def test_send_account_activation_email_success():
    user = User.objects.create_user(username="alice", email="alice@example.com", password="x")
    request = RequestFactory().get("/")
    assert send_account_activation_email(user, request)
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.subject == "Activate your account"
    assert email.to == ["alice@example.com"]
    assert "activate" in email.body.lower()


@pytest.mark.django_db
def test_password_reset_email(client):
    user = User.objects.create_user(username="bob", email="bob@example.com", password="secret")
    response = client.post(reverse('accounts:password_reset'), {"email": "bob@example.com"})
    assert response.status_code in (302, 200)
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert "reset your password" in email.subject.lower()
    assert email.to == ["bob@example.com"]


@pytest.mark.django_db
@patch('core.utils.email_helpers.render_to_string', return_value='Error: boom')
def test_send_error_email_via_template(mock_render):
    send_template_email('Error', 'error_email.txt', {'message': 'boom'}, ['dev@example.com'])
    assert len(mail.outbox) == 1
    email = mail.outbox[0]
    assert email.subject == 'Error'
    assert email.to == ['dev@example.com']
    assert 'boom' in email.body
