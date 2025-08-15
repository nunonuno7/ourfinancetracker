import re
from pathlib import Path

import pytest

TEMPLATE_DIRS = [
    Path('accounts/templates'),
    Path('core/templates'),
]

def iter_templates():
    for base in TEMPLATE_DIRS:
        for path in base.rglob('*.html'):
            if 'emails' in path.parts:
                continue
            yield path

@pytest.mark.parametrize('template_path', list(iter_templates()))
def test_no_inline_styles_or_unsafe_scripts(template_path):
    content = template_path.read_text()
    assert 'style="' not in content, f'inline style attribute found in {template_path}'
    # Check inline <script> tags have nonce
    for match in re.finditer(r'<script(?![^>]*\bsrc=)[^>]*>', content, re.IGNORECASE):
        tag = match.group(0)
        assert 'nonce=' in tag, f'missing nonce in script tag in {template_path}'
    # Check inline <style> tags have nonce
    for match in re.finditer(r'<style[^>]*>', content, re.IGNORECASE):
        tag = match.group(0)
        assert 'nonce=' in tag, f'missing nonce in style tag in {template_path}'
