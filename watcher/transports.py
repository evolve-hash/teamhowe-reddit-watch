"""
Reddit fetching without an API key.

Reddit now answers 403 to unauthenticated ``.json`` endpoints, so this module
does not use them at all. It uses three transports that are still open, in
order of how much they give us:

  1. LISTING RSS   https://www.reddit.com/r/<sub>/new/.rss
     Officially published Atom feed. Title, author, permalink, post id,
     timestamp, and - for text posts - the full body. No score.

  2. OLD REDDIT    https://old.reddit.com/r/<sub>/new/
     The pre-2018 HTML still carries every field we want as data-attributes:
     data-score, data-comments-count, data-domain, data-timestamp, flair.

  3. OLD SEARCH    https://old.reddit.com/search/?q=subreddit%3A<sub>+<term>
     Keyword sweeps, so a slow-burning thread that already scrolled off /new
     still gets found. Search results include a body preview.

Results are merged on the reddit post id, so each transport only has to fill
in what it knows. If old.reddit refuses a runner's IP the crawl still works
off RSS alone - it just loses score and comment counts.
"""

import gzip
import html as html_mod
import io
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


class FetchError(Exception):
    pass


class Fetcher(object):
    """
    Polite HTTP GET with retries, adaptive pacing and optional mirror fallback.

    Two behaviours here were learned the hard way from a real GitHub Actions
    run, and they matter:

    * old.reddit.com answers 403 to every request from a datacenter IP. Retrying
      it 12 more times does not help - it just burns requests and pushes the
      shared rate limiter closer to throttling the transport that DOES work. So
      after two 403s a host is marked blocked and skipped for the rest of the run.

    * The RSS feed is rate limited, not blocked. A 429 needs to be waited out in
      tens of seconds, not four, and once we have seen one we slow everything
      down for the rest of the run rather than walking into the next one.
    """

    RATE_LIMIT_BACKOFF = (30, 60, 120)
    BLOCK_AFTER_403 = 2

    def __init__(self, user_agent, delay=4.0, timeout=25, retries=3, mirrors=None):
        self.user_agent = user_agent
        self.delay = delay
        self.base_delay = delay
        self.timeout = timeout
        self.retries = retries
        self.mirrors = list(mirrors or [])
        self._last_request = 0.0
        self.log = []
        self.blocked_hosts = {}      # host -> reason
        self.rate_limited = 0        # how many 429s we absorbed
        self._forbidden = {}         # host -> consecutive 403 count

    # -- internals ---------------------------------------------------------
    def _wait(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request = time.time()

    def _open(self, url):
        request = urllib.request.Request(url, headers={
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip",
            "Cache-Control": "no-cache",
        })
        response = urllib.request.urlopen(request, timeout=self.timeout)
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def _host(url):
        try:
            return urllib.parse.urlsplit(url).netloc.lower()
        except Exception:
            return url

    def blocked(self, url):
        return self._host(url) in self.blocked_hosts

    # -- public ------------------------------------------------------------
    def get(self, url):
        """Return page text, or None if every attempt failed."""
        attempts = [url]
        if self.mirrors and "old.reddit.com" in url:
            for mirror in self.mirrors:
                attempts.append(url.replace("old.reddit.com", mirror.strip("/")))

        for candidate in attempts:
            host = self._host(candidate)
            if host in self.blocked_hosts:
                continue                           # this host is a dead end today
            rate_step = 0
            for attempt in range(1, self.retries + 1):
                self._wait()
                try:
                    body = self._open(candidate)
                    self._forbidden[host] = 0
                    return body
                except urllib.error.HTTPError as exc:
                    self.log.append("HTTP {} {}".format(exc.code, candidate))

                    if exc.code in (403, 451):
                        count = self._forbidden.get(host, 0) + 1
                        self._forbidden[host] = count
                        if count >= self.BLOCK_AFTER_403:
                            self.blocked_hosts[host] = "HTTP {}".format(exc.code)
                            self.log.append(
                                "SKIPPING {} for the rest of this run "
                                "({} refused {} times)".format(host, exc.code, count))
                        break
                    if exc.code == 404:
                        break

                    if exc.code in (429, 500, 502, 503, 504):
                        if exc.code == 429:
                            self.rate_limited += 1
                            # Slow the whole run down; walking into the next 429
                            # costs more than waiting does.
                            self.delay = max(self.delay, self.base_delay * 2)
                        if attempt < self.retries:
                            wait = self._retry_after(exc) or self.RATE_LIMIT_BACKOFF[
                                min(rate_step, len(self.RATE_LIMIT_BACKOFF) - 1)]
                            rate_step += 1
                            time.sleep(wait)
                            continue
                    break
                except Exception as exc:           # timeouts, DNS, resets
                    self.log.append("{} {}".format(type(exc).__name__, candidate))
                    if attempt < self.retries:
                        time.sleep(8 * attempt)
                        continue
        return None

    @staticmethod
    def _retry_after(exc):
        try:
            value = exc.headers.get("Retry-After")
            if value:
                return min(180, max(5, int(float(value))))
        except Exception:
            pass
        return None


# ------------------------------------------------------------------ utils ----
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v]+")


