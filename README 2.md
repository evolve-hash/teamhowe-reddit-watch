# Team Howe Reddit Watch

A watcher that reads the San Francisco subreddits every twenty minutes, works out
which threads are really about real estate, and tells you who posted them — so
Sherri or TJ can reply while the thread is still climbing.

It needs no Reddit API key. It reads the same public pages a person reads.

---

## What it produces

**A dashboard.** A Team Howe–branded page listing every matched thread: the
relevance score, the subreddit, the username, how long ago it went up, the
upvote and comment counts, an excerpt, the exact keywords that matched, and
buttons to open or reply to the thread. Filter by subreddit, search the text,
sort by relevance or recency, switch between "worth a reply" and everything.
There is a dark mode, because TJ asked for one.

**A weekly digest email.** Monday morning, one branded email: what people talked
about, where, and the twelve threads most worth your time.

**Hot-thread alerts.** The moment something crosses the line — somebody asking
for a realtor, somebody deciding whether to buy — an email goes out immediately.
Reddit ranks new threads on early engagement, so an hour matters. Each thread is
only ever emailed once.

**An RSS feed** at `feed.xml`, so the same stream can go into a reader, Slack, or
an Asana email-to-task address without any more code.

**Asana tasks**, optionally, for the hot ones.

---

## How it finds the right threads

TJ's real requirement was the hard part: catch the posts that are about real
estate *without* using the words "real estate". Somebody dropping a Chronicle
link. Somebody asking whether the Sunset is a good bet. Somebody writing
"$1.4M, 3bd/2ba, HOA $780".

So every post is scored across independent tiers, and the tiers add up:

| Tier | Weight | Examples |
|---|---|---|
| Buyer / seller intent | 14 | "looking for a realtor", "should I buy", "thinking of selling", "pre-approved", "bidding war" |
| SF-specific signals | 8 | TIC, Ellis Act, condo conversion, soft story, Prop 13, ADU, disclosure package |
| Transaction mechanics | 7 | escrow, contingency, closing costs, over asking, days on market |
| News / listing sources | 7 | sfchronicle.com, socketsite.com, sfyimby.com, zillow.com, redfin.com |
| Market talk | 6 | home prices, inventory, interest rates, HOA dues, property tax |
| Price & listing patterns | 5 | `$1.4M`, `$950k`, `3bd/2ba`, `1,200 sq ft`, `6.5% rate` |
| Neighborhoods | 3 | Noe Valley, Outer Sunset, Sea Cliff, Bernal Heights, and 80 more |
| Not-a-sale penalty | −14 | roommate wanted, sublet, apartment for rent, hiring, best burrito |

A tier scores its weight once, plus a quarter of it for each additional phrase.
So a post saying "realtor" six times does not outrank a post that genuinely
spans intent *and* price *and* neighborhood.

Anything scoring 11 or more is tracked. 24 or more — or any intent phrase in a
first-person voice — is flagged **worth a reply** and triggers an alert. Every
number here lives in `config.json` and every phrase in `keywords.json`; both are
plain text and safe to edit.

On the real thread sample this was tested against, 11 of 75 posts were kept.
The four flagged hot were: a homeowner about to make an offer asking for
inspectors, somebody asking for advice buying a SOMA condo, a thread about
realtors underpricing to start bidding wars, and a Chronicle-adjacent piece on
what new money is doing to SF home design. Nothing about Muni, the zoo, or
burritos made it through.

---

## Why there is no Reddit API key

Reddit closed the door on unauthenticated `.json` endpoints — they answer `403`
now, even from a laptop on home internet. Two doors are still open, and the
watcher uses both, plus a third for keyword sweeps:

1. **The official RSS feed** — `reddit.com/r/<sub>/new/.rss`. Titles, authors,
   permalinks, timestamps, and the full body of text posts.
2. **old.reddit.com HTML** — the pre-2018 layout still carries the score,
   comment count, link domain and flair as HTML attributes.
3. **old.reddit.com search** — keyword sweeps, so a slow-burning thread that
   already scrolled off `/new` still gets found.

Results are merged on the Reddit post ID, so each source only fills in what it
knows. If one source ever stops working the watcher keeps running on the others —
it just loses that source's extra fields.

---

## Setting it up

You need a GitHub account. Everything below is free.

### 1. Put the code on GitHub

Create a new **private** repository called `reddit-watch`, then from this folder:

```bash
git init
git add .
git commit -m "Team Howe Reddit Watch"
git branch -M main
git remote add origin https://github.com/<your-account>/reddit-watch.git
git push -u origin main
```

### 2. Turn on the dashboard

In the repository: **Settings → Pages**. Under "Build and deployment" set
Source to **Deploy from a branch**, branch **main**, folder **/docs**. Save.

A minute later the dashboard is live at
`https://<your-account>.github.io/reddit-watch/`. Copy that address into
`config.json` under `site.public_url` so the emails can link to it.

> A private repository's Pages site needs GitHub Pro. If you are on the free
> plan, either make the repository public — there is nothing secret in it, the
> credentials live in Settings, not in the files — or skip Pages and read
> `docs/index.html` straight from the repository.

