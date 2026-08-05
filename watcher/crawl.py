"""
Orchestrates one crawl: fetch every configured subreddit through every enabled
transport, merge, score, filter, and write the result into the store.
"""

from __future__ import print_function

import time
from datetime import datetime, timezone

from . import transports
from .scoring import Scorer, classify


def run(config, keywords, store, verbose=True):
    crawler = config.get("crawler", {})
    thresholds = config.get("thresholds", {})
    fetcher = transports.Fetcher(
        user_agent=crawler.get("user_agent", "TeamHoweRedditWatch/1.0"),
        delay=crawler.get("delay_seconds", 2.5),
        timeout=crawler.get("timeout_seconds", 25),
        retries=crawler.get("retries", 3),
        mirrors=crawler.get("mirrors", []),
        rate_budget=crawler.get("rate_limit_budget_seconds", 150),
    )
    scorer = Scorer(keywords, config.get("geo_terms", []))
    max_age = thresholds.get("max_post_age_days", 21)
    cutoff = transports.now_utc() - max_age * 86400

    # Searching every term against every subreddit on every run would be ~190
    # requests each time - rude to reddit and slow. Instead each run takes the
    # next slice of the sweep list and remembers where it stopped, so the whole
    # list is still covered, just spread over a few runs.
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
        "transport_counts": {"rss": 0, "old_html": 0, "old_search": 0},
        "sweeps_this_run": list(sweep_terms),
    }
    new_records = []

    for entry in config.get("subreddits", []):
        name = entry.get("name") if isinstance(entry, dict) else str(entry)
        scope = (entry.get("scope") if isinstance(entry, dict) else "all") or "all"
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

        old_listing = transports.old_listing_url(name)
        if crawler.get("use_old_reddit_html", True) and not fetcher.blocked(old_listing):
            html = fetcher.get(old_listing)
            parsed = transports.parse_old_listing(html, name) if html else []
            if parsed:
                ok = True
                stats["transport_counts"]["old_html"] += len(parsed)
            groups.append(parsed)

        if (crawler.get("use_search_sweeps", True) and scope == "all"
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

            record = _record(post, result, verdict, name)
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
    store.record_run(stats)
    return stats, new_records


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
        "found_via": post.get("found_via"),
        "sources": post.get("sources") or post.get("source") or "",
        "first_seen": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }


def _excerpt(body, limit=340):
    if not body:
        return ""
    text = " ".join(body.split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "..."
