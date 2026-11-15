"""The project runs as a website: Streamlit serves it, and a host supplies the keys.

These tests need no network and no API key.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from streamlit.testing.v1 import AppTest

import pipeline
import speech
import theme

ROOT = Path(__file__).parent.parent
APP = str(ROOT / "app.py")


def _config():
    tomllib = pytest.importorskip("tomllib")  # Python 3.11+
    return tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())


def test_server_settings_suit_a_public_website():
    cfg = _config()
    assert cfg["server"]["headless"] is True  # a host has no terminal to answer prompts
    assert cfg["server"]["enableStaticServing"] is True  # serves the bundled fonts
    assert cfg["browser"]["gatherUsageStats"] is False
    assert cfg["client"]["toolbarMode"] == "viewer"  # no developer menu or Deploy button
    assert cfg["client"]["showErrorDetails"] == "none"  # no stack traces for visitors
    assert cfg["theme"]["base"] == "light"


def test_bundled_fonts_exist_where_the_stylesheet_points():
    css = theme.css()
    for name in ("noto-sans-latin.woff2", "noto-serif-latin.woff2"):
        assert f"app/static/fonts/{name}" in css
        assert (ROOT / "static" / "fonts" / name).is_file()


def test_page_is_a_responsive_column_not_a_phone_frame():
    css = theme.css()
    assert "max-width:680px" in css and "max-width:480px" not in css
    assert "@media (min-width: 720px)" in css  # wider screens get the two-column starters


def test_runtime_requirements_leave_out_the_tests():
    runtime = (ROOT / "requirements.txt").read_text()
    dev = (ROOT / "requirements-dev.txt").read_text()
    assert "pytest" not in runtime and "streamlit" in runtime and "google-genai" in runtime
    assert "-r requirements.txt" in dev and "pytest" in dev


def test_keys_from_the_hosts_secrets_reach_the_environment(monkeypatch):
    """On Streamlit Community Cloud the keys are secrets, not environment variables."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(speech, "available", lambda: False)
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["GEMINI_API_KEY"] = "gemini-from-secrets"
    at.secrets["ELEVENLABS_API_KEY"] = "voice-from-secrets"
    at.run()
    assert not at.exception
    assert os.environ["GEMINI_API_KEY"] == "gemini-from-secrets"
    assert os.environ["ELEVENLABS_API_KEY"] == "voice-from-secrets"


def test_an_environment_key_wins_over_a_secret(monkeypatch):
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(pipeline, "warm_pages", lambda *a, **k: 0)
    monkeypatch.setattr(speech, "available", lambda: False)
    monkeypatch.setenv("GEMINI_API_KEY", "from-environment")
    at = AppTest.from_file(APP, default_timeout=30)
    at.secrets["GEMINI_API_KEY"] = "from-secrets"
    at.run()
    assert os.environ["GEMINI_API_KEY"] == "from-environment"
