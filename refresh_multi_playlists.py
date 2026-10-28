#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Refresh the public stream URLs in the multi-platform playlists and rebuild the
SCTV free/public playlist in the same run.

By default this script:

1. re-probes TV360, FPT Play, HTV and VTVgo public streams;
2. rewrites the per-platform and combined M3Us, JSON/CSV metadata, XMLTV EPG,
   HTML viewer and report;
3. rebuilds ``output/sctv_free_channels.m3u`` from
   ``output/sctv_channels.csv``.

The EPG snapshot is kept; only live stream URLs and the derived outputs are
refreshed. Run this every few hours because TV360, FPT Play, HTV and VTVgo CDN
tokens expire (typically 4-24 hours).

Usage:
    python refresh_multi_playlists.py               # multi-platform + SCTV
    python refresh_multi_playlists.py --skip-sctv   # multi-platform only
    python refresh_multi_playlists.py --sctv-only   # SCTV playlist only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import multi_extract as me

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_PATH = OUTPUT_DIR / "all_platform_data.json"
STATUS_PATH = OUTPUT_DIR / "stream_refresh_status.json"
SCTV_M3U = OUTPUT_DIR / "sctv_free_channels.m3u"
SCTV_JSON = OUTPUT_DIR / "sctv_free_channels.json"


def keep_previous(row: dict, referer: str, reason: str) -> bool:
    """Keep a still-valid previous URL when a refresh probe fails transiently."""
    old_url = row.get("stream_url") or ""
    if row.get("stream_status") != "included" or not old_url:
        return False
    host = (urlsplit(old_url).hostname or "").lower()
    if "stg" in host or host in me.VTVGO_VLC_BLOCKED_HOSTS:
        return False
    old_expiry = row.get("stream_expires_local") or ""
    if old_expiry:
        try:
            if datetime.fromisoformat(old_expiry) <= datetime.now(me.TZ) + timedelta(minutes=10):
                return False
        except ValueError:
            pass
    if not me.probe_stream(old_url, referer).get("ok"):
        return False
    row["notes"] = f"refresh probe failed; kept previous verified URL ({reason[:120]})"
    return True


def apply_result(row: dict, result, referer: str) -> None:
    result = result if isinstance(result, dict) else {"status": "excluded_no_stream", "error": str(result)}
    if result.get("status") == "included":
        row["stream_status"] = "included"
        row["stream_url"] = result.get("url") or ""
        row["stream_format"] = (result.get("probe") or {}).get("format") or ""
        row["stream_height"] = (result.get("probe") or {}).get("height") or ""
        row["stream_expires_local"] = result.get("expires") or ""
        row["notes"] = result.get("error") or ""
        return
    reason = result.get("error") or "probe failed"
    if keep_previous(row, referer, reason):
        return
    row["stream_status"] = result.get("status") or "excluded_no_stream"
    row["stream_url"] = ""
    row["stream_format"] = ""
    row["stream_height"] = ""
    row["stream_expires_local"] = ""
    row["notes"] = reason


