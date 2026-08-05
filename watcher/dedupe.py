"""
Crosspost folding.

The same Chronicle article gets submitted to r/bayarea and r/BayAreaRealEstate
within minutes, as two different posts with two different IDs. Showing both is
just noise, so records that are clearly the same story are folded into one -
the highest-scoring copy wins, and the others become an "also in r/..." note
with their own links kept.

Two records are the same story when either
  * they point at the same external URL (query strings stripped), or
  * their titles normalise to the same string.
"""

import re
import urllib.parse

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_STOP = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "is",
    "are", "was", "were", "be", "this", "that", "it", "its", "with", "from",
    "by", "as", "has", "have", "could", "would", "will", "new",
}


def _norm_title(title):
    text = _PUNCT.sub(" ", (title or "").lower())
    words = [w for w in text.split() if w and w not in _STOP]
    return " ".join(words[:12])


def _norm_url(url):
    if not url or not url.startswith("http"):
        return ""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        if "reddit.com" in host or "redd.it" in host:
            return ""
        path = parts.path.rstrip("/")
        return host + path
    except Exception:
        return ""


def fold(records):
    """Return records with crossposts merged, original order/score preserved."""
    ordered = sorted(
        records,
        key=lambda r: (-(r.get("relevance") or 0), -(r.get("created_utc") or 0)),
    )
    keepers = []
    by_url = {}
    by_title = {}

    for record in ordered:
        url_key = _norm_url(record.get("external_url"))
        title_key = _norm_title(record.get("title"))

        primary = None
        if url_key and url_key in by_url:
            primary = by_url[url_key]
        elif title_key and title_key in by_title:
            primary = by_title[title_key]

        if primary is None:
            copy = dict(record)
            copy["also_in"] = []
            keepers.append(copy)
            if url_key:
                by_url[url_key] = copy
            if title_key:
                by_title[title_key] = copy
            continue

        primary["also_in"].append({
            "subreddit": record.get("subreddit"),
            "permalink": record.get("permalink"),
            "comments": record.get("comments"),
            "score": record.get("score"),
        })
        # A story two subreddits picked up is worth slightly more attention, and
        # whichever copy has the liveliest thread is the one worth replying in.
        for field in ("comments", "score"):
            mine, theirs = primary.get(field), record.get(field)
            if theirs is not None and (mine is None or theirs > mine):
                primary[field] = theirs
        if record.get("verdict") == "hot":
            primary["verdict"] = "hot"
        if record.get("is_lead"):
            primary["is_lead"] = True

    return keepers
