import os
import base64
from django.conf import settings


class CSPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # per-request nonce
        nonce = base64.b64encode(os.urandom(16)).decode("ascii")
        request.csp_nonce = nonce

        response = self.get_response(request)

        # Build policy from settings.* (whitelist known directives only)
        policy = {
            "default-src": getattr(settings, "CSP_DEFAULT_SRC", ("'self'",)),
            "script-src": getattr(settings, "CSP_SCRIPT_SRC", ("'self'",)),
            "style-src": getattr(settings, "CSP_STYLE_SRC", ("'self'",)),
            "img-src": getattr(settings, "CSP_IMG_SRC", ("'self'", "data:")),
            "connect-src": getattr(settings, "CSP_CONNECT_SRC", ("'self'",)),
            "font-src": getattr(settings, "CSP_FONT_SRC", ("'self'", "data:")),
            "frame-src": getattr(settings, "CSP_FRAME_SRC", ()),
        }

        # Conditionally add the nonce to script/style src lists
        include_nonce_in = getattr(settings, "CSP_INCLUDE_NONCE_IN", ["script-src", "style-src"])
        for key in include_nonce_in:
            if key in policy:
                policy[key] = tuple(policy[key]) + (f"'nonce-{nonce}'",)

        # Assemble header string (semicolon-separated). DO NOT add any bogus tokens like 'nonce-in'.
        csp_parts = []
        for directive, sources in policy.items():
            if sources:
                csp_parts.append(f"{directive} {' '.join(sources)}")

        # Add 'upgrade-insecure-requests' as a valueless directive when enabled
        flag = getattr(settings, "CSP_UPGRADE_INSECURE_REQUESTS", False)
        if flag is True:
            csp_parts.append("upgrade-insecure-requests")

        # Set header
        if csp_parts:
            response.headers["Content-Security-Policy"] = "; ".join(csp_parts)

        return response
