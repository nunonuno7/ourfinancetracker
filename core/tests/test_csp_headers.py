import re
from django.urls import get_resolver, URLPattern, URLResolver
import pytest


def iter_paths():
    resolver = get_resolver()

    def walk(patterns, prefix=""):
        for pattern in patterns:
            if isinstance(pattern, URLPattern):
                if not hasattr(pattern.pattern, "_route"):
                    continue
                route = prefix + pattern.pattern._route
                if '<' in route:
                    continue
                path = '/' + route.lstrip('/')
                yield path
            elif isinstance(pattern, URLResolver):
                if not hasattr(pattern.pattern, "_route"):
                    continue
                yield from walk(pattern.url_patterns, prefix + pattern.pattern._route)
    for p in walk(resolver.url_patterns):
        if p.startswith('/admin') or p.startswith('/__'):
            continue
        if any(skip in p for skip in ('export', 'json-v2')):
            continue
        yield p


@pytest.mark.django_db
@pytest.mark.parametrize('path', list(iter_paths()))
def test_csp_header_present(client, django_user_model, path):
    user = django_user_model.objects.create_user(username='u', password='p')
    client.force_login(user)
    response = client.get(path)
    assert 'Content-Security-Policy' in response.headers, f'No CSP on {path}'
    csp = response.headers['Content-Security-Policy']
    assert "default-src 'self'" in csp
    assert re.search(r"script-src[^;]*'nonce-", csp)
    assert re.search(r"style-src[^;]*'nonce-", csp)
    assert 'nonce-in' not in csp
    assert "'unsafe-inline'" not in csp
    assert 'upgrade-insecure-requests' in csp
