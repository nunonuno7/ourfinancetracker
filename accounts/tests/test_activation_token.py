import pytest
from django.contrib.auth.models import User
from accounts.tokens import generate_activation_token, validate_activation_token, revoke_activation_token


@pytest.mark.django_db
def test_activation_token_cycle():
    user = User.objects.create_user(username="u1", password="pw", email="u1@example.com", is_active=False)
    token = generate_activation_token(user)
    assert validate_activation_token(user, token)
    revoke_activation_token(user)
    assert not validate_activation_token(user, token)
