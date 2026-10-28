#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage the generated EPG, playlists and viewers in a static ``public/`` folder.

The folder is deployed to Vercel by GitHub Actions. It contains only generated
artifacts, plus a small landing page and a copy of ``vercel.json``.

Usage:
    python build_public.py
    python build_public.py --output public
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DEFAULT_PUBLIC_DIR = BASE_DIR / "public"
VERCEL_CONFIG = BASE_DIR / "vercel.json"

REQUIRED_FILES = [
    "all_platform_epg.xml",
    "all_free_channels.m3u",
    "all_platform_schedule.html",
]

OPTIONAL_FILES = [
    "sctv_free_channels.m3u",
    "sctv_schedule.html",
    "sctv_free_channels.json",
    "sctv_free_channels_report.md",
    "multi_platform_report.md",
    "stream_refresh_status.json",
    "tv360_free_channels.m3u",
    "fptplay_free_channels.m3u",
    "htv_free_channels.m3u",
    "vtvgo_free_channels.m3u",
]


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def number(value) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    if value in (None, ""):
        return "?"
    return html.escape(str(value))


def date_range_label(days: list[str]) -> str:
    if not days:
        return "—"
    try:
        first = datetime.strptime(days[0], "%Y-%m-%d")
        last = datetime.strptime(days[-1], "%Y-%m-%d")
    except ValueError:
        return " — ".join(days)
    if first.year == last.year and first.month == last.month:
        return f"{first.day}–{last.day}/{first.month:02d}/{first.year}"
    return (
        f"{first.day}/{first.month:02d}/{first.year} – "
        f"{last.day}/{last.month:02d}/{last.year}"
    )


def copy_if_exists(source: Path, destination_dir: Path) -> bool:
    if not source.is_file():
        return False
    shutil.copy2(source, destination_dir / source.name)
    return True


def platform_rows() -> list[tuple[str, str, str]]:
    data = read_json(OUTPUT_DIR / "all_platform_data.json")
    per_platform = (data.get("summary") or {}).get("per_platform") or {}
    rows = []
    for platform in ("tv360", "fptplay", "htv", "vtvgo"):
        filename = f"{platform}_free_channels.m3u"
        if not (OUTPUT_DIR / filename).is_file():
            continue
        info = per_platform.get(platform) or {}
        rows.append(
            (
                html.escape(str(info.get("label") or platform)),
                filename,
                number(info.get("included")),
            )
        )
    return rows


