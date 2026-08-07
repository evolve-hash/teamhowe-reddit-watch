"""
Orchestrates one crawl: fetch every configured subreddit through every enabled
transport, merge, score, filter, and write the result into the store.
"""

from __future__ import print_function

import time
from datetime import datetime, timezone

from . import transports
from .scoring import Scorer, classify


def run(config, keywords, store, verbose=True, neighborhoods=None):
    crawler = config.get("crawler", {})
    thresholds = config.get("thresholds", {})
    fetcher = transports.Fetcher(
        user_agent=crawler.get("user_agent", "TeamHoweRedditWatch/1.0"),
        delay=crawler.get("delay_seconds", 2.5),
        timeout=crawler.get("timeout_seconds", 25),
        retries=crawler.get("retries", 3),
        mirrors=crawler.get("mirrors", []),
        rate_budget=crawler.get("rate_limit_budget_seconds", 150),
        # Falls back to the refresh Worker, which is already deployed and free,
        # when reddit refuses this runner's address directly.
        proxy_base=(crawler.get("proxy_base")
                    or config.get("site", {}).get("refresh_endpoint", "")),
        proxy_first=crawler.get("proxy_first", True),
    )
    scorer = Scorer(keywords, config.get("geo_terms", []), neighborhoods,
                    config.get("sf_proof_terms", []))
    max_age = thresholds.get("max_post_age_days", 21)
    cutoff = transports.now_utc() - max_age * 86400

    # Reddit throttles an unauthenticated datacenter IP after roughly seven
    # requests, and it always throttled the SAME tail of the list - measured on
    # a real GitHub run, subreddits 6..12 never once got fetched. So the list is
    # split: the subreddits marked "always" are fetched every run, and the rest
    # rotate a couple at a time. Core coverage stays at the schedule interval,
    # the long tail comes round every hour or so, and no run gets throttled.
    subreddit_plan = _plan_subreddits(config, store, crawler)

    all_sweeps = config.get("search_sweeps", [])
    per_run = int(crawler.get("search_sweeps_per_run", 4) or 0)
    if all_sweeps and 0 < per_run < len(all_sweeps):
        cursor = int(store.state.get("sweep_cursor", 0)) % len(all_sweeps)
        doubled = all_sweeps + all_sweeps
        sweep_terms = doubled[cursor:cursor + per_run]
        store.state["sweep_cursor"] = (cursor + per_run) % len(all_sweeps)
    else:
        sweep_terms = all_sweeps

    started = time.time()
    stats = {
        "subreddits_ok": 0,
        "subreddits_failed": [],
        "fetched": 0,
        "considered": 0,
        "kept": 0,
        "new": 0,
        "hot": 0,
        "leads": 0,
        "transport_counts": {"rss": 0, "old_html": 0, "old_search": 0,
                             "pullpush": 0},
        "sweeps_this_run": list(sweep_terms),
        "subreddits_this_run": [e.get("name") for e in subreddit_plan],
        "subreddits_configured": len(config.get("subreddits", [])),
    }
    new_records = []

    if verbose:
        print("Crawling {} of {} subreddit(s) this run...".format(
            len(subreddit_plan), len(config.get("subreddits", []))))

    for entry in subreddit_plan:
        name = entry.get("name")
        scope = entry.get("scope") or "all"
        if not name:
            continue

        groups = []
        ok = False

        if crawler.get("use_listing_rss", True):
            xml = fetcher.get(transports.listing_rss_url(name))
            parsed = transports.parse_listing_rss(xml, name) if xml else []
            if parsed:
                ok = True
                stats["transport_counts"]["rss"] += len(parsed)
            groups.append(parsed)

        # pullpush is keyless and returns body, score and comment count in one
        # request, so it is worth asking before the HTML scrapers. It is a free
        # community service though, so a failure is logged and shrugged off.
        if crawler.get("use_pullpush", True):
            payload = fetcher.get(transports.pullpush_listing_url(
                name, since_days=max_age))
            parsed = transports.parse_pullpush(payload, name) if payload else []
            if parsed:
                ok = True
                stats["transport_counts"]["pullpush"] += len(parsed)
            groups.append(parsed)

        old_listing = transports.old_listing_url(name)
        if crawler.get("use_old_reddit_html", True) and not fetcher.blocked(old_listing):
            html = fetcher.get(old_listing)
            parsed = transports.parse_old_listing(html, name) if html else []
            if parsed:
                ok = True
                stats["transport_counts"]["old_html"] += len(parsed)
            groups.append(parsed)

        if (crawler.get("use_search_sweeps", True) and scope in ("all", "bay")
                and not fetcher.blocked(transports.old_search_url(name, "x"))):
            for term in sweep_terms:
                html = fetcher.get(transports.old_search_url(name, term))
                parsed = transports.parse_old_search(html) if html else []
                if parsed:
                    ok = True
                    stats["transport_counts"]["old_search"] += len(parsed)
                    for post in parsed:
                        post.setdefault("subreddit", name)
                        post["found_via"] = term
                groups.append(parsed)

        merged = transports.merge(*groups)
        stats["fetched"] += len(merged)
        if ok:
            stats["subreddits_ok"] += 1
        else:
            stats["subreddits_failed"].append(name)

        if verbose:
            print("  r/{:<22} {:>4} posts   {}".format(
                name, len(merged), "ok" if ok else "NO DATA",
            ))

        for post in merged:
            created = post.get("created_utc")
            if created and created < cutoff:
                continue
            stats["considered"] += 1

            result = scorer.score(post)
            if scope == "geo" and not result["matched_geo"]:
                continue
            verdict = classify(result, thresholds)
            if verdict == "skip":
                continue

            # Bay-wide subreddits. r/BayAreaRealEstate is where somebody asks
            # "Monterey county - has anyone bought from Nino Homes in King
            # City?", and that thread was arriving flagged HOT LEAD. Requiring
            # San Francisco proof outright would be too blunt - half those
            # threads name no city at all and some of them are SF sellers - so
            # instead a thread with nothing tying it to the city can still be
            # listed, but it cannot be a lead and it cannot sit at the top of
            # Sherri's page ahead of a thread that IS demonstrably SF.
            unplaced = False
            if scope == "bay" and not result["matched_geo"]:
                unplaced = True
                result["is_lead"] = False
                verdict = "watch"

            record = _record(post, result, verdict, name)
            record["unplaced"] = unplaced
            saved = store.upsert(record)
            stats["kept"] += 1
            if saved.get("is_new"):
                stats["new"] += 1
                new_records.append(saved)
            if verdict == "hot":
                stats["hot"] += 1
            if result["is_lead"]:
                stats["leads"] += 1

    removed = store.prune(config.get("dashboard", {}).get("history_days", 60))
    stats["pruned"] = removed
    stats["duration_seconds"] = round(time.time() - started, 1)
    stats["finished_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stats["blocked_hosts"] = dict(fetcher.blocked_hosts)
    stats["rate_limited"] = fetcher.rate_limited
    stats["rate_limit_wait_seconds"] = round(fetcher.rate_waited, 1)
    stats["fetch_log"] = fetcher.log[-30:]
    stats["proxy_base"] = fetcher.proxy_base or ""
    # A run that reaches nothing still "succeeds" - it just republishes what was
    # already stored. That is exactly how a two day old dashboard managed to
    # look current. Say so explicitly, and let the page say so too.
    stats["healthy"] = stats["subreddits_ok"] > 0
    if stats["healthy"]:
        store.state["last_successful_crawl"] = stats["finished_at"]
    stats["last_successful_crawl"] = store.state.get("last_successful_crawl")
    store.record_run(stats)
    return stats, new_records


def _plan_subreddits(config, store, crawler):
    """Which subreddits this run touches: the 'always' ones plus a rotating slice."""
    entries = []
    for entry in config.get("subreddits", []):
        if isinstance(entry, dict):
            entries.append(dict(entry))
        elif entry:
            entries.append({"name": str(entry), "scope": "all"})

    core = [e for e in entries if e.get("always")]
    tail = [e for e in entries if not e.get("always")]
    per_run = int(crawler.get("rotating_per_run", 2) or 0)

    if not tail or per_run <= 0:
        return core or entries
    if per_run >= len(tail):
        return core + tail

    cursor = int(store.state.get("subreddit_cursor", 0)) % len(tail)
    slice_ = (tail + tail)[cursor:cursor + per_run]
    store.state["subreddit_cursor"] = (cursor + per_run) % len(tail)
    return core + slice_


def _record(post, result, verdict, subreddit):
    body = (post.get("body") or "").strip()
    return {
        "id": post["id"],
        "subreddit": post.get("subreddit") or subreddit,
        "title": post.get("title") or "(untitled)",
        "author": post.get("author") or "unknown",
        "author_url": "https://www.reddit.com/user/{}".format(post.get("author"))
                      if post.get("author") else None,
        "permalink": post.get("permalink"),
        "created_utc": post.get("created_utc"),
        "score": post.get("score"),
        "comments": post.get("comments"),
        "domain": post.get("domain") or "",
        "external_url": post.get("external_url") or "",
        "flair": post.get("flair") or "",
        "excerpt": _excerpt(body),
        "has_body": bool(body),
        "relevance": result["relevance"],
        "is_lead": result["is_lead"],
        "verdict": verdict,
        "hits": result["hits"],
        "tiers": result["tiers"],
        "neighborhoods": result.get("neighborhoods") or [],
        "out_of_area": result.get("out_of_area") or [],
        "found_via": post.get("found_via"),
        "sources": post.get("sources") or post.get("source") or "",
        "first_seen": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _excerpt(body, limit=340):
    if not body:
        return ""
    text = " ".join(body.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."
