# 5-minute interview walkthrough

> The example figures below show the *kind* of statement to make. Replace them with the findings from your own latest run before each interview.

**Setup:** open `radar.saralogy.com` in a browser tab before the call. As a fallback, run `radar serve` locally (it works offline).

---

**0:00 · The problem (Overview tab)**
"When I launched products in new EU markets, the first question was always the same: what does this category look like there? Who wins, at what price, with which story? That usually means weeks of desk research or an expensive panel. I built a tool that answers it from public shelf data in one run, across six Central European markets."

Point at the six KPI cards: median shelf price and leader per market. Then read two of the auto-generated insights aloud.

**0:45 · Price (Price tab)**
- *Brand price index:* "Philips prices about 40% above the market median everywhere, while Tefal sits well below. That is a consistent two-tier architecture."
- *Same model, different price:* "This is the one a commercial director cares about: identical SKUs with double-digit cross-border gaps. That is a grey-import and price-harmonisation risk."
- *Trend and movers:* "It runs weekly, so it catches price drops before a retailer promo goes live."

**1:45 · Positioning (Positioning tab)**
Switch the Y axis between rating and feature richness. "Top-right earned its premium. Bottom-right charges a premium without the proof." Then the claim heatmap: "This shows which brand owns which claim. Dual-zone is a crowded space, steam is still white space."

**2:30 · Competition (Competition tab)**
"Share of shelf vs share of voice. A brand that's visible but has few ratings is buying visibility; one with many ratings but little visibility is under-distributed." Show HHI: "Some markets are near-oligopolies, others are open for a challenger." Footprint: "pan-regional players vs local champions."

**3:15 · Market needs (Market needs tab)**
"Two lenses. On the left is revealed preference: features over-represented in the top 20. On the right is stated needs: what reviewers actually talk about in German, Polish, Czech and Hungarian, coloured red when it's a pain point. If noise is red in Germany, 'silent' is your German headline."

**4:00 · How it's built (Data & method tab)**
"Python, about 2,000 lines. One adapter per site, one YAML file per category, a SQLite history and a static dashboard. It respects robots.txt, rate-limits itself and never bypasses bot protection. When heureka.cz blocked automated access, I switched Czechia to Alza instead of forcing it. Switching to robot vacuums is a new YAML file, not new code."

**4:30 · Close**
"This is how I like to work: start from the marketing question, build the smallest thing that answers it reliably, and make the output something a team can act on."

---

**Likely follow-ups**

- *"How accurate is it?"* "It's a shelf view, not sales data. Rank, ratings and Ceneo purchase counts are proxies. I'd calibrate them against sell-out data on the job."
- *"Is scraping legal?"* "Public pages, polite rate, no logins, no personal data, aggregated output. Commercial use would need each site's terms or a data partnership."
- *"What would you add next?"* "A second channel per market for channel mix, LLM-based review clustering for needs we haven't defined, and alerts on competitor price moves."
