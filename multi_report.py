#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the multi-platform coverage report and interactive EPG viewer from
output/all_platform_data.json.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_PATH = OUTPUT_DIR / "all_platform_data.json"
REPORT_PATH = OUTPUT_DIR / "multi_platform_report.md"
HTML_PATH = OUTPUT_DIR / "all_platform_schedule.html"
COVERAGE_PATH = OUTPUT_DIR / "platform_coverage.csv"
UNIQUE_PATH = OUTPUT_DIR / "unique_channels.csv"
XMLTV_PATH = OUTPUT_DIR / "all_platform_epg.xml"
STATUS_PATH = OUTPUT_DIR / "stream_refresh_status.json"


def source_only_mode() -> bool:
    """Return True when streams were kept without a media probe."""
    env = os.environ.get("IPTV_SOURCE_ONLY", "").strip().lower()
    if env in {"1", "true", "yes", "on"}:
        return True
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return False
    return status.get("mode") == "source-only"

LABELS = {
    "tv360": "TV360",
    "fptplay": "FPT Play",
    "htv": "HTV",
    "vtvgo": "VTVgo",
    "mytv": "MyTV",
}
ORDER = ["tv360", "fptplay", "htv", "vtvgo", "mytv"]
DATES: list[str] = []


def date_range_label(days: list[str]) -> str:
    if not days:
        return "—"
    first = datetime.strptime(days[0], "%Y-%m-%d")
    last = datetime.strptime(days[-1], "%Y-%m-%d")
    if first.year == last.year and first.month == last.month:
        return f"{first.day}–{last.day}/{first.month:02d}/{first.year}"
    return (
        f"{first.day}/{first.month:02d}/{first.year} – "
        f"{last.day}/{last.month:02d}/{last.year}"
    )


def load() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def pct(part: int, total: int) -> str:
    return f"{part / total * 100:.1f}%" if total else "0.0%"


def build_coverage(payload: dict) -> list[dict]:
    rows = []
    for ch in payload["channels"]:
        rows.append(
            {
                "platform": ch["platform"],
                "platform_label": LABELS.get(ch["platform"], ch["platform"]),
                "platform_channel_id": ch["platform_channel_id"],
                "name": ch["name"],
                "category": ch.get("category", ""),
                "epg_days": ch.get("epg_days", 0),
                **{f"programmes_{d}": ch.get(f"programmes_{d}", 0) for d in DATES},
                "total_programmes": ch.get("total_programmes", 0),
                "stream_status": ch.get("stream_status", ""),
                "stream_height": ch.get("stream_height", ""),
            }
        )
    rows.sort(key=lambda r: (ORDER.index(r["platform"]) if r["platform"] in ORDER else 9, r["name"]))
    with COVERAGE_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def normalize_name(name: str) -> str:
    import re

    text = (name or "").upper()
    text = re.sub(r"\b(HD|FHD|UHD|4K|SD|VIP)\b", " ", text)
    text = re.sub(r"[^A-Z0-9À-Ỹ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def build_unique_channels(payload: dict) -> list[dict]:
    groups = defaultdict(list)
    for ch in payload["channels"]:
        key = normalize_name(ch["name"])
        if key:
            groups[key].append(ch)
    order = {"htv": 0, "tv360": 1, "vtvgo": 2, "fptplay": 3, "mytv": 4}
    rows = []
    for key, items in groups.items():
        items.sort(
            key=lambda ch: (
                0 if ch.get("stream_status") == "included" else 1,
                order.get(ch["platform"], 9),
                -int(ch.get("epg_days") or 0),
            )
        )
        best = items[0]
        rows.append(
            {
                "normalized_name": key,
                "display_name": best["name"],
                "platforms": ", ".join(sorted({LABELS.get(ch["platform"], ch["platform"]) for ch in items})),
                "best_platform": LABELS.get(best["platform"], best["platform"]),
                "best_channel_id": best["platform_channel_id"],
                "has_public_stream": "yes" if best.get("stream_status") == "included" else "no",
                "stream_height": best.get("stream_height", ""),
                "stream_expires_local": best.get("stream_expires_local", ""),
                "epg_days_max": max(int(ch.get("epg_days") or 0) for ch in items),
                "total_programmes_all_sources": sum(int(ch.get("total_programmes") or 0) for ch in items),
            }
        )
    rows.sort(key=lambda r: (r["has_public_stream"] != "yes", r["display_name"]))
    with UNIQUE_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)
    return rows


