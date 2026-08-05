#!/usr/bin/env python3
"""
Team Howe Reddit Watch - command line entry point.

    python3 cli.py crawl      fetch reddit, score, save state
    python3 cli.py build      regenerate the dashboard and the RSS feed
    python3 cli.py alerts     email any new hot threads we have not emailed yet
    python3 cli.py digest     email the weekly digest
    python3 cli.py run        crawl + build + alerts   (what the schedule runs)
    python3 cli.py test       score the bundled samples, no network needed
    python3 cli.py mark-seen  treat everything currently tracked as already
                              alerted, so the next alert email only contains
                              genuinely new threads

Options:
    --config PATH     default config.json
    --keywords PATH   default keywords.json
    --data PATH       default data/posts.json
    --out DIR         default docs
    --dry-run         do everything except actually send mail
    --quiet
"""

from __future__ import print_function

import argparse
import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from watcher import asana, crawl, dashboard, emails, feeds, mailer  # noqa: E402
from watcher.store import Store  # noqa: E402


def load_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Team Howe Reddit Watch")
    parser.add_argument("command",
                        choices=["crawl", "build", "alerts", "digest", "run", "test",
                                 "mark-seen"])
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--keywords", default=os.path.join(HERE, "keywords.json"))
    parser.add_argument("--data", default=os.path.join(HERE, "data", "posts.json"))
    parser.add_argument("--out", default=os.path.join(HERE, "docs"))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = load_json(args.config)
    keywords = load_json(args.keywords)
    verbose = not args.quiet
    store = Store(args.data)

    def say(*parts):
        if verbose:
            print(*parts)

    if args.command == "test":
        return _selftest(config, keywords, verbose)

    if args.command == "mark-seen":
        # Useful right after setup, or after lowering a threshold: the backlog
        # already sitting in the store is not news, and a 20-thread "reply now"
        # email is worse than no email. The dashboard still shows all of it.
        pending = [r["id"] for r in store.posts() if not store.already_alerted(r["id"])]
        store.mark_alerted(pending)
        store.save()
        say("Marked {} tracked thread(s) as already alerted. "
            "Alerts now only fire for threads found from here on.".format(len(pending)))
        return 0

    exit_code = 0

    if args.command in ("crawl", "run"):
        say("Crawling {} subreddit(s)...".format(len(config.get("subreddits", []))))
        stats, new_records = crawl.run(config, keywords, store, verbose=verbose)
        store.save()
        say("")
        say("  fetched {}   kept {}   new {}   hot {}   leads {}".format(
            stats["fetched"], stats["kept"], stats["new"], stats["hot"], stats["leads"]))
        say("  transports: {}".format(stats["transport_counts"]))
        if stats["subreddits_failed"]:
            say("  no data from: {}".format(", ".join(stats["subreddits_failed"])))
        if not stats["subreddits_ok"]:
            print("ERROR: every subreddit failed - reddit is refusing this IP.",
                  file=sys.stderr)
            for line in stats["fetch_log"][:6]:
                print("  " + line, file=sys.stderr)
            exit_code = 2
        _write_status(args.out, stats)

    if args.command in ("build", "run"):
        result = dashboard.build(config, store, os.path.join(args.out, "index.html"))
        say("Dashboard: {} ({} threads, {} hot)".format(
            result["path"], result["posts"], result["hot"]))
        feed = feeds.build(config, store, os.path.join(args.out, "feed.xml"))
        say("Feed:      {} ({} items)".format(feed["path"], feed["items"]))

    if args.command in ("alerts", "run"):
        pending = [r for r in store.posts()
                   if r.get("verdict") == "hot" and not store.already_alerted(r["id"])]
        pending.sort(key=lambda r: -r.get("relevance", 0))
        if not pending:
            say("Alerts:    nothing new to send")
        else:
            recipients = config.get("email", {}).get("alert_recipients", [])
            subject, html_body, text_body = emails.hot_alert(config, pending)
            if args.dry_run or not recipients or not config.get("email", {}).get("enabled", True):
                say("Alerts:    {} thread(s) ready; not sent ({}).".format(
                    len(pending),
                    "dry run" if args.dry_run else "no recipients / email disabled"))
                _dump_preview(args.out, "preview-alert.html", html_body, say)
            else:
                try:
                    sent = mailer.send(subject, html_body, text_body, recipients,
                                       config["email"].get("from_name", "Team Howe Reddit Watch"))
                    store.mark_alerted([r["id"] for r in pending])
                    store.save()
                    say("Alerts:    emailed {} thread(s) to {} recipient(s)".format(
                        len(pending), sent))
                except mailer.MailNotConfigured as exc:
                    say("Alerts:    not sent - {}".format(exc))
                    _dump_preview(args.out, "preview-alert.html", html_body, say)
            outcome = asana.push(config, pending)
            if "created" in outcome and outcome["created"]:
                say("Asana:     created {} task(s)".format(outcome["created"]))

    if args.command == "digest":
        records = store.posts()
        subject, html_body, text_body = emails.weekly_digest(config, records)
        recipients = config.get("email", {}).get("digest_recipients", [])
        if args.dry_run or not recipients or not config.get("email", {}).get("enabled", True):
            say("Digest:    built; not sent ({}).".format(
                "dry run" if args.dry_run else "no recipients / email disabled"))
            _dump_preview(args.out, "preview-digest.html", html_body, say)
        else:
            try:
                sent = mailer.send(subject, html_body, text_body, recipients,
                                   config["email"].get("from_name", "Team Howe Reddit Watch"))
                say("Digest:    emailed to {} recipient(s)".format(sent))
            except mailer.MailNotConfigured as exc:
                say("Digest:    not sent - {}".format(exc))
                _dump_preview(args.out, "preview-digest.html", html_body, say)

    return exit_code


