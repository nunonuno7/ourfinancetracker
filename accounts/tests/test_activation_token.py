import pytest
from django.contrib.auth.models import User
from accounts.tokens import activation_token_generator


@pytest.mark.django_db
def test_activation_token_invalid_after_activation():
    user = User.objects.create_user(
        username="u1", password="pw", email="u1@example.com", is_active=False
    )
    token = activation_token_generator.make_token(user)
    assert activation_token_generator.check_token(user, token)
    user.is_active = True
    user.save()
    assert not activation_token_generator.check_token(user, token)