def build_report(payload: dict, coverage: list[dict]) -> str:
    source_only = source_only_mode()
    channels = payload["channels"]
    schedules = payload["schedules"]
    summary = payload["summary"]
    per = summary["per_platform"]
    by_platform = defaultdict(list)
    for ch in channels:
        by_platform[ch["platform"]].append(ch)

    day_counts = defaultdict(lambda: defaultdict(int))
    for item in schedules:
        day_counts[item["platform"]][item["date"]] += 1

    status_labels = {
        "included": (
            "Included in M3U (source-only)"
            if source_only
            else "Included in M3U (verified)"
        ),
        "excluded_login": "Excluded: login required",
        "excluded_paid": "Excluded: paid/premium",
        "excluded_drm": "Excluded: DRM",
        "excluded_premium": "Excluded: premium stream",
        "excluded_no_stream": "No public stream / probe failed",
        "excluded_unavailable": "Channel unavailable",
        "public_unverified": "Public but not playlist-verified",
    }
    status_counts = Counter(ch.get("stream_status") for ch in channels)
    included = [ch for ch in channels if ch.get("stream_status") == "included"]

    try:
        import multi_extract as me

        combined_rows = me.dedupe_combined(channels)
    except Exception:
        combined_rows = [
            ch for ch in channels if ch.get("stream_status") == "included"
        ]
    combined = len(combined_rows)
    combined_platforms = Counter(ch["platform"] for ch in combined_rows)

    expiries = []
    for ch in combined_rows:
        if ch.get("stream_expires_local"):
            try:
                expiries.append(datetime.fromisoformat(ch["stream_expires_local"]))
            except Exception:
                pass
    earliest = min(expiries).strftime("%Y-%m-%d %H:%M UTC+7") if expiries else "unknown"
    latest = max(expiries).strftime("%Y-%m-%d %H:%M UTC+7") if expiries else "unknown"

    lines = []
    lines.append("# Multi-platform Vietnamese TV - EPG and free/public M3U")
    lines.append("")
    lines.append(
        f"Snapshot of **{summary['channels']} platform-channel listings** and "
        f"**{summary['programmes']:,} programme rows** for "
        f"**{DATES[0]} through {DATES[-1]}** (`Asia/Ho_Chi_Minh`, UTC+7)."
    )
    lines.append("")
    if source_only:
        lines.append(
            f"The combined playlist contains **{combined} deduplicated free channels**; "
            f"**{summary['included_streams']} platform streams** were kept from the "
            f"providers' public playback APIs (source-only mode; no media probe from "
            f"the CI runner). Only public, non-DRM streams are included. No login, "
            f"subscription, paywall or DRM bypass is used."
        )
    else:
        lines.append(
            f"The combined playlist contains **{combined} deduplicated free channels**; "
            f"**{summary['included_streams']} platform streams** passed an ffprobe "
            f"audio/video check. Only public, non-DRM streams are included. No login, "
            f"subscription, paywall or DRM bypass is used."
        )
    lines.append("")
    lines.append(f"Generated: `{payload['generated_at']}`")
    lines.append("")

    lines.append("## Coverage by platform")
    lines.append("")
    day_labels = [f"EPG {d[8:10]}/{d[5:7]}" for d in DATES]
    stream_header = "Streams included" if source_only else "Streams verified"
    headers = ["Platform", "Listed", *day_labels, f"{len(DATES)}/{len(DATES)} days", stream_header, "M3U source"]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] + ["---:"] * (len(headers) - 1)) + "|")
    for platform in ORDER:
        rows = by_platform.get(platform, [])
        day_cells = " | ".join(f"{day_counts[platform][d]:,}" for d in DATES)
        full = sum(1 for ch in rows if int(ch.get("epg_days") or 0) == len(DATES))
        included_count = sum(1 for ch in rows if ch.get("stream_status") == "included")
        m3u_source = (
            "— (EPG only)"
            if platform == "mytv"
            else f"`{platform}_free_channels.m3u`"
        )
        lines.append(
            f"| {LABELS[platform]} | {len(rows)} | {day_cells} | "
            f"{full}/{len(rows)} | {included_count} | {m3u_source} |"
        )
    total_cells = " | ".join(
        f"**{sum(day_counts[platform][d] for platform in ORDER):,}**"
        for d in DATES
    )
    total_full = sum(1 for ch in channels if int(ch.get("epg_days") or 0) == len(DATES))
    lines.append(
        f"| **Total** | **{len(channels)}** | {total_cells} | "
        f"**{total_full}/{len(channels)}** | **{summary['included_streams']}** | `all_free_channels.m3u` |"
    )
    lines.append("")

    last_day = DATES[-1]
    lines.append(f"### Why {last_day[8:10]}/{last_day[5:7]} may be incomplete on some platforms")
    lines.append("")
    lines.append(
        "Provider publication of the third day is uneven. At capture time "
        f"(`{payload['generated_at']}`), these were the {last_day} row counts:"
    )
    lines.append("")
    lines.append("| Platform | Channels with data | Rows |")
    lines.append("|---|---:|---:|")
    for platform in ORDER:
        rows = by_platform.get(platform, [])
        with_data = sum(
            1 for ch in rows if int(ch.get(f"programmes_{last_day}") or 0) > 0
        )
        lines.append(
            f"| {LABELS[platform]} | {with_data}/{len(rows)} | "
            f"{day_counts[platform][last_day]:,} |"
        )
    lines.append("")
    lines.append(
        "Channels without a row for that date are left empty; no rows are copied "
        "between platforms. Re-running `multi_extract.py` later fills them when "
        "the provider publishes."
    )
    lines.append("")

    lines.append("## Playlists")
    lines.append("")
    lines.append("| File | Entries | Notes |")
    lines.append("|---|---:|---|")
    combined_note = (
        "Combined, one longest-lived public stream per normalized channel name"
        if source_only
        else "Combined, one longest-lived verified public stream per normalized channel name"
    )
    lines.append(
        f"| `output/all_free_channels.m3u` | {combined} | {combined_note} |"
    )
    for platform in ORDER:
        count = sum(1 for ch in by_platform.get(platform, []) if ch.get("stream_status") == "included")
        if platform == "mytv":
            lines.append("| — | 0 | MyTV is EPG-only; anonymous playback returns 401 |")
            continue
        if platform == "fptplay":
            note = "FPT Play only; tokens expire in about 2-3 minutes - open immediately"
        elif platform == "htv":
            note = "HTV only; HTV7/HTV4 JWTs expire in about 10 minutes"
        elif platform == "tv360":
            note = "TV360 only; tokens last about 6 hours"
        elif platform == "vtvgo":
            note = "VTVgo only; tokens last about 1-15 hours (local channels may expire at 01:00)"
        else:
            note = f"{LABELS[platform]} only"
        lines.append(f"| `output/{platform}_free_channels.m3u` | {count} | {note} |")
    lines.append("")
    lines.append(
        "Each entry carries `tvg-id`, `tvg-name`, `tvg-logo`, `group-title` and the "
        "platform Referer required by the CDN. Open the combined playlist in VLC "
        "via **Media -> Open File**."
    )
    lines.append("")
    combined_desc = ", ".join(
        f"{LABELS.get(platform, platform)} ({combined_platforms.get(platform, 0)})"
        for platform in ORDER
        if combined_platforms.get(platform)
    ) or "no entries"
    source_word = "public" if source_only else "verified public"
    lines.append(
        f"The combined playlist contains {combined_desc} in this snapshot. It "
        f"prefers one {source_word} stream per normalized channel name and the "
        "longest remaining token. Very short-lived FPT Play and HTV7/HTV4 tokens "
        "are kept only in their per-platform playlists; HTV7, HTV4 and HTV9 may "
        "still appear in the combined list through TV360's longer-lived tokens. "
        "The short-lived per-platform entries remain in "
        "`fptplay_free_channels.m3u` and `htv_free_channels.m3u`."
    )
    lines.append("")
    lines.append(
        f"Combined-token expiry range in this snapshot: earliest **{earliest}**, "
        f"latest **{latest}**. Run `python refresh_multi_playlists.py` every 2-3 "
        "hours (or let the GitHub Actions workflow do it) to renew TV360 and "
        "VTVgo URLs. If you watch VTVgo local channels late at night, refresh "
        "after 01:00 because their current token may expire then."
    )
    lines.append("")
    lines.append("### Short-lived tokens")
    lines.append("")
    lines.append(
        "Static/unsigned replacements were tested and rejected by the CDNs, so the "
        "tokens cannot be removed. Measured lifetimes:"
    )
    lines.append("")
    lines.append("| Platform | Token lifetime | Handling |")
    lines.append("|---|---|---|")
    lines.append("| TV360 | about 6 hours | Included in combined M3U; refreshed every 3 hours |")
    lines.append("| VTVgo | about 1-15 hours; local/VTV6 tokens can expire at 01:00 | Included in combined M3U; refresh after midnight if watching local channels |")
    lines.append("| HTV9 | `rkey` URL, no parsed expiry | Included per-platform; TV360 copy used in combined |")
    lines.append("| HTV7 / HTV4 | about 10 minutes (JWT `exp`) | Per-platform only; open immediately after refresh |")
    lines.append("| FPT Play | about 2-3 minutes (`sign` epoch) | Per-platform only; open immediately after refresh |")
    lines.append("| MyTV | n/a | No anonymous playback; EPG only |")
    lines.append("")

    lines.append("## Stream inclusions and exclusions")
    lines.append("")
    lines.append("| Status | Channels | Meaning |")
    lines.append("|---|---:|---|")
    for status, count in status_counts.most_common():
        lines.append(f"| `{status}` | {count} | {status_labels.get(status, status)} |")
    lines.append("")

    lines.append("### Included channels by platform")
    lines.append("")
    for platform in ORDER:
        rows = [ch for ch in by_platform.get(platform, []) if ch.get("stream_status") == "included"]
        if not rows:
            continue
        lines.append(f"**{LABELS[platform]}** ({len(rows)})")
        lines.append("")
        lines.append("| Channel | Resolution | Expiry (UTC+7) |")
        lines.append("|---|---:|---|")
        for ch in rows:
            height = f"{ch['stream_height']}p" if ch.get("stream_height") else "-"
            expiry = ch.get("stream_expires_local") or "-"
            lines.append(f"| {ch['name']} | {height} | {expiry} |")
        lines.append("")

    fpt_rows = by_platform.get("fptplay", [])
    htv_rows = by_platform.get("htv", [])
    vtvgo_rows = by_platform.get("vtvgo", [])
    mytv_rows = by_platform.get("mytv", [])
    fpt_included = sum(1 for ch in fpt_rows if ch.get("stream_status") == "included")
    htv_included = sum(1 for ch in htv_rows if ch.get("stream_status") == "included")
    vtvgo_included = sum(1 for ch in vtvgo_rows if ch.get("stream_status") == "included")
    vtvgo_public = sum(1 for ch in vtvgo_rows if not ch.get("need_login"))

    lines.append("## Platform notes")
    lines.append("")
    lines.append(
        "- **TV360** - channel catalogue from the public `tv360.vn/tv` page; 3-day "
        "EPG from `get-live-schedule`; free streams from `composite/get-link`. "
        "The CDN rotates between `fo-hlc`, `rr1-ateme`, `livestream` and VOD-style "
        "hosts; "
        + (
            "VOD hosts are excluded and the live URL is kept after expiry/host checks."
            if source_only
            else "each URL is probed and retried before inclusion."
        )
    )
    lines.append(
        f"- **FPT Play** - {len(fpt_rows)} EPG channels from the signed public "
        "`api.fptplay.net` endpoints. Although many channels have `is_vip=0`, only "
        f"{fpt_included} "
        + (
            "had a public HLS URL kept in this snapshot; "
            if source_only
            else "returned a public, playable HLS stream in this snapshot; "
        )
        + "the rest remain in the EPG dataset but not in the M3U. The playable FPT "
        "URLs expire in about 2-3 minutes, so they are kept in "
        "`fptplay_free_channels.m3u` but not in the combined playlist."
    )
    lines.append(
        f"- **HTV** - {len(htv_rows)} channels listed on `htv.vn/truc-tuyen.htm` "
        f"(HTV9, HTV7, HTV4); {htv_included} have "
        + ("public HLS. " if source_only else "verified public HLS. ")
        + "HTV9 uses "
        "the HTVm share endpoint with an HMAC timestamp; HTV7/HTV4 use the public "
        "HTVC iframe JWPlayer URL. HTV7/HTV4 JWTs expire in about 10 minutes, so "
        "the combined playlist prefers their TV360 equivalents."
    )
    vtvgo_source_note = (
        "The provider's alternate hosts are ranked and known-bad VLC hosts are skipped."
        if source_only
        else "Every advertised HLS source for a channel is probed and the first "
        "working one is kept, so a broken primary CDN can fall back to the "
        "provider's backup."
    )
    lines.append(
        f"- **VTVgo** - {len(vtvgo_rows)} unique catalogue channels, "
        f"{vtvgo_public} not requiring login and {vtvgo_included} with a "
        + ("public stream. " if source_only else "verified stream. ")
        + f"EPG follows the same {len(DATES)}-day window; the third day can "
        "be partial while the provider publishes it. Playback is requested only "
        "for anonymous channels and only `sourceModes[0].isVip=0` clear HLS is "
        f"kept. {vtvgo_source_note} The seven `VTVgo · ...` theme channels use "
        "`fast-channel-stg.vtvdigital.vn`, a staging host rather than the "
        "production CDN. Two full VLC sweeps opened 0/7 and 4/7 of them, so they "
        "are unreliable; they stay in the EPG dataset but are excluded from the "
        "playlists. The `vtvgolive-ott3`, `liveh34`, `liveh12` and `vtclc` hosts "
        "fail the TLS handshake in VLC and are blocked for playlists; provincial "
        "channels use the broadcasters' own public CDNs, Hà Tĩnh uses a verified "
        "public fallback, and Gia Lai has no alternative and is EPG-only."
    )
    lines.append(
        f"- **MyTV** - {len(mytv_rows)} EPG channels. Every tested anonymous "
        "playback request, including VTV1, ANTV, HTV9 and international channels, "
        "returned `401 nologin_play_channel`. MyTV is therefore **EPG-only**; no "
        "MyTV URL is placed in any playlist. The extractor renews the anonymous "
        "MyTV token when it collects EPG; the stream refresher leaves MyTV "
        "untouched."
    )
    lines.append("")

    lines.append("## Verification")
    lines.append("")
    if source_only:
        lines.append(
            "This run used source-only mode: the provider's public URL was kept "
            "after the free/non-DRM, expiry and VLC-host checks, without an "
            "`ffprobe` media probe from the CI runner. A full local `ffprobe` "
            "sweep and a VLC 3.0.24 spot check covered the channels that "
            "previously failed (Ninh Bình, Phú Thọ, Thanh Hóa, Đồng Tháp, Hà "
            "Tĩnh, Sơn La, Tuyên Quang, Cao Bằng, Lào Cai, Vĩnh Long 1, An Giang "
            "2 and Cà Mau)."
        )
    else:
        lines.append(
            "Streams are probed with `ffprobe` during extraction and refresh. The "
            "initial snapshot was also checked in VLC 3.0.21 with the dummy "
            "video/audio output; that manual sweep covered the TV360 and VTVgo "
            "entries in the combined playlist at the time."
        )
    lines.append(
        f"- Current combined playlist: **{combined}** entries ("
        + ", ".join(
            f"{LABELS.get(platform, platform)} {count}"
            for platform, count in combined_platforms.items()
        )
        + ")."
    )
    lines.append(
        "- VLC must be run with `--no-crashdump`; a leftover crash-reporter dialog "
        "from a force-killed process blocks later launches and produces false "
        "failures."
    )
    lines.append("")

    lines.append("## Data files")
    lines.append("")
    lines.append("| File | Contents |")
    lines.append("|---|---|")
    lines.append("| `output/all_platform_channels.csv` | One row per platform-channel with EPG counts, stream status, URL and expiry |")
    lines.append("| `output/all_platform_schedule_3days.csv` | Normalized programme rows for all platforms |")
    lines.append("| `output/all_platform_data.json` | Full structured channels + schedules |")
    lines.append("| `output/all_platform_epg.xml` | XMLTV EPG using the same tvg-id values as the M3Us |")
    lines.append("| `output/all_platform_schedule.html` | Interactive viewer with platform/date/search filters |")
    lines.append("| `output/platform_coverage.csv` | Coverage summary per platform-channel |")
    lines.append("| `output/unique_channels.csv` | Deduplicated channel list with source platforms and best public stream |")
    lines.append(f"| `output/{'{platform}'}_channels.csv` | Per-platform channel metadata |")
    lines.append(f"| `output/{'{platform}'}_schedule_3days.csv` | Per-platform schedule rows |")
    lines.append(f"| `output/{'{platform}'}_free_channels.json` | Per-platform stream/probe details |")
    sctv_note = (
        "SCTV free/public playlist, preserved in source-only mode"
        if source_only
        else "SCTV free/public playlist, refreshed by the same command"
    )
    lines.append(f"| `output/sctv_free_channels.m3u` | {sctv_note} |")
    lines.append("| `output/stream_refresh_status.json` | Last refresh time, counts and expiry range |")
    lines.append("")

    lines.append("## Refresh")
    lines.append("")
    lines.append("Unified local refresh (stream URLs + SCTV playlist):")
    lines.append("")
    lines.append("```powershell")
    lines.append("python refresh_multi_playlists.py")
    lines.append("```")
    lines.append("")
    refresh_verb = (
        "re-read from the provider APIs" if source_only else "re-probed"
    )
    lines.append(
        f"The EPG snapshot is kept; stream URLs are {refresh_verb} and the "
        "per-platform and combined M3Us, XMLTV, HTML viewer and report are "
        "rebuilt. Use `--source-only` on a CI runner outside Vietnam, "
        "`--skip-sctv` to refresh only the multi-platform outputs, or "
        "`--sctv-only` to rebuild only the SCTV playlist."
    )
    lines.append("")
    lines.append("Full EPG re-extraction for the current 3-day window:")
    lines.append("")
    lines.append("```powershell")
    lines.append("python multi_extract.py")
    lines.append("python multi_report.py")
    lines.append("```")
    lines.append("")
    lines.append(
        "GitHub Actions runs the unified refresh every three hours and a full "
        "EPG rebuild daily. Configure `VERCEL_TOKEN`, `VERCEL_ORG_ID` and "
        "`VERCEL_PROJECT_ID` secrets to deploy the staged `public/` folder to "
        "Vercel. See `README_MULTI_PLATFORM.md`."
    )
    lines.append("")
    lines.append(
        "Optional local fallback: register the included Windows Scheduled Task "
        "with `powershell -ExecutionPolicy Bypass -File .\\setup_refresh_task.ps1`."
    )
    lines.append("")

    lines.append("## Method and compliance")
    lines.append("")
    if source_only:
        lines.append(
            "The extractor calls the same public, anonymous endpoints used by the "
            "providers' web players. It does not log in, purchase entitlements, "
            "bypass geo/paywall checks, decrypt protected media or remove DRM. A "
            "channel is included only when the public endpoint returns a clear, "
            "non-DRM HLS URL; source-only mode skips the media probe because the "
            "CI runner is outside Vietnam."
        )
    else:
        lines.append(
            "The extractor calls the same public, anonymous endpoints used by the "
            "providers' web players. It does not log in, purchase entitlements, "
            "bypass geo/paywall checks, decrypt protected media or remove DRM. A "
            "channel is included only when the public endpoint returns a clear HLS "
            "URL and ffprobe successfully decodes a video stream."
        )
    lines.append("")
    lines.append(
        "EPG rows are kept as returned by each source. HTV and MyTV publish start "
        "times without explicit end times, so their end times are derived from the "
        "next programme (last programme +30 minutes) and flagged in the "
        "`end_estimated` column. No schedule rows are shared between platforms."
    )
    lines.append("")
    lines.append("Use for personal, lawful purposes and respect each provider's terms.")
    lines.append("")
    return "\n".join(lines)


