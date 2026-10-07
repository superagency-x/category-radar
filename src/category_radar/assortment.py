"""Portfolio Lifecycle Matrix & Retailer Assortment Gap Analyzer (JBP Engine).

Provides Category Strategy Leads and Key Account Managers with:
- 4-Quadrant SKU Lifecycle classification (Hero Winner, Volume Challenger, Spec Specialist, EOL Candidate)
- Retailer Assortment Gap identification (e.g. MediaMarkt, Otto, Alza vs benchmark shelf)
- Feature Whitespace analysis: features rewarded by consumer demand but missing on retailer shelves
- Commercial Joint Business Planning (JBP) pitch talking points for retail buyers
"""

from __future__ import annotations

from typing import Any

from .analytics import _median, _pct, feature_lift
from .config import CategoryConfig


def classify_sku_lifecycle(item: dict) -> str:
    """Classify a product listing into a commercial lifecycle category."""
    rank = item.get("rank") or 999
    price = item.get("price_eur")
    rating = item.get("rating")
    claims = item.get("claims") or []

    if rating is not None and rating < 4.0 and rank > 30:
        return "At-Risk / EOL Candidate"
    if rank <= 20 and (rating is None or rating >= 4.4):
        return "Hero / Verified Winner"
    if rank <= 30 and price is not None and price <= 110:
        return "Volume Driver / Value Challenger"
    if len(claims) >= 3 or ("steam" in claims or "viewing_window" in claims):
        return "Spec Specialist / Premium Niche"
    if rank > 40:
        return "Decline / Tail Assortment"
    return "Mainstream Mature"


def analyze_portfolio_lifecycle(rows: list[dict], brand: str | None = None) -> dict[str, Any]:
    """Analyze the lifecycle distribution of listings across the category or a specific brand."""
    filtered = [r for r in rows if not brand or r["brand"].lower() == brand.lower()]
    by_category: dict[str, list[dict]] = {
        "Hero / Verified Winner": [],
        "Volume Driver / Value Challenger": [],
        "Spec Specialist / Premium Niche": [],
        "Mainstream Mature": [],
        "At-Risk / EOL Candidate": [],
        "Decline / Tail Assortment": [],
    }

    for r in filtered:
        cat = classify_sku_lifecycle(r)
        by_category.setdefault(cat, []).append(r)

    summary = {
        cat: {
            "count": len(items),
            "share_pct": _pct(len(items), len(filtered)),
            "median_eur": _median(r["price_eur"] for r in items),
            "top_skus": sorted(items, key=lambda x: x["rank"])[:3],
        }
        for cat, items in by_category.items()
    }

    return {
        "total_listings": len(filtered),
        "brand_filter": brand,
        "lifecycle_summary": summary,
    }


def analyze_retailer_assortment_gap(
    rows: list[dict],
    retailer_channel: str,
    benchmark_channel: str,
    cfg: CategoryConfig | None = None,
) -> dict[str, Any]:
    """Analyze missing models and feature whitespace between a direct retailer and market benchmark."""
    ret_rows = [r for r in rows if r.get("channel") == retailer_channel]
    bench_rows = [r for r in rows if r.get("channel") == benchmark_channel]

    if not ret_rows:
        return {"error": f"No listings found for retailer channel '{retailer_channel}'"}
    if not bench_rows:
        return {"error": f"No listings found for benchmark channel '{benchmark_channel}'"}

    ret_models = {r.get("model_key") for r in ret_rows if r.get("model_key")}
    bench_top20 = [r for r in bench_rows if r["rank"] <= 20]

    missing_top_models = [r for r in bench_top20 if r.get("model_key") and r.get("model_key") not in ret_models]

    # Feature whitespace: features that have high lift on benchmark but underrepresented at retailer
    ret_claims = cfg.claims if cfg else {}
    whitespace = []

    bench_lift = feature_lift(bench_rows, ret_claims)
    for fl in bench_lift:
        cid = fl["claim_id"]
        lift = fl["lift"]
        ret_with_claim = sum(1 for r in ret_rows if cid in r.get("claims", []))
        ret_share = _pct(ret_with_claim, len(ret_rows))

        # If market rewards feature (lift > 1.25) but retailer assortment has low penetration (< 25%)
        if lift is not None and lift >= 1.25 and ret_share < 30.0:
            whitespace.append(
                {
                    "claim_id": cid,
                    "label": fl["label"],
                    "market_lift": lift,
                    "benchmark_top20_share": fl["top_pct"],
                    "retailer_shelf_share": ret_share,
                    "gap_pct": round(fl["top_pct"] - ret_share, 1),
                }
            )

    # Commercial JBP hooks
    jbp_hooks = []
    if missing_top_models:
        top_missing_brands = list({r["brand"] for r in missing_top_models[:5]})
        jbp_hooks.append(
            f"📦 Assortment Gap: {retailer_channel} is missing {len(missing_top_models)} of the market's Top 20 best-sellers "
            f"(including key SKUs from {', '.join(top_missing_brands)})."
        )

    for ws in whitespace[:3]:
        jbp_hooks.append(
            f"💡 High-Yield Whitespace: '{ws['label']}' delivers a {ws['market_lift']}x market lift on comparison engines, "
            f"yet represents only {ws['retailer_shelf_share']}% of your shelf (a {ws['gap_pct']}% assortment deficit)."
        )

    return {
        "retailer_channel": retailer_channel,
        "benchmark_channel": benchmark_channel,
        "retailer_listings": len(ret_rows),
        "benchmark_listings": len(bench_rows),
        "missing_top20_count": len(missing_top_models),
        "missing_top20_models": [
            {
                "model_key": r.get("model_key"),
                "brand": r["brand"],
                "title": r["title"],
                "market_rank": r["rank"],
                "price_eur": r["price_eur"],
            }
            for r in missing_top_models[:8]
        ],
        "feature_whitespace": whitespace,
        "jbp_pitch_hooks": jbp_hooks,
    }
