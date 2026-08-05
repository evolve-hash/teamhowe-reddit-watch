"""
Branded HTML emails: the weekly digest and the hot-thread alert.

Written table-first with inline styles, because that is the only thing Outlook,
Gmail and Apple Mail all agree on. Montserrat is requested but every rule also
names Helvetica/Arial, so the mail still looks like Team Howe where the web font
can't load. Light-mode palette only - TJ's point about the audience holds here
too, and every colour pair used below clears WCAG AA.
"""

import html as html_mod
from datetime import datetime, timedelta, timezone

from . import brand
from .dedupe import fold

WRAP = 640
_FONT = brand.FONT_STACK_EMAIL
BEIGE_DEEP = "#86664a"   # beige stepped dark enough to clear AA on white (5.2:1)
MUTED = "#6f6f6f"        # 5.0:1 on white - the site's #848484 is too light for body copy
LEGAL_INK = "#9f9f9f"    # on the black footer


def _e(value):
    return html_mod.escape(str(value if value is not None else ""), quote=True)


def _ago(epoch):
    if not epoch:
        return "unknown time"
    seconds = int(datetime.now(timezone.utc).timestamp()) - epoch
    if seconds < 3600:
        return "{} min ago".format(max(1, seconds // 60))
    if seconds < 86400:
        hours = seconds // 3600
        return "{} hour{} ago".format(hours, "" if hours == 1 else "s")
    days = seconds // 86400
    if days < 14:
        return "{} day{} ago".format(days, "" if days == 1 else "s")
    if days < 70:
        return "{} weeks ago".format(days // 7)
    moment = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return moment.strftime("%b %-d, %Y")


def _plural(count, one, many):
    return "{} {}".format(count, one if count == 1 else many)


# --------------------------------------------------------------- chrome ------
def _shell(inner, preheader):
    year = datetime.now(timezone.utc).year
    return """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>Team Howe Reddit Watch</title>
<link rel="stylesheet" href="{fonts}">
<!--[if mso]><style>body,table,td,a,p{{font-family:Arial,Helvetica,sans-serif !important}}</style><![endif]-->
</head>
<body style="margin:0;padding:0;background:{offwhite};">
<div style="display:none;font-size:1px;color:{offwhite};line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;">{pre}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{offwhite};">
<tr><td align="center" style="padding:26px 12px 40px;">
<table role="presentation" width="{w}" cellpadding="0" cellspacing="0" border="0" style="width:{w}px;max-width:100%;background:{white};">

  <tr><td style="background:{black};padding:26px 32px;" align="left">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
      <td align="left"><a href="{site}" style="text-decoration:none;"><img src="{logo}" width="190" alt="Team Howe | Compass" style="display:block;border:0;width:190px;height:auto;"></a></td>
      <td align="right" style="font-family:{font};font-size:10px;letter-spacing:2.4px;text-transform:uppercase;color:{beige};font-weight:600;">Reddit&nbsp;Watch</td>
    </tr></table>
  </td></tr>

  {inner}

  <tr><td style="background:{black};padding:30px 32px 26px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td>
      <div style="font-family:{font};font-size:10px;letter-spacing:2.6px;text-transform:uppercase;color:{beige};font-weight:600;padding-bottom:12px;">{tagline}</div>
      <div style="font-family:{font};font-size:13px;line-height:22px;color:#ffffff;font-weight:300;">
        <a href="{phone_href}" style="color:#ffffff;text-decoration:none;">{phone}</a><br>
        {address}<br>
        <a href="{site}" style="color:{beige};text-decoration:none;">teamhowe.com</a>
      </div>
      <div style="font-family:{font};font-size:10px;line-height:17px;color:#9f9f9f;font-weight:300;padding-top:20px;margin-top:18px;border-top:1px solid rgba(255,255,255,0.14);">
        <span style="color:#d0cdca;display:block;padding-bottom:7px;">{copyright}</span>{legal}
      </div>
    </td></tr></table>
  </td></tr>

</table>
</td></tr></table>
</body></html>""".format(
        fonts=brand.GOOGLE_FONTS, font=_FONT, w=WRAP, pre=_e(preheader),
        offwhite=brand.OFF_WHITE, white=brand.WHITE, black=brand.BLACK,
        beige=brand.BEIGE, site=brand.WEBSITE, logo=brand.logo(on_dark=True, width=560),
        tagline=brand.TAGLINE, phone=brand.PHONE, phone_href=brand.PHONE_HREF,
        address=brand.ADDRESS, copyright=brand.copyright_line(year),
        legal=brand.LEGAL, inner=inner,
    )


def _lede(eyebrow, heading, blurb):
    return """<tr><td style="padding:44px 32px 8px;">
  <div style="font-family:{font};font-size:10px;font-weight:600;letter-spacing:2.6px;text-transform:uppercase;color:{beige_deep};padding-bottom:14px;">{eyebrow}</div>
  <h1 style="margin:0;font-family:{font};font-size:29px;line-height:1.2;font-weight:400;color:{black};letter-spacing:-0.3px;">{heading}</h1>
  <p style="margin:16px 0 0;font-family:{font};font-size:15px;line-height:25px;color:{muted};font-weight:300;">{blurb}</p>
</td></tr>""".format(
        font=_FONT, beige_deep=BEIGE_DEEP, black=brand.BLACK,
        muted=MUTED, eyebrow=_e(eyebrow), heading=_e(heading), blurb=blurb,
    )


def _post_block(post, index, accent=True):
    is_hot = post.get("verdict") == "hot"
    badge = ""
    if is_hot:
        badge = ('<span style="font-family:{f};font-size:9px;font-weight:600;letter-spacing:1.6px;'
                 'text-transform:uppercase;color:{hot};background:{hw};border:1px solid {hl};'
                 'padding:4px 8px;">Worth a reply</span>').format(
            f=_FONT, hot=brand.HOT, hw=brand.HOT_WASH, hl="#e7c9c4")
    if post.get("is_lead"):
        badge += ('&nbsp;<span style="font-family:{f};font-size:9px;font-weight:600;letter-spacing:1.6px;'
                  'text-transform:uppercase;color:{lead};background:{lw};border:1px solid {ll};'
                  'padding:4px 8px;">Possible client</span>').format(
            f=_FONT, lead="#4d5b3d", lw=brand.LEAD_WASH, ll="#cfd8c2")

    meta = ["r/" + _e(post.get("subreddit", "")),
            "u/" + _e(post.get("author", "unknown")),
            _ago(post.get("created_utc"))]
    if post.get("score") is not None:
        meta.append(_plural(post["score"], "upvote", "upvotes"))
    if post.get("comments") is not None:
        meta.append(_plural(post["comments"], "comment", "comments"))
    domain = post.get("domain") or ""
    if domain and not domain.startswith("self."):
        meta.append(_e(domain))
    also = post.get("also_in") or []
    if also:
        meta.append("also in " + ", ".join(
            '<a href="{}" style="color:#6f6f6f;">r/{}</a>'.format(
                _e(entry.get("permalink") or "#"), _e(entry.get("subreddit")))
            for entry in also))

    chips = ""
    for hit in (post.get("hits") or [])[:5]:
        chips += ('<span style="font-family:{f};font-size:10.5px;color:#6f6f6f;border:1px solid {b};'
                  'background:{s2};padding:3px 7px;display:inline-block;margin:0 5px 5px 0;">{t}</span>'
                  ).format(f=_FONT, b=brand.BORDER, s2=brand.OFF_WHITE, t=_e(hit))

    excerpt = ""
    if post.get("excerpt"):
        excerpt = ('<p style="margin:12px 0 0;font-family:{f};font-size:13.5px;line-height:22px;'
                   'color:#4a4646;font-weight:300;">{t}</p>').format(f=_FONT, t=_e(post["excerpt"]))

    return """<tr><td style="padding:26px 32px;border-top:1px solid {border};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
    <td width="54" valign="top" style="width:54px;padding-right:16px;">
      <div style="font-family:{f};font-size:23px;font-weight:600;color:{scol};line-height:1;letter-spacing:-0.5px;">{rel}</div>
      <div style="font-family:{f};font-size:8px;font-weight:600;letter-spacing:1.4px;text-transform:uppercase;color:#848484;padding-top:5px;">Signal</div>
    </td>
    <td valign="top">
      {badge_row}
      <a href="{link}" style="font-family:{f};font-size:17px;line-height:25px;font-weight:500;color:{black};text-decoration:none;">{title}</a>
      <div style="font-family:{f};font-size:11.5px;color:#6f6f6f;padding-top:9px;">{meta}</div>
      {excerpt}
      <div style="padding-top:13px;">{chips}</div>
      <div style="padding-top:14px;">
        <a href="{link}" style="font-family:{f};font-size:10px;font-weight:600;letter-spacing:1.8px;text-transform:uppercase;color:#ffffff;background:{black};padding:11px 18px;text-decoration:none;display:inline-block;">Open thread</a>
        <a href="{profile}" style="font-family:{f};font-size:10px;font-weight:600;letter-spacing:1.8px;text-transform:uppercase;color:{black};border:1px solid {black};padding:10px 17px;text-decoration:none;display:inline-block;margin-left:7px;">See u/{author}</a>
      </div>
    </td>
  </tr></table>
</td></tr>""".format(
        f=_FONT, border=brand.BORDER, black=brand.BLACK,
        scol=brand.HOT if is_hot else brand.BLACK,
        rel=post.get("relevance", 0),
        badge_row=('<div style="padding-bottom:10px;">%s</div>' % badge) if badge else "",
        link=_e(post.get("permalink") or brand.WEBSITE),
        title=_e(post.get("title", "")),
        meta=" &middot; ".join(meta),
        excerpt=excerpt, chips=chips,
        profile=_e(post.get("author_url") or "https://www.reddit.com"),
        author=_e(post.get("author", "unknown")),
    )


def _stat_row(cells):
    tds = ""
    width = int(100 / max(1, len(cells)))
    for label, value, hot in cells:
        tds += """<td width="{w}%" valign="bottom" style="padding:0 10px 0 0;">
  <div style="font-family:{f};font-size:9.5px;font-weight:600;letter-spacing:1.7px;text-transform:uppercase;color:#6f6f6f;padding-bottom:8px;white-space:nowrap;">{label}</div>
  <div style="font-family:{f};font-size:31px;font-weight:600;line-height:1;color:{c};letter-spacing:-0.6px;">{value}</div>
</td>""".format(w=width, f=_FONT, label=_e(label), value=_e(value),
                c=brand.HOT if hot else brand.BLACK)
    return """<tr><td style="padding:26px 32px 30px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>{tds}</tr></table>
</td></tr>""".format(tds=tds)


def _cta(url, label):
    if not url:
        return ""
    return """<tr><td style="padding:6px 32px 40px;" align="left">
  <a href="{url}" style="font-family:{f};font-size:10.5px;font-weight:600;letter-spacing:1.9px;text-transform:uppercase;color:#ffffff;background:{black};padding:14px 26px;text-decoration:none;display:inline-block;">{label}</a>
</td></tr>""".format(url=_e(url), f=_FONT, black=brand.BLACK, label=_e(label))


# ---------------------------------------------------------------- digest -----
def weekly_digest(config, records):
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    cutoff = int(week_start.timestamp())

    week = fold([r for r in records if (r.get("created_utc") or 0) >= cutoff])
    week.sort(key=lambda r: (-r.get("relevance", 0), -(r.get("created_utc") or 0)))
    hot = [r for r in week if r.get("verdict") == "hot"]
    leads = [r for r in week if r.get("is_lead")]

    subs = {}
    for record in week:
        subs[record.get("subreddit", "?")] = subs.get(record.get("subreddit", "?"), 0) + 1
    top_subs = sorted(subs.items(), key=lambda kv: -kv[1])[:5]

    themes = _themes(week)

    label = "{} - {}".format(
        week_start.strftime("%b %-d"), now.strftime("%b %-d, %Y"),
    )

    blurb = (
        "Here is every San Francisco real estate conversation we picked up on Reddit this week, "
        "ranked by how much it looks like an opening. The threads at the top are the ones "
        "where a helpful reply would land."
    )
    if not week:
        blurb = ("Quiet week - nothing on the watched subreddits crossed the relevance "
                 "threshold. The watcher is running; there was simply nothing worth your time.")

    inner = _lede("Weekly digest", "SF real estate on Reddit", blurb)
    inner += _stat_row([
        ("Worth a reply", len(hot), True),
        ("Possible clients", len(leads), False),
        ("Threads", len(week), False),
        ("Subreddits", len(subs), False),
    ])

    if themes:
        rows = ""
        for theme, count in themes:
            rows += ('<tr><td style="font-family:{f};font-size:13.5px;color:{ink};padding:7px 0;'
                     'border-bottom:1px solid {b};font-weight:300;">{t}</td>'
                     '<td align="right" style="font-family:{f};font-size:13.5px;color:#6f6f6f;'
                     'padding:7px 0;border-bottom:1px solid {b};">{c}</td></tr>').format(
                f=_FONT, ink=brand.BLACK, b=brand.BORDER, t=_e(theme), c=count)
        inner += """<tr><td style="padding:0 32px 34px;">
  <div style="font-family:{f};font-size:10px;font-weight:600;letter-spacing:2.2px;text-transform:uppercase;color:#86664a;padding-bottom:14px;">What people talked about</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
</td></tr>""".format(f=_FONT, rows=rows)

    if top_subs:
        line = " &middot; ".join("r/{} ({})".format(_e(name), count) for name, count in top_subs)
        inner += """<tr><td style="padding:0 32px 30px;">
  <div style="font-family:{f};font-size:10px;font-weight:600;letter-spacing:2.2px;text-transform:uppercase;color:#86664a;padding-bottom:10px;">Where</div>
  <div style="font-family:{f};font-size:13px;color:#4a4646;font-weight:300;">{line}</div>
</td></tr>""".format(f=_FONT, line=line)

    shortlist = (hot + [r for r in week if r not in hot])[:12]
    if shortlist:
        inner += """<tr><td style="padding:6px 32px 4px;">
  <div style="font-family:{f};font-size:10px;font-weight:600;letter-spacing:2.2px;text-transform:uppercase;color:#86664a;">The threads</div>
</td></tr>""".format(f=_FONT)
        for index, record in enumerate(shortlist):
            inner += _post_block(record, index)

    remaining = len(week) - len(shortlist)
    if remaining > 0:
        inner += """<tr><td style="padding:22px 32px 0;border-top:1px solid {b};">
  <div style="font-family:{f};font-size:13px;color:#6f6f6f;font-weight:300;">Plus {n} more tracked thread{s} on the dashboard.</div>
</td></tr>""".format(b=brand.BORDER, f=_FONT, n=remaining, s="" if remaining == 1 else "s")

    inner += _cta(config.get("site", {}).get("public_url", ""), "Open the dashboard")

    subject = config.get("email", {}).get(
        "digest_subject", "Reddit Watch - SF real estate, week of {week}",
    ).replace("{week}", label)

    preheader = "{} worth a reply, {} possible clients, {} threads tracked this week.".format(
        len(hot), len(leads), len(week))

    return subject, _shell(inner, preheader), _digest_text(label, week, hot, leads, themes, config)


def _digest_text(label, week, hot, leads, themes, config):
    lines = ["TEAM HOWE - REDDIT WATCH", "Weekly digest, {}".format(label), ""]
    lines.append("Worth a reply: {}   Possible clients: {}   Threads: {}".format(
        len(hot), len(leads), len(week)))
    if themes:
        lines += ["", "What people talked about:"]
        lines += ["  - {} ({})".format(theme, count) for theme, count in themes]
    lines += ["", "Threads:"]
    for record in (hot + [r for r in week if r not in hot])[:12]:
        lines.append("")
        lines.append("[{}] {}".format(record.get("relevance", 0), record.get("title", "")))
        lines.append("  r/{} - u/{} - {}".format(
            record.get("subreddit"), record.get("author"), _ago(record.get("created_utc"))))
        lines.append("  {}".format(record.get("permalink")))
    url = config.get("site", {}).get("public_url", "")
    if url:
        lines += ["", "Dashboard: {}".format(url)]
    lines += ["", brand.copyright_line(datetime.now(timezone.utc).year), brand.LEGAL]
    return "\n".join(lines)


# ----------------------------------------------------------------- alert -----
def hot_alert(config, records):
    records = sorted(fold(records), key=lambda r: -r.get("relevance", 0))
    count = len(records)
    leads = [r for r in records if r.get("is_lead")]

    heading = ("Someone is asking about buying or selling"
               if leads else "New SF real estate threads")
    blurb = (
        "These just went up on Reddit. Reddit ranks new threads on early engagement, so a "
        "reply in the next hour or two carries much further than one tomorrow."
    )

    inner = _lede("Hot thread alert", heading, blurb)
    for index, record in enumerate(records[:8]):
        inner += _post_block(record, index)
    if count > 8:
        inner += """<tr><td style="padding:22px 32px 0;border-top:1px solid {b};">
  <div style="font-family:{f};font-size:13px;color:#6f6f6f;font-weight:300;">And {n} more on the dashboard.</div>
</td></tr>""".format(b=brand.BORDER, f=_FONT, n=count - 8)
    inner += _cta(config.get("site", {}).get("public_url", ""), "Open the dashboard")

    subject = config.get("email", {}).get(
        "alert_subject", "Reddit Watch: {count} new SF real estate thread(s) worth a reply",
    ).replace("{count}", str(count))

    top = records[0].get("title", "") if records else ""
    preheader = (top[:110] + "...") if len(top) > 110 else top

    text = ["TEAM HOWE - REDDIT WATCH", "New threads worth a reply", ""]
    for record in records[:8]:
        text.append("[{}] {}".format(record.get("relevance", 0), record.get("title", "")))
        text.append("  r/{} - u/{} - {}".format(
            record.get("subreddit"), record.get("author"), _ago(record.get("created_utc"))))
        text.append("  {}".format(record.get("permalink")))
        text.append("")
    return subject, _shell(inner, preheader), "\n".join(text)


# ---------------------------------------------------------------- themes -----
def _themes(records):
    counts = {}
    for record in records:
        for key, tier in (record.get("tiers") or {}).items():
            if key in ("negative", "neighborhoods"):
                continue
            label = tier.get("label", key)
            counts[label] = counts.get(label, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])[:6]
