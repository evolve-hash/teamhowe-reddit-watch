#!/usr/bin/env python3
"""Writes the run summary that shows up on the Actions run page."""

import json
import os
import sys

STATUS = "docs/status.json"


def main():
    if not os.path.exists(STATUS):
        return 0
    try:
        with open(STATUS, "r", encoding="utf-8") as handle:
            run = json.load(handle)["last_run"]
    except Exception as exc:
        print("could not read {}: {}".format(STATUS, exc), file=sys.stderr)
        return 0

    lines = ["### Reddit Watch", "", "| | |", "|---|---|"]
    labels = [
        ("kept", "Threads matching"),
        ("new", "New since last run"),
        ("hot", "Worth a reply"),
        ("leads", "Possible clients"),
        ("fetched", "Posts fetched"),
        ("considered", "Posts scored"),
        ("subreddits_ok", "Subreddits answering"),
        ("duration_seconds", "Seconds taken"),
    ]
    for key, label in labels:
        lines.append("| {} | {} |".format(label, run.get(key)))

    blocked = run.get("blocked_hosts") or {}
    if blocked:
        lines += ["", "**Transports blocked from this runner's IP:** " + ", ".join(
            "`{}` ({})".format(host, why) for host, why in sorted(blocked.items()))]
        lines += ["", "This is expected on GitHub's servers - old.reddit.com refuses "
                      "datacenter IPs. The RSS transport carries the crawl; score and "
                      "comment counts are the only thing lost. Run it from a Mac "
                      "(`local/run_local.sh`) if you want those back."]
    if run.get("rate_limited"):
        lines += ["", "Reddit rate-limited {} request(s); the crawler slowed itself "
                      "down and retried.".format(run["rate_limited"])]

    sweeps = run.get("sweeps_this_run") or []
    if sweeps:
        lines += ["", "Search sweeps this run: " + ", ".join("`%s`" % s for s in sweeps)]

    failed = run.get("subreddits_failed") or []
    if failed:
        lines += ["", "**No data from:** " + ", ".join("`r/%s`" % s for s in failed)]
        if not run.get("subreddits_ok"):
            lines += ["", "Every subreddit failed - Reddit is refusing this runner's "
                          "IP. See the 'If it stops finding anything' section of the README."]
        for entry in (run.get("fetch_log") or [])[:5]:
            lines.append("- `{}`".format(entry))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    text = "\n".join(lines) + "\n"
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
