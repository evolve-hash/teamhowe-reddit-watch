#!/bin/bash
# Fallback runner: use this if GitHub's servers ever get blocked by Reddit.
# Same code, same output - it just runs from your own machine and internet
# connection, which Reddit is far more relaxed about.
#
#   chmod +x local/run_local.sh
#   ./local/run_local.sh
#
# To schedule it, see local/com.teamhowe.redditwatch.plist.

set -euo pipefail
cd "$(dirname "$0")/.."

# Email credentials, if you want the alerts to send from here too.
# Leave them unset and the run still builds the dashboard and writes previews.
#   export SMTP_HOST="smtp.gmail.com"
#   export SMTP_PORT="587"
#   export SMTP_USER="you@teamhowe.com"
#   export SMTP_PASSWORD="your-16-character-app-password"
[ -f local/env.sh ] && source local/env.sh

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "python3 not found. Install it from python.org or run: xcode-select --install" >&2
  exit 1
fi

mkdir -p logs
STAMP="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
{
  echo "=== run $STAMP ==="
  "$PY" cli.py run
} 2>&1 | tee -a "logs/watch.log"

echo ""
echo "Dashboard: file://$(pwd)/docs/index.html"
