"""
Tiered relevance scoring.

TJ's requirement: catch posts that are about real estate even when nobody
writes the words "real estate" - somebody dropping a Chronicle link, somebody
asking "should I buy in the Sunset", somebody quoting "$1.4M, 3bd/2ba".

So a post is scored across independent tiers (see keywords.json):

    intent        strong first-person buy/sell signals   -> also flags a LEAD
    transaction   escrow, contingency, closing costs...
    market        prices, rates, inventory, HOA...
    sf_specific   TIC, Ellis Act, soft story, Prop 13...
    neighborhoods Noe Valley, Outer Sunset, Sea Cliff...
    domains       sfchronicle.com, socketsite.com, zillow.com...
    patterns      regex for prices, bed/bath, sq ft, rates
    negative      roommate / sublet / job / burrito posts  -> subtracts

Each tier scores its weight once, plus 25% of the weight for every additional
distinct phrase in that tier, capped at double. That way a post that says
"realtor" six times doesn't outrank a post that genuinely spans several tiers.
"""

import re

_WORD_EDGE = r"(?:^|[^a-z0-9])"


class Scorer(object):
    def __init__(self, keywords, geo_terms=None):
        self.tiers = []
        for key, tier in keywords.items():
            if key.startswith("_") or not isinstance(tier, dict):
                continue
            terms = [t.lower() for t in tier.get("terms", [])]
            regexes = [re.compile(r, re.I) for r in tier.get("regex", [])]
            if not terms and not regexes:
                continue
            self.tiers.append({
                "key": key,
                "label": tier.get("label", key.title()),
                "weight": float(tier.get("weight", 1)),
                "lead": bool(tier.get("lead", False)),
                "terms": terms,
                "regexes": regexes,
            })
        self.geo_terms = [g.lower() for g in (geo_terms or [])]

    # ------------------------------------------------------------------ api --
    def score(self, post):
        """Return a dict of scoring results for one post dict."""
        haystack = self._haystack(post)
        total = 0.0
        penalty = 0.0
        hits = []
        by_tier = {}
        is_lead = False

        for tier in self.tiers:
            found = []
            for term in tier["terms"]:
                if self._contains(haystack, term):
                    found.append(term)
            for regex in tier["regexes"]:
                match = regex.search(haystack)
                if match:
                    snippet = match.group(0).strip()
                    if snippet and snippet.lower() not in [f.lower() for f in found]:
                        found.append(snippet)

            if not found:
                continue

            weight = tier["weight"]
            extra = min(len(found) - 1, 4) * 0.25 * abs(weight)
            contribution = weight + (extra if weight > 0 else -extra)
            if contribution < 0:
                penalty += contribution
            else:
                total += contribution
            by_tier[tier["key"]] = {
                "label": tier["label"],
                "hits": found[:8],
                "count": len(found),
                "points": round(contribution, 1),
            }
            hits.extend(found[:6])
            if tier["lead"]:
                is_lead = True

        # A lead phrase without a first-person voice is usually somebody
        # answering, not asking. Keep it relevant, drop the lead flag.
        if is_lead and not self._first_person(haystack):
            is_lead = False

        # A rental signal beats an intent signal. "Renter's agent - looking for
        # an agent to help me find a place" reads as a lead to a keyword matcher
        # and is worthless to a listing agent, so when the rental tier fires the
        # lead flag comes off and the full penalty stands.
        if penalty and "negative" in by_tier:
            is_lead = False
        total += penalty

        return {
            "relevance": int(round(max(total, 0))),
            "raw_score": round(total, 1),
            "is_lead": is_lead,
            "hits": _dedupe(hits)[:12],
            "tiers": by_tier,
            "matched_geo": self.mentions_geo(post),
        }

    def mentions_geo(self, post):
        haystack = self._haystack(post)
        return any(term in haystack for term in self.geo_terms)

    # -------------------------------------------------------------- helpers --
    @staticmethod
    def _haystack(post):
        parts = [
            post.get("title") or "",
            post.get("body") or "",
            post.get("flair") or "",
            post.get("domain") or "",
            post.get("external_url") or "",
        ]
        return (" " + " \n ".join(parts).lower() + " ")

    @staticmethod
    def _contains(haystack, term):
        if not term:
            return False
        # Domains and anything with punctuation match as plain substrings.
        if any(ch in term for ch in "./@&"):
            return term in haystack
        return re.search(
            _WORD_EDGE + re.escape(term) + r"(?:$|[^a-z0-9])", haystack
        ) is not None

    @staticmethod
    def _first_person(haystack):
        return re.search(
            r"(?:^|[^a-z])(?:i|i'm|im|i've|ive|my|we|we're|were|our|us|me|"
            r"anyone|anybody|looking for|need|help|recommend|advice|thoughts|"
            r"should i|should we|has anyone|does anyone)(?:$|[^a-z])",
            haystack,
        ) is not None


def _dedupe(items):
    seen = set()
    out = []
    for item in items:
        key = item.lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def classify(result, thresholds):
    """'hot' | 'watch' | 'skip' for one scoring result."""
    relevance = result["relevance"]
    if relevance < thresholds.get("include_score", 8):
        return "skip"
    if relevance >= thresholds.get("hot_score", 24):
        return "hot"
    if result["is_lead"] and thresholds.get("alert_on_lead", True):
        return "hot"
    return "watch"
