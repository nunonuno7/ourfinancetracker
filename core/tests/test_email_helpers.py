import smtplib
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.test import RequestFactory
from django.core.mail import BadHeaderError

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
