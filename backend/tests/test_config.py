import os
from pathlib import Path

from app.config import _load_env_file


def test_load_env_file_sets_values_without_overriding_environment():
    env_file = Path(__file__).parent / "fixtures" / "config.env"
    os.environ.pop("NEW_SETTING", None)
    os.environ["EXISTING_SETTING"] = "from-process"

    try:
        _load_env_file(env_file)
        assert os.environ["NEW_SETTING"] == "from file"
        assert os.environ["EXISTING_SETTING"] == "from-process"
    finally:
        os.environ.pop("NEW_SETTING", None)
        os.environ.pop("EXISTING_SETTING", None)
