"""The design tokens and the stone, checked without running the app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import theme


@pytest.mark.parametrize("kind", list(theme.PILLS))
def test_every_verdict_pill_meets_aa_contrast(kind):
    background, text = theme.PILLS[kind]
    assert theme.contrast(text, background) >= 4.5, f"{kind}: {theme.contrast(text, background):.2f}"


def test_contrast_matches_the_wcag_reference_values():
    assert round(theme.contrast("#000000", "#FFFFFF"), 1) == 21.0
    assert round(theme.contrast("#FFFFFF", "#FFFFFF"), 1) == 1.0


def test_body_colors_meet_aa_on_the_page_and_on_the_highlighter():
    assert theme.contrast(theme.NAVY, "#FFFFFF") >= 4.5 and theme.contrast(theme.GRAY, "#FFFFFF") >= 4.5
    assert theme.contrast(theme.NAVY, theme.MARK) >= 4.5 and theme.contrast(theme.BLUE, "#FFFFFF") >= 4.5


def test_css_keeps_touch_targets_large_and_respects_reduced_motion():
    css = theme.css()
    assert "min-height:44px" in css and "prefers-reduced-motion" in css


def test_stone_is_decorative_and_takes_the_verdict_kind():
    html = theme.stone("contradicted", 56)
    assert 'aria-hidden="true"' in html and 'class="stone contradicted"' in html
    assert 'class="stone reading"' in theme.stone("reading", 160)
    assert 'class="stone"' in theme.stone(None, 72)


def test_latin_fonts_are_bundled_so_the_demo_does_not_depend_on_the_network():
    css = theme.css()
    root = Path(__file__).parent.parent
    for name in ("noto-sans-latin.woff2", "noto-serif-latin.woff2"):
        assert f"app/static/fonts/{name}" in css and (root / "static" / "fonts" / name).stat().st_size > 10_000
    assert "family=Noto+Sans:" not in theme.FONTS_URL and "family=Noto+Serif" not in theme.FONTS_URL
    assert "enableStaticServing = true" in (root / ".streamlit" / "config.toml").read_text()
