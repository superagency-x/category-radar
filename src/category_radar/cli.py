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
import logging
import socketserver
import sys
import webbrowser
from pathlib import Path

from .channels import available_adapters, get_adapter
from .config import ConfigError, load_config
from .export import build_bundle, write_csvs, write_executive_brief, write_site_data
from .fetch import BlockedError, Fetcher, FetchError, RobotsDisallowed
from .pipeline import run_pipeline
from .store import Store

ROOT = Path.cwd()
STATUS_ICON = {"ok": "✅", "empty": "⚠️ ", "blocked": "⛔", "disallowed": "🚫", "error": "❌", "missing": "…"}


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
    print(f"Dashboard data   → {path}  ({bundle['meta']['counts']['listings']} listings, "
          f"{bundle['meta']['counts']['reviews']} reviews, {bundle['meta']['counts']['snapshots']} snapshot(s))")
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
    report = run_pipeline(cfg, Path(args.data_dir), channels=channels, with_reviews=not args.no_reviews,
                          progress=print)
    print(f"\nRun {report.run_id}: {report.total_listings} listings, {report.reviews} reviews")
    for cid, s in report.channel_status.items():
        print(f"  {STATUS_ICON.get(s['status'], '?')} {cid:<14} {s['status']:<10} {s['listings']:>4} listings  "
              f"{s.get('pages', 0)} page(s) via {s.get('via')}")
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
    with Fetcher(tmp, mode=crawl.get("fetcher", "auto"), delay_seconds=float(crawl.get("delay_seconds", 4)),
                 respect_robots=bool(crawl.get("respect_robots_txt", True)), user_agent=crawl.get("user_agent")) as f:
        for cid, ch in cfg.channels.items():
            if args.channels and cid not in args.channels.split(","):
                continue
            try:
                res = f.fetch(ch.start_url, language=cfg.language_of(ch.market), cache_path=tmp / f"{cid}.html")
                items = get_adapter(ch.adapter).parse(res.html, channel=cid, market=ch.market,
                                                      currency=cfg.currency_of(ch.market))
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
    import subprocess

    bundle = Path(args.site_dir) / "data" / "radar.json"
    if not bundle.exists():
        print("Nothing to publish: run `radar run` first.")
        return 2

    def git(*a: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *a], capture_output=True, text=True)

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="radar", description="Category Radar: Central European category intelligence")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="scrape → store → analyse → export")
    _common(p)
    p.add_argument("--channels", help="comma-separated subset, e.g. geizhals_de,ceneo_pl")
    p.add_argument("--no-reviews", action="store_true", help="skip product-page review mining (faster)")
    p.add_argument("--no-export", action="store_true")
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

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    return args.func(args, cfg)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
