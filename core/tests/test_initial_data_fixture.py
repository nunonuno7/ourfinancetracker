import json
from pathlib import Path


def test_initial_data_fixture_is_valid_json():
    fixture_path = Path("core/fixtures/initial_data.json")
    with fixture_path.open() as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert all("model" in item for item in data)
