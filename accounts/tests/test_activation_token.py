import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.tokens import generate_activation_token, validate_activation_token


@pytest.mark.django_db
def test_activation_token_invalid_after_login():
    user = User.objects.create_user(
        username="u1", password="pw", email="u1@example.com", is_active=False
    )
    token = generate_activation_token(user)
    assert validate_activation_token(user, token)

    # Simulate a login which updates ``last_login`` and invalidates the token.
    user.last_login = timezone.now()
    user.save(update_fields=["last_login"])

    assert not validate_activation_token(user, token)
