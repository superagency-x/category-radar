/* Category Radar dashboard: reads data/radar.json written by `radar export`. */
(() => {
  "use strict";

  const state = { data: null, market: null, tab: "overview", charts: {} };
  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

  // ---------- formatting
  const eur = (v, d = 0) => (v == null ? "–" : "€" + Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const num = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d }));
  const pct = (v, d = 1) => (v == null ? "–" : `${num(v, d)}%`);
  const local = (v, cur) => (v == null ? "–" : `${num(v, cur === "EUR" || cur === "CHF" ? 2 : 0)} ${cur}`);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const marketName = (m) => state.data.meta.markets[m]?.name ?? m;

  // ---------- brand colours: stable across every chart
  const PALETTE = ["#2f6fed", "#e8573f", "#18a37a", "#9b5de5", "#f2a516", "#0ea5c6", "#d6457e", "#6b7f2a", "#7a5c3e", "#5468ff", "#c2410c", "#0f766e"];
  const brandColor = (() => {
    const fixed = {};
    return (b) => {
      if (!fixed[b]) {
        const ranked = state.brandOrder || [];
        const i = ranked.indexOf(b);
        fixed[b] = i >= 0 && i < PALETTE.length ? PALETTE[i] : "#9aa3b2";
      }
      return fixed[b];
    };
  })();
  const alpha = (hex, a) => {
    const n = parseInt(hex.slice(1), 16);
    return `rgba(${n >> 16 & 255},${n >> 8 & 255},${n & 255},${a})`;
  };

  // ---------- charts
  function chart(id, config) {
    if (state.charts[id]) state.charts[id].destroy();
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    const ink = css("--ink-2"), line = css("--line");
    Chart.defaults.color = ink;
    Chart.defaults.borderColor = line;
    Chart.defaults.font.family = css("--font");
    Chart.defaults.font.size = 12;
    config.options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false }, config.options || {});
    state.charts[id] = new Chart(canvas, config);
    return state.charts[id];
  }

  // labels next to bubbles
  const bubbleLabels = {
    id: "bubbleLabels",
    afterDatasetsDraw(c) {
      const ctx = c.ctx;
      ctx.save();
      ctx.font = `600 11px ${css("--font")}`;
      ctx.fillStyle = css("--ink");
      c.data.datasets.forEach((ds, i) => {
        c.getDatasetMeta(i).data.forEach((pt) => {
          ctx.fillText(ds.label, pt.x + (pt.options.radius || 6) + 4, pt.y + 4);
        });
      });
      ctx.restore();
    },
  };

  // ---------- table helper
  function table(el, headers, rows, opts = {}) {
    const t = typeof el === "string" ? $(el) : el;
    if (!rows.length) {
      t.innerHTML = `<tbody><tr><td class="empty-state">${opts.empty || "No data for this market in the current snapshot."}</td></tr></tbody>`;
      return;
    }
    const th = headers.map((h) => `<th class="${h.num ? "num" : ""}">${esc(h.label)}</th>`).join("");
    const tb = rows.map((r) => `<tr>${headers.map((h) => `<td class="${h.cls ? h.cls(r) : h.num ? "num" : ""}"${h.style ? ` style="${h.style(r)}"` : ""}>${h.html ? h.html(r) : esc(h.get(r))}</td>`).join("")}</tr>`).join("");
    t.innerHTML = `<thead><tr>${th}</tr></thead><tbody>${tb}</tbody>`;
  }

  const heatStyle = (v, lo, mid, hi) => {
    if (v == null) return "";
    const a = css("--accent"), b = css("--bad");
    if (mid != null) { // diverging around mid (price index)
      const d = Math.max(-1, Math.min(1, (v - mid) / (hi - mid)));
      const col = d >= 0 ? b : a;
      return `background:${alpha(col.startsWith("#") ? col : "#2f6fed", Math.abs(d) * 0.45)}`;
    }
    const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo || 1)));
    return `background:${alpha(a.startsWith("#") ? a : "#2f6fed", 0.08 + t * 0.5)}`;
  };

  // ======================================================== OVERVIEW
  function renderOverview() {
    const { meta, insights } = state.data;
    const pm = insights.price.markets, lm = insights.landscape.markets;
    $("#kpis").innerHTML = Object.keys(meta.markets).map((m) => {
      const ch = Object.values(meta.channels).find((c) => c.market === m) || {};
      const dot = ch.status === "ok" ? "ok" : ch.status === "empty" || ch.status === "missing" ? "warn" : "bad";
      return `<button class="kpi ${m === state.market ? "active" : ""}" data-m="${m}" title="${esc(ch.status || "")}">
        <div class="flag"><span>${m} · ${esc(marketName(m))}</span><span class="dot ${dot}"></span></div>
        <div class="big">${eur(pm[m]?.median_eur)}</div>
        <div class="small">median shelf price</div><div class="small">${num(pm[m]?.n)} products · ${num(lm[m]?.n_brands)} brands</div>
        <div class="small">Leader <b>${esc(lm[m]?.leader || "–")}</b></div>
      </button>`;
    }).join("");
    $$("#kpis .kpi").forEach((b) => b.addEventListener("click", () => setMarket(b.dataset.m)));

    $("#insights").innerHTML = insights.insights.length
      ? insights.insights.map((i) => `<li><span class="tag">${esc(i.market === "ALL" ? i.topic : i.market + " · " + i.topic)}</span>${esc(i.text)}</li>`).join("")
      : `<li>No insights yet. Run the pipeline at least once.</li>`;

    const ms = Object.keys(pm).filter((m) => pm[m].median_eur != null);
    chart("c-market-price", {
      type: "bar",
      data: {
        labels: ms.map((m) => `${m}`),
        datasets: [
          { label: "P10–P90", data: ms.map((m) => [pm[m].p10_eur, pm[m].p90_eur]), backgroundColor: alpha("#2f6fed", 0.18), borderRadius: 6, barPercentage: 0.6 },
          { label: "Median", data: ms.map((m) => pm[m].median_eur), type: "line", showLine: false, pointRadius: 7, pointStyle: "rectRot", backgroundColor: css("--accent"), borderColor: css("--accent") },
        ],
      },
      options: { plugins: { tooltip: { callbacks: { label: (c) => Array.isArray(c.raw) ? `P10–P90: ${eur(c.raw[0])}–${eur(c.raw[1])}` : `Median: ${eur(c.raw)}` } } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => "€" + v } } } },
    });

    // stacked leader chart: top 5 brands per market + other
    const markets = Object.keys(lm);
    const topBrands = [...new Set(markets.flatMap((m) => lm[m].brands.slice(0, 5).map((b) => b.brand)))];
    chart("c-leaders", {
      type: "bar",
      data: {
        labels: markets.map((m) => `${m} · ${marketName(m)}`),
        datasets: [
          ...topBrands.map((b) => ({
            label: b, backgroundColor: brandColor(b), borderRadius: 2,
            data: markets.map((m) => lm[m].brands.find((x) => x.brand === b)?.visibility_share ?? 0),
          })),
          { label: "Other", backgroundColor: alpha("#9aa3b2", 0.35), data: markets.map((m) => Math.max(0, 100 - lm[m].brands.filter((x) => topBrands.includes(x.brand)).reduce((s, x) => s + x.visibility_share, 0))) },
        ],
      },
      options: { indexAxis: "y", scales: { x: { stacked: true, max: 100, ticks: { callback: (v) => v + "%" } }, y: { stacked: true } },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${pct(c.raw)}` } } } },
    });
  }

  // ======================================================== PRICE
  function renderPrice() {
    const m = state.market, P = state.data.insights.price;
    const mk = P.markets[m];
    chart("c-hist", {
      type: "bar",
      data: { labels: (mk?.histogram || []).map((b) => `€${b.from}–${b.to}`), datasets: [{ label: "Products", data: (mk?.histogram || []).map((b) => b.n), backgroundColor: css("--accent"), borderRadius: 4 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } },
    });

    const trend = P.trend;
    const dates = [...new Set(Object.values(trend).flat().map((p) => p.date))].sort();
    chart("c-trend", {
      type: "line",
      data: { labels: dates, datasets: Object.keys(trend).map((mm, i) => ({
        label: mm, data: dates.map((d) => trend[mm].find((p) => p.date === d)?.median_eur ?? null),
        borderColor: PALETTE[i], backgroundColor: PALETTE[i], tension: .25, spanGaps: true,
        borderWidth: mm === m ? 3 : 1.5, pointRadius: mm === m ? 4 : 2,
      })) },
      options: { plugins: { legend: { position: "bottom" } }, scales: { y: { ticks: { callback: (v) => "€" + v } } } },
    });
    $("#trend-note").textContent = dates.length < 2 ? "One snapshot so far. The trend fills in as `radar run` is scheduled (e.g. weekly)." : `${dates.length} snapshots from ${dates[0]} to ${dates[dates.length - 1]}.`;

    // brand price index heat table
    const idx = P.brand_price_index, markets = Object.keys(state.data.meta.markets);
    const brands = Object.keys(idx).filter((b) => Object.keys(idx[b]).length >= 2).sort((a, b) => Object.keys(idx[b]).length - Object.keys(idx[a]).length || a.localeCompare(b));
    table("#t-index", [{ label: "Brand", get: (b) => b }, ...markets.map((mm) => ({
      label: mm, num: true, cls: () => "cell", get: (b) => idx[b][mm] ?? "", style: (b) => heatStyle(idx[b][mm], 40, 100, 200),
    }))], brands, { empty: "Brand price index needs ≥2 products per brand per market." });

    table("#t-cross", [
      { label: "Model", cls: () => "title", get: (c) => c.title },
      ...markets.map((mm) => ({ label: mm, num: true, html: (c) => {
        const v = c.prices_eur[mm];
        if (v == null) return "";
        const cls = mm === c.cheapest ? "min" : mm === c.dearest ? "max" : "";
        return `<span class="${cls}">${eur(v)}</span>`;
      } })),
      { label: "Spread", num: true, get: (c) => pct(c.spread_pct, 0) },
    ], P.cross_market.slice(0, 15), { empty: "No model found in 3+ markets yet." });

    table("#t-ladder", [
      { label: "#", num: true, get: (r) => r.rank },
      { label: "Product", cls: () => "title", html: (r) => `<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>` },
      { label: "Tier", html: (r) => r.tier ? `<span class="badge ${esc(r.tier)}">${esc(r.tier)}</span>` : "" },
      { label: "Price", num: true, get: (r) => eur(r.price_eur) },
      { label: "Litre", num: true, get: (r) => r.capacity_l ? num(r.capacity_l, 1) : "–" },
    ], (P.ladder[m] || []).slice().reverse());

    table("#t-movers", [
      { label: "Mkt", get: (r) => r.market },
      { label: "Product", cls: () => "title", get: (r) => r.title },
      { label: "Before", num: true, get: (r) => local(r.from_local, r.currency) },
      { label: "Now", num: true, get: (r) => local(r.to_local, r.currency) },
      { label: "Δ", num: true, html: (r) => `<span class="${r.change_pct > 0 ? "up" : "down"}">${r.change_pct > 0 ? "+" : ""}${num(r.change_pct, 1)}%</span>` },
    ], P.movers, { empty: "Price movers appear from the second snapshot onwards." });
  }

  // ======================================================== POSITIONING
  function renderPositioning() {
    const m = state.market, P = state.data.insights.positioning;
    const pts = P.maps[m] || [];
    const ym = $("#y-metric").value;
    const yLabel = $("#y-metric").selectedOptions[0].text;
    const usable = pts.filter((p) => p[ym] != null);
    chart("c-map", {
      type: "bubble",
      data: { datasets: usable.map((p) => ({
        label: p.brand,
        data: [{ x: p.price_index, y: p[ym], r: 5 + Math.sqrt(p.visibility_share) * 3.2, p }],
        backgroundColor: alpha(brandColor(p.brand), 0.55), borderColor: brandColor(p.brand), borderWidth: 1.5,
      })) },
      options: {
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => {
          const p = c.raw.p;
          return [`${p.brand}: price index ${p.price_index}`, `${yLabel}: ${num(p[ym], 1)}`, `Visibility ${pct(p.visibility_share)} · ${p.listings} products`];
        } } } },
        scales: {
          x: { title: { display: true, text: "Price index (100 = market median)" }, suggestedMin: 40, suggestedMax: 180 },
          y: { title: { display: true, text: yLabel } },
        },
      },
      plugins: [bubbleLabels],
    });

    const mat = P.claim_matrix[m] || {}, labels = P.claim_labels;
    const claimKeys = Object.keys(labels);
    const brands = Object.keys(mat).sort((a, b) => (pts.find((p) => p.brand === b)?.visibility_share || 0) - (pts.find((p) => p.brand === a)?.visibility_share || 0));
    table("#t-claims", [{ label: "Brand", get: (b) => b }, ...claimKeys.map((k) => ({
      label: labels[k].split(" /")[0].replace(" (n-in-1)", ""), num: true, cls: () => "cell",
      get: (b) => (mat[b][k] ? Math.round(mat[b][k]) : ""), style: (b) => mat[b][k] ? heatStyle(mat[b][k], 0, null, 100) : "",
    }))], brands, { empty: "Claim matrix needs ≥2 products per brand." });

    const tm = P.tier_mix[m] || {}, tiers = P.tiers;
    const tb = Object.keys(tm).sort((a, b) => sum(Object.values(tm[b])) - sum(Object.values(tm[a]))).slice(0, 12);
    const tierCol = { Entry: "#18a37a", Mainstream: "#2f6fed", Premium: "#f2a516", "Super-premium": "#e8573f" };
    chart("c-tiers", {
      type: "bar",
      data: { labels: tb, datasets: tiers.map((t) => ({ label: t, data: tb.map((b) => tm[b][t] || 0), backgroundColor: tierCol[t] || "#9aa3b2", borderRadius: 2 })) },
      options: { indexAxis: "y", plugins: { legend: { position: "bottom" } }, scales: { x: { stacked: true, ticks: { precision: 0 } }, y: { stacked: true } } },
    });
  }
  const sum = (a) => a.reduce((s, x) => s + x, 0);

  // ======================================================== LANDSCAPE
  function renderLandscape() {
    const m = state.market, L = state.data.insights.landscape;
    const brands = (L.markets[m]?.brands || []).slice(0, 12);
    chart("c-shares", {
      type: "bar",
      data: { labels: brands.map((b) => b.brand), datasets: [
        { label: "Share of shelf (visibility)", data: brands.map((b) => b.visibility_share), backgroundColor: brands.map((b) => brandColor(b.brand)), borderRadius: 4 },
        { label: "Share of voice (ratings)", data: brands.map((b) => b.review_share ?? 0), backgroundColor: brands.map((b) => alpha(brandColor(b.brand), 0.35)), borderRadius: 4 },
        ...(brands.some((b) => b.purchase_share != null) ? [{ label: "Share of purchases (90 days)", data: brands.map((b) => b.purchase_share ?? 0), backgroundColor: alpha("#14181f", 0.25), borderRadius: 4 }] : []),
      ] },
      options: { plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${pct(c.raw)}` } } }, scales: { y: { ticks: { callback: (v) => v + "%" } } } },
    });

    const ms = Object.keys(L.markets);
    chart("c-hhi", {
      type: "bar",
      data: { labels: ms, datasets: [{ label: "HHI", data: ms.map((x) => L.markets[x].hhi),
        backgroundColor: ms.map((x) => L.markets[x].hhi > 2500 ? css("--bad") : L.markets[x].hhi > 1500 ? css("--warn") : css("--good")), borderRadius: 4 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } },
    });

    const fp = L.footprint.filter((f) => f.n >= 2 || L.markets[f.markets[0]]?.brands.find((b) => b.brand === f.brand)?.top20 > 0).slice(0, 30);
    table("#t-footprint", [
      { label: "Brand", get: (f) => f.brand },
      ...ms.map((x) => ({ label: x, html: (f) => f.markets.includes(x) ? `<span class="dot ok" style="background:${brandColor(f.brand)}"></span>` : "" })),
      { label: "Type", html: (f) => `<span class="badge">${esc(f.type)}</span>` },
    ], fp);

    table("#t-brands", [
      { label: "Brand", html: (b) => `<span class="dot" style="background:${brandColor(b.brand)};margin:0 6px 0 0"></span>${esc(b.brand)}` },
      { label: "Products", num: true, get: (b) => b.listings },
      { label: "In top 20", num: true, get: (b) => b.top20 },
      { label: "Best rank", num: true, get: (b) => b.best_rank },
      { label: "Visibility", num: true, get: (b) => pct(b.visibility_share) },
      { label: "Voice", num: true, get: (b) => pct(b.review_share) },
      { label: "Avg rating", num: true, get: (b) => num(b.avg_rating, 2) },
      { label: "Avg offers", num: true, get: (b) => num(b.avg_offers, 1) },
      { label: "Median €", num: true, get: (b) => eur(b.median_price_eur) },
      { label: "Paid slots", num: true, get: (b) => b.sponsored_listings || "" },
    ], L.markets[m]?.brands || []);
  }

  // ======================================================== NEEDS
  function renderNeeds() {
    const m = state.market, N = state.data.insights.needs;
    const lift = (N.feature_lift[m] || []).filter((x) => x.share_all > 0);
    chart("c-lift", {
      type: "bar",
      data: { labels: lift.map((x) => `${x.label}  ·  ${x.lift ? x.lift.toFixed(2) + "x" : ""}`), datasets: [
        { label: "Top 20", data: lift.map((x) => x.share_top20), backgroundColor: css("--accent"), borderRadius: 3 },
        { label: "Whole shelf", data: lift.map((x) => x.share_all), backgroundColor: alpha("#9aa3b2", 0.5), borderRadius: 3 },
      ] },
      options: { indexAxis: "y", plugins: { legend: { position: "bottom" } }, scales: { x: { max: 100, ticks: { callback: (v) => v + "%" } } } },
    });

    const sal = (N.review_salience[m] || []).filter((x) => x.mentions > 0);
    chart("c-salience", {
      type: "bar",
      data: { labels: sal.map((x) => x.label), datasets: [{ label: "% of reviews", data: sal.map((x) => x.salience_pct),
        backgroundColor: sal.map((x) => x.avg_rating_when_mentioned == null ? "#9aa3b2" : x.avg_rating_when_mentioned < 3.5 ? css("--bad") : x.avg_rating_when_mentioned < 4.3 ? css("--warn") : css("--good")), borderRadius: 3 }] },
      options: { indexAxis: "y", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => {
        const x = sal[c.dataIndex];
        return [`${pct(x.salience_pct)} of reviews (${x.mentions})`, `Avg rating when mentioned: ${num(x.avg_rating_when_mentioned, 2)}`];
      } } } }, scales: { x: { ticks: { callback: (v) => v + "%" } } } },
    });
    const n = N.review_counts[m] || 0;
    $("#salience-note").textContent = n
      ? `${n} reviews analysed. Colour = average star rating when the need is mentioned (red = pain point, green = delighter).`
      : "No reviews collected for this market yet. Run without --no-reviews, or the channel publishes no structured review data.";

    const cap = N.capacity;
    table("#t-capacity", [
      { label: "Market", get: (x) => `${x} · ${marketName(x)}` },
      { label: "Top-20 median (l)", num: true, get: (x) => num(cap[x].top20_median, 1) },
      { label: "Top-20 middle 50% (l)", num: true, get: (x) => cap[x].top20_iqr?.[0] != null ? `${num(cap[x].top20_iqr[0], 1)}–${num(cap[x].top20_iqr[1], 1)}` : "–" },
      { label: "Whole shelf (l)", num: true, get: (x) => num(cap[x].all_median, 1) },
    ], Object.keys(cap));

    table("#t-demand", [
      { label: "Product", cls: () => "title", get: (d) => d.title },
      { label: "Brand", get: (d) => d.brand },
      { label: "Bought (90d)", num: true, get: (d) => num(d.recent_purchases_90d) },
      { label: "Price", num: true, get: (d) => eur(d.price_eur) },
    ], N.demand_signals, { empty: "Only Ceneo (PL) publishes purchase counts." });
  }

  // ======================================================== DATA
  function renderData() {
    const meta = state.data.meta;
    table("#t-channels", [
      { label: "Channel", get: ([id]) => id },
      { label: "Market", get: ([, c]) => c.market },
      { label: "Type", get: ([, c]) => c.type.replace("_", " ") },
      { label: "Status", html: ([, c]) => `<span class="badge ${esc(c.status)}">${esc(c.status)}</span>` },
      { label: "Products", num: true, get: ([, c]) => c.listings ?? 0 },
      { label: "Pages", num: true, get: ([, c]) => c.pages ?? "" },
      { label: "Fetched via", get: ([, c]) => c.via ?? "" },
      { label: "Note", cls: () => "title", get: ([, c]) => c.error ?? "" },
    ], Object.entries(meta.channels));
    renderListings();
  }

  function renderListings() {
    const q = ($("#q").value || "").toLowerCase();
    const rows = state.data.listings.filter((l) => l.market === state.market && (!q || `${l.brand} ${l.title}`.toLowerCase().includes(q)));
    table("#t-listings", [
      { label: "#", num: true, get: (l) => l.rank },
      { label: "Brand", get: (l) => l.brand },
      { label: "Product", cls: () => "title", html: (l) => `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.title)}</a>${l.sponsored ? ' <span class="badge">paid</span>' : ""}` },
      { label: "Price", num: true, get: (l) => local(l.price_local, l.currency) },
      { label: "EUR", num: true, get: (l) => eur(l.price_eur) },
      { label: "Offers", num: true, get: (l) => l.offers ?? "" },
      { label: "Rating", num: true, get: (l) => l.rating != null ? `${num(l.rating, 1)} (${l.rating_count ?? 0})` : "" },
      { label: "Litre", num: true, get: (l) => l.capacity_l ?? "" },
      { label: "Claims", get: (l) => l.claims.join(", ") },
    ], rows);
  }

  // ======================================================== shell
  const RENDER = { overview: renderOverview, price: renderPrice, positioning: renderPositioning, landscape: renderLandscape, needs: renderNeeds, data: renderData };

  function setTab(tab) {
    state.tab = tab;
    $$("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === tab)));
    $$("section[data-panel]").forEach((s) => (s.hidden = s.dataset.panel !== tab));
    try { localStorage.setItem("radar.tab", tab); } catch (e) { /* storage unavailable */ }
    history.replaceState(null, "", `#${tab}/${state.market}`);
    RENDER[tab]();
  }

  function setMarket(m) {
    state.market = m;
    $$("#market-picker button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.m === m)));
    $$(".mk").forEach((s) => (s.textContent = `${m} · ${marketName(m)}`));
    try { localStorage.setItem("radar.market", m); } catch (e) { /* storage unavailable */ }
    history.replaceState(null, "", `#${state.tab}/${m}`);
    RENDER[state.tab]();
  }

  async function init() {
    let data;
    try {
      const res = await fetch("data/radar.json", { cache: "no-store" });
      if (!res.ok) throw new Error(res.status);
      data = await res.json();
    } catch (e) {
      $("#subtitle").textContent = "No data yet. Run `radar run` to scrape the markets, then reload.";
      return;
    }
    state.data = data;
    const meta = data.meta;
    // order brands by total visibility so the leaders get the strongest colours
    const vis = {};
    Object.values(data.insights.landscape.markets).forEach((mk) => mk.brands.forEach((b) => (vis[b.brand] = (vis[b.brand] || 0) + b.visibility_share)));
    state.brandOrder = Object.keys(vis).sort((a, b) => vis[b] - vis[a]);

    $("#sample-banner").hidden = meta.fx_source !== "sample";
    $("#title").textContent = `${meta.category.name} · Central Europe`;
    $("#subtitle").textContent = `Snapshot ${meta.snapshot_date} · ${Object.keys(meta.markets).length} markets · ${num(meta.counts.listings)} listings · ${num(meta.counts.brands)} brands · ${num(meta.counts.reviews)} reviews · ${meta.counts.snapshots} snapshot(s)`;
    $("#foot-meta").textContent = `Run ${meta.run_id} · FX ${meta.fx_source} · generated ${new Date(meta.generated_at).toLocaleString("en-GB")}`;

    const markets = Object.keys(meta.markets);
    $("#market-picker").innerHTML = markets.map((m) => `<button role="radio" data-m="${m}" aria-checked="false" title="${esc(marketName(m))}">${m}</button>`).join("");
    $$("#market-picker button").forEach((b) => b.addEventListener("click", () => setMarket(b.dataset.m)));
    $$("#tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
    $("#y-metric").addEventListener("change", renderPositioning);
    $("#q").addEventListener("input", renderListings);

    let m = markets[0], tab = "overview";
    try {
      const sm = localStorage.getItem("radar.market"), st = localStorage.getItem("radar.tab");
      if (sm && markets.includes(sm)) m = sm;
      if (st && RENDER[st]) tab = st;
    } catch (e) { /* storage unavailable */ }
    const hash = location.hash.slice(1).split("/");
    if (RENDER[hash[0]]) tab = hash[0];
    if (markets.includes(hash[1])) m = hash[1];
    state.market = m;
    $$(".mk").forEach((s) => (s.textContent = `${m} · ${marketName(m)}`));
    $$("#market-picker button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.m === m)));
    setTab(tab);
    window.addEventListener("hashchange", () => {
      const [t, mm] = location.hash.slice(1).split("/");
      if (markets.includes(mm) && mm !== state.market) { state.market = mm; setMarket(mm); }
      if (RENDER[t] && t !== state.tab) setTab(t);
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => RENDER[state.tab]());
  }

  init();
})();
