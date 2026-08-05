#!/bin/bash
# Runs one full cycle from this Mac and publishes the result.
#
#   crawl reddit -> score -> rebuild the dashboard -> commit -> push
#                -> GitHub Pages rebuilds -> the live site is current
#
# Why this exists in two flavours:
#
#   * GitHub Actions is the primary schedule and needs nothing from you.
#   * This script is the belt and braces. It also does something Actions
#     cannot: from home internet all three transports work, so it fetches all
#     twelve subreddits in one pass and brings back upvote and comment counts,
#     which old.reddit.com refuses to serve to datacenter IPs.
#
# Both write to the same data/posts.json, so they cannot fight - whoever runs
# last simply has the fuller picture.
#
# One-off:
#   chmod +x local/run_local.sh && ./local/run_local.sh
#
# Every 20 minutes, unattended: see local/com.teamhowe.redditwatch.plist

set -uo pipefail
cd "$(dirname "$0")/.."
REPO="$(pwd)"

# launchd gives a minimal PATH; Homebrew and gh live outside it.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Optional: SMTP credentials, if you want this machine to send the emails too.
# Put them in local/env.sh, which is gitignored:
#   export SMTP_HOST="smtp.gmail.com"
#   export SMTP_PORT="587"
#   export SMTP_USER="you@teamhowe.com"
#   export SMTP_PASSWORD="your-16-character-app-password"
[ -f local/env.sh ] && . local/env.sh

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "python3 not found. Run: xcode-select --install" >&2
  exit 1
fi

mkdir -p logs
LOG="logs/watch.log"
STAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"

{
  echo ""
  echo "=========== run $STAMP ==========="
  "$PY" -u cli.py run
  RC=$?

  # Publish, but only if this really is the git repo and something changed.
  if [ -d .git ] && [ "$RC" -eq 0 ]; then
    if [ -n "$(git status --porcelain data docs 2>/dev/null)" ]; then
      git add data docs
      git commit -q -m "Reddit watch (local): $(date -u '+%Y-%m-%d %H:%M UTC')" || true
      # A GitHub Actions run may have pushed since we last pulled.
      for attempt in 1 2 3; do
        git pull --rebase --autostash -q origin main && break
        sleep 5
      done
      if git push -q origin main; then
        echo "published: GitHub Pages will rebuild in about a minute"
      else
        echo "push failed - the crawl is still saved locally, next run retries" >&2
      fi
    else
      echo "nothing changed this run"
    fi
  fi
} 2>&1 | tee -a "$LOG"

# Keep the log from growing without bound.
if [ -f "$LOG" ] && [ "$(wc -l < "$LOG")" -gt 4000 ]; then
  tail -n 2000 "$LOG" > "$LOG.trim" && mv "$LOG.trim" "$LOG"
fi

echo ""
echo "Local dashboard: file://$REPO/docs/index.html"
