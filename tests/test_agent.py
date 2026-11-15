import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

import agent
import pipeline

CFG = pipeline.load_config()


# ------------------------------------------------------- catalog, links, fetch
def test_catalog_covers_school_and_federal_once():
    cat = agent.catalog("msu", CFG)
    urls = [c["url"] for c in cat]
    assert len(urls) == len(set(urls))
    assert cat[0]["scope"] == "school"
    emp = next(c for c in cat if c["url"] == "https://oiss.isp.msu.edu/students/current-students/employment")
    assert set(emp["topics"]) == {"oncampus", "opt", "stem_opt"}
    assert not any("uchicago" in u for u in urls)


def test_extract_links_keeps_only_allowlisted():
    html = (
        '<a href="/i-765">Form I-765</a><a href="https://evil.com/x">bad</a>'
        '<a href="https://www.uscis.gov/i-765#fees">dup</a><a href="mailto:a@b.c">m</a>'
        '<a href="https://uscis.gov.evil.com/">spoof</a>'
    )
    links = agent.extract_links(html, "https://www.uscis.gov/opt", ["uscis.gov"])
    assert links == [{"url": "https://www.uscis.gov/i-765", "text": "Form I-765"}]


def test_extract_links_caps_at_40():
    html = "".join(f'<a href="/p{i}">p{i}</a>' for i in range(100))
    assert len(agent.extract_links(html, "https://www.uscis.gov/", ["uscis.gov"])) == 40


def test_fetch_rejects_redirect_off_allowlist(monkeypatch):
    class R:
        status_code, url, content, text, headers = 200, "https://evil.com/", b"x", "<p>x</p>", {}

    monkeypatch.setattr("requests.get", lambda *a, **k: R())
    agent._cache.clear()
    assert agent.fetch("https://www.uscis.gov/a", ["uscis.gov"]) is None


def test_fetch_returns_text_and_links(monkeypatch):
    class R:
        status_code, url, content, headers = 200, "https://www.uscis.gov/a", b"x", {"content-type": "text/html"}
        text = '<title>A page</title><p>Fees apply.</p><a href="/g-1055">Fee schedule</a>'

    monkeypatch.setattr("requests.get", lambda *a, **k: R())
    agent._cache.clear()
    doc = agent.fetch("https://www.uscis.gov/a", ["uscis.gov"])
    assert doc["title"] == "A page" and "Fees apply." in doc["text"] and doc["date"] is None
    assert doc["links"] == [{"url": "https://www.uscis.gov/g-1055", "text": "Fee schedule"}]