def refresh_sctv() -> dict:
    """Run build_free_m3u.py and return a status dictionary.

    Failures are reported to the caller instead of raising, so a transient SCTV
    API problem never discards the already refreshed multi-platform outputs.
    """
    started = datetime.now(me.TZ)
    result = {
        "builder": "build_free_m3u.py",
        "status": "failed",
        "started_at": me.iso_local(started),
        "playlist": str(SCTV_M3U),
    }
    try:
        import build_free_m3u as builder

        code = builder.main()
    except SystemExit as exc:  # defensive: builder.main() normally returns an int
        code = int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 - keep the multi-platform outputs usable
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["duration_seconds"] = round((datetime.now(me.TZ) - started).total_seconds(), 1)
        print(f"[SCTV] refresh failed: {result['error']}", file=sys.stderr)
        return result

    result["duration_seconds"] = round((datetime.now(me.TZ) - started).total_seconds(), 1)
    if code != 0:
        result["exit_code"] = code
        result["error"] = f"build_free_m3u.py exited with {code}"
        print(f"[SCTV] refresh failed: {result['error']}", file=sys.stderr)
        return result

    result["status"] = "ok"
    try:
        data = json.loads(SCTV_JSON.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    for key in ("generated_at", "free_channels_total", "verified_live", "vod_only", "unavailable"):
        if key in data:
            result[key] = data[key]
    print(
        "[SCTV] "
        f"{result.get('verified_live', '?')} verified live / "
        f"{result.get('free_channels_total', '?')} free channels"
    )
    return result


def update_sctv_status(result: dict) -> None:
    """Record an SCTV-only run in the existing refresh status file."""
    if not STATUS_PATH.exists():
        return
    try:
        status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    status["sctv_free_playlist"] = result
    playlists = status.setdefault("playlists", [])
    if result.get("status") == "ok" and str(SCTV_M3U) not in playlists:
        playlists.append(str(SCTV_M3U))
    me.write_json(STATUS_PATH, status)


def refresh(skip_sctv: bool = False) -> int:
    if not DATA_PATH.exists():
        print(f"Missing {DATA_PATH}; run multi_extract.py first.", file=sys.stderr)
        return 1

    started = datetime.now(me.TZ)
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    window_days = (payload.get("window") or {}).get("days") or []
    if window_days:
        me.set_dates(window_days)
    else:
        print(
            "Warning: all_platform_data.json has no window.days; "
            "using the default date window for CSV columns.",
            file=sys.stderr,
        )
    channels = payload.get("channels") or []
    schedules = payload.get("schedules") or []
    by_platform = {}
    for row in channels:
        by_platform.setdefault(row["platform"], []).append(row)

    print(f"Refresh started {me.iso_local(started)}")
    print(f"Loaded {len(channels)} channels / {len(schedules)} programmes")

    # TV360 -------------------------------------------------------------
    print("[TV360] refreshing free streams")
    tv360_candidates = [
        row
        for row in by_platform.get("tv360", [])
        if row.get("is_free") and not row.get("is_drm") and not row.get("need_login")
    ]
    tv360_results = me.parallel(
        tv360_candidates,
        lambda row: me.tv360_stream(
            {
                "id": int(row["platform_channel_id"]),
                "name": row["name"],
                "is_free": row["is_free"],
                "is_drm": row["is_drm"],
                "need_login": row["need_login"],
            }
        ),
        workers=4,
    )
    for row, result in zip(tv360_candidates, tv360_results):
        apply_result(row, result, "https://tv360.vn/")

    # FPT Play ----------------------------------------------------------
    print("[FPT Play] refreshing free streams")
    fpt_candidates = by_platform.get("fptplay", [])
    fpt_results = me.parallel(
        fpt_candidates,
        lambda row: me.fpt_stream(
            {
                "id": row["platform_channel_id"],
                "name": row["name"],
                "verimatrix": row.get("is_drm"),
            }
        ),
        workers=5,
    )
    for row, result in zip(fpt_candidates, fpt_results):
        apply_result(row, result, "https://fptplay.vn/")
        if isinstance(result, dict):
            row["auto_profile"] = result.get("auto_profile") or row.get("auto_profile") or ""
            row["is_vip"] = result.get("is_vip")

    # HTV ---------------------------------------------------------------
    print("[HTV] refreshing 3 streams")
    for row in by_platform.get("htv", []):
        cid = row["platform_channel_id"]
        if cid == "2223":
            result = me.htv9_stream()
            referer = "https://htvm.htv.com.vn/"
        else:
            embed = "https://htvc.com.vn/iframe?content_id=256" if cid == "2221" else "https://htvc.com.vn/iframe?content_id=2528"
            result = me.htvc_stream(embed)
            referer = "https://htv.vn/"
        url = result.get("url") or ""
        probe = me.probe_stream(url, referer) if url else None
        ok = bool(url and probe and probe.get("ok"))
        expires = me.stream_expiry(url) if url else None
        apply_result(
            row,
            {
                "status": "included" if ok else "excluded_no_stream",
                "url": url if ok else "",
                "probe": probe,
                "expires": me.iso_local(expires) if expires else "",
                "error": "" if ok else (result.get("_error") or (probe or {}).get("error") or ""),
            },
            referer,
        )

    # VTVgo -------------------------------------------------------------
    print("[VTVgo] refreshing free streams")
    vtvgo_candidates = [
        row for row in by_platform.get("vtvgo", []) if not row.get("need_login")
    ]
    vtvgo_results = me.parallel(
        vtvgo_candidates,
        lambda row: me.vtvgo_playback({"id": row["platform_channel_id"], "name": row["name"]}),
        workers=5,
    )
    for row, result in zip(vtvgo_candidates, vtvgo_results):
        apply_result(row, result, "https://vtvgo.vn/")

    # MyTV is EPG-only; leave its exclusion reason intact. --------------
    print("[MyTV] EPG-only; no public stream refresh")

    # Rebuild outputs ---------------------------------------------------
    me.GENERATED_AT = started
    for platform, rows in by_platform.items():
        platform_schedules = [s for s in schedules if s.get("platform") == platform]
        me.write_platform_outputs(platform, rows, platform_schedules)

    combined = me.dedupe_combined(channels)
    m3u = me.build_m3u(
        combined, "Combined free/public Vietnamese TV", notes=me.COMBINED_NOTES
    )
    (OUTPUT_DIR / "all_free_channels.m3u").write_text(m3u, encoding="utf-8")
    me.write_csv(OUTPUT_DIR / "all_platform_channels.csv", channels, me.TV360_COLUMNS)

    per_platform = {}
    for platform, rows in by_platform.items():
        per_platform[platform] = {
            "label": me.PLATFORM_LABELS[platform],
            "channels": len(rows),
            "programmes": sum(1 for s in schedules if s.get("platform") == platform),
            "included": sum(1 for r in rows if r.get("stream_status") == "included"),
        }
    payload["generated_at"] = me.iso_local(started)
    payload["summary"] = {
        "channels": len(channels),
        "programmes": len(schedules),
        "included_streams": sum(1 for r in channels if r.get("stream_status") == "included"),
        "combined_playlist_entries": len(combined),
        "per_platform": per_platform,
    }
    me.write_json(DATA_PATH, payload)

    # Status report -----------------------------------------------------
    expiries = []
    for row in channels:
        value = row.get("stream_expires_local")
        if value:
            try:
                expiries.append(datetime.fromisoformat(value))
            except Exception:
                pass
    combined_expiries = []
    for row in combined:
        value = row.get("stream_expires_local")
        if value:
            try:
                combined_expiries.append(datetime.fromisoformat(value))
            except Exception:
                pass
    status = {
        "refreshed_at": me.iso_local(started),
        "duration_seconds": round((datetime.now(me.TZ) - started).total_seconds(), 1),
        "included_streams": payload["summary"]["included_streams"],
        "combined_playlist_entries": len(combined),
        "per_platform": per_platform,
        "earliest_stream_expiry": me.iso_local(min(expiries)) if expiries else None,
        "latest_stream_expiry": me.iso_local(max(expiries)) if expiries else None,
        "combined_earliest_stream_expiry": me.iso_local(min(combined_expiries)) if combined_expiries else None,
        "combined_latest_stream_expiry": me.iso_local(max(combined_expiries)) if combined_expiries else None,
        "expiry_note": (
            "earliest_stream_expiry includes short-lived FPT Play/HTV per-platform "
            "snapshots; use the combined_* fields for the combined M3U."
        ),
        "playlists": [
            str(OUTPUT_DIR / "all_free_channels.m3u"),
            *[str(OUTPUT_DIR / f"{p}_free_channels.m3u") for p in by_platform if (OUTPUT_DIR / f"{p}_free_channels.m3u").exists()],
        ],
    }

    if skip_sctv:
        status["sctv_free_playlist"] = {
            "status": "skipped",
            "builder": "build_free_m3u.py",
        }
    else:
        print("[SCTV] refreshing free/public playlist")
        sctv_result = refresh_sctv()
        status["sctv_free_playlist"] = sctv_result
        if sctv_result.get("status") == "ok":
            status["playlists"].append(str(SCTV_M3U))
        else:
            print(
                "Warning: SCTV playlist was not updated; "
                "the multi-platform outputs are intact.",
                file=sys.stderr,
            )

    me.write_json(STATUS_PATH, status)

    print()
    print(f"Included streams: {status['included_streams']}")
    print(f"Combined playlist entries: {len(combined)}")
    print(f"Earliest expiry (all): {status['earliest_stream_expiry']}")
    print(f"Earliest expiry (combined): {status['combined_earliest_stream_expiry']}")
    print(f"SCTV playlist: {status['sctv_free_playlist']['status']}")
    print(f"Status: {STATUS_PATH}")

    report_script = BASE_DIR / "multi_report.py"
    if report_script.exists():
        print("Regenerating report, XMLTV and HTML viewer...")
        completed = subprocess.run([sys.executable, str(report_script)], check=False)
        if completed.returncode != 0:
            print("multi_report.py failed", file=sys.stderr)
            return completed.returncode or 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh multi-platform stream URLs and the SCTV free/public playlist."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--skip-sctv",
        action="store_true",
        help="Refresh only the multi-platform outputs; leave the SCTV playlist unchanged.",
    )
    group.add_argument(
        "--sctv-only",
        action="store_true",
        help="Rebuild only the SCTV free/public playlist.",
    )
    args = parser.parse_args(argv)

    if args.sctv_only:
        result = refresh_sctv()
        update_sctv_status(result)
        if result.get("status") == "ok":
            print(f"SCTV playlist: {SCTV_M3U}")
            return 0
        return 1

    return refresh(skip_sctv=args.skip_sctv)


if __name__ == "__main__":
    sys.exit(main())