### 3. Let the workflow write back

**Settings → Actions → General → Workflow permissions** → choose
**Read and write permissions**. Save. The watcher needs this to commit each
run's results.

### 4. Give it a mailbox

**Settings → Secrets and variables → Actions → New repository secret**, four
times:

| Name | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | the address that sends, e.g. `reddit@teamhowe.com` |
| `SMTP_PASSWORD` | a Google **App Password**, not the account password |

App passwords are at **myaccount.google.com → Security → 2-Step Verification →
App passwords**. They are sixteen characters; paste it without the spaces.
Any SMTP provider works — Gmail is just the one most people already have.

### 5. Say who gets the mail

In `config.json`:

```json
"email": {
  "enabled": true,
  "digest_recipients": ["tj@teamhowe.com"],
  "alert_recipients":  ["tj@teamhowe.com", "evolve@teamhowe.com"]
}
```

Commit and push. TJ can then filter on the `X-TeamHowe-Source: reddit-watch`
header, or just on the subject line, and the whole stream lands in one label
instead of on his phone.

### 6. Kick off the first run

**Actions → Watch Reddit → Run workflow.** It takes two or three minutes
because it is polite about request spacing. Watch the run summary: it reports how
many posts were fetched, kept, and flagged, and names any subreddit that gave
nothing back.

---

## Running it by hand

```bash
python3 cli.py test      # score the bundled sample pages - no network needed
python3 cli.py crawl     # fetch and score
python3 cli.py build     # regenerate docs/index.html and docs/feed.xml
python3 cli.py alerts    # email new hot threads
python3 cli.py digest    # email the weekly digest
python3 cli.py run       # crawl + build + alerts, what the schedule runs
```

Add `--dry-run` to any of them and nothing is emailed — instead the message is
written to `docs/preview-alert.html` or `docs/preview-digest.html` so you can
open it in a browser first. Python 3.9 or newer; no packages to install.

`python3 cli.py test` is the useful one when you have been editing
`keywords.json`: it re-scores the saved sample pages and prints what was kept and
what was rejected, so you can see the effect of a change immediately without
touching Reddit.

---

## Tuning it

**`config.json`**

- `subreddits` — the watch list. `"scope": "all"` means any real-estate hit
  counts. `"scope": "geo"` means the post must *also* mention San Francisco or
  the Bay Area, which is what keeps r/RealEstate and r/FirstTimeHomeBuyer from
  flooding everything.
- `thresholds.include_score` — raise it for less noise, lower it for more
  coverage. 11 is the tested default.
- `thresholds.hot_score` — the alert line. 24 by default.
- `search_sweeps` — extra keyword searches per subreddit. Each one costs a
  request, so keep the list tight.
- `crawler.delay_seconds` — 2.5 is deliberately polite. Do not lower it.

**`keywords.json`** — add or remove phrases in any tier's `terms` list.
Matching is case-insensitive and whole-phrase, so `"open house"` will not fire
on "openhouse" and `"tic"` will not fire on "ticket".

---

## If it stops finding anything

The one real failure mode is Reddit deciding it does not like GitHub's servers.
The run summary will say `no data from:` and list every subreddit. If that
happens:

1. **Try the mirrors.** Add one or two public Redlib hosts to
   `crawler.mirrors` in `config.json`. They serve the same pages from a
   different address.
2. **Run it from this Mac instead.** Same code, your own internet connection,
   which Reddit is far more relaxed about:

   ```bash
   chmod +x local/run_local.sh
   ./local/run_local.sh
   ```

   To have it run itself every twenty minutes, edit the two paths in
   `local/com.teamhowe.redditwatch.plist`, copy it to `~/Library/LaunchAgents/`,
   and `launchctl load` it. Instructions are in the file.

Nothing is lost either way — the state file is the source of truth and both
paths write to the same one.

---

## What is in the folder

```
config.json      settings: subreddits, thresholds, recipients
keywords.json    the scoring dictionary
cli.py           the command line entry point
watcher/
  transports.py  fetching and parsing reddit without an API key
  scoring.py     the tiered relevance engine
  crawl.py       one crawl, end to end
  store.py       the JSON state file, dedupe, retention
  brand.py       Team Howe colours, type and assets, read off teamhowe.com
  dashboard.py   builds docs/index.html
  emails.py      the digest and the alert
  feeds.py       builds docs/feed.xml
  mailer.py      SMTP
  asana.py       optional task creation
docs/            what GitHub Pages serves
data/posts.json  the state file, committed each run
samples/         saved reddit pages, so `cli.py test` works offline
local/           scripts for running on a Mac instead
```

---

## A note on how to use it

The point is not volume. Reddit is unforgiving about accounts that only ever
show up to sell something, and a thread where "Sherri Howe is great" appears
from a brand-new account does more harm than nothing at all. The dashboard is
there so that when somebody genuinely asks a question Team Howe can answer
better than anyone else in the thread, you find out in time to answer it — as
yourself, usefully, before anyone mentions a listing.

---

Team Howe is a team of real estate agents affiliated with Compass. Compass is a
real estate broker licensed by the State of California and abides by Equal
Housing Opportunity laws. License Number 01527235.
