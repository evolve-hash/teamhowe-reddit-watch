"""
docs/feed.xml - a plain RSS 2.0 feed of everything the watcher flagged.

Two uses: TJ can subscribe in any reader instead of taking another push
notification, and it is the cheapest bridge into anything else (Zapier, Make,
Slack's /feed subscribe, Asana's email-to-task address).
"""

import html
import os
from datetime import datetime, timezone
from email.utils import formatdate

from . import brand
from .dedupe import fold


def build(config, store, out_path, limit=120):
    site = config.get("site", {})
    public = site.get("public_url", "") or brand.WEBSITE

    records = fold([r for r in store.posts() if r.get("created_utc")])
    records.sort(key=lambda r: -(r.get("created_utc") or 0))
    records = records[:limit]

    items = []
    for record in records:
        flags = []
        if record.get("verdict") == "hot":
            flags.append("WORTH A REPLY")
        if record.get("is_lead"):
            flags.append("POSSIBLE CLIENT")
        prefix = ("[{}] ".format(" / ".join(flags))) if flags else ""

        description_parts = [
            "<p><strong>Signal {}</strong> &middot; r/{} &middot; u/{}</p>".format(
                record.get("relevance", 0),
                html.escape(str(record.get("subreddit", ""))),
                html.escape(str(record.get("author", ""))),
            ),
        ]
        if record.get("excerpt"):
            description_parts.append("<p>{}</p>".format(html.escape(record["excerpt"])))
        if record.get("hits"):
            description_parts.append("<p><em>Matched: {}</em></p>".format(
                html.escape(", ".join(record["hits"][:8]))))
        stats = []
        if record.get("score") is not None:
            stats.append("{} upvotes".format(record["score"]))
        if record.get("comments") is not None:
            stats.append("{} comments".format(record["comments"]))
        if stats:
            description_parts.append("<p>{}</p>".format(" &middot; ".join(stats)))

        items.append("""  <item>
    <title>{title}</title>
    <link>{link}</link>
    <guid isPermaLink="false">teamhowe-reddit-watch-{gid}</guid>
    <pubDate>{pub}</pubDate>
    <category>r/{sub}</category>
    <author>reddit-watch@teamhowe.com (u/{author})</author>
    <description>{desc}</description>
  </item>""".format(
            title=html.escape(prefix + str(record.get("title", ""))),
            link=html.escape(str(record.get("permalink") or public)),
            gid=html.escape(str(record.get("id"))),
            pub=formatdate(record.get("created_utc"), usegmt=True),
            sub=html.escape(str(record.get("subreddit", ""))),
            author=html.escape(str(record.get("author", "unknown"))),
            desc=html.escape("".join(description_parts)),
        ))

    xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>Team Howe Reddit Watch - San Francisco real estate</title>
  <link>{public}</link>
  <atom:link href="{public}/feed.xml" rel="self" type="application/rss+xml"/>
  <description>Reddit threads about San Francisco real estate, scored for how much they look like an opening.</description>
  <language>en-us</language>
  <copyright>{copyright}</copyright>
  <lastBuildDate>{built}</lastBuildDate>
  <ttl>20</ttl>
{items}
</channel>
</rss>
""".format(
        public=html.escape(public.rstrip("/")),
        copyright=html.escape(brand.copyright_line(datetime.now(timezone.utc).year)),
        built=formatdate(usegmt=True),
        items="\n".join(items),
    )

    directory = os.path.dirname(os.path.abspath(out_path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(xml)
    return {"path": out_path, "items": len(items)}
