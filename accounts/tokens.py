"""Activation token utilities.

This module wraps Django's ``PasswordResetTokenGenerator`` for generating
and validating account activation links. The generator uses user state and a
timestamp to create time-sensitive tokens without needing any server-side
storage.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator


_activation_token_generator = PasswordResetTokenGenerator()


def generate_activation_token(user) -> str:
    """Return a time-sensitive activation token for ``user``."""

    return _activation_token_generator.make_token(user)


def validate_activation_token(user, token: str) -> bool:
    """Validate ``token`` for ``user`` using Django's built-in generator."""

    return _activation_token_generator.check_token(user, token)

