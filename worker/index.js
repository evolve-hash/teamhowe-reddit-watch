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

/**
 * Hosts /fetch is willing to read on the crawler's behalf. Keeping this list
 * short is the whole security model: the endpoint has to be public (a GitHub
 * runner cannot present a browser Origin), so it must not be usable as a
 * general purpose open proxy. Reddit and one keyless reddit archive, nothing
 * else, GET only, no request body forwarded, no cookies.
 */
const FETCH_ALLOWED_HOSTS = [
  "www.reddit.com",
  "old.reddit.com",
  "reddit.com",
  "api.pullpush.io",
];

const FETCH_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";

/**
 * Read-through proxy for the crawler.
 *
 * Why: reddit refuses unauthenticated requests from datacenter address space,
 * and GitHub's hosted runners are datacenter address space - a scheduled run on
 * 2026-08-07 fetched 0 posts from 6 subreddits, every one a 403. Requests made
 * from a Worker leave Cloudflare's edge instead, which is a different answer to
 * the same question. Responses are cached briefly so a burst of subreddits does
 * not turn into a burst of upstream hits.
 */
async function proxyFetch(request, env) {
  const target = new URL(request.url).searchParams.get("url");
  if (!target) {
    return json({ ok: false, error: "Pass ?url=" }, 400, {});
  }
  let parsed;
  try {
    parsed = new URL(target);
  } catch (err) {
    return json({ ok: false, error: "Malformed url." }, 400, {});
  }
  const hosts = (env.FETCH_HOSTS || FETCH_ALLOWED_HOSTS.join(","))
    .split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  if (parsed.protocol !== "https:" || !hosts.includes(parsed.hostname.toLowerCase())) {
    return json({ ok: false, error: "Host not allowed." }, 403, {});
  }

  let upstream;
  try {
    upstream = await fetch(parsed.toString(), {
      headers: {
        "User-Agent": env.FETCH_UA || FETCH_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
      },
      cf: { cacheTtl: 120, cacheEverything: true },
      redirect: "follow",
    });
  } catch (err) {
    return json({ ok: false, error: "Upstream unreachable." }, 502, {});
  }

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "Content-Type":
        upstream.headers.get("Content-Type") || "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=120",
      "X-Upstream-Status": String(upstream.status),
      "X-Upstream-Host": parsed.hostname,
    },
  });
}

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

    // The crawler's read-through proxy. Deliberately before the POST-only gate:
    // this one is a GET, and it is called from a GitHub runner, which has no
    // browser Origin to check. Its protection is the host allow-list.
    if (new URL(request.url).pathname === "/fetch") {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return json({ ok: false, error: "Use GET." }, 405, {});
      }
      return proxyFetch(request, env);
    }

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
