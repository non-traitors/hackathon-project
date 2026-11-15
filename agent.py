"""Bounded agent on top of the claim-checking pipeline.

The single-pass checker in pipeline.py reads a fixed set of pages chosen by
keyword. The agent decides for itself what to read: it plans which curated
official pages to open, may follow links from those pages while staying inside
the allowlist, and stops within fixed limits. What it may NOT decide on its own
is the answer: every quote still has to appear word for word in a page we
fetched, exactly as in pipeline.validate_output.

If anything in the agent fails, the claim is handed to pipeline.check_claim.
"""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

import pipeline

MAX_LINKS = 40  # links kept per page
LINK_TEXT_CHARS = 80


# ------------------------------------------------------- catalog, links, fetch
def allowed_hosts(school_key: str, config: dict) -> list[str]:
    return config["federal"] + config["schools"][school_key]["domains"]


def catalog(school_key: str, config: dict) -> list[dict]:
    """Every curated page for this school: school pages first, then federal."""
    entries: dict[str, dict] = {}
    groups = (
        ("school", config["schools"][school_key].get("seeds", {})),
        ("federal", config["seeds"]["federal"]),
    )
    for scope, by_topic in groups:
        for topic, urls in by_topic.items():
            for url in urls:
                entry = entries.setdefault(url, {"url": url, "topics": [], "scope": scope})
                if topic not in entry["topics"]:
                    entry["topics"].append(topic)
    return list(entries.values())


class _LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: Optional[str] = None
        self._text: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None


def extract_links(markup: str, base_url: str, allowed: list[str]) -> list[dict]:
    """Links on a page that stay inside the allowlist, in page order."""
    parser = _LinkExtractor()
    parser.feed(markup)
    base = urldefrag(base_url)[0]
    out: list[dict] = []
    seen = {base}
    for href, text in parser.links:
        url = urldefrag(urljoin(base_url, href.strip()))[0]
        if urlparse(url).scheme not in ("http", "https") or url in seen:
            continue
        if not pipeline._host_allowed(url, allowed):
            continue
        seen.add(url)
        label = re.sub(r"\s+", " ", text).strip()[:LINK_TEXT_CHARS]
        out.append({"url": url, "text": label})
        if len(out) == MAX_LINKS:
            break
    return out


_cache: dict[str, tuple[float, Optional[dict]]] = {}


def fetch(url: str, allowed: list[str]) -> Optional[dict]:
    """Fetch one allowlisted page: its text and its allowlisted links, or None.

    Same rules as pipeline._fetch_one; it also keeps the page's links so the
    agent can offer them to the model.
    """
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < pipeline.CACHE_TTL:
        return hit[1]
    doc = None
    try:
        import requests

        r = requests.get(url, headers={"User-Agent": pipeline.USER_AGENT}, timeout=pipeline.FETCH_TIMEOUT)
        # A redirect must not leave the allowlist.
        if (
            r.status_code == 200
            and pipeline._host_allowed(r.url, allowed)
            and len(r.content) <= pipeline.MAX_PAGE_BYTES
        ):
            ctype = r.headers.get("content-type", "").lower()
            if "pdf" in ctype or url.lower().endswith(".pdf"):
                title, text, links = Path(urlparse(url).path).name, pipeline._pdf_to_text(r.content), []
            else:
                title, text = pipeline.html_to_text(r.text)
                links = extract_links(r.text, r.url, allowed)
            if text:
                doc = {
                    "url": url,
                    "title": title or url,
                    "text": text[: pipeline.PAGE_CHARS],
                    "date": None,
                    "links": links,
                }
    except Exception:
        doc = None  # unreadable pages are simply not used as evidence
    _cache[url] = (time.time(), doc)
    return doc