def strip_html(fragment):
    if not fragment:
        return ""
    text = fragment.replace("<br>", "\n").replace("<br/>", "\n").replace("</p>", "\n")
    text = _TAG_RE.sub(" ", text)
    text = html_mod.unescape(html_mod.unescape(text))
    text = _WS_RE.sub(" ", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def _iso_to_epoch(value):
    try:
        cleaned = value.strip().replace("Z", "+00:00")
        return int(datetime.fromisoformat(cleaned).timestamp())
    except Exception:
        return None


# ------------------------------------------------------------ transport 1 ----
_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.S)


def parse_listing_rss(xml, subreddit):
    """Atom feed -> list of partial post dicts."""
    posts = []
    for chunk in _ENTRY_RE.findall(xml or ""):
        post_id = _first(chunk, r"<id>\s*(t3_\w+)\s*</id>")
        if not post_id:
            continue
        title = html_mod.unescape(_first(chunk, r"<title>(.*?)</title>", flags=re.S) or "")
        author = (_first(chunk, r"<author>\s*<name>\s*/u/([^<\s]+)") or "").strip()
        permalink = _first(chunk, r'<link href="([^"]+)"')
        published = _first(chunk, r"<published>(.*?)</published>")
        content = _first(chunk, r'<content type="html">(.*?)</content>', flags=re.S) or ""
        content = html_mod.unescape(html_mod.unescape(content))

        # Text posts carry their body between the SC_OFF / SC_ON markers.
        body = ""
        marker = re.search(r"<!--\s*SC_OFF\s*-->(.*?)<!--\s*SC_ON\s*-->", content, re.S)
        if marker:
            body = strip_html(marker.group(1))

        # Link posts carry the outbound URL in the [link] anchor.
        external = None
        link_anchor = re.search(r'<a href="([^"]+)">\s*\[link\]', content)
        if link_anchor and "reddit.com/r/" not in link_anchor.group(1):
            external = link_anchor.group(1)

        posts.append({
            "id": post_id,
            "subreddit": subreddit,
            "title": strip_html(title),
            "author": author,
            "permalink": permalink or "https://www.reddit.com/comments/{}".format(post_id[3:]),
            "created_utc": _iso_to_epoch(published or ""),
            "body": body,
            "external_url": external,
            "domain": _domain_of(external) if external else "self.{}".format(subreddit),
            "source": "rss",
        })
    return posts


# ------------------------------------------------------------ transport 2 ----
def parse_old_listing(html, subreddit):
    """old.reddit.com listing HTML -> list of partial post dicts."""
    posts = []
    if not html:
        return posts
    for chunk in re.split(r'(?=<div class="\s*thing )', html):
        if 'data-fullname="t3_' not in chunk:
            continue
        if 'data-promoted="true"' in chunk:
            continue
        post_id = _first(chunk, r'data-fullname="(t3_\w+)"')
        if not post_id:
            continue
        timestamp = _first(chunk, r'data-timestamp="(\d+)"')
        title = _first(
            chunk,
            r'<a[^>]*class="[^"]*\btitle\b[^"]*"[^>]*>(.*?)</a>',
            flags=re.S,
        )
        permalink = _first(chunk, r'data-permalink="([^"]+)"')
        posts.append({
            "id": post_id,
            "subreddit": _first(chunk, r'data-subreddit="([^"]+)"') or subreddit,
            "title": strip_html(title or ""),
            "author": _first(chunk, r'data-author="([^"]+)"') or "",
            "permalink": "https://www.reddit.com" + permalink if permalink else None,
            "created_utc": int(int(timestamp) / 1000) if timestamp else None,
            "score": _int(_first(chunk, r'data-score="(-?\d+)"')),
            "comments": _int(_first(chunk, r'data-comments-count="(\d+)"')),
            "domain": _first(chunk, r'data-domain="([^"]+)"') or "",
            "external_url": html_mod.unescape(_first(chunk, r'data-url="([^"]+)"') or ""),
            "flair": html_mod.unescape(
                _first(chunk, r'<span class="linkflairlabel[^"]*"[^>]*title="([^"]*)"') or ""
            ),
            "nsfw": 'data-nsfw="true"' in chunk,
            "source": "old_html",
        })
    return posts


