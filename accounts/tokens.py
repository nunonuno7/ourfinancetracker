from django.contrib.auth.tokens import PasswordResetTokenGenerator


class ActivationTokenGenerator(PasswordResetTokenGenerator):
    """Token generator that invalidates tokens once the user is activated."""

    def _make_hash_value(self, user, timestamp):  # type: ignore[override]
        return f"{user.pk}{timestamp}{user.is_active}"


activation_token_generator = ActivationTokenGenerator()
