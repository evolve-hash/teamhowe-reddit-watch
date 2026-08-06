# The Refresh button's endpoint

The dashboard is a static page. Starting a crawl means making an authenticated
request to GitHub, and a token cannot live in a public page — anyone could then
act on the repository. So the token lives in this Worker instead, and the page
only ever talks to the Worker.

**Cost: nothing.** Cloudflare's free plan allows 100,000 Worker requests per day
and does not ask for a card. A button pressed a few times a day uses a rounding
error of that.

---

## Setup, five steps

You need Node installed (`node -v`). Everything below runs from this folder.

### 1. Make the GitHub token

GitHub → **Settings → Developer settings → Personal access tokens → Fine-grained
tokens → Generate new token**.

- **Repository access:** Only select repositories → `teamhowe-reddit-watch`
- **Permissions → Repository permissions → Actions:** **Read and write**
- Nothing else. No other permission is needed and none should be granted.
- Expiration: whatever you are comfortable with. When it expires the button
  stops working and the page will say so; you regenerate and repeat step 3.

Copy the token. This is the only moment GitHub shows it to you.

### 2. Log in to Cloudflare

```bash
cd worker
npx wrangler login
```

A browser window opens; approve it. If you have no Cloudflare account, the same
flow will offer to create one — free, no card.

### 3. Store the token as a secret

```bash
npx wrangler secret put GITHUB_TOKEN
```

Paste the token when prompted. It is stored encrypted by Cloudflare. It is never
in this repository, never in the dashboard, and never visible in the Worker's
logs.

### 4. Deploy

```bash
npx wrangler deploy
```

Wrangler prints the URL, something like
`https://teamhowe-reddit-watch.<your-subdomain>.workers.dev`.

### 5. Point the dashboard at it

In `config.json`, set:

```json
"site": {
  "refresh_endpoint": "https://teamhowe-reddit-watch.<your-subdomain>.workers.dev"
}
```

Commit and push. The button changes from "opens GitHub" to a real refresh: it
starts the crawl, shows progress, and reloads the page when the new data is
live — roughly four minutes, most of which is the crawler being polite to
Reddit.

Until `refresh_endpoint` is set, the button falls back to opening the GitHub
Actions page, so nothing is ever broken mid-setup.

---

## Checking it

```bash
curl -X POST -H "Origin: https://evolve-hash.github.io" \
     https://teamhowe-reddit-watch.<your-subdomain>.workers.dev
```

- `{"ok":true,"started":true}` — working.
- `{"ok":false,"error":"...token is missing, expired, or lacks Actions write access."}`
  — redo steps 1 and 3.
- `{"ok":false,"cooling":true,...}` — the 90-second cooldown; wait and retry.

Logs: `npx wrangler tail`.

---

## What it will and will not do

It dispatches one workflow, on one repository, and nothing else. The token it
holds can only write to Actions on that single repo — it cannot read your code,
push commits, or touch anything else you own.

The endpoint is public, because the page that calls it is public. Two things
keep that boring: a 90-second cooldown in the Worker, and a concurrency group on
the workflow, so the worst a determined stranger achieves is making Team Howe's
dashboard slightly more up to date than it needs to be. Actions minutes on a
public repository are free and unmetered.