# ------------------------------------------------------------ transport 3 ----
def parse_old_search(html):
    """old.reddit.com search HTML -> list of partial post dicts (incl. body)."""
    posts = []
    if not html:
        return posts
    for chunk in re.split(r'(?=<div class="\s*search-result search-result-link)', html):
        if 'data-fullname="t3_' not in chunk:
            continue
        post_id = _first(chunk, r'data-fullname="(t3_\w+)"')
        if not post_id:
            continue
        permalink = _first(chunk, r'<a href="(https://old\.reddit\.com/r/[^"]+)" class="search-title')
        if permalink:
            permalink = permalink.replace("old.reddit.com", "www.reddit.com")
        body = _first(chunk, r'<div class="search-result-body">.*?<div class="md">(.*?)</div>', flags=re.S)
        posts.append({
            "id": post_id,
            "subreddit": _first(chunk, r'class="search-subreddit-link[^"]*"[^>]*>r/([^<]+)</a>') or "",
            "title": strip_html(
                _first(chunk, r'class="search-title[^"]*"[^>]*>(.*?)</a>', flags=re.S) or ""
            ),
            "author": _first(chunk, r'class="author may-blank[^"]*"[^>]*>([^<]+)</a>') or "",
            "permalink": permalink,
            "created_utc": _iso_to_epoch(_first(chunk, r'<time[^>]*datetime="([^"]+)"') or ""),
            "score": _int(_first(chunk, r'class="search-score">(-?\d+) point')),
            "comments": _int(_first(chunk, r'class="search-comments[^"]*"[^>]*>(\d+) comment')),
            "body": strip_html(body or ""),
            "source": "old_search",
        })
    return posts


# ------------------------------------------------------------------ merge ----
_PREFERRED = ("score", "comments", "flair", "domain", "external_url")


def merge(*groups):
    """Merge partial dicts from several transports, keyed on post id."""
    merged = {}
    for group in groups:
        for post in group or []:
            existing = merged.get(post["id"])
            if existing is None:
                merged[post["id"]] = dict(post)
                continue
            for key, value in post.items():
                if value in (None, "", []) :
                    continue
                current = existing.get(key)
                if current in (None, "", []):
                    existing[key] = value
                elif key == "body" and len(str(value)) > len(str(current)):
                    existing[key] = value          # keep the fullest body we saw
                elif key in _PREFERRED and post.get("source") == "old_html":
                    existing[key] = value          # listing HTML is authoritative
            sources = set(str(existing.get("sources") or existing.get("source") or "").split("+"))
            sources.add(post.get("source", ""))
            existing["sources"] = "+".join(sorted(s for s in sources if s))
    for post in merged.values():
        post.setdefault("sources", post.get("source", ""))
    return list(merged.values())


# ------------------------------------------------------------------- urls ----
def listing_rss_url(subreddit):
    return "https://www.reddit.com/r/{}/new/.rss?limit=100".format(subreddit)


def old_listing_url(subreddit):
    return "https://old.reddit.com/r/{}/new/?limit=100".format(subreddit)


def old_search_url(subreddit, term, sort="new", period="month"):
    query = 'subreddit:{} {}'.format(subreddit, term)
    return "https://old.reddit.com/search/?q={}&sort={}&t={}&restrict_sr=on".format(
        urllib.parse.quote_plus(query), sort, period,
    )


# ----------------------------------------------------------------- helpers ----
def _first(text, pattern, flags=0):
    match = re.search(pattern, text or "", flags)
    return match.group(1) if match else None


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _domain_of(url):
    try:
        host = urllib.parse.urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def now_utc():
    return int(datetime.now(timezone.utc).timestamp())
