"""Automated Competitor Battlecards for Commercial & GTM Sales Teams.

Generates head-to-head benchmarking between a focus brand and its key competitors:
- Price index gap and price corridor comparison
- Visibility share & installed review base
- Feature & claim superiority matrix
- Independent editorial test score validation
- Retailer distribution footprint
- Actionable sales pitch hooks and counter-arguments
"""

from __future__ import annotations

import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Any

from .analytics import _median, _pct, visibility_weight
from .config import CategoryConfig


def generate_battlecard(
    rows: list[dict],
    brand: str,
    competitor: str | None = None,
    market: str = "DE",
    cfg: CategoryConfig | None = None,
) -> dict[str, Any]:
    """Generate a comprehensive commercial battlecard between brand and competitor."""
    m_rows = [r for r in rows if r["market"] == market]
    if not m_rows:
        return {"error": f"No data found for market '{market}'."}

    # If no competitor specified, pick the market leader other than brand
    brand_vis: dict[str, float] = defaultdict(float)
    total_vis = sum(visibility_weight(r["rank"]) for r in m_rows) or 1.0
    for r in m_rows:
        brand_vis[r["brand"]] += visibility_weight(r["rank"])

    sorted_brands = sorted(brand_vis.keys(), key=lambda b: -brand_vis[b])
    if not competitor:
        competitor = next((b for b in sorted_brands if b.lower() != brand.lower()), sorted_brands[0])

    b_items = [r for r in m_rows if r["brand"].lower() == brand.lower()]
    c_items = [r for r in m_rows if r["brand"].lower() == competitor.lower()]

    if not b_items:
        return {"error": f"Brand '{brand}' not found in market '{market}'."}
    if not c_items:
        return {"error": f"Competitor '{competitor}' not found in market '{market}'."}

    m_prices = [r["price_eur"] for r in m_rows if r["price_eur"] is not None]
    m_median = _median(m_prices) or 1.0

    b_prices = [r["price_eur"] for r in b_items if r["price_eur"] is not None]
    c_prices = [r["price_eur"] for r in c_items if r["price_eur"] is not None]

    b_med = _median(b_prices) or 0.0
    c_med = _median(c_prices) or 0.0

    b_idx = round(100 * b_med / m_median) if m_median else 100
    c_idx = round(100 * c_med / m_median) if m_median else 100
    price_gap_pct = round(100.0 * (b_med - c_med) / c_med, 1) if c_med else 0.0

    # Visibility & Review Share
    b_vis_share = round(100.0 * brand_vis[brand] / total_vis, 1)
    c_vis_share = round(100.0 * brand_vis[competitor] / total_vis, 1)

    total_ratings = sum(r.get("rating_count") or 0 for r in m_rows) or 1
    b_reviews = sum(r.get("rating_count") or 0 for r in b_items)
    c_reviews = sum(r.get("rating_count") or 0 for r in c_items)

    b_rev_share = round(100.0 * b_reviews / total_ratings, 1)
    c_rev_share = round(100.0 * c_reviews / total_ratings, 1)

    # Average Ratings
    b_rated = [r["rating"] for r in b_items if r.get("rating") is not None]
    c_rated = [r["rating"] for r in c_items if r.get("rating") is not None]
    b_avg_rating = round(st.mean(b_rated), 2) if b_rated else None
    c_avg_rating = round(st.mean(c_rated), 2) if c_rated else None

    # Editorial Test Scores
    b_scores = [r["test_score"] for r in b_items if r.get("test_score") is not None]
    c_scores = [r["test_score"] for r in c_items if r.get("test_score") is not None]
    b_avg_test = round(st.mean(b_scores), 1) if b_scores else None
    c_avg_test = round(st.mean(c_scores), 1) if c_scores else None

    # Claims / Feature Matrix
    claims_catalog = cfg.claims if cfg else {}
    claim_matrix = []
    advantages = []
    vulnerabilities = []

    for cid, cdef in claims_catalog.items():
        label = getattr(cdef, "label", cid)
        b_count = sum(1 for r in b_items if cid in r.get("claims", []))
        c_count = sum(1 for r in c_items if cid in r.get("claims", []))
        b_pct = _pct(b_count, len(b_items))
        c_pct = _pct(c_count, len(c_items))

        diff = b_pct - c_pct
        if diff >= 20.0:
            advantages.append(f"{label} ({b_pct}% vs {c_pct}%)")
        elif diff <= -20.0:
            vulnerabilities.append(f"{label} ({b_pct}% vs {c_pct}%)")

        claim_matrix.append(
            {
                "claim_id": cid,
                "label": label,
                "brand_pct": b_pct,
                "competitor_pct": c_pct,
                "advantage": "brand" if diff > 5 else "competitor" if diff < -5 else "neutral",
            }
        )

    # Distribution channels
    b_channels = sorted({str(r["channel"]) for r in b_items if r.get("channel")})
    c_channels = sorted({str(r["channel"]) for r in c_items if r.get("channel")})

    # Actionable Sales Rep Pitch Hooks
    hooks = []
    if price_gap_pct < -5:
        hooks.append(
            f"💰 Price Advantage: Offer a {abs(price_gap_pct)}% lower shelf price vs {competitor} "
            f"(€{b_med} vs €{c_med}), unlocking higher volume while protecting retailer margin."
        )
    elif price_gap_pct > 5:
        hooks.append(
            f"💎 Premium Justification: Priced at a {price_gap_pct}% premium vs {competitor}, "
            f"supported by richer feature specifications and premium build tiering."
        )

    if advantages:
        hooks.append(
            f"✨ Feature Superiority: Differentiate against {competitor} by spotlighting: {', '.join(advantages[:3])}."
        )

    if b_avg_rating and c_avg_rating and b_avg_rating > c_avg_rating:
        hooks.append(
            f"⭐ Quality Proof: Outperforming {competitor} in customer satisfaction "
            f"({b_avg_rating}★ vs {c_avg_rating}★ across verified purchaser reviews)."
        )

    if b_avg_test and (not c_avg_test or b_avg_test > c_avg_test):
        hooks.append(
            f"🏆 Certified Lab Winner: Verified by independent German editorial testing "
            f"(Stiftung Warentest score {b_avg_test}/100)."
        )

    return {
        "market": market,
        "brand": brand,
        "competitor": competitor,
        "summary": {
            "brand_listings": len(b_items),
            "competitor_listings": len(c_items),
            "brand_median_eur": b_med,
            "competitor_median_eur": c_med,
            "market_median_eur": m_median,
            "price_gap_pct": price_gap_pct,
            "brand_price_index": b_idx,
            "competitor_price_index": c_idx,
            "brand_visibility_share": b_vis_share,
            "competitor_visibility_share": c_vis_share,
            "brand_review_share": b_rev_share,
            "competitor_review_share": c_rev_share,
            "brand_avg_rating": b_avg_rating,
            "competitor_avg_rating": c_avg_rating,
            "brand_avg_test_score": b_avg_test,
            "competitor_avg_test_score": c_avg_test,
        },
        "advantages": advantages,
        "vulnerabilities": vulnerabilities,
        "claim_matrix": claim_matrix,
        "channels": {
            "brand_channels": b_channels,
            "competitor_channels": c_channels,
        },
        "sales_hooks": hooks,
        "hero_skus": {
            "brand_heroes": sorted(b_items, key=lambda r: r["rank"])[:3],
            "competitor_heroes": sorted(c_items, key=lambda r: r["rank"])[:3],
        },
    }


