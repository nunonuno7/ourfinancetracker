from django.conf import settings

class CSPMiddleware:
    """Apply Content Security Policy headers based on settings."""

    def __init__(self, get_response):
        self.get_response = get_response
        directives = []
        for attr in dir(settings):
            if attr.startswith("CSP_"):
                directive = attr[4:].replace("_", "-").lower()
                sources = getattr(settings, attr)
                if isinstance(sources, (list, tuple, set)):
                    value = " ".join(sources)
                else:
                    value = sources
                directives.append(f"{directive} {value}")
        self.header_value = "; ".join(directives)

    def __call__(self, request):
        response = self.get_response(request)
        if self.header_value:
            response["Content-Security-Policy"] = self.header_value
        return response
