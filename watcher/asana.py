"""
Optional Asana hand-off - Eduard's idea from the meeting: instead of only an
email, a hot thread becomes a task so nothing quietly scrolls past.

Off by default. Turn it on in config.json and set ASANA_TOKEN as a repository
secret. This uses Asana's own API (a personal access token, no Reddit key
involved) and fails soft: if Asana is unreachable the crawl still succeeds.
"""

import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

API = "https://app.asana.com/api/1.0/tasks"


def push(config, records):
    settings = config.get("asana", {})
    if not settings.get("enabled"):
        return {"skipped": "disabled"}
    token = os.environ.get("ASANA_TOKEN")
    project = settings.get("project_gid")
    if not token or not project:
        return {"skipped": "missing ASANA_TOKEN or project_gid"}

    if settings.get("only_hot", True):
        records = [r for r in records if r.get("verdict") == "hot"]
    if not records:
        return {"created": 0}

    created, failed = 0, []
    for record in records[:20]:
        payload = {"data": {
            "projects": [project],
            "name": "Reddit: {}".format((record.get("title") or "")[:180]),
            "notes": _notes(record),
        }}
        if settings.get("assignee_gid"):
            payload["data"]["assignee"] = settings["assignee_gid"]
        request = urllib.request.Request(
            API,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=25).read()
            created += 1
        except urllib.error.HTTPError as exc:
            failed.append("{} {}".format(exc.code, record.get("id")))
        except Exception as exc:
            failed.append("{} {}".format(type(exc).__name__, record.get("id")))
    return {"created": created, "failed": failed}


def _notes(record):
    lines = [
        record.get("permalink") or "",
        "",
        "Signal score: {}".format(record.get("relevance", 0)),
        "Subreddit: r/{}".format(record.get("subreddit", "")),
        "Posted by: u/{}".format(record.get("author", "unknown")),
    ]
    if record.get("created_utc"):
        lines.append("Posted: {}".format(
            datetime.fromtimestamp(record["created_utc"], tz=timezone.utc)
            .strftime("%Y-%m-%d %H:%M UTC")))
    if record.get("is_lead"):
        lines.append("Flagged as a possible client conversation.")
    if record.get("hits"):
        lines.append("Matched keywords: {}".format(", ".join(record["hits"][:10])))
    if record.get("excerpt"):
        lines += ["", "Excerpt:", record["excerpt"]]
    lines += ["", "Suggested action: read the thread first, then reply as yourself with "
                  "something specific and useful. Do not open with a pitch."]
    return "\n".join(lines)