def render_battlecard_html(card: dict[str, Any]) -> str:
    """Render a standalone, printable executive battlecard HTML sheet."""
    s = card["summary"]
    hooks_html = "".join(f"<li>{h}</li>" for h in card["sales_hooks"]) or "<li>No critical gaps identified.</li>"
    adv_html = "".join(f"<li>✅ <strong>{a}</strong></li>" for a in card["advantages"]) or "<li>Evenly matched.</li>"
    vuln_html = (
        "".join(f"<li>⚠️ <strong>{v}</strong></li>" for v in card["vulnerabilities"])
        or "<li>No major vulnerabilities.</li>"
    )

    def _format_badge(adv: str) -> str:
        if adv == "brand":
            return '<span style="color:#15803d;font-weight:700;">WIN</span>'
        elif adv == "competitor":
            return '<span style="color:#b91c1c;font-weight:700;">LAG</span>'
        return '<span style="color:#64748b;">–</span>'

    claims_rows_list = []
    for c in card["claim_matrix"]:
        badge = _format_badge(c["advantage"])
        claims_rows_list.append(
            f"<tr>"
            f"<td><strong>{c['label']}</strong></td>"
            f"<td style='text-align:right;'>{c['brand_pct']}%</td>"
            f"<td style='text-align:right;'>{c['competitor_pct']}%</td>"
            f"<td style='text-align:center;'>{badge}</td>"
            f"</tr>"
        )
    claims_rows = "".join(claims_rows_list)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Sales Battlecard: {card["brand"]} vs. {card["competitor"]} ({card["market"]})</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.5; color: #0f172a; max-width: 960px; margin: 32px auto; padding: 0 20px; background: #f8fafc; }}
    .card {{ background: #fff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); margin-bottom: 20px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #2f6fed; padding-bottom: 12px; margin-bottom: 20px; }}
    h1 {{ margin: 0; font-size: 24px; color: #0f172a; }}
    .tag {{ background: #e0e7ff; color: #3730a3; padding: 4px 10px; border-radius: 999px; font-size: 13px; font-weight: 700; text-transform: uppercase; }}
    .grid-kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }}
    .kpi {{ background: #f1f5f9; padding: 14px; border-radius: 8px; text-align: center; }}
    .kpi .num {{ font-size: 22px; font-weight: 800; color: #2f6fed; margin-top: 4px; }}
    .kpi .sub {{ font-size: 11.5px; color: #64748b; font-weight: 600; text-transform: uppercase; }}
    .grid-two {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
    h2 {{ font-size: 16px; margin: 0 0 12px; color: #1e293b; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }}
    ul {{ margin: 0; padding-left: 20px; font-size: 13.5px; }}
    li {{ margin-bottom: 8px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; }}
    th {{ background: #f8fafc; font-weight: 700; color: #475569; }}
    .hooks {{ background: #eff6ff; border-left: 4px solid #2f6fed; padding: 14px 18px; border-radius: 6px; margin-bottom: 20px; }}
    .hooks h3 {{ margin: 0 0 8px; font-size: 14.5px; color: #1d4ed8; }}
    @media print {{ body {{ max-width: 100%; margin: 0; padding: 10mm; background: #fff; }} .card {{ box-shadow: none; border: 1px solid #cbd5e1; }} }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div>
        <span class="tag">Commercial Battlecard · {card["market"]} Market</span>
        <h1 style="margin-top:6px;">{card["brand"]} <span style="color:#64748b;font-weight:400;">vs.</span> {card["competitor"]}</h1>
      </div>
      <div style="text-align:right;font-size:12px;color:#64748b;">
        <div>Central Europe Category Radar</div>
        <div>Market Benchmark (100 = €{s["market_median_eur"]})</div>
      </div>
    </div>

    <!-- Top KPIs -->
    <div class="grid-kpis">
      <div class="kpi">
        <div class="sub">Price Gap</div>
        <div class="num" style="color:{"#15803d" if s["price_gap_pct"] <= 0 else "#b91c1c"};">{s["price_gap_pct"]:+}%</div>
        <div style="font-size:11px;color:#64748b;">€{s["brand_median_eur"]} vs €{s["competitor_median_eur"]}</div>
      </div>
      <div class="kpi">
        <div class="sub">Visibility Share</div>
        <div class="num">{s["brand_visibility_share"]}% <span style="font-size:12px;color:#64748b;">vs {s["competitor_visibility_share"]}%</span></div>
        <div style="font-size:11px;color:#64748b;">Rank-Weighted Shelf</div>
      </div>
      <div class="kpi">
        <div class="sub">Customer Rating</div>
        <div class="num">{s["brand_avg_rating"] or "–"}★ <span style="font-size:12px;color:#64748b;">vs {s["competitor_avg_rating"] or "–"}★</span></div>
        <div style="font-size:11px;color:#64748b;">Verified Reviews</div>
      </div>
      <div class="kpi">
        <div class="sub">Editorial Test</div>
        <div class="num">{s["brand_avg_test_score"] or "–"} <span style="font-size:12px;color:#64748b;">vs {s["competitor_avg_test_score"] or "–"}</span></div>
        <div style="font-size:11px;color:#64748b;">Stiftung Warentest (0–100)</div>
      </div>
    </div>

    <!-- Sales Pitch Hooks -->
    <div class="hooks">
      <h3>🎯 Key Commercial Pitch Hooks &amp; Retailer Talking Points</h3>
      <ul>{hooks_html}</ul>
    </div>

    <!-- Advantage vs Vulnerability -->
    <div class="grid-two">
      <div>
        <h2>✨ Product &amp; Specification Advantages</h2>
        <ul>{adv_html}</ul>
      </div>
      <div>
        <h2>⚠️ Competitive Vulnerabilities &amp; Counters</h2>
        <ul>{vuln_html}</ul>
      </div>
    </div>

    <!-- Claim Matrix -->
    <h2>Feature &amp; Claim Ownership Matrix (% of Range Carrying Claim)</h2>
    <table>
      <thead>
        <tr>
          <th>Claim / Specification</th>
          <th style="text-align:right;">{card["brand"]}</th>
          <th style="text-align:right;">{card["competitor"]}</th>
          <th style="text-align:center;">Edge</th>
        </tr>
      </thead>
      <tbody>
        {claims_rows}
      </tbody>
    </table>

    <div style="margin-top:24px;display:flex;justify-content:space-between;font-size:12px;color:#64748b;border-top:1px solid #e2e8f0;padding-top:12px;">
      <span>Distribution: <strong>{card["brand"]}</strong> in {len(card["channels"]["brand_channels"])} channels · <strong>{card["competitor"]}</strong> in {len(card["channels"]["competitor_channels"])} channels</span>
      <span>Confidential · Generated by Category Radar Commercial Engine</span>
    </div>
  </div>
</body>
</html>"""


def export_battlecard(card: dict[str, Any], export_dir: Path) -> Path:
    """Export battlecard to an HTML file in export_dir."""
    export_dir.mkdir(parents=True, exist_ok=True)
    slug = f"battlecard_{card['brand'].lower()}_vs_{card['competitor'].lower()}_{card['market'].lower()}.html"
    path = export_dir / slug
    html = render_battlecard_html(card)
    path.write_text(html, encoding="utf-8")
    return path
