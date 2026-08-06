/**
 * Team Howe Reddit Watch - refresh endpoint.
 *
 * Why this exists: the dashboard is a static page on GitHub Pages, and asking
 * GitHub to run the crawler needs an authenticated request. A token cannot live
 * in a public page - anyone on the internet would be able to act on the repo.
 * So the token lives here instead, as a Cloudflare secret, and the page only
 * ever calls this endpoint.
 *
 * Free tier: 100,000 requests a day, no card required. A button pressed a few
 * times a day will never come close.
 *
 * Deploy: see worker/README.md
 */

const ALLOWED_METHODS = "POST, OPTIONS";
const COOLDOWN_SECONDS = 90;

function corsHeaders(origin, allowed) {
  const headers = {
    "Access-Control-Allow-Methods": ALLOWED_METHODS,
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
  if (origin && allowed.includes(origin)) {
    headers["Access-Control-Allow-Origin"] = origin;
  }
  return headers;
}

function json(body, status, extra) {
  return new Response(JSON.stringify(body), {
    status: status,
    headers: Object.assign(
      { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      extra || {}
    ),
  });
}

/**
 * A crude but effective cooldown. The endpoint is necessarily public, so this
 * keeps an accidental double-click - or a bored bot - from queueing a hundred
 * crawls. The workflow itself also has a concurrency group, so the worst case
 * was always "runs queue up", never "something breaks".
 */
async function recentlyTriggered(cacheKeyUrl) {
  const cache = caches.default;
  const hit = await cache.match(cacheKeyUrl);
  if (hit) return true;
  await cache.put(
    cacheKeyUrl,
    new Response("1", { headers: { "Cache-Control": "max-age=" + COOLDOWN_SECONDS } })
  );
  return false;
}

export default {
  async fetch(request, env) {
    const allowed = (env.ALLOWED_ORIGINS || "")
      .split(",").map((s) => s.trim()).filter(Boolean);
    const origin = request.headers.get("Origin");
    const cors = corsHeaders(origin, allowed);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (request.method !== "POST") {
      return json({ ok: false, error: "Use POST." }, 405, cors);
    }
    if (allowed.length && (!origin || !allowed.includes(origin))) {
      return json({ ok: false, error: "Origin not allowed." }, 403, cors);
    }
    if (!env.GITHUB_TOKEN || !env.REPO) {
      return json(
        { ok: false, error: "Worker is missing GITHUB_TOKEN or REPO." }, 500, cors);
    }

    const lockUrl = "https://reddit-watch.invalid/cooldown";
    if (await recentlyTriggered(lockUrl)) {
      return json({
        ok: false, cooling: true,
        error: "A refresh was just started. Give it a couple of minutes.",
      }, 429, cors);
    }

    const workflow = env.WORKFLOW || "watch.yml";
    const ref = env.BRANCH || "main";
    const api = `https://api.github.com/repos/${env.REPO}/actions/workflows/${workflow}/dispatches`;

    let upstream;
    try {
      upstream = await fetch(api, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Accept": "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          // GitHub rejects API requests with no User-Agent.
          "User-Agent": "teamhowe-reddit-watch-refresh",
        },
        body: JSON.stringify({ ref: ref }),
      });
    } catch (err) {
      return json({ ok: false, error: "Could not reach GitHub." }, 502, cors);
    }

    // 204 No Content is what a successful dispatch returns.
    if (upstream.status === 204) {
      return json({ ok: true, started: true }, 202, cors);
    }

    const detail = await upstream.text();
    // Never echo the token or the raw auth error back to a public page.
    const safe = upstream.status === 401 || upstream.status === 403
      ? "The Worker's GitHub token is missing, expired, or lacks Actions write access."
      : `GitHub answered ${upstream.status}.`;
    console.log("dispatch failed", upstream.status, detail.slice(0, 300));
    return json({ ok: false, error: safe }, 502, cors);
  },
};
