#!/usr/bin/env python3
"""
Which way into reddit still works from a GitHub runner?

Context: on 2026-08-07 a scheduled run came back with subreddits_ok: 0 and
blocked_hosts {old.reddit.com: 403, www.reddit.com: 403}. Reddit refuses
unauthenticated requests from datacenter address space, and GitHub's hosted
runners live in exactly that address space. The crawl was "succeeding" while
fetching nothing, so the dashboard kept re-publishing a two day old store.

This script is a measurement, not a fix. It asks every candidate route the same
question - can you hand me reddit posts from here - and writes down the answer
so the transport chain is built on data instead of on a guess.

Run it where the crawler runs (the workflow calls it), read probe-results.txt.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BOT_UA = ("TeamHoweRedditWatch/1.0 (SF real estate monitoring; "
          "contact evolve@teamhowe.com)")

SUB = "sanfrancisco"
WORKER = os.environ.get("REFRESH_ENDPOINT", "").rstrip("/")

REDDIT_RSS = "https://www.reddit.com/r/{}/new/.rss?limit=100".format(SUB)
OLD_LISTING = "https://old.reddit.com/r/{}/new/?limit=100".format(SUB)


def via_worker(target):
    if not WORKER:
        return None
    return "{}/fetch?url={}".format(WORKER, urllib.parse.quote(target, safe=""))


CANDIDATES = [
    # (label, url, user_agent)
    ("reddit rss / bot UA", REDDIT_RSS, BOT_UA),
    ("reddit rss / browser UA", REDDIT_RSS, BROWSER_UA),
    ("reddit rss no-slash", "https://www.reddit.com/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("old.reddit listing", OLD_LISTING, BROWSER_UA),
    ("old.reddit rss", "https://old.reddit.com/r/{}/new/.rss".format(SUB), BROWSER_UA),
    ("old.reddit search", "https://old.reddit.com/search/?q=" +
        urllib.parse.quote_plus("subreddit:{} should i buy".format(SUB)) +
        "&sort=new&t=month&restrict_sr=on", BROWSER_UA),

    # Keyless third-party archives and mirrors.
    ("pullpush submissions", "https://api.pullpush.io/reddit/search/submission/"
        "?subreddit={}&size=25".format(SUB), BROWSER_UA),
    ("pullpush full-text", "https://api.pullpush.io/reddit/search/submission/"
        "?q=%22san+francisco%22+house&size=25", BROWSER_UA),
    ("redlib catsarch", "https://redlib.catsarch.com/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("redlib perennialte", "https://redlib.perennialte.ch/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("redlib privacyredirect", "https://redlib.privacyredirect.com/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("safereddit", "https://safereddit.com/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("opnxng", "https://l.opnxng.com/r/{}/new.rss".format(SUB), BROWSER_UA),
    ("rsshub", "https://rsshub.app/reddit/subreddit/{}/new".format(SUB), BROWSER_UA),
    ("jina reader -> reddit rss", "https://r.jina.ai/" + REDDIT_RSS, BROWSER_UA),

    # Search engines that index reddit, as a last-resort discovery channel.
    ("bing rss site:", "https://www.bing.com/search?q=" +
        urllib.parse.quote_plus("site:reddit.com/r/{} house".format(SUB)) +
        "&format=rss", BROWSER_UA),
    ("google news rss", "https://news.google.com/rss/search?q=" +
        urllib.parse.quote_plus("site:reddit.com san francisco housing"), BROWSER_UA),

    # The Cloudflare Worker he already pays nothing for, used as a fetch proxy.
    ("WORKER -> reddit rss", via_worker(REDDIT_RSS), BROWSER_UA),
    ("WORKER -> old.reddit listing", via_worker(OLD_LISTING), BROWSER_UA),
    ("WORKER -> old.reddit search", via_worker(
        "https://old.reddit.com/search/?q=" +
        urllib.parse.quote_plus("subreddit:{} should i buy".format(SUB)) +
        "&sort=new&t=month&restrict_sr=on"), BROWSER_UA),
]


def usable(body):
    """Rough count of how many reddit posts this response actually contains."""
    if not body:
        return 0
    return max(
        body.count("<entry>"),
        body.count('data-fullname="t3_'),
        body.count('"id":'),
        body.count("reddit.com/r/"),
    )


def probe(label, url, agent):
    if not url:
        return {"label": label, "status": "SKIPPED (no worker endpoint set)"}
    request = urllib.request.Request(url, headers={
        "User-Agent": agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    started = time.time()
    try:
        response = urllib.request.urlopen(request, timeout=30)
        body = response.read().decode("utf-8", errors="replace")
        return {
            "label": label, "url": url, "status": response.getcode(),
            "bytes": len(body), "posts": usable(body),
            "seconds": round(time.time() - started, 1),
            "sample": " ".join(body[:180].split()),
        }
    except urllib.error.HTTPError as exc:
        return {"label": label, "url": url, "status": exc.code,
                "bytes": 0, "posts": 0,
                "seconds": round(time.time() - started, 1),
                "sample": (exc.reason or "")[:80]}
    except Exception as exc:
        return {"label": label, "url": url, "status": type(exc).__name__,
                "bytes": 0, "posts": 0,
                "seconds": round(time.time() - started, 1),
                "sample": str(exc)[:120]}


def main():
    results = []
    for label, url, agent in CANDIDATES:
        result = probe(label, url, agent)
        results.append(result)
        print("{:<32} {:>6}  posts={:<4} {}".format(
            label, str(result.get("status")), result.get("posts", 0),
            result.get("sample", "")[:70]))
        sys.stdout.flush()
        time.sleep(2)

    lines = ["Transport probe from a GitHub Actions runner",
             "Generated: " + time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
             "Worker endpoint: " + (WORKER or "(not set)"),
             "",
             "{:<32} {:>8} {:>8} {:>7}  {}".format(
                 "ROUTE", "STATUS", "BYTES", "POSTS", "NOTE"),
             "-" * 100]
    for result in results:
        lines.append("{:<32} {:>8} {:>8} {:>7}  {}".format(
            result["label"], str(result.get("status")), result.get("bytes", 0),
            result.get("posts", 0), result.get("sample", "")[:44]))
    winners = [r for r in results if r.get("posts", 0) >= 5
               and str(r.get("status")) == "200"]
    lines += ["", "USABLE ROUTES: " + (", ".join(w["label"] for w in winners) or "NONE")]

    with open("probe-results.txt", "w") as handle:
        handle.write("\n".join(lines) + "\n")
    with open("probe-results.json", "w") as handle:
        json.dump(results, handle, indent=1)
    print("\n".join(lines[-2:]))


if __name__ == "__main__":
    main()
