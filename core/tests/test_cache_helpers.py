import pytest
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from core.utils.cache_helpers import clear_tx_cache, get_cache_key_for_transactions
from datetime import date


@pytest.mark.django_db
def test_clear_tx_cache_removes_keys():
    key = get_cache_key_for_transactions(1, date.today().replace(day=1), date.today())
    cache.set(key, 'value')
    clear_tx_cache(1, force=True)
    assert cache.get(key) is None


def test_clear_tx_cache_handles_missing_keys():
    mock_cache = MagicMock()
    mock_cache.get.return_value = None
    mock_cache.delete.side_effect = KeyError
    with patch('core.utils.cache_helpers.cache', mock_cache):
        clear_tx_cache(2, force=True)
    assert mock_cache.delete.call_count > 0
