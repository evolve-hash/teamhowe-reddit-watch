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

This was tuned against live data, not guesses. A full run over the twelve
subreddits read **977 posts and kept 42**, of which 17 were flagged worth a
reply. Among them: a couple selling their Fremont condo and shopping flat-fee
agents, somebody asking which of two houses to buy at $2.85M, a first-time buyer
whose father is putting half down, a buyer who wants an hourly attorney instead
of a commissioned buyer's agent, a tenant being offered a buyout on the duplex
he lives in, and a request for realtor recommendations. Nothing about Muni, the
zoo, or burritos made it through.

Two false-positive patterns showed up in that live data and are handled
explicitly. Renters were the big one — "moving to SF", on its own, was the
single largest source of fake leads, so relocation phrases sit in their own
non-lead tier and only become a lead alongside real buy/sell language, and any
rental signal at all ("shared room", "renter's agent", "month-to-month") removes
the lead flag outright. The other was crossposts: the same Chronicle article
submitted to two subreddits showed up twice, so records with the same link or
title are folded into one entry with an "also in r/…" note.

The repository ships already populated with that run, so the dashboard has
real content in it the moment Pages goes live.

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

### What that means in practice, measured

The three transports do not behave the same everywhere, and the difference was
measured on both, not guessed:

| | From a Mac on home internet | From a GitHub Actions runner |
|---|---|---|
| Listing RSS | works | works, but rate limited |
| old.reddit.com HTML | works | **403 — blocked outright** |
| old.reddit.com search | works | **403 — blocked outright** |

Reddit refuses old.reddit.com to datacenter IP ranges, which is most of the
cloud. So on GitHub the crawl runs on RSS alone: it still gets every title,
author, body, timestamp and permalink — everything the scoring needs — but score
and comment counts come back empty, because only the HTML carries those.

The crawler handles this by itself rather than flailing. After two 403s from a
host it marks that host blocked and skips it for the rest of the run, so it stops
burning requests (and stops pushing the shared rate limiter toward throttling the
transport that *does* work). A 429 is waited out in tens of seconds, honouring
`Retry-After` where Reddit sends one, and the whole run slows down after the
first one. Each run reports on the Actions summary page exactly which transports
were blocked and how many requests were throttled — it is never silent about
reduced coverage.

RSS itself is rate limited from those IPs, and measurably so: Reddit served about
seven requests and then threw `429` at everything after. That throttled the *same
tail of the list every single run* — subreddits six through twelve never once got
fetched. A crawler that quietly covers only the first five subreddits is worse
than one that admits it, so the list is now split:

- The four marked `"always": true` in `config.json` — r/sanfrancisco, r/AskSF,
  r/SFBayHousing, r/BayAreaRealEstate — are fetched **every run**, every 20 minutes.
- The other eight **rotate**, two per run, so the full list comes round about
  every 80 minutes.

That is six requests a run, which stays under the throttle. Posts sit on `/new`
for hours, so an hour-old sweep of the long tail loses nothing real; what it buys
is that no subreddit is silently ignored forever. Which subreddits a run touched
is printed in the run summary. To change the balance, move the `"always"` flags
or raise `crawler.rotating_per_run`.

If you want the upvote and comment counts back, run it from the Mac instead —
`local/run_local.sh`, see the fallback section below. Same code, same state file,
and on home internet all three transports work, so it fetches all twelve
subreddits in one pass.

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

### 6. If scheduled runs never fire

Actions has two kinds of trigger and GitHub treats them differently. Pressing
**Run workflow** (`workflow_dispatch`) works from the first minute. `schedule`
does not: on a **brand-new GitHub account** GitHub does not dispatch scheduled
events at all, and it stays that way until the account has a verified email
address and a little history. Measured on this repository: five consecutive
scheduled slots passed with zero runs while manual runs succeeded every time,
on an account eight minutes older than the repo.

If `Actions -> Watch Reddit` shows only "Manually run" entries and no
"Scheduled" ones:

1. Verify the email on the GitHub account (**Settings -> Emails**, click the
   link GitHub sends). This is the usual unlock.
2. Give it an hour and check again for a run whose trigger reads *Scheduled*.
3. In the meantime, and permanently if you prefer, use the Mac schedule in
   `local/` — it publishes to the same site and does not depend on GitHub's
   scheduler at all.

Nothing about the live site depends on this. GitHub Pages serves a static file;
it is up whether or not anything has crawled recently. The schedule only affects
how fresh the numbers are.

### 7. Refreshing it by hand, from the site

The dashboard has a **Refresh now** button in the top-right. It opens the
Actions page for the workflow, where **Run workflow** is one click. Three
minutes later the site has rebuilt.

It is a link rather than a real button on purpose: triggering a workflow needs a
GitHub token, and the dashboard is a public page. Embedding a token there would
let anyone on the internet act on the repository. One extra click is the right
price for that.

### 8. Kick off the first run

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
python3 cli.py mark-seen # set the alert baseline: treat everything currently
                         #   tracked as already alerted
```

`mark-seen` is worth knowing about. The watcher has been running since before the
email was switched on, so there is a backlog of threads it has never emailed
about. Without this, the very first alert email would be twenty-odd threads
spanning three weeks — which is a reading list, not a "reply now". Run it once
before adding the SMTP secrets and alerts start clean; the backlog is all still
on the dashboard. Also worth running after you lower `include_score` or
`hot_score`, for the same reason.

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
- `search_sweeps` — extra keyword searches per subreddit. Only
  `crawler.search_sweeps_per_run` of them run each time (4 by default), rotating
  through the list, so the whole list still gets covered but no single run makes
  two hundred requests. A full run is about 70 requests and takes three minutes.
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

   To have it run itself every twenty minutes — crawl, rebuild, commit and
   push, so the live site stays current with nobody touching anything:

   ```bash
   cp local/com.teamhowe.redditwatch.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.teamhowe.redditwatch.plist
   tail -f logs/watch.log
   ```

   The paths in the plist are already set for this checkout; edit them if you
   move the folder. `launchctl unload` the same path to stop it. This runs only
   while the Mac is awake and online, which is the one thing GitHub's schedule
   does better — so the two together cover each other.

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
