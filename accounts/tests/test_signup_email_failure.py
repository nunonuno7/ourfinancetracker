import smtplib
from unittest.mock import patch

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_signup_email_failure(client, settings):
    settings.DEBUG = True
    settings.SECURE_SSL_REDIRECT = False
    data = {
        "username": "newuser",
        "email": "newuser@example.com",
        "password": "password123",
    }
    with patch("accounts.views.send_mail", side_effect=smtplib.SMTPException("fail")):
        response = client.post(reverse("accounts:signup"), data)
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert any("error sending the activation email" in str(m) for m in messages)