def _dump_preview(out_dir, name, html_body, say):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(html_body)
    say("           preview written to {}".format(path))


def _write_status(out_dir, stats):
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(os.path.join(out_dir, "status.json"), "w", encoding="utf-8") as handle:
        json.dump({
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "last_run": stats,
        }, handle, indent=1)


def _selftest(config, keywords, verbose):
    """Score the bundled sample pages - proves parsing and scoring offline."""
    from watcher import transports
    from watcher.scoring import Scorer, classify

    samples = os.path.join(HERE, "samples")
    if not os.path.isdir(samples):
        print("No samples/ directory to test against.", file=sys.stderr)
        return 1

    scorer = Scorer(keywords, config.get("geo_terms", []))
    groups = []
    checks = []

    rss_path = os.path.join(samples, "new.rss")
    if os.path.exists(rss_path):
        with open(rss_path, encoding="utf-8") as handle:
            parsed = transports.parse_listing_rss(handle.read(), "sanfrancisco")
        checks.append(("listing RSS", len(parsed)))
        groups.append(parsed)

    for name, sub in (("old_new.html", "sanfrancisco"), ("old_asksf.html", "AskSF")):
        path = os.path.join(samples, name)
        if os.path.exists(path):
            with open(path, encoding="utf-8", errors="replace") as handle:
                parsed = transports.parse_old_listing(handle.read(), sub)
            checks.append(("old listing " + sub, len(parsed)))
            groups.append(parsed)

    search_path = os.path.join(samples, "old_search.html")
    if os.path.exists(search_path):
        with open(search_path, encoding="utf-8", errors="replace") as handle:
            parsed = transports.parse_old_search(handle.read())
        checks.append(("old search", len(parsed)))
        groups.append(parsed)

    merged = transports.merge(*groups)
    print("Parser check")
    for label, count in checks:
        flag = "ok " if count else "FAIL"
        print("  [{}] {:<22} {:>4} posts".format(flag, label, count))
    print("  merged unique posts: {}".format(len(merged)))

    kept = []
    for post in merged:
        result = scorer.score(post)
        verdict = classify(result, config.get("thresholds", {}))
        if verdict != "skip":
            kept.append((result["relevance"], verdict, result["is_lead"], post, result))
    kept.sort(key=lambda row: -row[0])

    print("")
    print("Scoring check - {} of {} posts crossed the threshold".format(len(kept), len(merged)))
    for relevance, verdict, is_lead, post, result in kept[:15]:
        print("  {:>3}  {:<5} {:<5} r/{:<16} {}".format(
            relevance, verdict, "LEAD" if is_lead else "", post.get("subreddit", "?"),
            (post.get("title") or "")[:64]))
        if verbose:
            print("        {}".format(", ".join(result["hits"][:6])))

    print("")
    print("Rejected sample (should look off-topic):")
    for post in merged:
        result = scorer.score(post)
        if classify(result, config.get("thresholds", {})) == "skip":
            print("   {:>3}  {}".format(result["relevance"], (post.get("title") or "")[:70]))
    return 0 if any(count for _, count in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