def build_index() -> str:
    data = read_json(OUTPUT_DIR / "all_platform_data.json")
    status = read_json(OUTPUT_DIR / "stream_refresh_status.json")
    sctv = read_json(OUTPUT_DIR / "sctv_free_channels.json")
    summary = data.get("summary") or {}
    per_platform = summary.get("per_platform") or {}
    days = (data.get("window") or {}).get("days") or []
    generated_at = status.get("refreshed_at") or data.get("generated_at") or "—"

    channels = number(summary.get("channels"))
    programmes = number(summary.get("programmes"))
    included = number(summary.get("included_streams"))
    combined = number(summary.get("combined_playlist_entries"))
    sctv_verified = number(sctv.get("verified_live"))

    platform_table = "\n".join(
        f'<tr><td><a href="{html.escape(filename)}">{label}</a></td>'
        f'<td class="num">{count}</td></tr>'
        for label, filename, count in platform_rows()
    ) or '<tr><td colspan="2" class="muted">No per-platform playlists found.</td></tr>'

    sctv_card = ""
    if (OUTPUT_DIR / "sctv_free_channels.m3u").is_file():
        sctv_card = f"""
      <a class="card" href="sctv_free_channels.m3u">
        <strong>SCTV free playlist</strong>
        <span>{sctv_verified} verified live channels</span>
      </a>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vietnamese TV — EPG and free playlists</title>
<style>
  :root {{
    color-scheme: dark;
    --bg:#0b1120; --panel:#111a2e; --panel2:#17223a; --line:#26344f;
    --text:#e7eefc; --muted:#8fa3c4; --accent:#38bdf8; --accent2:#22c55e;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:15px/1.55 "Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }}
  main {{ max-width:980px; margin:0 auto; padding:32px 22px 60px; }}
  h1 {{ margin:0 0 6px; font-size:30px; letter-spacing:-.02em; }}
  h2 {{ margin:30px 0 12px; font-size:18px; }}
  .sub {{ color:var(--muted); margin:0 0 24px; }}
  .stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; }}
  .stat {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }}
  .stat strong {{ display:block; font-size:24px; line-height:1.2; }}
  .stat span {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.06em; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; }}
  .card {{ display:flex; flex-direction:column; gap:4px; padding:16px; border:1px solid var(--line); border-radius:12px; background:var(--panel); color:var(--text); text-decoration:none; }}
  .card:hover {{ border-color:var(--accent); background:var(--panel2); }}
  .card strong {{ font-size:16px; }}
  .card span {{ color:var(--muted); font-size:13px; }}
  .card.primary {{ border-color:#0ea5e9; background:linear-gradient(135deg,#0c4a6e,#111a2e); }}
  table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line); border-radius:12px; overflow:hidden; }}
  th,td {{ padding:10px 14px; border-bottom:1px solid var(--line); text-align:left; }}
  th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.05em; }}
  tr:last-child td {{ border-bottom:0; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  a {{ color:var(--accent); }}
  .muted {{ color:var(--muted); }}
  .note {{ margin-top:22px; padding:14px 16px; border:1px solid #713f12; border-radius:12px; background:#1c1407; color:#fde68a; font-size:13px; }}
  footer {{ margin-top:30px; color:var(--muted); font-size:12px; }}
</style>
</head>
<body>
<main>
  <h1>Vietnamese TV — EPG and free playlists</h1>
  <p class="sub">
    Auto-generated by GitHub Actions · Updated <strong>{html.escape(str(generated_at))}</strong>
    · EPG window <strong>{html.escape(date_range_label(days))}</strong> (UTC+7)
  </p>

  <div class="stats">
    <div class="stat"><strong>{channels}</strong><span>channel listings</span></div>
    <div class="stat"><strong>{programmes}</strong><span>programme rows</span></div>
    <div class="stat"><strong>{included}</strong><span>verified streams</span></div>
    <div class="stat"><strong>{combined}</strong><span>combined entries</span></div>
  </div>

  <h2>Start here</h2>
  <div class="cards">
    <a class="card primary" href="all_free_channels.m3u">
      <strong>Combined playlist</strong>
      <span>{combined} verified free/public entries · M3U</span>
    </a>
    <a class="card" href="all_platform_epg.xml">
      <strong>XMLTV EPG</strong>
      <span>{channels} channels · {programmes} programmes</span>
    </a>
    <a class="card" href="all_platform_schedule.html">
      <strong>Web EPG viewer</strong>
      <span>Browse by platform, date and channel</span>
    </a>{sctv_card}
  </div>

  <h2>Per-platform playlists</h2>
  <table>
    <thead><tr><th>Playlist</th><th class="num">Entries</th></tr></thead>
    <tbody>{platform_table}</tbody>
  </table>

  <h2>SCTV</h2>
  <div class="cards">
    <a class="card" href="sctv_free_channels.m3u">
      <strong>SCTV free playlist</strong>
      <span>{sctv_verified} verified live channels</span>
    </a>
    <a class="card" href="sctv_schedule.html">
      <strong>SCTV schedule</strong>
      <span>Current SCTV EPG snapshot</span>
    </a>
    <a class="card" href="sctv_free_channels_report.md">
      <strong>SCTV report</strong>
      <span>Included channels, exclusions and expiry</span>
    </a>
  </div>

  <div class="note">
    Playlist URLs are signed by the providers and expire. GitHub Actions
    refreshes the streams every three hours and rebuilds the EPG daily. Only
    public, non-DRM streams from anonymous endpoints are included; there is no
    login, premium entitlement, paywall or DRM bypass.
  </div>

  <footer>
    <a href="multi_platform_report.md">Multi-platform report</a> ·
    <a href="stream_refresh_status.json">Refresh status</a> ·
    <a href="all_platform_schedule.html">EPG viewer</a>
    <br>Use for personal, lawful purposes and respect each provider's terms.
  </footer>
</main>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stage generated files for static hosting.")
    parser.add_argument(
        "--output",
        default=str(DEFAULT_PUBLIC_DIR),
        help="Destination folder (default: public/).",
    )
    args = parser.parse_args(argv)
    destination = Path(args.output).resolve()
    destination.mkdir(parents=True, exist_ok=True)

    missing = [name for name in REQUIRED_FILES if not (OUTPUT_DIR / name).is_file()]
    if missing:
        print(
            "Missing required generated files: " + ", ".join(missing),
            file=sys.stderr,
        )
        return 1

    copied = 0
    for name in REQUIRED_FILES + OPTIONAL_FILES:
        if copy_if_exists(OUTPUT_DIR / name, destination):
            copied += 1

    if VERCEL_CONFIG.is_file():
        shutil.copy2(VERCEL_CONFIG, destination / "vercel.json")
        copied += 1
    else:
        print(f"Warning: {VERCEL_CONFIG} not found; deploying without headers config.", file=sys.stderr)

    index_path = destination / "index.html"
    index_path.write_text(build_index(), encoding="utf-8", newline="\n")
    copied += 1

    print(f"Staged {copied} files in {destination}")
    for path in sorted(destination.iterdir()):
        if path.is_file():
            print(f"  {path.name:<35} {path.stat().st_size:>10,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