def xml_text(value) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value or ""))
    return escape(text)


def xmltv_time(value: str) -> str:
    return datetime.fromisoformat(value).strftime("%Y%m%d%H%M%S %z")


def build_xmltv(payload: dict) -> int:
    by_channel = defaultdict(list)
    for item in payload["schedules"]:
        by_channel[(item["platform"], item["platform_channel_id"])].append(item)
    order = {name: idx for idx, name in enumerate(ORDER)}
    channels = sorted(
        payload["channels"],
        key=lambda ch: (order.get(ch["platform"], 9), ch["name"]),
    )
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<tv generator-info-name="multi-platform-vietnamese-epg">',
    ]
    for ch in channels:
        key = f"{ch['platform']}.{ch['platform_channel_id']}"
        lines.append(f"  <channel id={quoteattr(key)}>")
        lines.append(f"    <display-name>{xml_text(ch['name'])}</display-name>")
        if ch.get("logo"):
            lines.append(f"    <icon src={quoteattr(ch['logo'])}/>")
        lines.append("  </channel>")
    count = 0
    for ch in channels:
        key = f"{ch['platform']}.{ch['platform_channel_id']}"
        for item in by_channel.get((ch["platform"], ch["platform_channel_id"]), []):
            start = xmltv_time(item["start_local"])
            stop = xmltv_time(item["end_local"])
            lines.append(
                f'  <programme start="{start}" stop="{stop}" channel={quoteattr(key)}>'
            )
            lines.append(f'    <title lang="vi">{xml_text(item["title"])}</title>')
            if item.get("description"):
                lines.append(f'    <desc lang="vi">{xml_text(item["description"])}</desc>')
            lines.append("  </programme>")
            count += 1
    lines.append("</tv>")
    XMLTV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return count


