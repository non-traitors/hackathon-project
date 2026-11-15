"""Shared test setup."""
import pytest


@pytest.fixture(autouse=True)
def _single_check_mode(monkeypatch):
    """The older app tests cover the single-check screens, which stay as the USE_CHAT=0 mode.
    Tests of the chat set USE_CHAT=1 themselves."""
    monkeypatch.setenv("USE_CHAT", "0")
