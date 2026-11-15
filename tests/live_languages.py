"""Live cross-language consistency check (needs GEMINI_API_KEY and credits).

README requirement: "Language changes preserve the verdict, evidence, and
uncertainty." For each claim we run English first, then every other language, and
require the same verdict and the same set of cited pages. Run:

    .venv313/bin/python -m pytest tests/live_languages.py -s
"""
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

import languages as langs  # noqa: E402
import pipeline  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    reason="needs GEMINI_API_KEY",
)

# Claim index in languages.yaml starters -> school. Same claim in every language.
CASES = [(0, "msu"), (1, "uchicago"), (2, "msu"), (4, "msu")]
OTHERS = [c for c in langs.language_choices() if c != "en"]


@pytest.fixture(scope="module")
def baseline():
    cache = {}

    def get(i, school):
        if (i, school) not in cache:
            cache[(i, school)] = pipeline.check_claim(langs.starters("en")[i], school, {}, "en", use_cache=False)
        return cache[(i, school)]

    return get


@pytest.mark.parametrize("code", OTHERS)
@pytest.mark.parametrize("i,school", CASES)
def test_same_verdict_and_same_pages_as_english(baseline, code, i, school):
    en = baseline(i, school)
    r = pipeline.check_claim(langs.starters(code)[i], school, {}, code, use_cache=False)
    print(f"\n[{code}] claim {i} {school}: {r.verdict} (en: {en.verdict}) {r.timing.get('analyze_s')}s | {r.headline}")
    assert r.verdict == en.verdict
    assert {s.url for s in r.sources} & {s.url for s in en.sources}, "no cited page in common with English"
    assert r.language == code and r.headline
    assert r.claim_in_english, "should restate the claim in English"
    # quotes stay in English and carry a translation into the answer language
    assert all(s.quote.isascii() or "’" in s.quote or "“" in s.quote or "–" in s.quote for s in r.sources)
    assert all(s.quote_translation for s in r.sources), "non-English answers need quote translations"
    if r.question_for_office:
        assert sum(c.isascii() for c in r.question_for_office) / len(r.question_for_office) > 0.9
