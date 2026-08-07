"""
Builds docs/index.html - the Team Howe branded dashboard.

Single self-contained file: brand CSS inline, post data embedded as JSON,
vanilla JS for filtering/sorting and the daily-volume column chart. Nothing
to install, works from a file:// path or GitHub Pages.
"""

import json
import os
from datetime import datetime, timedelta, timezone

from . import brand
from .dedupe import fold

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>__TITLE__ | Team Howe</title>
<link rel="icon" href="__FAVICON__">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="__GOOGLE_FONTS__">
<style>
:root{
  --font:__FONT__;
  --ink:#211f1f; --ink-soft:#4a4646; --muted:#6f6f6f; --muted-2:#848484;
  --surface:#ffffff; --surface-2:#f8f8f8; --surface-3:#f6f0ea;
  --border:#eeeeee; --border-2:#e2ded9;
  --beige:#ccb091; --beige-deep:#86664a; --bar:#a8825c;
  --hot:#8c2f27; --hot-wash:#f9eeec; --hot-line:#e7c9c4;
  --lead:#4d5b3d; --lead-wash:#f0f2ec; --lead-line:#cfd8c2;
  --dark:#211f1f;
}
html[data-theme="dark"]{
  --ink:#f4f2f0; --ink-soft:#d8d4d0; --muted:#a8a29c; --muted-2:#9a938c;
  --surface:#141414; --surface-2:#1e1c1c; --surface-3:#241f1b;
  --border:#2e2b2b; --border-2:#3a3634;
  --beige:#ccb091; --beige-deep:#ccb091; --bar:#ccb091;
  --hot:#e0a49a; --hot-wash:#2a1b19; --hot-line:#4b302c;
  --lead:#adc48f; --lead-wash:#1c2118; --lead-line:#333d29;
  --dark:#0d0d0d;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0;max-width:100%;overflow-x:hidden}
body{
  font-family:var(--font); font-size:16px; line-height:1.65;
  color:var(--ink); background:var(--surface);
  -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;
}
a{color:inherit}
.wrap{max-width:1160px;margin:0 auto;padding:0 28px}
.eyebrow{
  font-size:11px;font-weight:600;letter-spacing:.22em;text-transform:uppercase;
  color:var(--beige-deep);margin:0 0 14px;
}
h1,h2,h3{font-weight:400;letter-spacing:-.01em;margin:0}
h1{font-size:45px;line-height:1.12}
h2{font-size:28px;line-height:1.2}
h3{font-size:20px;line-height:1.35}

/* ---------------------------------------------------------- masthead --- */
.masthead{background:var(--dark);color:#fff;padding:0}
.masthead .wrap{
  display:flex;align-items:center;gap:24px;min-height:88px;
  padding-top:14px;padding-bottom:14px;
}
.masthead img{height:34px;width:auto;display:block}
.masthead .rule{width:1px;height:34px;background:rgba(255,255,255,.28)}
.masthead .tag{
  font-size:11px;letter-spacing:.22em;text-transform:uppercase;
  font-weight:500;color:#ccb091;
}
.masthead .right{margin-left:auto;display:flex;align-items:center;gap:18px}
.masthead .stamp{font-size:11.5px;letter-spacing:.06em;color:#b6b6b6;text-align:right}
.masthead .stamp .when{display:block}
.themebtn,.refreshbtn{
  background:transparent;border:1px solid rgba(255,255,255,.3);color:#fff;
  font-family:var(--font);font-size:10px;font-weight:600;letter-spacing:.18em;
  text-transform:uppercase;padding:9px 14px;cursor:pointer;text-decoration:none;
  display:inline-block;white-space:nowrap;
}
.themebtn:hover,.refreshbtn:hover{border-color:#ccb091;color:#ccb091}
.refreshbtn{background:#ccb091;border-color:#ccb091;color:#211f1f}
.refreshbtn:hover{background:transparent;color:#ccb091}

/* -------------------------------------------------------------- lede --- */
.lede{padding:64px 0 40px;border-bottom:1px solid var(--border)}
.lede p.sub{
  margin:18px 0 0;max-width:60ch;font-size:17px;color:var(--muted);font-weight:300;
}

/* --------------------------------------------------------------- kpis --- */
.kpiband{border-bottom:1px solid var(--border)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr)}
.kpi{padding:34px 0 32px;border-left:1px solid var(--border);padding-left:26px}
.kpi:first-child{border-left:0;padding-left:0}
.kpi .k-label{
  font-size:10.5px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;
  color:var(--muted);margin:0 0 12px;min-height:2.4em;
}
.kpi .k-value{font-size:44px;font-weight:600;line-height:1;letter-spacing:-.02em}
.kpi .k-delta{font-size:12.5px;color:var(--muted);margin-top:10px;padding-right:20px}
.kpi.is-hot .k-value{color:var(--hot)}

/* -------------------------------------------------------------- chart --- */
.chartcard{padding:44px 0 40px;border-bottom:1px solid var(--border)}
.chart-head{display:flex;align-items:baseline;gap:16px;flex-wrap:wrap;margin-bottom:26px}
.chart-head h3{font-size:20px}
.chart-head .note{font-size:12.5px;color:var(--muted)}
#chart{width:100%;height:170px;display:block;overflow:visible}
#chart .grid{stroke:var(--border);stroke-width:1;shape-rendering:crispEdges}
#chart .bar{fill:var(--bar)}
#chart .bar.dim{fill:var(--border-2)}
#chart .hit{fill:transparent;cursor:pointer}
#chart text{font-family:var(--font);fill:var(--muted);font-size:10.5px}
#chart text.val{fill:var(--ink);font-weight:600;font-size:11px}
.tt{
  position:fixed;z-index:60;pointer-events:none;opacity:0;transition:opacity .1s;
  background:var(--dark);color:#fff;padding:9px 13px;font-size:12px;line-height:1.5;
  box-shadow:0 8px 24px rgba(0,0,0,.22);white-space:nowrap;
}
.tt b{color:#ccb091;font-weight:600}
details.datatable{margin-top:22px}
details.datatable summary{
  cursor:pointer;font-size:11px;font-weight:600;letter-spacing:.16em;
  text-transform:uppercase;color:var(--muted);
}
details.datatable table{border-collapse:collapse;margin-top:16px;font-size:13px}
details.datatable th,details.datatable td{
  border-bottom:1px solid var(--border);padding:7px 20px 7px 0;text-align:left;
  font-variant-numeric:tabular-nums;font-weight:400;
}
details.datatable th{
  font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:600;
}

/* ----------------------------------------------------------- controls --- */
.controls{
  position:sticky;top:0;z-index:40;background:var(--surface);
  border-bottom:1px solid var(--border);padding:16px 0;
}
.controls .wrap{display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.controls input[type=search],.controls select{
  font-family:var(--font);font-size:13px;color:var(--ink);background:var(--surface);
  border:1px solid var(--border-2);padding:10px 13px;min-width:0;
}
.controls input[type=search]{flex:1 1 240px}
.controls input[type=search]::placeholder{color:var(--muted-2)}
.seg{display:flex;border:1px solid var(--border-2)}
.seg button{
  font-family:var(--font);font-size:10.5px;font-weight:600;letter-spacing:.14em;
  text-transform:uppercase;background:transparent;color:var(--muted);border:0;
  padding:11px 15px;cursor:pointer;border-left:1px solid var(--border-2);
}
.seg button:first-child{border-left:0}
.seg button[aria-pressed=true]{background:var(--dark);color:#fff}
html[data-theme=dark] .seg button[aria-pressed=true]{background:var(--beige);color:#211f1f}
.count{font-size:12.5px;color:var(--muted);margin-left:auto;white-space:nowrap}

/* ------------------------------------------------------------ results --- */
.results{padding:8px 0 70px}
.card{
  padding:28px 0;border-bottom:1px solid var(--border);
  display:grid;grid-template-columns:76px 1fr;gap:26px;
}
.score{text-align:center;padding-top:4px}
.score .n{font-size:27px;font-weight:600;line-height:1;letter-spacing:-.02em}
.score .l{
  font-size:9px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:var(--muted);margin-top:6px;
}
.card.hot .score .n{color:var(--hot)}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:11px}
.badge{
  font-size:9.5px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  padding:5px 9px;display:inline-flex;align-items:center;gap:6px;
}
.badge.hot{background:var(--hot-wash);color:var(--hot);border:1px solid var(--hot-line)}
.badge.lead{background:var(--lead-wash);color:var(--lead);border:1px solid var(--lead-line)}
.badge.new{background:var(--surface-3);color:var(--beige-deep);border:1px solid var(--border-2)}
.card h3 a{text-decoration:none;background-image:linear-gradient(var(--beige),var(--beige));
  background-size:0 1px;background-repeat:no-repeat;background-position:0 100%;
  transition:background-size .2s}
.card h3 a:hover{background-size:100% 1px}
.meta{font-size:12.5px;color:var(--muted);margin-top:10px;display:flex;flex-wrap:wrap;gap:0}
.meta span:not(:first-child)::before{content:"·";margin:0 9px;color:var(--border-2)}
.meta a{color:var(--muted);text-decoration:none;border-bottom:1px solid var(--border-2)}
.meta a:hover{color:var(--ink)}
.excerpt{margin:14px 0 0;font-size:14.5px;color:var(--ink-soft);font-weight:300;max-width:78ch}
.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:15px}
.chip{
  font-size:11px;color:var(--muted);border:1px solid var(--border);
  padding:4px 9px;background:var(--surface-2);
}
.actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:18px}
.btn{
  font-size:10px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;
  text-decoration:none;padding:11px 17px;border:1px solid var(--ink);color:var(--ink);
  background:transparent;cursor:pointer;font-family:var(--font);
}
.btn:hover{background:var(--ink);color:var(--surface)}
.btn.primary{background:var(--ink);color:var(--surface)}
.btn.primary:hover{background:var(--beige-deep);border-color:var(--beige-deep);color:#fff}
.btn.dismiss{border-color:var(--border-2);color:var(--muted)}
.btn.dismiss:hover{background:var(--hot);border-color:var(--hot);color:#fff}
.card.gone{display:none}
.dismissbar{
  display:flex;align-items:center;gap:14px;flex-wrap:wrap;
  padding:16px 0;border-bottom:1px solid var(--border);
}
.dismissbar .n{font-size:12.5px;color:var(--muted)}
.linkbtn{
  background:none;border:0;padding:0;cursor:pointer;font-family:var(--font);
  font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;
  color:var(--beige-deep);border-bottom:1px solid var(--border-2);
}
.linkbtn:hover{color:var(--ink);border-bottom-color:var(--ink)}
.learn{
  background:var(--surface-3);border:1px solid var(--border-2);
  padding:22px 24px;margin:20px 0 0;
}
.learn h3{font-size:15px;font-weight:500;margin:0 0 8px}
.learn p{margin:0 0 14px;font-size:13.5px;color:var(--ink-soft);font-weight:300;max-width:70ch}
.learn code{
  display:block;background:var(--surface);border:1px solid var(--border);
  padding:12px 14px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
  font-size:12px;color:var(--ink);white-space:pre-wrap;word-break:break-word;margin:0 0 12px;
}
.learn .why{font-size:12.5px;color:var(--muted);margin-bottom:12px}
.review .card{opacity:.55}
.review .card .btn.dismiss{border-color:var(--lead);color:var(--lead)}
.empty{padding:80px 0;text-align:center;color:var(--muted)}
.empty strong{display:block;font-size:20px;color:var(--ink);font-weight:400;margin-bottom:8px}

/* ------------------------------------------------------------- footer --- */
footer{background:var(--dark);color:#b6b6b6;padding:56px 0 46px;font-weight:300}
footer .top{display:flex;gap:40px;flex-wrap:wrap;align-items:flex-start;margin-bottom:34px}
footer img{height:30px;width:auto}
footer .contact{font-size:13px;line-height:1.9}
footer .contact a{color:#fff;text-decoration:none}
footer .contact a:hover{color:#ccb091}
footer .tagline{
  font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:#ccb091;margin-bottom:12px;
}
footer .legal{font-size:11px;line-height:1.85;color:#9f9f9f;border-top:1px solid rgba(255,255,255,.14);padding-top:24px}
footer .legal .cr{color:#d0cdca;display:block;margin-bottom:8px}

/* ------------------------------------------------------------- mobile --- */
/* The masthead is the one row that cannot survive being squeezed: a logo, a
   timestamp and two controls do not fit across a phone. Rather than shrink
   everything until it overflows, it becomes three short rows -
   logo + theme toggle, then the timestamp, then Refresh full width, which is
   also the easiest thing to hit with a thumb. `display:contents` on .right
   lets its children take part in the wrap directly. */
@media (max-width:900px){
  h1{font-size:32px}
  .wrap{padding:0 20px}

  .masthead .wrap{
    flex-wrap:wrap;align-items:center;min-height:0;gap:12px;
    padding-top:16px;padding-bottom:18px;
  }
  .masthead .right{display:contents}
  .masthead .tag,.masthead .rule{display:none}
  .masthead img{height:26px}
  .masthead .brand{order:1;margin-right:auto;min-width:0}
  .masthead .themebtn{order:2;flex:0 0 auto}
  .masthead .stamp{
    order:3;flex:0 0 100%;text-align:left;font-size:11px;line-height:1.5;
  }
  .masthead .stamp .when{display:inline}
  .masthead .refreshbtn{order:4;flex:0 0 100%;text-align:center;padding:13px 14px}

  .kpis{grid-template-columns:repeat(2,1fr)}
  .kpi{border-left:0;border-top:1px solid var(--border);padding:26px 0 24px;padding-left:0}
  .kpi:nth-child(-n+2){border-top:0}
  .kpi:nth-child(even){border-left:1px solid var(--border);padding-left:22px}
  /* Keep two lines of room so a wrapping label does not shove its number out
     of line with the number beside it. */
  .kpi .k-label{min-height:3.1em}
  .kpi .k-value{font-size:38px}

  .card{grid-template-columns:1fr;gap:0}
  .score{display:flex;align-items:baseline;gap:10px;text-align:left;margin-bottom:12px}
  .score .l{margin-top:0}
  .lede{padding:44px 0 30px}
  .lede p.sub{font-size:16px}
  .chart-head{margin-bottom:20px}
  .controls{padding:14px 0}
  .controls .wrap{gap:10px}
  .count{margin-left:0;flex:0 0 100%}
  .btn{padding:11px 14px;letter-spacing:.12em}
  /* The meta line wraps on a phone, and a middot inherited from ::before then
     dangles at the start of the new line. Drop the separators and let the gap
     do the work. */
  .meta{gap:2px 14px}
  .meta span:not(:first-child)::before{content:"";margin:0}
}

/* Small phones. Nothing may exceed the viewport here either. */
@media (max-width:400px){
  .wrap{padding:0 16px}
  h1{font-size:28px}
  .masthead img{height:23px}
  .masthead .themebtn{padding:8px 10px;letter-spacing:.12em}
  .masthead .stamp{font-size:10.5px}
  .kpi .k-value{font-size:32px}
  .kpi:nth-child(even){padding-left:16px}
  .seg button{padding:11px 11px;letter-spacing:.1em}
  .btn{font-size:9.5px;padding:11px 12px}
  .chip{font-size:10.5px}
  .excerpt{font-size:14px}
}

/* Only the narrowest phones give up the two-column stat row. */
@media (max-width:340px){
  .kpis{grid-template-columns:1fr}
  .kpi{border-left:0!important;padding-left:0!important;padding-top:22px;padding-bottom:20px}
  .kpi:first-child{border-top:0}
  .kpi .k-label{min-height:0}
}
/* Shown only when the last crawl came back empty, or when nothing has been
   collected in a while. A page that silently republishes two day old threads
   under a fresh "Updated" stamp is worse than a page that admits it. */
.stale{background:var(--hot-wash);border-bottom:1px solid var(--hot-line)}
.stale .wrap{
  display:flex;align-items:baseline;gap:8px 14px;flex-wrap:wrap;
  padding-top:14px;padding-bottom:14px;
}
.stale .tagword{
  font-size:10.5px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;
  color:var(--hot);white-space:nowrap;
}
.stale p{margin:0;font-size:14px;line-height:1.5;color:var(--ink-soft);flex:1 1 320px}
.stale .why{color:var(--muted);font-size:12.5px;display:block;margin-top:3px}
@media (max-width:400px){.stale p{font-size:13.5px}}

@media print{.controls,.themebtn,.actions{display:none}body{background:#fff}}
</style>
</head>
<body data-palette="__BAR__">

<header class="masthead">
  <div class="wrap">
    <a class="brand" href="__WEBSITE__"><img src="__LOGO_LIGHT__" alt="Team Howe | Compass"></a>
    <div class="rule"></div>
    <div class="tag">__TITLE__</div>
    <div class="right">
      <div class="stamp">Updated <span class="when">__UPDATED__</span></div>
      __REFRESH_BTN__
      <button class="themebtn" id="themebtn" type="button">Dark</button>
    </div>
  </div>
</header>
__STALE_BANNER__
<section class="lede"><div class="wrap">
  <p class="eyebrow">Lead intelligence</p>
  <h1>__HEADLINE__</h1>
  <p class="sub">__SUBTITLE__</p>
</div></section>

<section class="kpiband"><div class="wrap"><div class="kpis">
  <div class="kpi is-hot">
    <p class="k-label">Worth a reply now</p>
    <div class="k-value">__KPI_HOT__</div>
    <div class="k-delta">Open threads flagged hot or as a lead</div>
  </div>
  <div class="kpi">
    <p class="k-label">New in last 7 days</p>
    <div class="k-value">__KPI_WEEK__</div>
    <div class="k-delta">__KPI_WEEK_DELTA__</div>
  </div>
  <div class="kpi">
    <p class="k-label">Threads tracked</p>
    <div class="k-value">__KPI_TOTAL__</div>
    <div class="k-delta">Rolling __HISTORY_DAYS__-day window</div>
  </div>
  <div class="kpi">
    <p class="k-label">Subreddits watched</p>
    <div class="k-value">__KPI_SUBS__</div>
    <div class="k-delta">__KPI_SUBS_DELTA__</div>
  </div>
</div></div></section>

<section class="chartcard"><div class="wrap">
  <div class="chart-head">
    <h3>Matching threads per day</h3>
    <span class="note">Last __CHART_DAYS__ days &middot; hover a column for the count</span>
  </div>
  <svg id="chart" role="img" aria-label="Matching threads per day over the last __CHART_DAYS__ days"></svg>
  <details class="datatable">
    <summary>View as data table</summary>
    <table><thead><tr><th>Date</th><th>Matching threads</th></tr></thead>
    <tbody id="chart-table"></tbody></table>
  </details>
</div></section>

<section class="controls"><div class="wrap">
  <input type="search" id="q" placeholder="Search titles, text, keywords, usernames&hellip;" aria-label="Search threads">
  <select id="sub" aria-label="Filter by subreddit"></select>
  <div class="seg" role="group" aria-label="Filter by priority">
    <button type="button" data-view="hot" aria-pressed="true">Worth a reply</button>
    <button type="button" data-view="all" aria-pressed="false">Everything</button>
  </div>
  <select id="sort" aria-label="Sort">
    <option value="relevance">Sort: Relevance</option>
    <option value="new">Sort: Newest</option>
    <option value="comments">Sort: Most comments</option>
    <option value="score">Sort: Most upvotes</option>
  </select>
  <select id="range" aria-label="Time range">
    <option value="3">Last 3 days</option>
    <option value="7">Last 7 days</option>
    <option value="14" selected>Last 14 days</option>
    <option value="9999">All tracked</option>
  </select>
  <span class="count" id="count"></span>
</div></section>

<section class="dismissbar" id="dismissbar" hidden><div class="wrap" style="display:flex;align-items:center;gap:14px;flex-wrap:wrap">
  <span class="n" id="dismiss-n"></span>
  <button class="linkbtn" id="dismiss-toggle" type="button">Review dismissed</button>
  <button class="linkbtn" id="dismiss-clear" type="button">Bring them all back</button>
</div></section>

<section id="learnwrap"><div class="wrap"><div class="learn" id="learn" hidden>
  <h3 id="learn-title"></h3>
  <p id="learn-body"></p>
  <div class="why" id="learn-why"></div>
  <code id="learn-code"></code>
  <button class="btn" id="learn-copy" type="button">Copy this</button>
</div></div></section>

<main class="results"><div class="wrap" id="list"></div></main>

<footer><div class="wrap">
  <div class="top">
    <div><img src="__LOGO_LIGHT__" alt="Team Howe | Compass"></div>
    <div class="contact">
      <div class="tagline">__TAGLINE__</div>
      <a href="__PHONE_HREF__">__PHONE__</a><br>
      __ADDRESS__<br>
      <a href="__WEBSITE__">teamhowe.com</a>
    </div>
  </div>
  <div class="legal">
    <span class="cr">__COPYRIGHT__</span>
    __LEGAL__
  </div>
</div></footer>

<div class="tt" id="tt"></div>

<script id="payload" type="application/json">__DATA__</script>
<script>
(function(){
  "use strict";
  var DATA = JSON.parse(document.getElementById("payload").textContent);
  var posts = DATA.posts, daily = DATA.daily;
  var state = {q:"", sub:"", view:"hot", sort:"relevance", range:14, review:false};

  /* ---------------------------------------------------------- dismissals --
     Sherri's request: "it would be nice to be able to check it off the list as
     not relevant so I don't have to keep seeing it". Kept in this browser, so
     it works instantly and offline and needs nothing from the server. What she
     dismisses is also used to spot a pattern - see renderLearn(). */
  var DKEY = "teamhowe-reddit-watch-dismissed-v1";
  var dismissed = {};
  try { dismissed = JSON.parse(localStorage.getItem(DKEY) || "{}") || {}; }
  catch (e) { dismissed = {}; }
  function persist(){
    try { localStorage.setItem(DKEY, JSON.stringify(dismissed)); } catch (e) {}
  }
  function isDismissed(id){ return Object.prototype.hasOwnProperty.call(dismissed, id); }
  function dismiss(p){
    dismissed[p.id] = {
      t: p.title, sub: p.subreddit,
      places: p.places || [], elsewhere: p.elsewhere || [],
      when: Math.floor(Date.now()/1000)
    };
    persist();
  }
  function restore(id){ delete dismissed[id]; persist(); }

  /* ------------------------------------------------------------- theme -- */
  var root = document.documentElement, tbtn = document.getElementById("themebtn");
  function setTheme(t){
    root.setAttribute("data-theme", t);
    tbtn.textContent = (t === "dark" ? "Light" : "Dark");
    drawChart();
  }
  tbtn.addEventListener("click", function(){
    setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) setTheme("dark");

  /* -------------------------------------------------------------- utils -- */
  function ago(epoch){
    if(!epoch) return "unknown time";
    var s = Math.floor(Date.now()/1000) - epoch;
    if (s < 90) return "just now";
    if (s < 3600) return Math.round(s/60) + " min ago";
    if (s < 86400) { var h = Math.round(s/3600); return h + (h===1?" hour ago":" hours ago"); }
    var d = Math.round(s/86400);
    if (d < 14) return d + (d===1?" day ago":" days ago");
    if (d < 70) return Math.round(d/7) + " weeks ago";
    return new Date(epoch*1000).toLocaleDateString("en-US",
      {month:"short", day:"numeric", year:"numeric"});
  }
  function plural(n, one, many){ return n + " " + (n === 1 ? one : many); }
  function esc(s){
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
  }
  function num(n){ return (n === null || n === undefined) ? "–" : String(n); }

  /* ----------------------------------------------------------- tooltip -- */
  var tt = document.getElementById("tt");
  function showTip(html, x, y){
    tt.innerHTML = html; tt.style.opacity = "1";
    var r = tt.getBoundingClientRect();
    tt.style.left = Math.max(8, Math.min(x - r.width/2, window.innerWidth - r.width - 8)) + "px";
    tt.style.top = Math.max(8, y - r.height - 12) + "px";
  }
  function hideTip(){ tt.style.opacity = "0"; }

  /* ------------------------------------------------------------- chart -- */
  var SVG = "http://www.w3.org/2000/svg";
  function el(name, attrs){
    var node = document.createElementNS(SVG, name);
    for (var k in attrs) if (attrs.hasOwnProperty(k)) node.setAttribute(k, attrs[k]);
    return node;
  }
  function drawChart(){
    var svg = document.getElementById("chart");
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = svg.clientWidth || 1100, H = 170;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    var padL = 34, padR = 8, padT = 22, padB = 26;
    var plotW = W - padL - padR, plotH = H - padT - padB;
    var max = 1;
    daily.forEach(function(d){ if (d.n > max) max = d.n; });
    var ticks = niceTicks(max);
    var top = ticks[ticks.length-1];

    ticks.forEach(function(t){
      var y = padT + plotH - (t/top)*plotH;
      svg.appendChild(el("line", {class:"grid", x1:padL, x2:W-padR, y1:y, y2:y}));
      var label = el("text", {x:padL-9, y:y+3.5, "text-anchor":"end"});
      label.textContent = t;
      svg.appendChild(label);
    });

    var band = plotW / daily.length;
    var GAP = 2;                                  /* surface gap, 2px */
    var barW = Math.min(24, Math.max(3, band - GAP));
    var peak = -1, peakVal = -1;
    daily.forEach(function(d, i){ if (d.n > peakVal){ peakVal = d.n; peak = i; } });

    daily.forEach(function(d, i){
      var x = padL + i*band + (band - barW)/2;
      var h = (d.n/top) * plotH;
      var y = padT + plotH - h;
      if (d.n > 0){
        var r = Math.min(4, barW/2, h);
        /* rounded data-end, square at the baseline */
        var path = "M" + x + "," + (padT+plotH) +
                   " L" + x + "," + (y+r) +
                   " Q" + x + "," + y + " " + (x+r) + "," + y +
                   " L" + (x+barW-r) + "," + y +
                   " Q" + (x+barW) + "," + y + " " + (x+barW) + "," + (y+r) +
                   " L" + (x+barW) + "," + (padT+plotH) + " Z";
        svg.appendChild(el("path", {class:"bar", d:path}));
      }
      var hit = el("rect", {class:"hit", x:padL+i*band, y:padT, width:band, height:plotH});
      hit.addEventListener("mousemove", function(ev){
        showTip("<b>" + d.n + "</b> matching thread" + (d.n===1?"":"s") + "<br>" + d.label, ev.clientX, ev.clientY);
      });
      hit.addEventListener("mouseleave", hideTip);
      svg.appendChild(hit);
      if (i === peak && peakVal > 0){
        var val = el("text", {class:"val", x:x + barW/2, y:y-7, "text-anchor":"middle"});
        val.textContent = peakVal;
        svg.appendChild(val);
      }
      if (i === 0 || i === daily.length-1 || i === Math.floor(daily.length/2)){
        var tick = el("text", {x:x + barW/2, y:H-8, "text-anchor": i===0 ? "start" : (i===daily.length-1 ? "end" : "middle")});
        tick.textContent = d.short;
        svg.appendChild(tick);
      }
    });
  }
  function niceTicks(max){
    var step = Math.max(1, Math.ceil(max/4));
    var mag = Math.pow(10, Math.floor(Math.log(step)/Math.LN10));
    step = Math.ceil(step/mag)*mag;
    var out = [], t = 0;
    while (t <= max + step*0.001){ out.push(t); t += step; }
    if (out.length < 2) out.push(step);
    return out;
  }
  window.addEventListener("resize", drawChart);

  var tbody = document.getElementById("chart-table");
  tbody.innerHTML = daily.map(function(d){
    return "<tr><td>" + esc(d.label) + "</td><td>" + d.n + "</td></tr>";
  }).join("");

  /* ------------------------------------------------------------ filter -- */
  var subSelect = document.getElementById("sub");
  var subs = {};
  posts.forEach(function(p){ subs[p.subreddit] = (subs[p.subreddit]||0) + 1; });
  var subNames = Object.keys(subs).sort(function(a,b){ return subs[b]-subs[a]; });
  subSelect.innerHTML = '<option value="">All subreddits</option>' + subNames.map(function(s){
    return '<option value="' + esc(s) + '">r/' + esc(s) + " (" + subs[s] + ")</option>";
  }).join("");

  function matches(p){
    if (state.review) return isDismissed(p.id);
    if (isDismissed(p.id)) return false;
    if (state.sub && p.subreddit !== state.sub) return false;
    if (state.view === "hot" && p.verdict !== "hot") return false;
    if (state.range < 9999){
      var cutoff = Date.now()/1000 - state.range*86400;
      if ((p.created_utc || 0) < cutoff) return false;
    }
    if (state.q){
      var hay = (p.title + " " + (p.excerpt||"") + " " + p.author + " " + p.subreddit + " " +
                 (p.hits||[]).join(" ") + " " + (p.domain||"")).toLowerCase();
      var terms = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      for (var i=0;i<terms.length;i++) if (hay.indexOf(terms[i]) === -1) return false;
    }
    return true;
  }
  var SORTS = {
    relevance: function(a,b){ return (b.relevance-a.relevance) || ((b.created_utc||0)-(a.created_utc||0)); },
    "new":     function(a,b){ return (b.created_utc||0)-(a.created_utc||0); },
    comments:  function(a,b){ return (b.comments||0)-(a.comments||0); },
    score:     function(a,b){ return (b.score||0)-(a.score||0); }
  };

  function card(p){
    var badges = [];
    if (p.verdict === "hot") badges.push('<span class="badge hot">&#9873; Worth a reply</span>');
    if (p.is_lead) badges.push('<span class="badge lead">&#9679; Possible client</span>');
    if (p.fresh) badges.push('<span class="badge new">New</span>');
    (p.places || []).slice(0,3).forEach(function(place){
      badges.push('<span class="badge new">' + esc(place) + '</span>');
    });

    var meta = ['<span>r/' + esc(p.subreddit) + "</span>"];
    meta.push('<span><a href="' + esc(p.author_url||"#") + '" target="_blank" rel="noopener">u/' + esc(p.author) + "</a></span>");
    meta.push("<span>" + esc(ago(p.created_utc)) + "</span>");
    if (p.score !== null && p.score !== undefined) meta.push("<span>" + plural(p.score, "upvote", "upvotes") + "</span>");
    if (p.comments !== null && p.comments !== undefined) meta.push("<span>" + plural(p.comments, "comment", "comments") + "</span>");
    if (p.domain && p.domain.indexOf("self.") !== 0) meta.push("<span>" + esc(p.domain) + "</span>");
    if (p.also_in && p.also_in.length){
      var links = p.also_in.map(function(a){
        return '<a href="' + esc(a.permalink||"#") + '" target="_blank" rel="noopener">r/' + esc(a.subreddit) + "</a>";
      }).join(", ");
      meta.push("<span>also in " + links + "</span>");
    }

    var chips = (p.hits||[]).slice(0,7).map(function(h){ return '<span class="chip">' + esc(h) + "</span>"; }).join("");

    var actions = '<a class="btn primary" href="' + esc(p.permalink) + '" target="_blank" rel="noopener">Open thread</a>';
    actions += '<a class="btn" href="' + esc(p.permalink) + '" target="_blank" rel="noopener">Reply on Reddit</a>';
    if (p.author && p.author !== "unknown")
      actions += '<a class="btn" href="https://www.reddit.com/user/' + esc(p.author) + '" target="_blank" rel="noopener">See u/' + esc(p.author) + '</a>';
    actions += state.review
      ? '<button class="btn dismiss" type="button" data-restore="' + esc(p.id) + '">Bring back</button>'
      : '<button class="btn dismiss" type="button" data-dismiss="' + esc(p.id) + '">Not relevant</button>';
    if (p.external_url && p.external_url.indexOf("http") === 0 && p.domain.indexOf("self.") !== 0)
      actions += '<a class="btn" href="' + esc(p.external_url) + '" target="_blank" rel="noopener">Source article</a>';

    return '<article class="card' + (p.verdict === "hot" ? " hot" : "") + '">' +
      '<div class="score"><div class="n">' + p.relevance + '</div><div class="l">Signal</div></div>' +
      "<div>" +
        (badges.length ? '<div class="badges">' + badges.join("") + "</div>" : "") +
        '<h3><a href="' + esc(p.permalink) + '" target="_blank" rel="noopener">' + esc(p.title) + "</a></h3>" +
        '<div class="meta">' + meta.join("") + "</div>" +
        (p.excerpt ? '<p class="excerpt">' + esc(p.excerpt) + "</p>" : "") +
        (chips ? '<div class="chips">' + chips + "</div>" : "") +
        '<div class="actions">' + actions + "</div>" +
      "</div></article>";
  }

  function render(){
    var rows = posts.filter(matches).sort(SORTS[state.sort]).slice(0, DATA.max_posts);
    var list = document.getElementById("list");
    list.className = state.review ? "wrap review" : "wrap";
    document.getElementById("count").textContent =
      rows.length + (rows.length === 1 ? " thread" : " threads")
      + (state.review ? " dismissed" : "");
    if (!rows.length){
      list.innerHTML = '<div class="empty"><strong>' +
        (state.review ? "Nothing dismissed yet."
                      : "Nothing matches those filters.") + "</strong>" +
        (state.review ? "Use \u201cNot relevant\u201d on a thread and it will stop appearing here."
                      : "Try widening the time range, or switch to Everything.") + "</div>";
    } else {
      list.innerHTML = rows.map(card).join("");
    }
    renderDismissBar();
    renderLearn();
    /* The headline number should reflect what is actually left to read. */
    var openHot = posts.filter(function(p){
      return p.verdict === "hot" && !isDismissed(p.id);
    }).length;
    var hotEl = document.querySelector(".kpi.is-hot .k-value");
    if (hotEl) hotEl.textContent = openHot;
  }

  /* ------------------------------------------------------- dismissed bar -- */
  function renderDismissBar(){
    var ids = Object.keys(dismissed);
    var bar = document.getElementById("dismissbar");
    if (!ids.length){ bar.hidden = true; return; }
    bar.hidden = false;
    document.getElementById("dismiss-n").textContent =
      ids.length + (ids.length === 1 ? " thread marked not relevant" : " threads marked not relevant");
    document.getElementById("dismiss-toggle").textContent =
      state.review ? "Back to the list" : "Review dismissed";
  }

  /* ------------------------------------------------------------ learning --
     One dismissal is a judgement call; the same place three times is a rule the
     watcher is missing. So the page counts what keeps leaking and hands over the
     exact line to add - reviewed by a person, because auto-blacklisting a place
     from a single click could quietly silence Noe Valley. */
  function renderLearn(){
    var box = document.getElementById("learn");
    var counts = {}, kinds = {};
    Object.keys(dismissed).forEach(function(id){
      var d = dismissed[id] || {};
      (d.elsewhere || []).forEach(function(x){
        counts[x] = (counts[x]||0) + 1; kinds[x] = "out_of_area";
      });
      (d.places || []).forEach(function(x){
        counts[x] = (counts[x]||0) + 1; kinds[x] = "neighborhood";
      });
      if (!(d.elsewhere||[]).length && !(d.places||[]).length){
        var key = "r/" + (d.sub || "?");
        counts[key] = (counts[key]||0) + 1; kinds[key] = "subreddit";
      }
    });
    var top = Object.keys(counts).filter(function(k){ return counts[k] >= 2; })
                    .sort(function(a,b){ return counts[b]-counts[a]; });
    if (!top.length){ box.hidden = true; return; }

    var term = top[0], kind = kinds[term], n = counts[term];
    box.hidden = false;
    document.getElementById("learn-title").textContent =
      "A pattern in what you are dismissing";
    var body, code, why;
    if (kind === "out_of_area"){
      body = "You have marked " + n + " threads mentioning \u201c" + term +
             "\u201d as not relevant, and it is already on the out-of-area list \u2014 " +
             "so these got through because the thread also mentioned San Francisco. " +
             "Worth a look at whether that pairing is ever useful to you.";
      code = "already in keywords.json \u2192 out_of_area \u2192 \"" + term + "\"";
      why = "No change needed unless you want the pairing dropped too.";
    } else if (kind === "neighborhood"){
      body = "You have dismissed " + n + " threads about " + term +
             ", which is on Team Howe\u2019s list. If it is no longer an area you want " +
             "to hear about, lower or remove it in neighborhoods.json.";
      code = "neighborhoods.json \u2192 find \"" + term + "\" \u2192 set \"weight\": 0";
      why = "Weight 0 keeps the record but stops it earning points.";
    } else {
      body = "You have dismissed " + n + " threads from " + term +
             " with no place named. That subreddit may simply not be worth watching.";
      code = "config.json \u2192 subreddits \u2192 remove { \"name\": \"" +
             term.replace("r/","") + "\" }";
      why = "Removing it also frees up requests against Reddit\u2019s rate limit.";
    }
    document.getElementById("learn-body").textContent = body;
    document.getElementById("learn-why").textContent = why;
    document.getElementById("learn-code").textContent = code;
  }

  document.getElementById("list").addEventListener("click", function(ev){
    var el = ev.target.closest ? ev.target.closest("[data-dismiss],[data-restore]") : null;
    if (!el) return;
    ev.preventDefault();
    var id = el.getAttribute("data-dismiss");
    if (id){
      var post = null;
      for (var i=0;i<posts.length;i++) if (posts[i].id === id) { post = posts[i]; break; }
      if (post) dismiss(post);
    } else {
      restore(el.getAttribute("data-restore"));
    }
    render();
  });
  document.getElementById("dismiss-toggle").addEventListener("click", function(){
    state.review = !state.review; render();
    window.scrollTo({top: document.querySelector(".results").offsetTop - 80, behavior: "smooth"});
  });
  document.getElementById("dismiss-clear").addEventListener("click", function(){
    if (!Object.keys(dismissed).length) return;
    dismissed = {}; persist(); state.review = false; render();
  });
  document.getElementById("learn-copy").addEventListener("click", function(){
    var text = document.getElementById("learn-code").textContent;
    var btn = this;
    function done(){ btn.textContent = "Copied"; setTimeout(function(){ btn.textContent = "Copy this"; }, 1600); }
    if (navigator.clipboard && navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(done, done);
    } else { done(); }
  });
  document.getElementById("q").addEventListener("input", function(e){ state.q = e.target.value; render(); });
  subSelect.addEventListener("change", function(e){ state.sub = e.target.value; render(); });
  document.getElementById("sort").addEventListener("change", function(e){ state.sort = e.target.value; render(); });
  document.getElementById("range").addEventListener("change", function(e){ state.range = parseInt(e.target.value,10); render(); });
  Array.prototype.forEach.call(document.querySelectorAll(".seg button"), function(btn){
    btn.addEventListener("click", function(){
      Array.prototype.forEach.call(document.querySelectorAll(".seg button"), function(other){
        other.setAttribute("aria-pressed", other === btn ? "true" : "false");
      });
      state.view = btn.getAttribute("data-view");
      render();
    });
  });

  /* Never land the reader on an empty page: if the default filters find
     nothing, widen the window (and then the priority) and say so. */
  function relaxIfEmpty(){
    if (!posts.length) return;
    if (posts.filter(matches).length) return;
    state.range = 9999;
    document.getElementById("range").value = "9999";
    if (posts.filter(matches).length) return;
    state.view = "all";
    Array.prototype.forEach.call(document.querySelectorAll(".seg button"), function(btn){
      btn.setAttribute("aria-pressed", btn.getAttribute("data-view") === "all" ? "true" : "false");
    });
  }

  /* ---------------------------------------------------------- refreshing --
     Press it and the crawl starts on GitHub's servers. The page then watches
     status.json until the timestamp moves, and reloads itself. Nobody has to
     visit GitHub, and nobody has to guess whether it worked. */
  var refreshBtn = document.getElementById("refreshbtn");
  if (refreshBtn){
    var POLL_MS = 15000, GIVE_UP_MS = 8 * 60 * 1000;
    refreshBtn.addEventListener("click", function(){
      var btn = refreshBtn, endpoint = btn.getAttribute("data-endpoint");
      var started = Date.now();
      function say(text){ btn.textContent = text; }
      function fail(text){
        btn.disabled = false; say(text);
        setTimeout(function(){ say("Refresh now"); }, 6000);
      }
      btn.disabled = true; say("Starting\u2026");

      fetch(endpoint, {method:"POST", headers:{"Content-Type":"application/json"}})
        .then(function(res){
          return res.json().catch(function(){ return {}; }).then(function(body){
            return {status: res.status, body: body};
          });
        })
        .then(function(r){
          if (r.status === 202 && r.body.ok){ watch(); return; }
          if (r.status === 429){ fail("Just refreshed \u2014 wait a minute"); return; }
          fail("Failed \u2014 see console");
          if (r.body.error) console.error("[reddit-watch] refresh:", r.body.error);
        })
        .catch(function(err){
          console.error("[reddit-watch] refresh:", err);
          fail("Could not reach the refresher");
        });

      function watch(){
        var elapsed = Date.now() - started;
        var mins = Math.floor(elapsed/60000), secs = Math.floor((elapsed%60000)/1000);
        say("Crawling\u2026 " + mins + ":" + (secs < 10 ? "0" : "") + secs);
        if (elapsed > GIVE_UP_MS){ fail("Still running \u2014 reload shortly"); return; }
        fetch("status.json?cb=" + Date.now(), {cache:"no-store"})
          .then(function(res){ return res.ok ? res.json() : null; })
          .then(function(status){
            var stamp = status && status.generated_at;
            if (stamp && DATA.built_at && stamp > DATA.built_at){
              say("Updated \u2014 reloading");
              setTimeout(function(){ location.reload(); }, 700);
            } else {
              setTimeout(watch, POLL_MS);
            }
          })
          .catch(function(){ setTimeout(watch, POLL_MS); });
      }
    });
  }

  drawChart();
  relaxIfEmpty();
  render();
})();
</script>
</body>
</html>
"""


def build(config, store, out_path):
    site = config.get("site", {})
    dash = config.get("dashboard", {})
    history_days = int(dash.get("history_days", 60))
    chart_days = 21

    records = fold([r for r in store.posts() if r.get("created_utc")])
    records.sort(key=lambda r: (-r.get("relevance", 0), -(r.get("created_utc") or 0)))

    now = datetime.now(timezone.utc)
    week_cutoff = int((now - timedelta(days=7)).timestamp())
    prev_week_cutoff = int((now - timedelta(days=14)).timestamp())
    fresh_cutoff = int((now - timedelta(days=1)).timestamp())

    hot = [r for r in records if r.get("verdict") == "hot"]
    this_week = [r for r in records if (r.get("created_utc") or 0) >= week_cutoff]
    last_week = [r for r in records
                 if prev_week_cutoff <= (r.get("created_utc") or 0) < week_cutoff]

    payload_posts = []
    for record in records[:int(dash.get("max_posts", 300))]:
        payload_posts.append({
            "id": record["id"],
            "subreddit": record.get("subreddit", ""),
            "title": record.get("title", ""),
            "author": record.get("author", "unknown"),
            "author_url": record.get("author_url"),
            "permalink": record.get("permalink"),
            "created_utc": record.get("created_utc"),
            "score": record.get("score"),
            "comments": record.get("comments"),
            "domain": record.get("domain", ""),
            "external_url": record.get("external_url", ""),
            "excerpt": record.get("excerpt", ""),
            "relevance": record.get("relevance", 0),
            "is_lead": bool(record.get("is_lead")),
            "verdict": record.get("verdict", "watch"),
            "hits": record.get("hits", [])[:8],
            "fresh": (record.get("created_utc") or 0) >= fresh_cutoff,
            "also_in": record.get("also_in") or [],
            "places": record.get("neighborhoods") or [],
            "elsewhere": record.get("out_of_area") or [],
        })

    daily = _daily_series(records, chart_days)

    delta = len(this_week) - len(last_week)
    if last_week:
        week_delta = "{} vs {} the week before".format(
            "{:+d}".format(delta) if delta else "level",
            len(last_week),
        )
    else:
        week_delta = "First full week of tracking"

    subs = config.get("subreddits", [])
    geo_count = sum(1 for s in subs if isinstance(s, dict) and s.get("scope") == "geo")

    html = TEMPLATE
    replacements = {
        "__TITLE__": site.get("title", "Reddit Watch"),
        "__HEADLINE__": "Who is talking about San Francisco real estate right now",
        "__SUBTITLE__": site.get("subtitle", ""),
        "__UPDATED__": _stamp(now, site.get("timezone", "America/Los_Angeles")),
        "__FONT__": brand.FONT,
        "__GOOGLE_FONTS__": brand.GOOGLE_FONTS,
        "__FAVICON__": brand.FAVICON,
        "__LOGO_LIGHT__": brand.logo(on_dark=True, width=960),
        "__WEBSITE__": brand.WEBSITE,
        "__TAGLINE__": brand.TAGLINE,
        "__PHONE__": brand.PHONE,
        "__PHONE_HREF__": brand.PHONE_HREF,
        "__ADDRESS__": brand.ADDRESS,
        "__COPYRIGHT__": brand.copyright_line(now.year),
        "__LEGAL__": brand.LEGAL,
        "__BAR__": brand.BEIGE,
        "__REFRESH_BTN__": _refresh_button(site.get("repo_url", ""),
                                          site.get("refresh_endpoint", "")),
        "__STALE_BANNER__": _stale_banner(store, now),
        "__KPI_HOT__": str(len(hot)),
        "__KPI_WEEK__": str(len(this_week)),
        "__KPI_WEEK_DELTA__": week_delta,
        "__KPI_TOTAL__": str(len(records)),
        "__KPI_SUBS__": str(len(subs)),
        "__KPI_SUBS_DELTA__": "{} SF-first, {} filtered to Bay Area mentions".format(
            len(subs) - geo_count, geo_count),
        "__HISTORY_DAYS__": str(history_days),
        "__CHART_DAYS__": str(chart_days),
        "__DATA__": json.dumps(
            {"posts": payload_posts, "daily": daily,
             "max_posts": int(dash.get("max_posts", 300)),
             "built_at": now.replace(microsecond=0).isoformat()},
            ensure_ascii=False,
        ).replace("</", "<\\/"),
    }
    for token, value in replacements.items():
        html = html.replace(token, value)

    directory = os.path.dirname(os.path.abspath(out_path))
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(html)

    return {
        "path": out_path,
        "posts": len(payload_posts),
        "hot": len(hot),
        "this_week": len(this_week),
    }


STALE_AFTER_HOURS = 6


def _stale_banner(store, now):
    """
    Say out loud when the threads on the page are older than the page is.

    This exists because of a real failure: reddit started refusing GitHub's
    runner addresses, every fetch came back 403, and the crawl still finished
    "successfully" with 0 posts. The dashboard rebuilt itself, stamped a fresh
    "Updated" time on the masthead, and served threads from two days earlier.
    Nothing was broken enough to notice, which is the worst kind of broken.
    """
    runs = [r for r in (store.state.get("runs") or []) if isinstance(r, dict)]
    last = runs[-1] if runs else None
    if not last:
        return ""

    reached_reddit = int(last.get("subreddits_ok") or 0) > 0
    last_ok = store.state.get("last_successful_crawl")
    if not last_ok:
        for run in reversed(runs):
            if int(run.get("subreddits_ok") or 0) > 0:
                last_ok = run.get("finished_at")
                break

    age_hours = None
    if last_ok:
        try:
            stamp = datetime.fromisoformat(str(last_ok).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age_hours = (now - stamp).total_seconds() / 3600.0
        except Exception:
            age_hours = None

    if reached_reddit and (age_hours is None or age_hours < STALE_AFTER_HOURS):
        return ""

    if age_hours is None:
        age = "an unknown amount of time"
    elif age_hours < 1:
        age = "under an hour"
    elif age_hours < 48:
        age = "{} hour{}".format(int(round(age_hours)),
                                 "" if int(round(age_hours)) == 1 else "s")
    else:
        age = "{} days".format(int(age_hours // 24))

    blocked = last.get("blocked_hosts") or {}
    if not reached_reddit:
        headline = ("Reddit refused every request on the last check, so nothing "
                    "new could be collected. The threads below were last "
                    "refreshed {} ago.".format(age))
    else:
        headline = ("Nothing new has come in for {}. The threads below are still "
                    "the most recent ones found.".format(age))

    why = ""
    if blocked:
        why = ("Refused: " + ", ".join(sorted(blocked.keys())) +
               ". Reddit blocks anonymous requests from datacenter networks; "
               "the crawler retries through the Team Howe worker automatically.")

    return (
        '\n<section class="stale"><div class="wrap">'
        '<span class="tagword">Data is stale</span>'
        '<p>{}{}</p>'
        '</div></section>'
    ).format(
        _escape(headline),
        '<span class="why">{}</span>'.format(_escape(why)) if why else "",
    )


def _escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _refresh_button(repo_url, endpoint=""):
    """
    A real button when there is somewhere authenticated to send the request, and
    a link to the Actions page when there is not.

    Triggering a workflow needs a GitHub token and this page is public, so the
    token lives in a tiny Cloudflare Worker instead (see worker/README.md) and
    the button calls that. Until `site.refresh_endpoint` is configured the button
    still works, it just opens GitHub - so the dashboard is never broken
    mid-setup.
    """
    if endpoint:
        return ('<button class="refreshbtn" id="refreshbtn" type="button" '
                'data-endpoint="{}">Refresh now</button>').format(endpoint.rstrip("/"))
    if not repo_url:
        return ""
    return ('<a class="refreshbtn" target="_blank" rel="noopener" '
            'title="Opens GitHub Actions - press Run workflow there" '
            'href="{}/actions/workflows/watch.yml">Refresh now</a>').format(
        repo_url.rstrip("/"))


def _daily_series(records, days):
    today = datetime.now(timezone.utc).date()
    buckets = {}
    for record in records:
        created = record.get("created_utc")
        if not created:
            continue
        day = datetime.fromtimestamp(created, tz=timezone.utc).date()
        buckets[day] = buckets.get(day, 0) + 1
    series = []
    for offset in range(days - 1, -1, -1):
        day = today - timedelta(days=offset)
        series.append({
            "label": day.strftime("%a %b %-d") if os.name != "nt" else day.strftime("%a %b %d"),
            "short": day.strftime("%b %-d") if os.name != "nt" else day.strftime("%b %d"),
            "n": buckets.get(day, 0),
        })
    return series


def _stamp(moment, tz_name="America/Los_Angeles"):
    """Show the time in TJ's timezone; fall back to UTC if tzdata is missing."""
    label = "UTC"
    local = moment
    try:
        from zoneinfo import ZoneInfo
        local = moment.astimezone(ZoneInfo(tz_name))
        label = local.tzname() or tz_name
    except Exception:
        pass
    day = local.strftime("%-d") if os.name != "nt" else str(local.day)
    hour = local.strftime("%-I") if os.name != "nt" else str(int(local.strftime("%I")))
    return "{} {}, {} at {}:{} {} {}".format(
        local.strftime("%b"), day, local.strftime("%Y"),
        hour, local.strftime("%M"), local.strftime("%p").lower(), label,
    )
