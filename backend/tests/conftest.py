import os

import pytest

from app.config_loader import load_app_config


@pytest.fixture(autouse=True)
def configure_test_env() -> None:
    os.environ.setdefault("GEMINI_MODEL_LOW", "gemini-2.5-flash")
    os.environ.setdefault("GEMINI_MODEL_MEDIUM", "gemini-2.5-flash")
    os.environ.setdefault("GEMINI_MODEL_HIGH", "gemini-2.5-pro")
    load_app_config.cache_clear()
    yield
    load_app_config.cache_clear()
