#!/usr/bin/env python3
"""
Build an M3U playlist for the free/public SCTV Online channels.

- Reads output/sctv_channels.csv and keeps only channels with is_premium == "no".
- Requests each free channel's public player info from the same anonymous
  endpoint used by https://sctvonline.vn/detail/<slug>.
- Verifies every live HLS URL with ffprobe before adding it to the playlist.
- Writes output/sctv_free_channels.m3u, output/sctv_free_channels.json and
  output/sctv_free_channels_report.md.

No account login, premium entitlement, paywall or DRM bypass is involved. The
endpoint is the public one the website itself calls for anonymous visitors.
Signed CDN URLs expire after a few weeks, so re-run this script to refresh
them.

Usage:
    python build_free_m3u.py
    python refresh_multi_playlists.py --sctv-only   # same builder, unified entry point
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
CHANNELS_CSV = OUTPUT_DIR / "sctv_channels.csv"
M3U_PATH = OUTPUT_DIR / "sctv_free_channels.m3u"
JSON_PATH = OUTPUT_DIR / "sctv_free_channels.json"
REPORT_PATH = OUTPUT_DIR / "sctv_free_channels_report.md"

API = "https://apicdn.sctvonline.vn"
CONFIG_ID = "11c16ed3-c8ce-4afe-92d2-60154db68a48"
BUILD_SECRET = "370f7e0b3c3f6c7984c67cd8b4cf198295b37d20bcc7803ae700277a17a258c7"
ACCOUNT_ID = ""
TZ = timezone(timedelta(hours=7))
TZ_NAME = "Asia/Ho_Chi_Minh"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0 Safari/537.36"
)
API_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "vi",
    "Origin": "https://sctvonline.vn",
    "Referer": "https://sctvonline.vn/",
    "x-user-agent": "vn.sctvonline.web/2.16.180.102533 (Windows/10; ; desktop)",
    "x-trace-account-id": "anonymous",
}

FFPROBE = shutil.which("ffprobe")
PROBE_TIMEOUT = 45


def request_auth(path: str) -> str:
    """Reproduce the anonymous x-req-auth header used by the public web player."""
    timestamp = str(int(time.time()))
    message = f"{ACCOUNT_ID},{timestamp},{path},{BUILD_SECRET}"
    digest = hashlib.sha256(message.encode("utf-8")).hexdigest()
    return f"{CONFIG_ID}.{timestamp}.{digest}"


def fetch_json(url: str) -> dict:
    headers = dict(API_HEADERS)
    path = urllib.parse.urlsplit(url).path
    headers["x-req-auth"] = request_auth(path)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def view_endpoint(slug: str) -> str:
    select = {
        "Content": [
            "current_season",
            "id",
            "slug",
            "is_watchable",
            "progress",
            "youtube_video_id",
            "link_play",
            "play_info",
            "payment_infors",
            "is_favorite",
            "badges",
            "cwl_info",
            "warning_message",
            "price",
            "payment_type",
            "drm_session_info",
        ]
    }
    query = urllib.parse.urlencode(
        {"select": json.dumps(select, separators=(",", ":"))}
    )
    return f"{API}/tenants/sctv/contents/{slug}/view?{query}"


def expiry_from_url(url: str) -> datetime | None:
    match = re.search(r"/(\d{10})/anonymous/", url)
    if not match:
        return None
    return datetime.fromtimestamp(int(match.group(1)), tz=timezone.utc).astimezone(TZ)


def probe_stream(url: str) -> dict:
    """Return playback details for an HLS URL, using ffprobe when available."""
    result = {
        "ok": False,
        "method": "ffprobe" if FFPROBE else "http",
        "streams": [],
        "error": None,
    }
    if FFPROBE:
        command = [
            FFPROBE,
            "-v",
            "error",
            "-rw_timeout",
            "20000000",
            "-user_agent",
            "VLC/3.0.21 LibVLC/3.0.21",
            "-headers",
            "Referer: https://sctvonline.vn/\r\n",
            "-show_entries",
            "stream=index,codec_name,codec_type,width,height",
            "-show_entries",
            "format=format_name",
            "-of",
            "json",
            url,
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=PROBE_TIMEOUT
            )
        except subprocess.TimeoutExpired:
            result["error"] = "ffprobe timeout"
            return result
        if completed.returncode == 0 and completed.stdout.strip():
            try:
                payload = json.loads(completed.stdout)
            except json.JSONDecodeError:
                payload = {}
            streams = []
            for stream in payload.get("streams", []):
                streams.append(
                    {
                        "type": stream.get("codec_type"),
                        "codec": stream.get("codec_name"),
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                    }
                )
            result["streams"] = streams
            result["format"] = payload.get("format", {}).get("format_name")
            result["ok"] = bool(streams)
        if not result["ok"]:
            stderr = (completed.stderr or "").strip().splitlines()
            result["error"] = stderr[-1][:300] if stderr else "ffprobe failed"
        return result

    # Fallback: validate that the master playlist is reachable and well formed.
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "VLC/3.0.21 LibVLC/3.0.21",
            "Referer": "https://sctvonline.vn/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read(4096).decode("utf-8", "replace")
            result["ok"] = response.status == 200 and "#EXTM3U" in body
    except Exception as exc:  # noqa: BLE001 - report the failure, do not crash
        result["error"] = str(exc)[:300]
    return result


def resolution_label(streams: list[dict]) -> str:
    heights = sorted(
        {
            int(stream["height"])
            for stream in streams
            if stream.get("type") == "video" and stream.get("height")
        },
        reverse=True,
    )
    if not heights:
        return "-"
    return f"{heights[0]}p"


def m3u_attr(value: str) -> str:
    return str(value).replace('"', "'").strip()


def load_free_channels() -> list[dict]:
    with CHANNELS_CSV.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [row for row in rows if row.get("is_premium") == "no"]


def collect() -> dict:
    channels = load_free_channels()
    records = []
    print(f"Free channels: {len(channels)}")

    for index, channel in enumerate(channels, start=1):
        name = channel["channel_name"].strip()
        slug = channel["channel_slug"].strip()
        is_live_flag = channel.get("is_live", "").strip() == "yes"
        print(f"[{index:2}/{len(channels)}] {name} ({slug}) ...", end=" ", flush=True)

        record = {
            "name": name,
            "slug": slug,
            "logo": channel.get("logo_url", "").strip(),
            "categories": channel.get("categories", "").strip(),
            "is_live_flag": is_live_flag,
            "is_premium": channel.get("is_premium"),
            "detail_url": f"https://sctvonline.vn/detail/{slug}",
            "status": "unavailable",
            "status_label": "Unavailable",
            "stream_url": None,
            "expires_at": None,
            "expires_at_display": None,
            "probe": None,
        }

        try:
            payload = fetch_json(view_endpoint(slug))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            record["error"] = f"API error: {exc}"
            records.append(record)
            print("API error")
            continue

        play_info = payload.get("play_info") or {}
        stream_url = payload.get("link_play") or (play_info.get("data") or {}).get(
            "link_play"
        )
        play_error = play_info.get("error")

        if not stream_url or play_error not in (0, None):
            record["status"] = "vod_only" if not is_live_flag else "unavailable"
            record["status_label"] = (
                "Free VOD channel - no linear stream"
                if not is_live_flag
                else "No public play link"
            )
            record["error"] = play_info.get("detail") or "no play link"
            records.append(record)
            print(record["status_label"])
            continue

        if "/anonymous/live" not in stream_url:
            record["status"] = "vod_only" if not is_live_flag else "unavailable"
            record["status_label"] = "Not a linear live stream"
            record["stream_url"] = stream_url
            record["error"] = "play link is not an anonymous live HLS URL"
            records.append(record)
            print(record["status_label"])
            continue

        record["stream_url"] = stream_url
        expires = expiry_from_url(stream_url)
        if expires:
            record["expires_at"] = expires.isoformat()
            record["expires_at_display"] = expires.strftime("%Y-%m-%d %H:%M %Z")

        probe = probe_stream(stream_url)
        record["probe"] = probe
        if probe["ok"]:
            record["status"] = "verified"
            record["status_label"] = "Verified live"
            print(f"verified ({resolution_label(probe['streams'])})")
        else:
            record["status"] = "unplayable"
            record["status_label"] = "Play link returned but stream failed"
            record["error"] = probe.get("error")
            print(f"FAILED: {probe.get('error')}")

        records.append(record)

    verified = [record for record in records if record["status"] == "verified"]
    return {
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": TZ_NAME,
        "source": "https://sctvonline.vn",
        "free_channels_total": len(records),
        "verified_live": len(verified),
        "vod_only": sum(1 for record in records if record["status"] == "vod_only"),
        "unavailable": sum(
            1 for record in records if record["status"] in {"unavailable", "unplayable"}
        ),
        "channels": records,
    }


def write_m3u(records: list[dict]) -> None:
    lines = [
        "#EXTM3U",
        '# Playlist: SCTV Online - free/public channels only (is_premium="no")',
        f"# Generated: {datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}",
        "# Note: stream URLs are signed and expire; re-run refresh_multi_playlists.py --sctv-only to refresh.",
        "",
    ]
    for record in records:
        if record["status"] != "verified":
            continue
        lines.append(
            "#EXTINF:-1 "
            f'tvg-id="{m3u_attr(record["slug"])}" '
            f'tvg-name="{m3u_attr(record["name"])}" '
            f'tvg-logo="{m3u_attr(record["logo"])}" '
            'group-title="SCTV Online Free",'
            f'{record["name"]}'
        )
        # The CDN rejects requests without the site Referer and redirects them
        # to the SCTV homepage. VLC needs this per-item option to play the HLS
        # stream; other players that ignore #EXTVLCOPT still get the plain URL.
        lines.append("#EXTVLCOPT:http-referrer=https://sctvonline.vn/")
        lines.append(record["stream_url"])
    M3U_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_report(data: dict) -> None:
    verified = [record for record in data["channels"] if record["status"] == "verified"]
    others = [record for record in data["channels"] if record["status"] != "verified"]
    expiring = [
        (datetime.fromisoformat(record["expires_at"]), record["name"])
        for record in verified
        if record.get("expires_at")
    ]
    earliest = min(expiring) if expiring else None

    lines = [
        "# SCTV Online - Free Channels M3U",
        "",
        f"- Generated: **{data['generated_at']}** ({data['timezone']})",
        f"- Source: <{data['source']}>",
        f"- Free channels found: **{data['free_channels_total']}**",
        f"- Verified live streams in playlist: **{data['verified_live']}**",
        f"- Free VOD-only channels (not in playlist): **{data['vod_only']}**",
        f"- Unavailable / unplayable: **{data['unavailable']}**",
        f"- Playlist: `{M3U_PATH.name}`",
        *(
            [
                "- Earliest signed-URL expiry: "
                f"**{earliest[0].strftime('%Y-%m-%d %H:%M %Z')}** ({earliest[1]})"
            ]
            if earliest
            else []
        ),
        "",
        "Only channels with `is_premium=no` are included. No account login,",
        "premium entitlement, paywall or DRM bypass is used.",
        "",
        "## Playlist channels",
        "",
        "| # | Channel | Resolution | Signed URL expires | Stream |",
        "|---:|---|---|---|---|",
    ]
    for index, record in enumerate(verified, start=1):
        lines.append(
            f"| {index} | {record['name']} | {resolution_label(record['probe']['streams'])} "
            f"| {record['expires_at_display'] or '-'} | [HLS]({record['stream_url']}) |"
        )

    if others:
        lines += [
            "",
            "## Free channels excluded from the playlist",
            "",
            "| Channel | Slug | Reason |",
            "|---|---|---|",
        ]
        for record in others:
            reason = record["status_label"]
            if record.get("error"):
                reason += f" - {record['error']}"
            lines.append(f"| {record['name']} | `{record['slug']}` | {reason} |")

    lines += [
        "",
        "## Refresh",
        "",
        "The CDN URLs are signed and expire. Re-run:",
        "",
        "```powershell",
        "python refresh_multi_playlists.py --sctv-only",
        "```",
        "",
        "Or run the standalone builder:",
        "",
        "```powershell",
        "python build_free_m3u.py",
        "```",
        "",
        "The script:",
        "",
        "1. Reads the free-channel list from `output/sctv_channels.csv`.",
        "2. Calls the same anonymous player endpoint as the public detail page.",
        "3. Verifies each live HLS URL with `ffprobe` before writing it.",
        "4. Rewrites the M3U, JSON data and this report.",
        "5. Optionally run `python verify_vlc_playlist.py` to open every entry in",
        "   VLC and confirm the adaptive/HLS demux and audio/video decoding.",
        "",
        "Requirements: Python 3.10+ and `ffprobe` on PATH (optional; without it",
        "the script falls back to an HTTP playlist check).",
        "",
        "## Notes",
        "",
        "- The playlist uses standard HLS (`#EXTM3U` + `master.m3u8`).",
        "- Each entry carries `#EXTVLCOPT:http-referrer=https://sctvonline.vn/`.",
        "  The CDN rejects requests without the site Referer and redirects them to",
        "  the SCTV homepage. Tested with VLC 3.0.20 on Windows: opening the M3U",
        "  selects the adaptive/HLS demux and plays video and audio.",
        "- Players that ignore `#EXTVLCOPT` need the same Referer set manually.",
        "- Check the `Signed URL expires` column: some channels (currently Cà Mau)",
        "  receive shorter-lived URLs than the others.",
        "- `tvg-id` is the SCTV channel slug; `tvg-logo` comes from the channel list.",
        "- Some streams are geo-restricted to Vietnam by the provider.",
        "- The four 24/7 content channels (`THỂ THAO 24/7`, `Việt Nam 360`,",
        "  `PHIM VIỆT 24/7`, `VŨ TRỤ HÀI`) are free but VOD-only; they do not expose",
        "  a linear live stream, so they are not in the M3U.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    if not CHANNELS_CSV.exists():
        print(f"Missing input: {CHANNELS_CSV}", file=sys.stderr)
        return 1

    data = collect()
    OUTPUT_DIR.mkdir(exist_ok=True)
    write_m3u(data["channels"])
    JSON_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_report(data)

    print()
    print(f"Verified live: {data['verified_live']}")
    print(f"VOD-only:      {data['vod_only']}")
    print(f"Unavailable:   {data['unavailable']}")
    print(f"Playlist:      {M3U_PATH}")
    print(f"Report:        {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
