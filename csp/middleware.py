"""Lightweight middleware to emit a Content-Security-Policy header.

This project uses a very small subset of ``django-csp``.  The original
implementation simply exposed every ``CSP_*`` setting as a directive which
caused a couple of issues in production:

* helper settings such as ``CSP_NONCE_IN`` were turned into bogus directives
  (``nonce-in``);
* boolean directives like ``upgrade-insecure-requests`` were emitted with the
  string ``True`` as their value;
* there was no support for per-request nonces to allow safe inline code.

The middleware below fixes those problems while keeping the configuration
style used in the project.
"""

from secrets import token_urlsafe

from django.conf import settings


class CSPMiddleware:
    """Apply Content Security Policy headers based on settings."""

    def __init__(self, get_response):
        self.get_response = get_response

        # Collect all ``CSP_*`` settings that map directly to CSP directives.
        self._directive_settings = {}
        for attr in dir(settings):
            if not attr.startswith("CSP_"):
                continue
            # Helper settings that shouldn't become directives
            if attr in {"CSP_NONCE_IN", "CSP_INCLUDE_NONCE_IN", "CSP_UPGRADE_INSECURE_REQUESTS"}:
                continue
            directive = attr[4:].replace("_", "-").lower()
            self._directive_settings[directive] = getattr(settings, attr)

        # ``CSP_NONCE_IN`` is the canonical setting, but support the old
        # ``CSP_INCLUDE_NONCE_IN`` for backwards compatibility.
        nonce_in = list(getattr(settings, "CSP_NONCE_IN", []))
        nonce_in += list(getattr(settings, "CSP_INCLUDE_NONCE_IN", []))
        self._nonce_directives = {
            d.replace("_", "-").lower() for d in nonce_in
        }

    def _build_header(self, nonce: str | None) -> str:
        directives: list[str] = []
        for directive, value in self._directive_settings.items():
            # Boolean directives are included without a value when True.
            if isinstance(value, bool):
                if value:
                    directives.append(directive)
                continue

            if isinstance(value, (list, tuple, set)):
                sources = list(value)
            else:
                sources = [value]

            if nonce and directive in self._nonce_directives:
                sources.append(f"'nonce-{nonce}'")

            directives.append(f"{directive} {' '.join(sources)}".strip())

        flag = getattr(settings, "CSP_UPGRADE_INSECURE_REQUESTS", False)
        if flag is True:
            directives.append("upgrade-insecure-requests")

        return "; ".join(directives)

    def __call__(self, request):
        nonce = None
        if self._nonce_directives:
            nonce = token_urlsafe(16)
            request.csp_nonce = nonce

        header_value = self._build_header(nonce)

        response = self.get_response(request)
        if header_value:
            response["Content-Security-Policy"] = header_value
        return response
