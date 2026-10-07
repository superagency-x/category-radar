"""Command-line interface.

radar run        scrape all channels, store, analyse, write dashboard data
radar doctor     health-check every channel (robots, fetch, parse) without storing
radar export     rebuild dashboard data from the database
radar reparse    re-parse saved HTML of a past day (no network)
radar serve      open the dashboard locally
radar publish    commit + push the dashboard data (GitHub Pages redeploys)
radar channels   list configured channels and adapters
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
import webbrowser
from pathlib import Path

from .channels import available_adapters, get_adapter
from .config import ConfigError, load_config
from .export import build_bundle, write_csvs, write_executive_brief, write_site_data
from .fetch import BlockedError, Fetcher, FetchError, RobotsDisallowed
from .health import app as health_app
from .logging_config import configure_logging, get_logger
from .pipeline import run_pipeline
from .store import Store

ROOT = Path.cwd()
STATUS_ICON = {"ok": "✅", "empty": "⚠️ ", "blocked": "⛔", "disallowed": "🚫", "error": "❌", "missing": "…"}
log = get_logger(__name__)


def _common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", default="config/airfryer.yaml", help="category YAML (default: %(default)s)")
    p.add_argument("--data-dir", default="data", help="where the database and raw HTML live")
    p.add_argument("--site-dir", default="site", help="dashboard folder")
    p.add_argument("-v", "--verbose", action="store_true")


def _export(cfg, data_dir: Path, site_dir: Path) -> None:
    store = Store(data_dir / "radar.sqlite")
    try:
        bundle = build_bundle(cfg, store)
    finally:
        store.close()
    path = write_site_data(bundle, site_dir)
    csvs = write_csvs(bundle, data_dir / "exports")
    md_brief, html_brief = write_executive_brief(bundle, data_dir / "exports")
    # Also mirror executive brief and CSVs into site/data for direct web dashboard access
    try:
        import shutil

        site_data = site_dir / "data"
        site_data.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html_brief, site_data / "executive_brief.html")
        for c in csvs:
            prefix = "listings" if "listings_" in c.name else "brands"
            shutil.copy2(c, site_data / f"{prefix}.csv")
    except Exception as e:
        log.warning("site_export_mirror_failed", error=str(e))
    print(
        f"Dashboard data   → {path}  ({bundle['meta']['counts']['listings']} listings, "
        f"{bundle['meta']['counts']['reviews']} reviews, {bundle['meta']['counts']['snapshots']} snapshot(s))"
    )
    for c in csvs:
        print(f"CSV              → {c}")
    print(f"Executive Brief  → {md_brief}")
    print(f"HTML Dossier     → {html_brief}")


def cmd_run(args, cfg) -> int:
    channels = args.channels.split(",") if args.channels else None
    if channels:
        unknown = set(channels) - set(cfg.channels)
        if unknown:
            print(f"Unknown channel(s): {', '.join(sorted(unknown))}")
            return 2
    if getattr(args, "async_mode", False):
        import asyncio

        from .pipeline import run_pipeline_async

        report = asyncio.run(run_pipeline_async(cfg, Path(args.data_dir), channels=channels))
    else:
        report = run_pipeline(
            cfg, Path(args.data_dir), channels=channels, with_reviews=not args.no_reviews, progress=print
        )
    print(f"\nRun {report.run_id}: {report.total_listings} listings, {report.reviews} reviews")
    for cid, s in report.channel_status.items():
        print(
            f"  {STATUS_ICON.get(s['status'], '?')} {cid:<14} {s['status']:<10} {s['listings']:>4} listings  "
            f"{s.get('pages', 0)} page(s) via {s.get('via')}"
        )
    if not args.no_export:
        _export(cfg, Path(args.data_dir), Path(args.site_dir))
    return 0 if report.total_listings else 1


def cmd_reparse(args, cfg) -> int:
    raw = Path(args.data_dir) / "raw" / args.date
    if not raw.exists():
        print(f"No saved HTML for {args.date} in {raw}")
        return 2
    report = run_pipeline(cfg, Path(args.data_dir), offline_raw_dir=raw, with_reviews=False, progress=print)
    print(f"Re-parsed {report.total_listings} listings from {raw}")
    _export(cfg, Path(args.data_dir), Path(args.site_dir))
    return 0


def cmd_export(args, cfg) -> int:
    _export(cfg, Path(args.data_dir), Path(args.site_dir))
    return 0


def cmd_report(args, cfg) -> int:
    """Print the executive category intelligence dossier and confirm exports."""
    store = Store(Path(args.data_dir) / "radar.sqlite")
    try:
        bundle = build_bundle(cfg, store)
    finally:
        store.close()
    md_path, html_path = write_executive_brief(bundle, Path(args.data_dir) / "exports")
    print(md_path.read_text(encoding="utf-8"))
    print(f"\n[Artifacts written: {md_path} | {html_path}]")
    return 0


def cmd_doctor(args, cfg) -> int:
    """Fetch page 1 of every channel and report whether parsing still works."""
    crawl = cfg.crawl
    tmp = Path(args.data_dir) / "raw" / "_doctor"
    worst = 0
    with Fetcher(
        tmp,
        mode=crawl.get("fetcher", "auto"),
        delay_seconds=float(crawl.get("delay_seconds", 4)),
        respect_robots=bool(crawl.get("respect_robots_txt", True)),
        user_agent=crawl.get("user_agent"),
    ) as f:
        for cid, ch in cfg.channels.items():
            if args.channels and cid not in args.channels.split(","):
                continue
            try:
                res = f.fetch(ch.start_url, language=cfg.language_of(ch.market), cache_path=tmp / f"{cid}.html")
                items = get_adapter(ch.adapter).parse(
                    res.html, channel=cid, market=ch.market, currency=cfg.currency_of(ch.market)
                )
                priced = sum(1 for i in items if i.price)
                status = "ok" if items and priced >= len(items) * 0.8 else "empty"
                detail = f"{len(items)} products, {priced} with price, via {res.via}"
                if items:
                    detail += f" | #1: {items[0].title[:40]} @ {items[0].price} {items[0].currency}"
            except BlockedError as e:
                status, detail = "blocked", str(e)
            except RobotsDisallowed as e:
                status, detail = "disallowed", str(e)
            except FetchError as e:
                status, detail = "error", str(e)
            worst = max(worst, 0 if status == "ok" else 1)
            print(f"{STATUS_ICON.get(status, '?')} {cid:<14} {status:<10} {detail}")
    return worst


def cmd_serve(args, cfg) -> int:
    site = Path(args.site_dir).resolve()
    if not (site / "data" / "radar.json").exists():
        print("No dashboard data yet: run `radar run` (or `radar export`) first.")
        return 2
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Serving {site} at {url}  (Ctrl+C to stop)")
        if not args.no_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


def cmd_publish(args, cfg) -> int:
    """Commit the exported dashboard bundle and push; the Pages workflow deploys it."""
    import subprocess  # nosec B404

    bundle = Path(args.site_dir) / "data" / "radar.json"
    if not bundle.exists():
        print("Nothing to publish: run `radar run` first.")
        return 2

    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], capture_output=True, text=True)  # nosec B603 B607

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        print("This folder is not a git repository yet. See README → 'Publish to radar.saralogy.com'.")
        return 2
    import json

    date = json.loads(bundle.read_text(encoding="utf-8"))["meta"]["snapshot_date"]
    git("add", str(bundle))
    if git("diff", "--cached", "--quiet").returncode == 0:
        print("Dashboard data unchanged, nothing to publish.")
        return 0
    c = git("commit", "-m", f"data: market snapshot {date}")
    if c.returncode != 0:
        print(c.stderr or c.stdout)
        return 1
    p = git("push")
    print(p.stdout or p.stderr or "Pushed.")
    return p.returncode


def cmd_channels(args, cfg) -> int:
    print(f"Category: {cfg.name}  ({cfg.path})\nAdapters available: {', '.join(available_adapters())}\n")
    for cid, ch in cfg.channels.items():
        print(f"  {cid:<14} {ch.market}  {ch.adapter:<10} {ch.type:<17} max {ch.max_pages} page(s)  {ch.start_url}")
    return 0


def cmd_health(args, cfg) -> int:
    """Start health check server."""
    import uvicorn

    log.info("health_server_start", port=args.port)
    uvicorn.run(health_app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


def cmd_migrate(args, cfg) -> int:
    """Run database migrations."""
    import subprocess  # nosec B404
    import sys

    alembic_bin = Path(sys.executable).parent / "alembic"
    cmd = [str(alembic_bin) if alembic_bin.exists() else "alembic", "upgrade", "head"]
    result = subprocess.run(cmd, cwd=Path.cwd())  # nosec B603
    return result.returncode


def cmd_api(args, cfg) -> int:
    """Start API server."""
    import uvicorn

    from .api import app

    log.info("api_server_start", port=args.port)
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")
    return 0


def cmd_battlecard(args, cfg) -> int:
    """Generate and display commercial sales battlecard."""
    store = Store(Path(args.data_dir) / "radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            print("No data in database. Run `radar run` first.")
            return 2
        rows = store.listings(run_id)
    finally:
        store.close()

    from .battlecards import export_battlecard, generate_battlecard

    card = generate_battlecard(rows, brand=args.brand, competitor=args.competitor, market=args.market, cfg=cfg)
    if "error" in card:
        print(f"Error: {card['error']}")
        return 1

    s = card["summary"]
    print("\n=======================================================")
    print(f"🎯 SALES BATTLECARD: {card['brand']} vs {card['competitor']} ({card['market']} Market)")
    print("=======================================================")
    print(
        f"Price Benchmark:      {card['brand']} €{s['brand_median_eur']} vs {card['competitor']} €{s['competitor_median_eur']} ({s['price_gap_pct']:+}%)"
    )
    print(
        f"Brand Price Index:    {card['brand']} idx {s['brand_price_index']} vs {card['competitor']} idx {s['competitor_price_index']} (100 = market median)"
    )
    print(
        f"Visibility Share:     {card['brand']} {s['brand_visibility_share']}% vs {card['competitor']} {s['competitor_visibility_share']}%"
    )
    print(
        f"Customer Rating:      {card['brand']} {s['brand_avg_rating'] or '–'}★ vs {card['competitor']} {s['competitor_avg_rating'] or '–'}★"
    )
    if s["brand_avg_test_score"] or s["competitor_avg_test_score"]:
        print(
            f"Stiftung Warentest:   {card['brand']} {s['brand_avg_test_score'] or '–'}/100 vs {card['competitor']} {s['competitor_avg_test_score'] or '–'}/100"
        )

    print("\n🎯 KEY COMMERCIAL PITCH HOOKS:")
    for h in card["sales_hooks"]:
        print(f"  • {h}")

    print("\n✨ PRODUCT & SPEC ADVANTAGES:")
    for a in card["advantages"] or ["No critical gap."]:
        print(f"  + {a}")

    print("\n⚠️ COMPETITOR VULNERABILITIES & COUNTERS:")
    for v in card["vulnerabilities"] or ["Evenly matched."]:
        print(f"  - {v}")

    export_path = export_battlecard(card, Path(args.data_dir) / "exports")
    try:
        import shutil

        site_data = Path(args.site_dir) / "data"
        site_data.mkdir(parents=True, exist_ok=True)
        shutil.copy2(export_path, site_data / export_path.name)
    except Exception as exc:
        log.debug("battlecard_site_copy_skipped", error=str(exc))

    print(f"\n[Battlecard written: {export_path}]")
    return 0


def cmd_alert(args, cfg) -> int:
    """Run autonomous market anomaly detection and dispatch alerts."""
    store = Store(Path(args.data_dir) / "radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            print("No data in database. Run `radar run` first.")
            return 2
        latest = store.listings(run_id)
        history = store.listings()
    finally:
        store.close()

    from .alerts import AlertSeverity, detect_alerts, dispatch_webhook, format_alerts_markdown
    from .settings import settings

    min_sev = AlertSeverity(args.min_severity)
    alerts = detect_alerts(latest, history, cfg, min_severity=min_sev)
    bulletin = format_alerts_markdown(alerts)
    print(bulletin)

    webhook_url = (
        args.webhook or getattr(settings, "alert_webhook_url", None) or getattr(settings, "slack_webhook_url", None)
    )
    if webhook_url:
        ok = dispatch_webhook(alerts, webhook_url)
        print(f"\n[Webhook dispatch: {'✅ Success' if ok else '❌ Failed'} -> {webhook_url}]")
    return 0


def cmd_jbp(args, cfg) -> int:
    """Generate Joint Business Planning retailer assortment gap analysis."""
    store = Store(Path(args.data_dir) / "radar.sqlite")
    try:
        run_id = store.latest_run_id()
        if not run_id:
            print("No data in database. Run `radar run` first.")
            return 2
        rows = store.listings(run_id)
    finally:
        store.close()

    from .assortment import analyze_retailer_assortment_gap

    gap = analyze_retailer_assortment_gap(rows, args.retailer, args.benchmark, cfg=cfg)
    if "error" in gap:
        print(f"Error: {gap['error']}")
        return 1

    print("\n=======================================================")
    print(f"🏬 RETAILER JBP ASSORTMENT GAP: {args.retailer} vs {args.benchmark}")
    print("=======================================================")
    print(f"Listings tracked:     Retailer: {gap['retailer_listings']} | Benchmark: {gap['benchmark_listings']}")
    print(f"Missing Top-20 SKUs:  {gap['missing_top20_count']} best-selling models absent from retailer shelf")

    print("\n🎯 JBP NEGOTIATION TALKING POINTS:")
    for hook in gap["jbp_pitch_hooks"]:
        print(f"  • {hook}")

    if gap["feature_whitespace"]:
        print("\n💡 HIGH-YIELD FEATURE WHITESPACES:")
        for ws in gap["feature_whitespace"]:
            print(
                f"  + {ws['label']}: Market Lift {ws['market_lift']}x vs Retailer Share {ws['retailer_shelf_share']}% (Deficit: {ws['gap_pct']}%)"
            )

    return 0


def cmd_categories(args, cfg) -> int:
    """List available category configurations."""
    cfg_dir = Path("config")
    files = sorted(cfg_dir.glob("*.yaml")) if cfg_dir.exists() else []
    print(f"Available Category Profiles ({len(files)} configured):")
    for f in files:
        try:
            c = load_config(f)
            active_marker = " (active)" if str(f) == args.config else ""
            print(
                f"  • {c.id:<14} '{c.name}' [{len(c.markets)} markets, {len(c.channels)} channels] ({f}){active_marker}"
            )
        except Exception:
            print(f"  • {f.stem:<14} (syntax error in {f})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Category Radar: Central European category intelligence")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="scrape → store → analyse → export")
    _common(p)
    p.add_argument("--channels", help="comma-separated subset, e.g. geizhals_de,ceneo_pl")
    p.add_argument("--no-reviews", action="store_true", help="skip product-page review mining (faster)")
    p.add_argument("--no-export", action="store_true")
    p.add_argument("--async", dest="async_mode", action="store_true", help="use async concurrent scraping")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("doctor", help="check every channel still fetches and parses")
    _common(p)
    p.add_argument("--channels")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("export", help="rebuild dashboard data from the database")
    _common(p)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("report", help="display and export executive category intelligence dossier")
    _common(p)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("reparse", help="re-parse saved HTML of a past day, offline")
    _common(p)
    p.add_argument("--date", required=True, help="YYYY-MM-DD folder under data/raw/")
    p.set_defaults(func=cmd_reparse)

    p = sub.add_parser("serve", help="open the dashboard locally")
    _common(p)
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("publish", help="commit + push dashboard data so the website updates")
    _common(p)
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("channels", help="list configured channels")
    _common(p)
    p.set_defaults(func=cmd_channels)

    p = sub.add_parser("health", help="start health check server for monitoring")
    _common(p)
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("migrate", help="run database migrations")
    _common(p)
    p.set_defaults(func=cmd_migrate)

    p = sub.add_parser("api", help="start REST API server")
    _common(p)
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_api)

    p = sub.add_parser("battlecard", help="generate commercial competitor battlecard")
    _common(p)
    p.add_argument("--brand", required=True, help="focus brand name (e.g. Ninja, Philips, Cosori)")
    p.add_argument("--competitor", help="competitor brand name (defaults to market leader)")
    p.add_argument("--market", default="DE", help="market code (DE, AT, CH, PL, CZ, HU)")
    p.set_defaults(func=cmd_battlecard)

    p = sub.add_parser("alert", help="run autonomous GTM anomaly detection and dispatch alerts")
    _common(p)
    p.add_argument("--webhook", help="Slack, Discord, or Teams webhook URL")
    p.add_argument(
        "--min-severity",
        default="medium",
        choices=["critical", "high", "medium", "info"],
        help="minimum alert severity threshold",
    )
    p.set_defaults(func=cmd_alert)

    p = sub.add_parser("jbp", help="generate Joint Business Planning retailer assortment gap analysis")
    _common(p)
    p.add_argument(
        "--retailer", default="mediamarkt_de", help="retailer channel ID (e.g. mediamarkt_de, otto_de, alza_cz)"
    )
    p.add_argument("--benchmark", default="geizhals_de", help="benchmark comparison engine channel ID")
    p.set_defaults(func=cmd_jbp)

    p = sub.add_parser("categories", help="list configured category profiles")
    _common(p)
    p.set_defaults(func=cmd_categories)

    args = parser.parse_args(argv)
    configure_logging(Path(args.data_dir), args.verbose)
    log.info("cli_start", cmd=args.cmd, config=args.config)
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    return args.func(args, cfg)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
