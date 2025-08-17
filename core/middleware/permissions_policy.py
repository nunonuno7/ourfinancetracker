"""Middleware to set a restrictive Permissions-Policy header."""


class PermissionsPolicyMiddleware:
    """Add a default Permissions-Policy header to every response."""

    POLICY = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", self.POLICY)
        return response