def build_html(payload: dict) -> str:
    compact_channels = [
        {
            "p": ch["platform"],
            "id": ch["platform_channel_id"],
            "n": ch["name"],
            "c": ch.get("category", ""),
            "l": ch.get("logo", ""),
            "d": ch.get("epg_days", 0),
            "s": ch.get("stream_status", ""),
            "h": ch.get("stream_height", ""),
        }
        for ch in payload["channels"]
    ]
    compact_schedules = [
        [
            s["platform"],
            s["platform_channel_id"],
            s["date"],
            s["start_local"][11:16],
            s["end_local"][11:16],
            s["title"],
            s.get("description", ""),
            s.get("end_estimated", "no"),
        ]
        for s in payload["schedules"]
    ]
    data = {
        "generated_at": payload["generated_at"],
        "window": payload["window"],
        "channels": compact_channels,
        "schedules": compact_schedules,
        "labels": LABELS,
    }
    data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lịch phát sóng - TV360, FPT Play, HTV, VTVgo, MyTV</title>
<style>
  :root {{
    color-scheme: dark;
    --bg:#0b1120; --panel:#111a2e; --panel2:#17223a; --line:#26344f;
    --text:#e7eefc; --muted:#8fa3c4; --accent:#38bdf8; --accent2:#22c55e;
    --warn:#f59e0b; --danger:#ef4444;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font:14px/1.45 "Segoe UI",system-ui,sans-serif; background:var(--bg); color:var(--text); }}
  header {{ padding:18px 22px; border-bottom:1px solid var(--line); background:linear-gradient(120deg,#0f172a,#13213d); }}
  h1 {{ margin:0 0 4px; font-size:20px; }}
  .sub {{ color:var(--muted); font-size:13px; }}
  .controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:center; padding:12px 22px; border-bottom:1px solid var(--line); background:var(--panel); position:sticky; top:0; z-index:5; }}
  .seg {{ display:flex; border:1px solid var(--line); border-radius:8px; overflow:hidden; }}
  .seg button {{ border:0; background:transparent; color:var(--muted); padding:7px 12px; cursor:pointer; font-weight:600; }}
  .seg button.active {{ background:var(--accent); color:#062033; }}
  select,input {{ background:var(--panel2); color:var(--text); border:1px solid var(--line); border-radius:8px; padding:7px 10px; }}
  input {{ min-width:240px; }}
  .note {{ color:var(--warn); font-size:12px; }}
  .layout {{ display:grid; grid-template-columns:330px 1fr; min-height:calc(100vh - 125px); }}
  aside {{ border-right:1px solid var(--line); overflow:auto; max-height:calc(100vh - 125px); padding:8px; }}
  .ch {{ display:flex; gap:10px; align-items:center; padding:8px; border-radius:8px; cursor:pointer; border:1px solid transparent; }}
  .ch:hover {{ background:var(--panel2); }}
  .ch.active {{ background:#16324d; border-color:#2b6f96; }}
  .ch img {{ width:44px; height:28px; object-fit:contain; background:#fff; border-radius:4px; flex:none; }}
  .ch .nm {{ font-weight:600; font-size:13px; }}
  .ch .meta {{ color:var(--muted); font-size:11px; }}
  .badge {{ display:inline-block; padding:1px 6px; border-radius:999px; font-size:10px; margin-left:4px; }}
  .b3 {{ background:#14532d; color:#86efac; }} .b2 {{ background:#713f12; color:#fde68a; }} .b0 {{ background:#450a0a; color:#fca5a5; }}
  main {{ padding:18px 22px; overflow:auto; }}
  .title {{ display:flex; flex-wrap:wrap; gap:10px; align-items:baseline; margin-bottom:12px; }}
  .title h2 {{ margin:0; font-size:18px; }}
  .title .muted {{ color:var(--muted); }}
  table {{ width:100%; border-collapse:collapse; }}
  th,td {{ text-align:left; padding:9px 10px; border-bottom:1px solid var(--line); vertical-align:top; }}
  th {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.04em; position:sticky; top:0; background:var(--bg); }}
  td.time {{ white-space:nowrap; color:var(--accent); font-variant-numeric:tabular-nums; width:115px; }}
  td.desc {{ color:var(--muted); font-size:12px; }}
  .empty {{ color:var(--muted); padding:30px 0; }}
  .pill {{ background:var(--panel2); border:1px solid var(--line); border-radius:999px; padding:2px 8px; font-size:11px; color:var(--muted); }}
  @media (max-width:800px) {{ .layout {{ grid-template-columns:1fr; }} aside {{ max-height:260px; border-right:0; border-bottom:1px solid var(--line); }} }}
</style>
</head>
<body>
<header>
  <h1>Lịch phát sóng đa nền tảng</h1>
  <div class="sub">TV360 · FPT Play · HTV · VTVgo · MyTV &nbsp;|&nbsp; {date_range_label(DATES)} &nbsp;|&nbsp; Asia/Ho_Chi_Minh (UTC+7)</div>
</header>
<div class="controls">
  <div class="seg" id="dates"></div>
  <select id="platform"></select>
  <input id="search" placeholder="Tìm kênh hoặc chương trình...">
  <span class="pill" id="count"></span>
  <span class="note" id="daynote"></span>
</div>
<div class="layout">
  <aside id="channels"></aside>
  <main>
    <div class="title"><h2 id="chname">Chọn một kênh</h2><span class="muted" id="chmeta"></span></div>
    <table><thead><tr><th>Giờ</th><th>Chương trình</th><th>Mô tả</th></tr></thead><tbody id="programs"></tbody></table>
    <div class="empty" id="empty"></div>
  </main>
</div>
<script id="epg-data" type="application/json">{data_json}</script>
<script>
const DATA = JSON.parse(document.getElementById('epg-data').textContent);
const DATES = DATA.window.days;
const LABELS = DATA.labels;
const ORDER = ['tv360','fptplay','htv','vtvgo','mytv'];
const byKey = new Map();
for (const s of DATA.schedules) {{
  const k = s[0] + '|' + s[1] + '|' + s[2];
  if (!byKey.has(k)) byKey.set(k, []);
  byKey.get(k).push({{time:s[3], end:s[4], title:s[5], desc:s[6], est:s[7]}});
}}
let state = {{date: DATES[0], platform:'tv360', channel:null, search:''}};

const $ = id => document.getElementById(id);
function esc(v) {{ return String(v ?? '').replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c])); }}

function init() {{
  $('dates').innerHTML = DATES.map(d => `<button data-d="${{d}}" class="${{d===state.date?'active':''}}">${{d.slice(8,10)}}/${{d.slice(5,7)}}</button>`).join('');
  $('platform').innerHTML = ORDER.map(p => `<option value="${{p}}">${{LABELS[p]}}</option>`).join('');
  $('platform').value = state.platform;
  $('dates').addEventListener('click', e => {{
    const b = e.target.closest('button'); if (!b) return;
    state.date = b.dataset.d; document.querySelectorAll('#dates button').forEach(x=>x.classList.toggle('active',x===b)); renderChannels(); renderPrograms();
  }});
  $('platform').addEventListener('change', e => {{ state.platform=e.target.value; state.channel=null; renderChannels(); renderPrograms(); }});
  $('search').addEventListener('input', e => {{ state.search=e.target.value.toLowerCase(); renderChannels(); }});
  renderChannels();
}}

function channelList() {{
  const q = state.search;
  return DATA.channels.filter(c => c.p === state.platform && (!q || c.n.toLowerCase().includes(q) || (c.c||'').toLowerCase().includes(q)))
    .sort((a,b)=> a.n.localeCompare(b.n,'vi'));
}}

function renderChannels() {{
  const list = channelList();
  $('count').textContent = list.length + ' kênh';
  if (!state.channel || !list.some(c=>c.id===state.channel)) state.channel = list.length ? list[0].id : null;
  $('channels').innerHTML = list.map(c => {{
    const dc = c.d===3?'b3':c.d===2?'b2':'b0';
    return `<div class="ch ${{c.id===state.channel?'active':''}}" data-id="${{esc(c.id)}}">
      <img src="${{esc(c.l)}}" loading="lazy" onerror="this.style.visibility='hidden'">
      <div><div class="nm">${{esc(c.n)}}</div><div class="meta">${{c.h?c.h+'p · ':''}}${{esc(c.c)}} <span class="badge ${{dc}}">${{c.d}}/3 ngày</span></div></div>
    </div>`;
  }}).join('') || '<div class="empty">Không có kênh phù hợp.</div>';
  document.querySelectorAll('.ch').forEach(el => el.addEventListener('click', () => {{ state.channel=el.dataset.id; renderChannels(); renderPrograms(); }}));
  renderPrograms();
}}

function renderPrograms() {{
  const ch = DATA.channels.find(c => c.p===state.platform && c.id===state.channel);
  const rows = ch ? (byKey.get(ch.p+'|'+ch.id+'|'+state.date) || []) : [];
  $('chname').textContent = ch ? ch.n : 'Chọn một kênh';
  $('chmeta').textContent = ch ? `${{LABELS[ch.p]}} · ${{state.date}} · ${{rows.length}} chương trình` : '';
  $('programs').innerHTML = rows.map(r => `<tr><td class="time">${{esc(r.time)}}–${{esc(r.end)}}${{r.est==='yes'?' *':''}}</td><td>${{esc(r.title)}}</td><td class="desc">${{esc(r.desc)}}</td></tr>`).join('');
  $('empty').textContent = rows.length ? '' : 'Chưa có dữ liệu EPG cho kênh/ngày này. Nhà cung cấp có thể chưa công bố lịch.';
  $('daynote').textContent = !rows.length && state.date===DATES[DATES.length-1] ? 'Ngày cuối chưa được nền tảng này công bố đầy đủ lúc chụp dữ liệu' : '';
}}
init();
</script>
</body>
</html>
"""


def main() -> int:
    global DATES
    payload = load()
    DATES = list(payload.get("window", {}).get("days") or [])
    if not DATES:
        DATES = sorted({item["date"] for item in payload.get("schedules", [])})
    if not DATES:
        print("No EPG dates in all_platform_data.json", file=sys.stderr)
        return 1
    coverage = build_coverage(payload)
    unique = build_unique_channels(payload)
    xmltv_count = build_xmltv(payload)
    REPORT_PATH.write_text(build_report(payload, coverage), encoding="utf-8")
    HTML_PATH.write_text(build_html(payload), encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {HTML_PATH}")
    print(f"Wrote {COVERAGE_PATH}")
    print(f"Wrote {UNIQUE_PATH} ({len(unique)} normalized channels)")
    print(f"Wrote {XMLTV_PATH} ({xmltv_count} programmes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
