"""Category analytics: price, positioning, competitive landscape, market needs.

Pure functions over the listing/review rows from the store. Every metric is
deliberately simple and explainable in one sentence, because a marketing team
has to trust a number before acting on it.

Key definitions
  Shelf rank       position on the channel's popularity-sorted category page
  Visibility share brand share of shelf weighted by 1/log2(rank+1), the same
                   discounting search engines use: rank 1 counts 1.0, rank 3
                   counts 0.5, rank 15 counts 0.25
  Price index      brand median price / market median price x 100
  Review share     brand share of all ratings on the shelf, a proxy for
                   installed base / historic sales
  Feature lift     share of top-20 products with a claim / share of all
                   products with it. Above 1 means the market rewards it.
  HHI              Herfindahl-Hirschman index on visibility share (0-10,000)
"""

from __future__ import annotations

import math
import re
import statistics as st
from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from .config import CategoryConfig

TOP_N = 20


# ------------------------------------------------------------------ helpers
def _median(xs: Iterable[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(st.median(vals), 2) if vals else None


def _pct(part: float, whole: float) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def percentile(sorted_vals: list[float], p: float) -> float | None:
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return round(sorted_vals[int(k)], 2)
    return round(sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo), 2)


def visibility_weight(rank: int) -> float:
    return 1.0 / math.log2(rank + 1)


def _by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        out[r[key]].append(r)
    return out


def dedupe_variants(rows: list[dict]) -> list[dict]:
    """Colour variants share a model_key; keep the best-ranked one per market."""
    best: dict[tuple[str, str], dict] = {}
    for r in sorted(rows, key=lambda r: (r["market"], r["rank"])):
        best.setdefault((r["market"], r["model_key"]), r)
    return list(best.values())


def assign_tiers(rows: list[dict], tiers: list[dict]) -> None:
    for market, items in _by(rows, "market").items():
        prices = sorted(r["price_eur"] for r in items if r["price_eur"] is not None)
        cuts = [(t["name"], percentile(prices, t["max_pct"])) for t in tiers]
        for r in items:
            r["tier"] = None
            if r["price_eur"] is None:
                continue
            for name, cut in cuts:
                if cut is not None and r["price_eur"] <= cut:
                    r["tier"] = name
                    break


# ------------------------------------------------------------------ price
def price_analysis(rows: list[dict], history: list[dict], cfg: CategoryConfig) -> dict[str, Any]:
    markets = {}
    for m, items in _by(rows, "market").items():
        prices = sorted(r["price_eur"] for r in items if r["price_eur"] is not None)
        local = sorted(r["price_local"] for r in items if r["price_local"] is not None)
        top = [r["price_eur"] for r in items if r["rank"] <= TOP_N and r["price_eur"] is not None]
        per_litre = [r["price_eur"] / r["capacity_l"] for r in items if r["price_eur"] and r["capacity_l"]]
        markets[m] = {
            "currency": cfg.currency_of(m),
            "n": len(items),
            "median_eur": _median(prices),
            "median_local": _median(local),
            "p10_eur": percentile(prices, 10),
            "p90_eur": percentile(prices, 90),
            "top20_median_eur": _median(top),
            "median_eur_per_litre": _median(per_litre),
            "histogram": _histogram(prices),
        }

    # brand price index per market
    brand_index: dict[str, dict[str, float]] = defaultdict(dict)
    for m, items in _by(rows, "market").items():
        mkt_med = markets[m]["median_eur"]
        for brand, b_items in _by(items, "brand").items():
            b_med = _median(r["price_eur"] for r in b_items)
            if mkt_med and b_med and len(b_items) >= 2:
                brand_index[brand][m] = round(100 * b_med / mkt_med)

    # cross-market price of identical models
    cross = []
    for key, items in _by(rows, "model_key").items():
        per_m = {}
        for r in sorted(items, key=lambda r: r["price_eur"] or 1e9):
            if r["price_eur"] is not None and r["market"] not in per_m:
                per_m[r["market"]] = r["price_eur"]
        if len(per_m) >= 3:
            lo, hi = min(per_m.values()), max(per_m.values())
            cross.append(
                {
                    "model_key": key,
                    "title": items[0]["title"],
                    "brand": items[0]["brand"],
                    "prices_eur": per_m,
                    "spread_pct": round(100 * (hi - lo) / lo, 1) if lo else None,
                    "cheapest": min(per_m, key=per_m.get),
                    "dearest": max(per_m, key=per_m.get),
                }
            )
    cross.sort(key=lambda c: -(c["spread_pct"] or 0))

    return {
        "markets": markets,
        "brand_price_index": brand_index,
        "cross_market": cross[:25],
        "trend": price_trend(history),
        "movers": price_movers(history),
        "ladder": {
            m: sorted(
                [
                    {
                        "brand": r["brand"],
                        "title": r["title"],
                        "price_eur": r["price_eur"],
                        "price_local": r["price_local"],
                        "tier": r.get("tier"),
                        "rank": r["rank"],
                        "capacity_l": r["capacity_l"],
                        "url": r["url"],
                    }
                    for r in items
                    if r["price_eur"] is not None
                ],
                key=lambda x: x["price_eur"],
            )
            for m, items in _by(rows, "market").items()
        },
    }


def _histogram(prices: list[float], bucket: int = 25) -> list[dict[str, Any]]:
    if not prices:
        return []
    top = min(int(max(prices) // bucket + 1) * bucket, 400)
    buckets = Counter(min(int(p // bucket) * bucket, top - bucket) for p in prices)
    return [{"from": b, "to": b + bucket, "n": buckets.get(b, 0)} for b in range(0, top, bucket)]


def price_trend(history: list[dict]) -> dict[str, list[dict[str, Any]]]:
    """Median shelf price per market per snapshot date (top-20 products)."""
    out: dict[str, list[dict[str, Any]]] = {}
    for m, items in _by(history, "market").items():
        series = []
        for d, day in sorted(_by(items, "snapshot_date").items()):
            top = [r["price_eur"] for r in day if r["rank"] <= TOP_N and r["price_eur"] is not None]
            series.append({"date": d, "median_eur": _median(top), "n": len(day)})
        out[m] = series
    return out


def price_movers(history: list[dict], min_change_pct: float = 5.0) -> list[dict[str, Any]]:
    """Products whose price changed by >= min_change_pct between the two latest snapshots."""
    dates = sorted({r["snapshot_date"] for r in history})
    if len(dates) < 2:
        return []
    prev_d, last_d = dates[-2], dates[-1]
    prev = {(r["market"], r["model_key"]): r for r in history if r["snapshot_date"] == prev_d}
    movers = []
    for r in history:
        if r["snapshot_date"] != last_d:
            continue
        p = prev.get((r["market"], r["model_key"]))
        if not p or not p["price_local"] or not r["price_local"]:
            continue
        chg = 100 * (r["price_local"] - p["price_local"]) / p["price_local"]
        if abs(chg) >= min_change_pct:
            movers.append(
                {
                    "market": r["market"],
                    "brand": r["brand"],
                    "title": r["title"],
                    "from_local": p["price_local"],
                    "to_local": r["price_local"],
                    "currency": r["currency"],
                    "change_pct": round(chg, 1),
                    "rank": r["rank"],
                    "rank_before": p["rank"],
                }
            )
    movers.sort(key=lambda m: m["change_pct"])
    return movers[:40]


# ------------------------------------------------------------------ landscape
def landscape(rows: list[dict]) -> dict[str, Any]:
    markets = {}
    presence: dict[str, set[str]] = defaultdict(set)
    for m, items in _by(rows, "market").items():
        total_w = sum(visibility_weight(r["rank"]) for r in items)
        total_reviews = sum(r["rating_count"] or 0 for r in items)
        total_bought = sum((r["extra"] or {}).get("recent_purchases_90d") or 0 for r in items)
        brands = []
        for b, b_items in _by(items, "brand").items():
            presence[b].add(m)
            vis = sum(visibility_weight(r["rank"]) for r in b_items)
            reviews = sum(r["rating_count"] or 0 for r in b_items)
            ratings = [r["rating"] for r in b_items if r["rating"] is not None and (r["rating_count"] or 0) >= 3]
            bought = sum((r["extra"] or {}).get("recent_purchases_90d") or 0 for r in b_items)
            brands.append(
                {
                    "brand": b,
                    "listings": len(b_items),
                    "top20": sum(1 for r in b_items if r["rank"] <= TOP_N),
                    "best_rank": min(r["rank"] for r in b_items),
                    "visibility_share": _pct(vis, total_w),
                    "review_share": _pct(reviews, total_reviews) if total_reviews else None,
                    "purchase_share": _pct(bought, total_bought) if total_bought else None,
                    "avg_rating": round(st.mean(ratings), 2) if ratings else None,
                    "avg_offers": round(st.mean([r["offers"] for r in b_items if r["offers"]]), 1)
                    if any(r["offers"] for r in b_items)
                    else None,
                    "sponsored_listings": sum(1 for r in b_items if r["sponsored"]),
                    "median_price_eur": _median(r["price_eur"] for r in b_items),
                }
            )
        brands.sort(key=lambda b: -b["visibility_share"])
        hhi = round(sum(b["visibility_share"] ** 2 for b in brands))
        markets[m] = {
            "brands": brands,
            "hhi": hhi,
            "concentration": "highly concentrated"
            if hhi > 2500
            else "moderately concentrated"
            if hhi > 1500
            else "competitive",
            "n_brands": len(brands),
            "top3_share": round(sum(b["visibility_share"] for b in brands[:3]), 1),
            "sponsored_share": _pct(sum(1 for r in items if r["sponsored"]), len(items)),
            "leader": brands[0]["brand"] if brands else None,
        }
    n_markets = len(markets)
    footprint = sorted(
        (
            {
                "brand": b,
                "markets": sorted(ms),
                "n": len(ms),
                "type": "pan-regional"
                if len(ms) >= max(2, n_markets - 1)
                else "multi-market"
                if len(ms) >= 2
                else "local",
            }
            for b, ms in presence.items()
        ),
        key=lambda x: (-x["n"], x["brand"]),
    )
    return {"markets": markets, "footprint": footprint}


# ------------------------------------------------------------------ positioning
def positioning(rows: list[dict], cfg: CategoryConfig, land: dict[str, Any], price: dict[str, Any]) -> dict[str, Any]:
    claim_labels = {k: v["label"] for k, v in cfg.claims.items()}
    maps: dict[str, list[dict]] = {}
    claim_matrix: dict[str, dict[str, dict[str, float]]] = {}
    tier_mix: dict[str, dict[str, dict[str, int]]] = {}
    for m, items in _by(rows, "market").items():
        land_b = {b["brand"]: b for b in land["markets"][m]["brands"]}
        pts = []
        for b, b_items in _by(items, "brand").items():
            idx = price["brand_price_index"].get(b, {}).get(m)
            if idx is None or len(b_items) < 2:
                continue
            claims_per = st.mean(len(r["claims"]) for r in b_items)
            caps = [r["capacity_l"] for r in b_items if r["capacity_l"]]
            pts.append(
                {
                    "brand": b,
                    "price_index": idx,
                    "avg_rating": land_b[b]["avg_rating"],
                    "visibility_share": land_b[b]["visibility_share"],
                    "claims_per_product": round(claims_per, 1),
                    "median_capacity_l": _median(caps),
                    "dual_zone_share": _pct(sum(1 for r in b_items if r["dual_zone"]), len(b_items)),
                    "listings": len(b_items),
                }
            )
        maps[m] = sorted(pts, key=lambda p: -p["visibility_share"])
        mat = {}
        for b, b_items in _by(items, "brand").items():
            if len(b_items) < 2:
                continue
            mat[b] = {k: _pct(sum(1 for r in b_items if k in r["claims"]), len(b_items)) for k in claim_labels}
        claim_matrix[m] = mat
        tiers: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in items:
            if r.get("tier"):
                tiers[r["brand"]][r["tier"]] += 1
        tier_mix[m] = {b: dict(t) for b, t in tiers.items()}
    return {
        "claim_labels": claim_labels,
        "maps": maps,
        "claim_matrix": claim_matrix,
        "tier_mix": tier_mix,
        "tiers": [t["name"] for t in cfg.price_tiers],
    }


# ------------------------------------------------------------------ needs
def market_needs(rows: list[dict], reviews: list[dict], cfg: CategoryConfig) -> dict[str, Any]:
    claim_labels = {k: v["label"] for k, v in cfg.claims.items()}
    # 1) revealed preference: which features does the shelf reward?
    lift: dict[str, list[dict]] = {}
    capacity: dict[str, dict[str, Any]] = {}
    for m, items in _by(rows, "market").items():
        top = [r for r in items if r["rank"] <= TOP_N]
        out = []
        for k, label in claim_labels.items():
            share_all = _pct(sum(1 for r in items if k in r["claims"]), len(items))
            share_top = _pct(sum(1 for r in top if k in r["claims"]), len(top))
            out.append(
                {
                    "claim": k,
                    "label": label,
                    "share_all": share_all,
                    "share_top20": share_top,
                    "lift": round(share_top / share_all, 2) if share_all else None,
                }
            )
        lift[m] = sorted(out, key=lambda x: -(x["lift"] or 0))
        caps_top = sorted(r["capacity_l"] for r in top if r["capacity_l"])
        caps_all = sorted(r["capacity_l"] for r in items if r["capacity_l"])
        capacity[m] = {
            "top20_median": _median(caps_top),
            "all_median": _median(caps_all),
            "top20_iqr": [percentile(caps_top, 25), percentile(caps_top, 75)],
        }

    # 2) stated needs: what reviewers talk about (salience) and how happy they are
    patterns = {k: re.compile(v["pattern"], re.IGNORECASE) for k, v in cfg.needs.items()}
    salience: dict[str, list[dict]] = {}
    for m, revs in _by(reviews, "market").items():
        out = []
        for k, pat in patterns.items():
            hits = [r for r in revs if pat.search(r["text"])]
            ratings = [r["rating"] for r in hits if r["rating"] is not None]
            out.append(
                {
                    "need": k,
                    "label": cfg.needs[k]["label"],
                    "mentions": len(hits),
                    "salience_pct": _pct(len(hits), len(revs)),
                    "avg_rating_when_mentioned": round(st.mean(ratings), 2) if ratings else None,
                }
            )
        salience[m] = sorted(out, key=lambda x: -x["salience_pct"])

    # 3) hard demand signals some channels expose
    demand = []
    for r in rows:
        bought = (r["extra"] or {}).get("recent_purchases_90d")
        if bought:
            demand.append(
                {
                    "market": r["market"],
                    "brand": r["brand"],
                    "title": r["title"],
                    "recent_purchases_90d": bought,
                    "price_eur": r["price_eur"],
                }
            )
    demand.sort(key=lambda d: -d["recent_purchases_90d"])

    return {
        "feature_lift": lift,
        "capacity": capacity,
        "review_salience": salience,
        "review_counts": {m: len(v) for m, v in _by(reviews, "market").items()},
        "demand_signals": demand[:20],
    }


# ------------------------------------------------------------------ promotions, tests & omnichannel
def promotional_intensity(rows: list[dict]) -> dict[str, Any]:
    """Analyse UVP (MSRP) vs real shelf price and promotional discount depth."""
    by_mkt: dict[str, dict[str, Any]] = {}
    top_deals = []

    for m, items in _by(rows, "market").items():
        with_uvp = [r for r in items if r.get("price_eur") and (r.get("extra") or {}).get("uvp_eur")]
        brand_deals: dict[str, list[float]] = defaultdict(list)
        for r in with_uvp:
            uvp = r["extra"]["uvp_eur"]
            price = r["price_eur"]
            if uvp > price:
                disc = round(100 * (uvp - price) / uvp, 1)
                brand_deals[r["brand"]].append(disc)
                top_deals.append(
                    {
                        "market": m,
                        "channel": r["channel"],
                        "brand": r["brand"],
                        "title": r["title"],
                        "price_eur": price,
                        "uvp_eur": uvp,
                        "discount_depth_pct": disc,
                        "url": r["url"],
                    }
                )

        brand_stats = []
        for b, discs in brand_deals.items():
            brand_stats.append(
                {
                    "brand": b,
                    "avg_discount_pct": round(st.mean(discs), 1),
                    "deal_count": len(discs),
                    "max_discount_pct": max(discs),
                }
            )
        brand_stats.sort(key=lambda x: -x["avg_discount_pct"])

        all_discs = [d for discs in brand_deals.values() for d in discs]
        by_mkt[m] = {
            "products_with_uvp": len(with_uvp),
            "discounted_products": len(all_discs),
            "avg_discount_pct": round(st.mean(all_discs), 1) if all_discs else 0.0,
            "brands": brand_stats,
        }

    top_deals.sort(key=lambda d: -d["discount_depth_pct"])
    return {
        "markets": by_mkt,
        "top_deals": top_deals[:25],
    }


def editorial_testing(rows: list[dict]) -> dict[str, Any]:
    """Analyse Stiftung Warentest / Testberichte editorial scores vs consumer ratings."""
    tested = []
    for r in rows:
        ts = (r.get("extra") or {}).get("test_score")
        if ts is not None and r.get("rating") is not None:
            score = float(ts)
            rating = float(r["rating"])
            quadrant = (
                "Verified Winner"
                if score >= 75 and rating >= 4.2
                else "Consumer Darling"
                if score < 75 and rating >= 4.2
                else "Lab Winner / Hidden Gem"
                if score >= 75 and rating < 4.2
                else "Underperformer"
            )
            tested.append(
                {
                    "brand": r["brand"],
                    "title": r["title"],
                    "market": r["market"],
                    "channel": r["channel"],
                    "model_key": r["model_key"],
                    "test_score": score,
                    "user_rating": rating,
                    "rating_count": r.get("rating_count"),
                    "price_eur": r.get("price_eur"),
                    "quadrant": quadrant,
                    "url": r["url"],
                }
            )

    tested.sort(key=lambda x: (-x["test_score"], -x["user_rating"]))
    quadrant_counts = dict(Counter(x["quadrant"] for x in tested))

    return {
        "count": len(tested),
        "quadrant_counts": quadrant_counts,
        "items": tested[:50],
        "avg_test_score": round(st.mean(x["test_score"] for x in tested), 1) if tested else None,
    }


def omnichannel_comparison(rows: list[dict]) -> dict[str, Any]:
    """Compare shelf presence and pricing across Comparison Engines and Direct Retailers."""
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_channel[r["channel"]].append(r)

    channel_stats = []
    for cid, items in by_channel.items():
        prices = [r["price_eur"] for r in items if r.get("price_eur")]
        channel_stats.append(
            {
                "channel": cid,
                "market": items[0]["market"],
                "channel_type": items[0].get("channel_type", "price_comparison"),
                "listings": len(items),
                "median_price_eur": _median(prices),
                "p10_eur": percentile(sorted(prices), 10) if prices else None,
                "p90_eur": percentile(sorted(prices), 90) if prices else None,
                "brands_count": len({r["brand"] for r in items}),
            }
        )
    channel_stats.sort(key=lambda x: (x["market"], x["channel"]))
    return {"channels": channel_stats}


# ------------------------------------------------------------------ narrative
def key_insights(
    price: dict,
    land: dict,
    pos: dict,
    needs: dict,
    promos: dict,
    editorial: dict,
    cfg: CategoryConfig,
) -> list[dict[str, str]]:
    """Plain-language 'so what' statements generated from the numbers."""
    out: list[dict[str, str]] = []
    mk = land["markets"]
    for m in sorted(mk):
        d = mk[m]
        if not d["brands"]:
            continue
        lead = d["brands"][0]
        out.append(
            {
                "market": m,
                "topic": "landscape",
                "text": f"{cfg.markets[m]['name']}: {lead['brand']} leads shelf visibility with "
                f"{lead['visibility_share']}%; the top 3 brands hold {d['top3_share']}% "
                f"({d['concentration']}, HHI {d['hhi']}).",
            }
        )
    meds = {m: v["median_eur"] for m, v in price["markets"].items() if v["median_eur"]}
    if len(meds) >= 2:
        lo, hi = min(meds, key=meds.get), max(meds, key=meds.get)
        out.append(
            {
                "market": "ALL",
                "topic": "price",
                "text": f"The median air fryer on the shelf costs €{meds[lo]:.0f} in {cfg.markets[lo]['name']} "
                f"vs €{meds[hi]:.0f} in {cfg.markets[hi]['name']} "
                f"({100 * (meds[hi] - meds[lo]) / meds[lo]:.0f}% gap).",
            }
        )
    if price["cross_market"]:
        c = price["cross_market"][0]
        out.append(
            {
                "market": "ALL",
                "topic": "price",
                "text": f"Largest cross-border gap on an identical model: {c['title']} is "
                f"{c['spread_pct']}% dearer in {c['dearest']} than in {c['cheapest']}, "
                f"a grey-import / price-harmonisation risk.",
            }
        )

    for m, pdata in promos.get("markets", {}).items():
        if pdata.get("discounted_products", 0) >= 2:
            top_b = pdata["brands"][0]
            out.append(
                {
                    "market": m,
                    "topic": "price",
                    "text": f"{cfg.markets[m]['name']}: Promotional discount depth averages {pdata['avg_discount_pct']}% below UVP (MSRP); {top_b['brand']} cuts deepest (avg -{top_b['avg_discount_pct']}%).",
                }
            )

    if editorial.get("count", 0) >= 2:
        top_t = editorial["items"][0]
        out.append(
            {
                "market": "ALL",
                "topic": "positioning",
                "text": f"Editorial testing: {editorial['count']} models carry certified test scores; {top_t['brand']} leads with {top_t['test_score']:.0f}/100 and {top_t['user_rating']}★ user rating ({top_t['quadrant']}).",
            }
        )

    for m, items in needs["feature_lift"].items():
        winners = [x for x in items if x["lift"] and x["lift"] >= 1.2 and x["share_all"] >= 10]
        if winners:
            w = winners[0]
            out.append(
                {
                    "market": m,
                    "topic": "needs",
                    "text": f"{cfg.markets[m]['name']}: '{w['label']}' appears in {w['share_top20']}% of the "
                    f"top-20 vs {w['share_all']}% of the full shelf (lift {w['lift']}x), so the market rewards it.",
                }
            )
    for m, items in needs["review_salience"].items():
        if items and items[0]["mentions"]:
            s = items[0]
            out.append(
                {
                    "market": m,
                    "topic": "needs",
                    "text": f"{cfg.markets[m]['name']}: the most-discussed need in reviews is "
                    f"'{s['label']}' ({s['salience_pct']}% of reviews).",
                }
            )
    multi = [f for f in land["footprint"] if f["type"] == "pan-regional"]
    if multi:
        out.append(
            {
                "market": "ALL",
                "topic": "landscape",
                "text": "Pan-regional brands present in (almost) every market: "
                + ", ".join(f["brand"] for f in multi[:8])
                + ".",
            }
        )
    return out


def seasonality_analysis(history: list[dict]) -> dict[str, Any]:
    """Analyze price trends by month to detect seasonality patterns."""
    monthly_data = defaultdict(list)

    for r in history:
        if r.get("price_eur") and r.get("rank", 999) <= TOP_N:
            month = r["snapshot_date"][5:7]  # Extract MM from YYYY-MM-DD
            monthly_data[month].append(r["price_eur"])

    monthly_stats = {}
    for month, prices in sorted(monthly_data.items()):
        if prices:
            monthly_stats[month] = {
                "median": round(st.median(prices), 2),
                "mean": round(st.mean(prices), 2),
                "min": round(min(prices), 2),
                "max": round(max(prices), 2),
                "count": len(prices),
            }

    # Detect seasonal patterns
    if len(monthly_stats) >= 3:
        months = sorted(monthly_stats.keys())
        medians = [monthly_stats[m]["median"] for m in months]

        # Simple seasonality: is there a clear peak/trough?
        peak_month = months[medians.index(max(medians))]
        trough_month = months[medians.index(min(medians))]
        seasonal_range = max(medians) - min(medians)
        avg_price = st.mean(medians)
        seasonality_strength = round(seasonal_range / avg_price * 100, 1) if avg_price else 0
    else:
        peak_month = None
        trough_month = None
        seasonality_strength = 0

    return {
        "monthly": monthly_stats,
        "peak_month": peak_month,
        "trough_month": trough_month,
        "seasonality_strength_pct": seasonality_strength,
        "interpretation": (
            f"Strong seasonality ({seasonality_strength}% range) with peak in {peak_month}"
            if seasonality_strength > 10
            else "Moderate seasonality"
            if seasonality_strength > 5
            else "Weak seasonality - prices stable year-round"
        ),
    }


def cross_elasticity(history: list[dict]) -> dict[str, Any]:
    """Analyze how price changes affect rank (price elasticity)."""
    dates = sorted({r["snapshot_date"] for r in history})
    if len(dates) < 2:
        return {"elasticity_by_brand": {}, "note": "Insufficient history"}

    prev_d, last_d = dates[-2], dates[-1]
    prev = {(r["market"], r["model_key"]): r for r in history if r["snapshot_date"] == prev_d}

    elasticity_data = []

    for r in history:
        if r["snapshot_date"] != last_d:
            continue

        p = prev.get((r["market"], r["model_key"]))
        if not p or not p.get("price_local") or not r.get("price_local"):
            continue

        price_change_pct = 100 * (r["price_local"] - p["price_local"]) / p["price_local"]
        rank_change = p["rank"] - r["rank"]  # Positive = rank improved (lower number)

        if price_change_pct != 0:
            elasticity = rank_change / price_change_pct
            elasticity_data.append(
                {
                    "brand": r["brand"],
                    "model_key": r["model_key"],
                    "market": r["market"],
                    "price_change_pct": round(price_change_pct, 1),
                    "rank_change": rank_change,
                    "elasticity": round(elasticity, 3),
                }
            )

    # Aggregate by brand
    by_brand = defaultdict(list)
    for e in elasticity_data:
        by_brand[e["brand"]].append(e)

    brand_elasticity = {}
    for brand, items in by_brand.items():
        avg_elasticity = st.mean([e["elasticity"] for e in items])
        brand_elasticity[brand] = {
            "avg_elasticity": round(avg_elasticity, 3),
            "sample_size": len(items),
            "interpretation": (
                "Highly elastic - price sensitive"
                if avg_elasticity > 0.5
                else "Moderately elastic"
                if avg_elasticity > 0.1
                else "Inelastic - price insensitive"
                if avg_elasticity > -0.1
                else "Counter-intuitive (lower price = worse rank)"
            ),
        }

    return {
        "elasticity_by_brand": brand_elasticity,
        "top_elastic": sorted(elasticity_data, key=lambda x: -x["elasticity"])[:10],
    }


def detect_outliers(rows: list[dict]) -> dict[str, Any]:
    """Detect unusual price movements and anomalies."""
    outliers = []

    for market, items in _by(rows, "market").items():
        prices = [r["price_eur"] for r in items if r.get("price_eur")]
        if len(prices) < 5:
            continue

        prices_sorted = sorted(prices)
        q1 = percentile(prices_sorted, 25)
        q3 = percentile(prices_sorted, 75)
        iqr = q3 - q1 if (q1 is not None and q3 is not None) else 0
        lower_bound = q1 - 1.5 * iqr if iqr and q1 is not None else (q1 * 0.5 if q1 is not None else 0)
        upper_bound = q3 + 1.5 * iqr if iqr and q3 is not None else (q3 * 1.5 if q3 is not None else 1000)

        for r in items:
            if r.get("price_eur"):
                if r["price_eur"] < lower_bound:
                    outliers.append(
                        {
                            "brand": r["brand"],
                            "title": r["title"],
                            "market": market,
                            "price_eur": r["price_eur"],
                            "type": "price_undercut",
                            "severity": "extreme" if r["price_eur"] < lower_bound * 0.5 else "moderate",
                        }
                    )
                elif r["price_eur"] > upper_bound:
                    outliers.append(
                        {
                            "brand": r["brand"],
                            "title": r["title"],
                            "market": market,
                            "price_eur": r["price_eur"],
                            "type": "price_premium",
                            "severity": "extreme" if r["price_eur"] > upper_bound * 1.5 else "moderate",
                        }
                    )

    return {
        "outliers": sorted(outliers, key=lambda x: x["price_eur"])[:20],
        "count": len(outliers),
    }


def brand_velocity(history: list[dict]) -> dict[str, Any]:
    """Track brand momentum: new entrants, declining brands, rising stars."""
    dates = sorted({r["snapshot_date"] for r in history})
    if len(dates) < 2:
        return {"velocity": {}, "note": "Insufficient history"}

    first_d, last_d = dates[0], dates[-1]

    first_run = {r["brand"]: r for r in history if r["snapshot_date"] == first_d}
    last_run = {r["brand"]: r for r in history if r["snapshot_date"] == last_d}

    velocity = {}

    # New entrants
    new_brands = set(last_run.keys()) - set(first_run.keys())
    for brand in new_brands:
        velocity[brand] = {
            "status": "new_entrant",
            "first_seen": last_d,
            "listings": len([r for r in history if r["brand"] == brand and r["snapshot_date"] == last_d]),
        }

    # Declining brands (disappeared)
    departed_brands = set(first_run.keys()) - set(last_run.keys())
    for brand in departed_brands:
        velocity[brand] = {
            "status": "departed",
            "last_seen": last_d,
            "listings_at_departure": len([r for r in history if r["brand"] == brand and r["snapshot_date"] == first_d]),
        }

    # Rising stars (improved visibility)
    for brand in set(first_run.keys()) & set(last_run.keys()):
        first_items = [r for r in history if r["brand"] == brand and r["snapshot_date"] == first_d]
        last_items = [r for r in history if r["brand"] == brand and r["snapshot_date"] == last_d]

        first_vis = sum(visibility_weight(r["rank"]) for r in first_items)
        last_vis = sum(visibility_weight(r["rank"]) for r in last_items)

        if first_vis > 0 and last_vis > first_vis * 1.2:  # 20% growth
            velocity[brand] = {
                "status": "rising_star",
                "visibility_change_pct": round(100 * (last_vis - first_vis) / first_vis, 1),
                "current_listings": len(last_items),
            }
        elif first_vis > 0 and last_vis < first_vis * 0.8:  # 20% decline
            velocity[brand] = {
                "status": "declining",
                "visibility_change_pct": round(100 * (last_vis - first_vis) / first_vis, 1),
                "current_listings": len(last_items),
            }

    return {
        "velocity": velocity,
        "summary": {
            "new_entrants": len(new_brands),
            "departed": len(departed_brands),
            "rising_stars": len([v for v in velocity.values() if v["status"] == "rising_star"]),
            "declining": len([v for v in velocity.values() if v["status"] == "declining"]),
        },
    }


# ------------------------------------------------------------------ entry
def analyse(latest: list[dict], history: list[dict], reviews: list[dict], cfg: CategoryConfig) -> dict[str, Any]:
    rows = dedupe_variants(latest)
    assign_tiers(rows, cfg.price_tiers)
    price = price_analysis(rows, dedupe_variants_by_date(history), cfg)
    land = landscape(rows)
    pos = positioning(rows, cfg, land, price)
    needs = market_needs(rows, reviews, cfg)
    promos = promotional_intensity(latest)
    editorial = editorial_testing(latest)
    omnichannel = omnichannel_comparison(latest)
    seasonality = seasonality_analysis(history)
    elasticity = cross_elasticity(history)
    outliers = detect_outliers(rows)
    velocity = brand_velocity(history)
    return {
        "price": price,
        "landscape": land,
        "positioning": pos,
        "needs": needs,
        "promotions": promos,
        "editorial": editorial,
        "omnichannel": omnichannel,
        "seasonality": seasonality,
        "cross_elasticity": elasticity,
        "outliers": outliers,
        "brand_velocity": velocity,
        "insights": key_insights(price, land, pos, needs, promos, editorial, cfg),
    }


def dedupe_variants_by_date(history: list[dict]) -> list[dict]:
    out = []
    for day in _by(history, "snapshot_date").values():
        out += dedupe_variants(day)
    return out
