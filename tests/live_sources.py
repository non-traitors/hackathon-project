"""Live health check of every curated source page (needs internet, no API key).

Run before the demo:  .venv313/bin/python -m pytest tests/live_sources.py -s
Official sites move pages; a failure here means a seed URL in sources.yaml is stale.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import pipeline  # noqa: E402

CFG = pipeline.load_config()


def _all_seeds():
    out = []
    for key, school in CFG["schools"].items():
        allowed = CFG["federal"] + school["domains"]
        urls = [u for lst in CFG["seeds"]["federal"].values() for u in lst]
        urls += [u for lst in school.get("seeds", {}).values() for u in lst]
        out += [(u, tuple(allowed)) for u in dict.fromkeys(urls)]
    return list(dict.fromkeys(out))


@pytest.mark.parametrize("url,allowed", _all_seeds())
def test_seed_page_is_readable(url, allowed):
    pipeline._cache.pop(url, None)
    doc = pipeline._fetch_one(url, list(allowed))
    assert doc is not None, f"unreadable or moved: {url}"
    print(f"\n{len(doc['text']):6} chars  date={doc['date']}  {url[8:80]}")
    assert len(doc["text"]) >= 500, f"almost empty page: {url}"
