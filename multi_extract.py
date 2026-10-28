#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-platform Vietnamese TV EPG + free/public M3U builder.

Platforms:
  * TV360       https://tv360.vn/tv
  * FPT Play    https://fptplay.vn/xem-truyen-hinh/
  * HTV         https://htv.vn/truc-tuyen.htm
  * VTVgo       https://vtvgo.vn/
  * MyTV        https://mytv.com.vn/truyen-hinh

Window: 3 days starting today in Asia/Ho_Chi_Minh (UTC+7).  Override with
`--start-date YYYY-MM-DD --days N`.

Only public/anonymous endpoints are used.  A channel is put in an M3U only
when its public player returns a clear (non-DRM) HLS URL and ffprobe can read
audio/video from it.  No login, subscription, paywall or DRM bypass is used.

Usage:
    python multi_extract.py       # full extract + build
    python refresh_multi_playlists.py  # refresh only stream URLs and M3Us
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data" / "multi"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

TZ = timezone(timedelta(hours=7))
TZ_NAME = "Asia/Ho_Chi_Minh"
GENERATED_AT = datetime.now(TZ)


def window_dates(start: datetime | None = None, days: int = 3) -> list[str]:
    """Return the EPG window as ISO dates, starting today in UTC+7 by default."""
    first = (start or datetime.now(TZ)).date()
    return [(first + timedelta(days=offset)).isoformat() for offset in range(days)]


DATES = window_dates()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
)
VLC_UA = "VLC/3.0.21 LibVLC/3.0.21"

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

FFPROBE = shutil.which("ffprobe")
PROBE_TIMEOUT = 18

# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    print(msg, flush=True)


def http(
    url: str,
    headers: dict | None = None,
    data: bytes | None = None,
    method: str | None = None,
    timeout: int = 45,
    retries: int = 3,
) -> tuple[int | None, bytes]:
    last_status: int | None = None
    last_body = b""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=data, headers=headers or {}, method=method
            )
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            try:
                last_body = exc.read()
            except Exception:
                last_body = b""
            if exc.code in (400, 401, 403, 404, 410):
                break
        except Exception as exc:  # noqa: BLE001
            last_status = None
            last_body = str(exc).encode("utf-8", "replace")
        time.sleep(0.4 * (attempt + 1))
    return last_status, last_body


def http_json(url: str, headers: dict | None = None, **kwargs):
    status, body = http(url, headers=headers, **kwargs)
    try:
        return status, json.loads(body.decode("utf-8", "replace"))
    except Exception:
        return status, None


def parallel(items: list, fn, workers: int = 6) -> list:
    out: list = [None] * len(items)
    if not items:
        return out
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fn, item): idx for idx, item in enumerate(items)}
        done = 0
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                out[idx] = fut.result()
            except Exception as exc:  # noqa: BLE001
                out[idx] = {"_error": str(exc)}
            done += 1
            if done % 50 == 0:
                log(f"    ... {done}/{len(items)}")
    return out


def iso_local(dt: datetime) -> str:
    return dt.astimezone(TZ).replace(microsecond=0).isoformat()


def parse_ts(value, unit: str = "s") -> datetime | None:
    try:
        n = int(str(value).strip())
    except Exception:
        return None
    if n <= 0:
        return None
    if unit == "ms" or n > 10_000_000_000:
        n /= 1000.0
    return datetime.fromtimestamp(n, tz=TZ)


def parse_local(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(TZ)
        except Exception:
            return None
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=TZ)
    return dt.astimezone(TZ)


def clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def abs_url(value: str | None, base: str) -> str:
    if not value:
        return ""
    value = str(value).strip()
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http"):
        return value
    return urllib.parse.urljoin(base, value)


def jwt_exp(url: str) -> datetime | None:
    for token in re.findall(r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", url):
        try:
            payload = token.split(".")[1]
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
            exp = data.get("exp")
            if exp:
                return datetime.fromtimestamp(int(exp), tz=TZ)
        except Exception:
            pass
    return None


def stream_expiry(url: str) -> datetime | None:
    if not url:
        return None
    exp = jwt_exp(url)
    if exp:
        return exp
    m = re.search(r"[?&]sign=(\d{10})-", url)
    if m:
        return datetime.fromtimestamp(int(m.group(1)), tz=TZ)
    m = re.search(r"[?&]expireAt=(\d{10})", url)
    if m:
        return datetime.fromtimestamp(int(m.group(1)), tz=TZ)
    m = re.search(r"/(\d{10})/", url)
    if m:
        n = int(m.group(1))
        if 1_700_000_000 < n < 2_000_000_000:
            return datetime.fromtimestamp(n, tz=TZ)
    return None


def probe_stream(url: str, referer: str) -> dict:
    result = {
        "ok": False,
        "format": None,
        "height": None,
        "streams": [],
        "error": None,
        "method": "ffprobe" if FFPROBE else "http",
    }
    if not url:
        result["error"] = "empty URL"
        return result
    if FFPROBE:
        cmd = [
            FFPROBE,
            "-v",
            "error",
            "-rw_timeout",
            "15000000",
            "-user_agent",
            VLC_UA,
            "-headers",
            f"Referer: {referer}\r\n",
            "-show_entries",
            "stream=codec_type,codec_name,width,height",
            "-show_entries",
            "format=format_name",
            "-of",
            "json",
            url,
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
        except subprocess.TimeoutExpired:
            result["error"] = "ffprobe timeout"
            return result
        except Exception as exc:  # noqa: BLE001
            result["error"] = str(exc)[:300]
            return result
        if proc.returncode == 0 and proc.stdout.strip():
            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                payload = {}
            streams = payload.get("streams", [])
            result["streams"] = [
                {
                    "type": s.get("codec_type"),
                    "codec": s.get("codec_name"),
                    "width": s.get("width"),
                    "height": s.get("height"),
                }
                for s in streams
            ]
            result["format"] = (payload.get("format") or {}).get("format_name")
            heights = [
                int(s["height"])
                for s in result["streams"]
                if s.get("height") and str(s.get("height")).isdigit()
            ]
            result["height"] = max(heights) if heights else None
            result["ok"] = any(s.get("type") == "video" for s in result["streams"])
        if not result["ok"]:
            stderr = (proc.stderr or "").strip().splitlines()
            result["error"] = (stderr[-1] if stderr else "ffprobe failed")[:300]
        return result

    # Fallback without ffprobe: fetch the master playlist.
    status, body = http(
        url,
        headers={"User-Agent": VLC_UA, "Referer": referer},
        timeout=25,
        retries=2,
    )
    text = body.decode("utf-8", "replace")
    result["ok"] = status == 200 and "#EXTM3U" in text
    result["format"] = "hls" if result["ok"] else None
    result["error"] = None if result["ok"] else f"HTTP {status}"
    return result


def write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# TV360
# ---------------------------------------------------------------------------

TV360_SECRET = "eNdtOeNDeNcRyPteDsCREt#2022"
TV360_KEY = bytes.fromhex(hashlib.sha1(TV360_SECRET.encode()).hexdigest()[:32])


def tv360_encrypt(text: str) -> str:
    data = text.encode("utf-8")
    pad = 16 - len(data) % 16
    data += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(TV360_KEY), modes.ECB()).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode()


def tv360_decrypt(b64: str) -> str:
    raw = base64.b64decode(b64)
    dec = Cipher(algorithms.AES(TV360_KEY), modes.ECB()).decryptor()
    out = dec.update(raw) + dec.finalize()
    return out[:-out[-1]].decode("utf-8")


def tv360_headers(referer: str = "https://tv360.vn/tv") -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Referer": referer,
        "Origin": "https://tv360.vn",
        "Accept": "application/json, text/plain, */*",
        "tz": TZ_NAME,
    }


def tv360_catalog() -> list[dict]:
    cache = DATA_DIR / "tv360_catalog.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    status, html = http(
        "https://tv360.vn/tv/htv7-hd?ch=193&c=0",
        headers={**tv360_headers(), "Accept": "text/html,application/xhtml+xml"},
        retries=3,
    )
    text = html.decode("utf-8", "replace")
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        text,
        re.S,
    )
    if not match:
        raise RuntimeError("TV360 __NEXT_DATA__ not found")
    data = json.loads(match.group(1))
    categories = data["props"]["pageProps"].get("detailCat") or []
    seen: dict[int, dict] = {}
    for cat in categories:
        for channel in cat.get("content") or []:
            cid = int(channel["id"])
            if cid not in seen:
                seen[cid] = {
                    "id": cid,
                    "name": clean_text(channel.get("name")),
                    "slug": channel.get("slug") or "",
                    "category": clean_text(cat.get("name")),
                    "categories": [clean_text(cat.get("name"))],
                    "logo": abs_url(channel.get("coverImage"), "https://tv360.vn/"),
                    "description": clean_text(channel.get("description")),
                    "is_free": 1 if channel.get("isFree") == 1 else 0,
                    "is_drm": int(channel.get("isDrm") or 0),
                    "need_login": 1 if channel.get("needLogin") == 1 else 0,
                    "price": channel.get("price") or 0,
                    "partner": channel.get("partnerType") or "",
                    "source_page": abs_url(channel.get("link"), "https://tv360.vn/"),
                }
            else:
                if clean_text(cat.get("name")) not in seen[cid]["categories"]:
                    seen[cid]["categories"].append(clean_text(cat.get("name")))
    channels = sorted(seen.values(), key=lambda x: x["id"])
    write_json(cache, channels)
    return channels


def tv360_schedule(channel_id: int, date: str) -> dict:
    url = (
        "https://tv360.vn/public/v1/live/get-live-schedule?"
        + urllib.parse.urlencode({"id": channel_id, "datetime": date})
    )
    status, payload = http_json(url, headers=tv360_headers())
    if status != 200 or not isinstance(payload, dict):
        return {"_status": status, "schedules": []}
    if payload.get("errorCode") != 200:
        return {"_status": status, "error": payload.get("message"), "schedules": []}
    return payload.get("data") or {"schedules": []}


def tv360_get_link(channel_id: int) -> dict:
    params = {
        "id": str(channel_id),
        "type": "LIVE",
        "mod": "LIVE",
        "t": str(int(time.time())),
        "secured": "true",
        "llc": "1",
    }
    sq = tv360_encrypt(urllib.parse.urlencode(params))
    url = "https://tv360.vn/public/v1/composite/get-link?" + urllib.parse.urlencode(
        {"sq": sq, "secured": "true"}
    )
    status, payload = http_json(url, headers=tv360_headers("https://tv360.vn/tv"))
    if status != 200 or not isinstance(payload, dict):
        return {"_error": f"HTTP {status}"}
    if payload.get("errorCode") != 200:
        return {"_error": payload.get("message") or f"errorCode {payload.get('errorCode')}"}
    data = payload.get("data")
    try:
        if isinstance(data, str):
            return json.loads(tv360_decrypt(data))
        if isinstance(data, dict):
            return data
    except Exception as exc:  # noqa: BLE001
        return {"_error": f"decrypt: {exc}"}
    return {"_error": "no data"}


def tv360_stream(channel: dict) -> dict:
    cid = channel["id"]
    last_error = ""
    for attempt in range(3):
        info = tv360_get_link(cid)
        url = str(info.get("urlStreaming") or "")
        if not url:
            last_error = str(info.get("_error") or info.get("message") or "no stream URL")
            time.sleep(0.25)
            continue
        if int(info.get("isDrm") or 0) != 0:
            return {"status": "excluded_drm", "error": "isDrm != 0", "url": "", "probe": None}
        probe = probe_stream(url, "https://tv360.vn/")
        if probe["ok"]:
            return {
                "status": "included",
                "error": None,
                "url": url,
                "probe": probe,
                "expires": iso_local(stream_expiry(url)) if stream_expiry(url) else "",
            }
        last_error = probe.get("error") or "ffprobe failed"
        time.sleep(0.3)
    return {"status": "excluded_no_stream", "error": last_error, "url": "", "probe": None}


def build_tv360() -> tuple[list[dict], list[dict], list[dict]]:
    log("[TV360] catalog")
    catalog = tv360_catalog()
    log(f"  {len(catalog)} unique channels")

    log("[TV360] 3-day schedules")
    tasks = [(ch, date) for ch in catalog for date in DATES]
    payloads = parallel(tasks, lambda item: tv360_schedule(item[0]["id"], item[1]), workers=6)
    by_key = {}
    for (ch, date), payload in zip(tasks, payloads):
        by_key[(ch["id"], date)] = payload if isinstance(payload, dict) else {}

    log("[TV360] free stream probe")
    free = [ch for ch in catalog if ch["is_free"] and not ch["is_drm"] and not ch["need_login"]]
    log(f"  {len(free)} metadata-free channels")
    stream_results = parallel(free, tv360_stream, workers=4)
    streams = {ch["id"]: res for ch, res in zip(free, stream_results)}

    channels: list[dict] = []
    schedules: list[dict] = []
    for ch in catalog:
        day_counts = {}
        for date in DATES:
            items = (by_key.get((ch["id"], date)) or {}).get("schedules") or []
            day_counts[date] = len(items)
            for item in items:
                start = parse_ts(item.get("epochSt"), "ms")
                end = parse_ts(item.get("epochEt"), "ms")
                if start is None and item.get("startTime"):
                    start = parse_local(f"{date}T{item['startTime']}:00")
                if end is None and item.get("endTime") and start:
                    end = parse_local(f"{date}T{item['endTime']}:00")
                    if end and end < start:
                        end += timedelta(days=1)
                if start is None:
                    continue
                if end is None or end <= start:
                    end = start + timedelta(minutes=30)
                schedules.append(
                    {
                        "platform": "tv360",
                        "platform_channel_id": str(ch["id"]),
                        "channel_name": ch["name"],
                        "date": start.astimezone(TZ).date().isoformat(),
                        "start_local": iso_local(start),
                        "end_local": iso_local(end),
                        "title": clean_text(item.get("name")),
                        "description": clean_text(item.get("description")),
                        "source_programme_id": str(item.get("id") or ""),
                        "end_estimated": "no" if item.get("epochEt") else "yes",
                    }
                )
        stream = streams.get(ch["id"]) or {}
        status_value = stream.get("status") or "excluded_paid"
        if not (ch["is_free"] and not ch["is_drm"] and not ch["need_login"]):
            if ch["need_login"]:
                status_value = "excluded_login"
            elif ch["is_drm"]:
                status_value = "excluded_drm"
            else:
                status_value = "excluded_paid"
        channels.append(
            {
                "platform": "tv360",
                "platform_channel_id": str(ch["id"]),
                "name": ch["name"],
                "slug": ch["slug"],
                "channel_number": "",
                "category": ch["category"],
                "logo": ch["logo"],
                "is_free": ch["is_free"],
                "is_drm": ch["is_drm"],
                "need_login": ch["need_login"],
                "stream_status": status_value,
                "stream_url": stream.get("url") or "",
                "stream_format": (stream.get("probe") or {}).get("format") or "",
                "stream_height": (stream.get("probe") or {}).get("height") or "",
                "stream_expires_local": stream.get("expires") or "",
                "epg_days": sum(1 for v in day_counts.values() if v),
                **{f"programmes_{d}": day_counts[d] for d in DATES},
                "total_programmes": sum(day_counts.values()),
                "source_page": ch["source_page"],
                "notes": stream.get("error") or "",
            }
        )
    channels.sort(key=lambda x: int(x["platform_channel_id"]))
    return channels, schedules, free


# ---------------------------------------------------------------------------
# FPT Play
# ---------------------------------------------------------------------------

FPT_SECRET = "6ea6d2a4e2d3a4bd5e275401aa086d"
FPT_VER = "v7.1_w"


def fpt_params(path: str, extra: dict | None = None) -> dict:
    expiry = int(time.time()) + 3600
    clean_path = path.lstrip("/").split("?")[0]
    message = FPT_SECRET + str(expiry) + "/api/" + FPT_VER + "/" + clean_path
    signature = (
        base64.b64encode(hashlib.md5(message.encode()).digest())
        .decode()
        .replace("+", "-")
        .replace("/", "_")
        .replace("=", "")
    )
    params = {
        "st": signature,
        "e": expiry,
        "device": "Chrome(version:152.0.0.0)",
        "drm": 1,
        "version": "8.8.23",
    }
    if extra:
        params.update(extra)
    return params


def fpt_api(path: str, extra: dict | None = None, timeout: int = 45):
    url = (
        "https://api.fptplay.net/api/"
        + FPT_VER
        + path
        + "?"
        + urllib.parse.urlencode(fpt_params(path, extra))
    )
    return http_json(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": "https://fptplay.vn",
            "Referer": "https://fptplay.vn/",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=timeout,
    )


def fpt_detail(channel_id: str) -> dict:
    _, payload = fpt_api("/tv/detail/" + channel_id)
    return (payload or {}).get("Channel") or {}


def fpt_stream(channel: dict) -> dict:
    cid = channel["id"]
    detail = fpt_detail(cid)
    profile = detail.get("auto_profile") or "adaptive_bitrate"
    status, payload = fpt_api(
        f"/stream/tv/{cid}/{profile}",
        {"enable_preview": 1, "stream_profile": 1},
    )
    data = (payload or {}).get("data") or {}
    url = str(data.get("url") or "")
    if status != 200 or not url:
        return {
            "status": "excluded_login" if status == 401 else "excluded_no_stream",
            "url": "",
            "probe": None,
            "error": f"HTTP {status}" if status else "no stream URL",
            "auto_profile": profile,
            "is_vip": detail.get("is_vip"),
        }
    if int(data.get("is_vip") or 0) != 0:
        return {
            "status": "excluded_premium",
            "url": "",
            "probe": None,
            "error": "stream is_vip=1",
            "auto_profile": profile,
            "is_vip": detail.get("is_vip"),
        }
    probe = probe_stream(url, "https://fptplay.vn/")
    if not probe["ok"]:
        return {
            "status": "excluded_no_stream",
            "url": "",
            "probe": probe,
            "error": probe.get("error") or "ffprobe failed",
            "auto_profile": profile,
            "is_vip": detail.get("is_vip"),
        }
    return {
        "status": "included",
        "url": url,
        "probe": probe,
        "error": None,
        "auto_profile": profile,
        "is_vip": detail.get("is_vip"),
        "expires": iso_local(stream_expiry(url)) if stream_expiry(url) else "",
    }


def build_fptplay() -> tuple[list[dict], list[dict], list[dict]]:
    log("[FPT Play] catalog")
    status, payload = fpt_api("/content/tv/channels", {"time_out": 3000})
    data = (payload or {}).get("data") or {}
    raw = data.get("channels") or []
    groups = {str(g.get("id")): clean_text(g.get("name")) for g in data.get("groups") or []}
    log(f"  {len(raw)} channels")

    log("[FPT Play] 3-day schedules")
    tasks = [(ch, date) for ch in raw for date in DATES]
    payloads = parallel(
        tasks,
        lambda item: fpt_api(
            f"/content/tv/schedules/{item[0]['id']}", {"day": item[1]}
        ),
        workers=6,
    )
    by_key = {}
    for (ch, date), result in zip(tasks, payloads):
        _, body = result if isinstance(result, tuple) else (None, result)
        by_key[(ch["id"], date)] = ((body or {}).get("data") or {}).get("schedule_list") or []

    log("[FPT Play] public stream probe")
    stream_results = parallel(raw, fpt_stream, workers=5)
    streams = {ch["id"]: res for ch, res in zip(raw, stream_results)}

    channels: list[dict] = []
    schedules: list[dict] = []
    for ch in raw:
        day_counts = {}
        for date in DATES:
            items = by_key.get((ch["id"], date)) or []
            day_counts[date] = len(items)
            for item in items:
                start = parse_ts(item.get("start_time"), "s")
                end = parse_ts(item.get("end_time"), "s")
                if start is None:
                    continue
                if end is None or end <= start:
                    end = start + timedelta(minutes=30)
                schedules.append(
                    {
                        "platform": "fptplay",
                        "platform_channel_id": str(ch["id"]),
                        "channel_name": clean_text(ch.get("name")),
                        "date": start.astimezone(TZ).date().isoformat(),
                        "start_local": iso_local(start),
                        "end_local": iso_local(end),
                        "title": clean_text(item.get("title")),
                        "description": "",
                        "source_programme_id": str(item.get("id") or ""),
                        "end_estimated": "no",
                    }
                )
        stream = streams.get(ch["id"]) or {}
        channels.append(
            {
                "platform": "fptplay",
                "platform_channel_id": str(ch["id"]),
                "name": clean_text(ch.get("name")),
                "slug": str(ch.get("id")),
                "channel_number": str(ch.get("channel_number") or ""),
                "category": groups.get(str(ch.get("group_id")), ""),
                "logo": abs_url(ch.get("original_logo"), "https://fptplay.vn/"),
                "is_free": 1 if str(stream.get("is_vip") or "0") == "0" else 0,
                "is_drm": 1 if str(ch.get("verimatrix") or "0") != "0" else 0,
                "need_login": 0,
                "stream_status": stream.get("status") or "excluded_no_stream",
                "stream_url": stream.get("url") or "",
                "stream_format": (stream.get("probe") or {}).get("format") or "",
                "stream_height": (stream.get("probe") or {}).get("height") or "",
                "stream_expires_local": stream.get("expires") or "",
                "epg_days": sum(1 for v in day_counts.values() if v),
                **{f"programmes_{d}": day_counts[d] for d in DATES},
                "total_programmes": sum(day_counts.values()),
                "source_page": "https://fptplay.vn/xem-truyen-hinh/",
                "notes": stream.get("error") or "",
                "auto_profile": stream.get("auto_profile") or "",
                "is_vip": stream.get("is_vip"),
            }
        )
    channels.sort(key=lambda x: (int(x["channel_number"] or 0), x["name"]))
    return channels, schedules, raw


# ---------------------------------------------------------------------------
# HTV
# ---------------------------------------------------------------------------

HTV_PAGE = "https://htv.vn/truc-tuyen.htm"
HTV_EPG = "https://htv.vn/ajax/programchannel.api"
HTV_SECRET = "W3b4pp_HTV@2025"
HTV_CHANNELS = [
    {"id": "2223", "name": "HTV9", "embed": "https://htvm.htv.com.vn/vcc/htv9hd", "stream_type": "htv9"},
    {"id": "2221", "name": "HTV7", "embed": "https://htvc.com.vn/iframe?content_id=256", "stream_type": "htvc"},
    {"id": "22214", "name": "HTV4", "embed": "https://htvc.com.vn/iframe?content_id=2528", "stream_type": "htvc"},
]


def htv_headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Referer": HTV_PAGE,
        "Origin": "https://htv.vn",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/plain, */*",
    }


def htv_epg(channel_id: str, date: str) -> list[dict]:
    url = HTV_EPG + "?" + urllib.parse.urlencode({"id": channel_id, "date": date})
    status, payload = http_json(url, headers=htv_headers())
    if status != 200 or not isinstance(payload, dict):
        return []
    return payload.get("data") or []


def htv9_stream() -> dict:
    now = str(int(time.time()))
    signature = hmac.new(HTV_SECRET.encode(), now.encode(), hashlib.sha256).hexdigest()
    url = (
        "https://api-htvm.mytv.vn/api/v1/share/channel/190/play?&uuid="
        + str(uuid.uuid4())
    )
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://htvm.htv.com.vn/",
        "Origin": "https://htvm.htv.com.vn",
        "Accept": "*/*",
        "Content-Type": "application/json",
        "x-api-time": now,
        "x-api-sign": signature,
    }
    status, body = http(url, headers=headers, data=b"{}", method="POST", retries=2)
    try:
        payload = json.loads(body.decode("utf-8", "replace"))
        stream_url = payload["data"]["data"]["object"][0]
    except Exception:
        return {"_error": f"HTV9 share HTTP {status}: {body[:160]!r}"}
    return {"url": stream_url}


def htvc_stream(embed: str) -> dict:
    status, body = http(
        embed,
        headers={"User-Agent": USER_AGENT, "Referer": HTV_PAGE},
        retries=2,
    )
    text = body.decode("utf-8", "replace")
    urls = re.findall(r"https?://[^\"'\\\s]+?\.m3u8[^\"'\\\s]*", text)
    if not urls:
        return {"_error": f"no m3u8 in HTVC iframe (HTTP {status})"}
    return {"url": urls[0]}


def build_htv() -> tuple[list[dict], list[dict], list[dict]]:
    log("[HTV] 3-day EPG + streams")
    # enrich metadata from the public page
    _, page_body = http(HTV_PAGE, headers={"User-Agent": USER_AGENT}, retries=2)
    page = page_body.decode("utf-8", "replace")
    page_meta = {}
    for match in re.finditer(r"<button[^>]*class=\"box-show-item item\"[^>]*>", page):
        tag = match.group(0)
        did = re.search(r'data-id="([^"]+)"', tag)
        title = re.search(r'title="([^"]+)"', tag)
        if did and title:
            after = page[match.end():match.end() + 600]
            img = re.search(r'<img[^>]+src="([^"]+)"', after)
            page_meta[did.group(1)] = {
                "name": clean_text(title.group(1)),
                "logo": abs_url(img.group(1), "https://htv.vn/") if img else "",
            }

    channels: list[dict] = []
    schedules: list[dict] = []
    included = []
    for base in HTV_CHANNELS:
        cid = base["id"]
        meta = page_meta.get(cid, {})
        name = meta.get("name") or base["name"]
        day_counts = {}
        for date in DATES:
            items = htv_epg(cid, date)
            day_counts[date] = len(items)
            for idx, item in enumerate(items):
                start = parse_local(item.get("ScheduleTime"))
                if start is None:
                    continue
                end = None
                if idx + 1 < len(items):
                    end = parse_local(items[idx + 1].get("ScheduleTime"))
                estimated = "no" if end and end > start else "yes"
                if end is None or end <= start:
                    end = start + timedelta(minutes=30)
                schedules.append(
                    {
                        "platform": "htv",
                        "platform_channel_id": cid,
                        "channel_name": name,
                        "date": start.astimezone(TZ).date().isoformat(),
                        "start_local": iso_local(start),
                        "end_local": iso_local(end),
                        "title": clean_text(item.get("Title")),
                        "description": clean_text(item.get("Description")),
                        "source_programme_id": str(item.get("Id") or ""),
                        "end_estimated": estimated,
                    }
                )
        if base["stream_type"] == "htv9":
            result = htv9_stream()
            referer = "https://htvm.htv.com.vn/"
        else:
            result = htvc_stream(base["embed"])
            referer = "https://htv.vn/"
        url = result.get("url") or ""
        probe = probe_stream(url, referer) if url else None
        if url and probe and probe["ok"]:
            status_value = "included"
            included.append((base, name, url, referer, probe))
        else:
            status_value = "excluded_no_stream"
        channels.append(
            {
                "platform": "htv",
                "platform_channel_id": cid,
                "name": name,
                "slug": name.lower().replace(" ", "-"),
                "channel_number": "",
                "category": "HTV",
                "logo": meta.get("logo") or "",
                "is_free": 1,
                "is_drm": 0,
                "need_login": 0,
                "stream_status": status_value,
                "stream_url": url,
                "stream_format": (probe or {}).get("format") or "",
                "stream_height": (probe or {}).get("height") or "",
                "stream_expires_local": iso_local(stream_expiry(url)) if url and stream_expiry(url) else "",
                "epg_days": sum(1 for v in day_counts.values() if v),
                **{f"programmes_{d}": day_counts[d] for d in DATES},
                "total_programmes": sum(day_counts.values()),
                "source_page": HTV_PAGE,
                "notes": result.get("_error") or (probe or {}).get("error") or "",
            }
        )
    return channels, schedules, included


# ---------------------------------------------------------------------------
# VTVgo
# ---------------------------------------------------------------------------

VTVGO_HEADERS = {
    "User-Agent": USER_AGENT,
    "Origin": "https://vtvgo.vn",
    "Referer": "https://vtvgo.vn/",
    "Accept": "application/json, text/plain, */*",
}

# VLC's GnuTLS stack cannot complete a handshake with this VTVgo edge host.
# ffprobe (OpenSSL) sometimes succeeds, so a plain probe is not enough; skip it
# for playlist use and rely on the provider's alternate source or a fallback.
VTVGO_VLC_BLOCKED_HOSTS = {"vtvgolive-ott3.vtvdigital.vn"}

# Hà Tĩnh's only public VTVgo source is on the blocked host above. This public
# backup CDN is advertised by the channel's own player and was verified in VLC.
VTVGO_FALLBACKS = {
    "Truyền hình Hà Tĩnh": "https://cohauw9bgpvod.vcdn.cloud/httv1/index.m3u8",
}


def vtvgo_catalog() -> list[dict]:
    cache = DATA_DIR / "vtvgo_catalog.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    status, payload = http_json(
        "https://api.vtvdigital.org/display/v21.0/catalogs/with-channels?platform=web",
        headers=VTVGO_HEADERS,
    )
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"VTVgo catalog HTTP {status}")
    seen: dict[str, dict] = {}
    for catalog in payload.get("data") or []:
        cname = clean_text(catalog.get("name"))
        for channel in catalog.get("channels") or []:
            cid = str(channel.get("id"))
            if cid not in seen:
                seen[cid] = {
                    "id": cid,
                    "name": clean_text(channel.get("name")),
                    "logo": channel.get("logo") or "",
                    "thumbnail": channel.get("thumbnail") or "",
                    "must_login": bool(channel.get("mustLogin")),
                    "enabled": bool(channel.get("enabled", True)),
                    "epg_channel_id": channel.get("epgChannelId") or "",
                    "catalogs": [cname],
                }
            elif cname not in seen[cid]["catalogs"]:
                seen[cid]["catalogs"].append(cname)
    channels = sorted(seen.values(), key=lambda x: (not x["id"].isdigit(), int(x["id"]) if x["id"].isdigit() else 0, x["name"]))
    write_json(cache, channels)
    return channels


def vtvgo_epg_batch(channel_ids: list[str]) -> dict:
    url = "https://api.vtvdigital.org/display/v21.0/epg?" + urllib.parse.urlencode(
        {
            "channelIDs": ",".join(channel_ids),
            "from": DATES[0],
            "to": DATES[-1],
            "platform": "web",
        }
    )
    status, payload = http_json(url, headers=VTVGO_HEADERS)
    if status != 200 or not isinstance(payload, dict):
        return {}
    return payload.get("data") or {}


def vtvgo_playback(channel: dict) -> dict:
    body = json.dumps({"channelId": str(channel["id"]), "platform": "web"}).encode()
    status, payload = http_json(
        "https://api.vtvdigital.org/live-channel/v21.0/playback/source",
        headers={**VTVGO_HEADERS, "Content-Type": "application/json"},
        data=body,
        method="POST",
        retries=2,
    )
    if status != 200 or not isinstance(payload, dict):
        return {"status": "excluded_no_stream", "error": f"HTTP {status}"}
    data = payload.get("data") or {}
    modes = data.get("sourceModes") or []
    if not modes:
        return {"status": "excluded_no_stream", "error": "no sourceModes"}
    mode = modes[0]
    if int(mode.get("isVip") or 0) != 0:
        return {"status": "excluded_premium", "error": "sourceModes[0].isVip=1"}
    urls: list[str] = []
    for source in mode.get("multiSource") or []:
        if str(source.get("manifestType") or "hls").lower() != "hls":
            continue
        for item in source.get("sources") or []:
            candidate = item.get("url")
            if candidate and candidate not in urls:
                urls.append(candidate)
    if not urls:
        return {"status": "excluded_no_stream", "error": "no HLS source"}
    errors: list[str] = []

    def try_url(candidate: str, label: str):
        probe = probe_stream(candidate, "https://vtvgo.vn/")
        if not probe["ok"]:
            # VTVgo's edge hosts occasionally fail TLS or time out on the first
            # attempt; one quick retry recovers most transient failures.
            time.sleep(1.0)
            probe = probe_stream(candidate, "https://vtvgo.vn/")
        if probe["ok"]:
            expires = stream_expiry(candidate)
            return {
                "status": "included",
                "url": candidate,
                "probe": probe,
                "expires": iso_local(expires) if expires else "",
                "error": None if label == "primary" else label,
            }
        errors.append(f"{label}: {probe.get('error') or 'ffprobe failed'}")
        return None

    for url in urls:
        host = (urllib.parse.urlsplit(url).hostname or "").lower()
        if "stg" in host:
            errors.append(f"{host}: staging host")
            continue
        if host in VTVGO_VLC_BLOCKED_HOSTS:
            errors.append(f"{host}: blocked (TLS handshake fails in VLC)")
            continue
        result = try_url(url, "primary")
        if result:
            return result

    fallback = VTVGO_FALLBACKS.get(str(channel.get("name") or ""))
    if fallback:
        result = try_url(fallback, "fallback source; primary VTVgo host fails TLS in VLC")
        if result:
            return result

    return {
        "status": "excluded_no_stream",
        "error": "all HLS sources failed: " + " | ".join(errors[:3]),
        "url": "",
        "probe": None,
    }


def build_vtvgo() -> tuple[list[dict], list[dict], list[dict]]:
    log("[VTVgo] catalog")
    catalog = vtvgo_catalog()
    log(f"  {len(catalog)} unique channels; {sum(1 for c in catalog if not c['must_login'])} anonymous-eligible")

    log("[VTVgo] 3-day EPG (batched)")
    batches = [catalog[i:i + 8] for i in range(0, len(catalog), 8)]
    batch_results = parallel(
        batches,
        lambda batch: vtvgo_epg_batch([c["id"] for c in batch]),
        workers=4,
    )
    epg_map: dict[str, list] = defaultdict(list)
    for batch, result in zip(batches, batch_results):
        if not isinstance(result, dict):
            continue
        for ch in batch:
            epg_map[ch["id"]] = result.get(ch["id"]) or []

    log("[VTVgo] public playback probe")
    free = [c for c in catalog if not c["must_login"] and c["enabled"]]
    play_results = parallel(free, vtvgo_playback, workers=5)
    streams = {c["id"]: r for c, r in zip(free, play_results)}

    channels: list[dict] = []
    schedules: list[dict] = []
    for ch in catalog:
        day_counts = {}
        for bucket in epg_map.get(ch["id"], []):
            for item in bucket.get("programs") or []:
                start = parse_local(item.get("startTime"))
                end = parse_local(item.get("endTime"))
                if start is None:
                    continue
                if end is None or end <= start:
                    end = start + timedelta(minutes=30)
                day = start.astimezone(TZ).date().isoformat()
                if day not in DATES:
                    continue
                day_counts[day] = day_counts.get(day, 0) + 1
                schedules.append(
                    {
                        "platform": "vtvgo",
                        "platform_channel_id": ch["id"],
                        "channel_name": ch["name"],
                        "date": day,
                        "start_local": iso_local(start),
                        "end_local": iso_local(end),
                        "title": clean_text(item.get("title")),
                        "description": clean_text(item.get("description")),
                        "source_programme_id": str(item.get("slotId") or ""),
                        "end_estimated": "no",
                    }
                )
        stream = streams.get(ch["id"]) or {}
        if ch["must_login"]:
            status_value = "excluded_login"
        elif not ch["enabled"]:
            status_value = "excluded_unavailable"
        else:
            status_value = stream.get("status") or "excluded_no_stream"
        channels.append(
            {
                "platform": "vtvgo",
                "platform_channel_id": ch["id"],
                "name": ch["name"],
                "slug": ch["id"],
                "channel_number": "",
                "category": ", ".join(ch["catalogs"][:2]),
                "logo": ch["logo"],
                "is_free": 0 if ch["must_login"] else 1,
                "is_drm": 0,
                "need_login": 1 if ch["must_login"] else 0,
                "stream_status": status_value,
                "stream_url": stream.get("url") or "",
                "stream_format": (stream.get("probe") or {}).get("format") or "",
                "stream_height": (stream.get("probe") or {}).get("height") or "",
                "stream_expires_local": stream.get("expires") or "",
                "epg_days": sum(1 for d in DATES if day_counts.get(d)),
                **{f"programmes_{d}": day_counts.get(d, 0) for d in DATES},
                "total_programmes": sum(day_counts.values()),
                "source_page": "https://vtvgo.vn/",
                "notes": stream.get("error") or "",
                "epg_channel_id": ch["epg_channel_id"],
            }
        )
    return channels, schedules, free


# ---------------------------------------------------------------------------
# MyTV (EPG only; anonymous playback requires login)
# ---------------------------------------------------------------------------

MYTV_BASE = "https://apigw.mytv.vn"
MYTV_MAC = "bb43b1f48d970b10aa98aa463e403a0a"


def mytv_token() -> str:
    body = json.dumps(
        {
            "device_model": "Browser",
            "device_name": "Electron",
            "device_type": 127,
            "platform": "WEBAPP",
            "version_number": "5",
        }
    ).encode()
    url = MYTV_BASE + "/api/v1/noauth/token-no-login-v2?" + urllib.parse.urlencode(
        {
            "req_id": MYTV_MAC + "|" + str(int(time.time() * 1000)),
            "platform": "WEBAPP",
            "support_4k": 1,
        }
    )
    status, payload = http_json(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": "https://mytv.com.vn",
            "Referer": "https://mytv.com.vn/",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "macaddress": MYTV_MAC,
            "manufacturer_id": MYTV_MAC,
        },
        data=body,
        method="POST",
        retries=2,
    )
    token = ((payload or {}).get("data") or {}).get("token") if isinstance(payload, dict) else None
    if not token:
        raise RuntimeError(f"MyTV token failed: HTTP {status} {str(payload)[:200]}")
    return token


def mytv_headers(token: str) -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Origin": "https://mytv.com.vn",
        "Referer": "https://mytv.com.vn/",
        "Accept": "*/*",
        "authorization": token,
        "macaddress": MYTV_MAC,
        "manufacturer_id": MYTV_MAC,
    }


def mytv_get(path: str, token: str, params: dict | None = None):
    query = {
        "uuid": MYTV_MAC + "1793117353789",
        "req_id": MYTV_MAC + "|" + str(int(time.time() * 1000)),
        "platform": "WEBAPP",
        "support_4k": 1,
    }
    if params:
        query.update(params)
    sep = "&" if "?" in path else "?"
    url = MYTV_BASE + path + sep + urllib.parse.urlencode(query)
    return http_json(url, headers=mytv_headers(token), timeout=30)


def mytv_schedule(channel_id: int, date: str, token: str) -> list[dict]:
    status, payload = mytv_get(f"/api/v1/channel/{channel_id}/schedule", token, {"date": date})
    if status != 200 or not isinstance(payload, dict):
        return []
    return ((payload.get("data") or {}).get("schedule")) or []


def mytv_play_check(channel_id: int, token: str) -> dict:
    url = MYTV_BASE + f"/api/v1/channel/{channel_id}/play?" + urllib.parse.urlencode(
        {
            "uuid": MYTV_MAC + "1793117353789",
            "req_id": MYTV_MAC + "|" + str(int(time.time() * 1000)),
            "platform": "WEBAPP",
            "support_4k": 1,
        }
    )
    status, payload = http_json(
        url,
        headers={**mytv_headers(token), "Content-Type": "application/json"},
        data=b"{}",
        method="POST",
        retries=1,
    )
    if not isinstance(payload, dict):
        return {"status": "excluded_no_stream", "error": f"HTTP {status}"}
    if payload.get("result") == 0 and (payload.get("data") or {}).get("url"):
        return {"status": "public", "error": None}
    return {
        "status": "excluded_login",
        "error": payload.get("error_type") or payload.get("message") or f"HTTP {status}",
    }


def build_mytv() -> tuple[list[dict], list[dict], list[dict]]:
    log("[MyTV] anonymous token")
    token = mytv_token()
    log("[MyTV] channel list")
    status, payload = mytv_get("/api/v1/channel", token, {"cate_id": "undefined"})
    raw = (payload or {}).get("data") or []
    log(f"  {len(raw)} channels")

    categories = {}
    _, cat_payload = mytv_get("/api/v1/channel/cates", token)
    for item in (cat_payload or {}).get("data") or []:
        if isinstance(item, dict):
            categories[str(item.get("id"))] = clean_text(item.get("name"))

    log("[MyTV] 3-day EPG")
    tasks = [(ch, date) for ch in raw for date in DATES]
    results = parallel(
        tasks, lambda item: mytv_schedule(item[0]["channel_id"], item[1], token), workers=8
    )
    by_key = {}
    for (ch, date), items in zip(tasks, results):
        by_key[(ch["channel_id"], date)] = items if isinstance(items, list) else []

    play_candidates = [
        ch for ch in raw if ch.get("play") == 1 and ch.get("drm") == 0 and ch.get("product_id") in (0, None)
    ]
    log(f"[MyTV] playback check on {len(play_candidates)} anonymous candidates")
    play_results = parallel(play_candidates, lambda ch: mytv_play_check(ch["channel_id"], token), workers=8)
    play_map = {ch["channel_id"]: r for ch, r in zip(play_candidates, play_results)}

    channels: list[dict] = []
    schedules: list[dict] = []
    for ch in raw:
        cid = ch["channel_id"]
        day_counts = {}
        for date in DATES:
            items = by_key.get((cid, date)) or []
            day_counts[date] = len(items)
            for idx, item in enumerate(items):
                start = parse_local(f"{date}T{str(item.get('time') or '')}:00")
                if start is None:
                    continue
                end = None
                if idx + 1 < len(items):
                    end = parse_local(f"{date}T{str(items[idx + 1].get('time') or '')}:00")
                estimated = "no" if end and end > start else "yes"
                if end is None or end <= start:
                    end = start + timedelta(minutes=30)
                schedules.append(
                    {
                        "platform": "mytv",
                        "platform_channel_id": str(cid),
                        "channel_name": clean_text(ch.get("name")),
                        "date": start.astimezone(TZ).date().isoformat(),
                        "start_local": iso_local(start),
                        "end_local": iso_local(end),
                        "title": clean_text(item.get("title")),
                        "description": "",
                        "source_programme_id": "",
                        "end_estimated": estimated,
                    }
                )
        play = play_map.get(cid) or {}
        if ch.get("drm"):
            status_value = "excluded_drm"
        elif ch.get("play") != 1:
            status_value = "excluded_paid"
        elif play.get("status") == "public":
            status_value = "public_unverified"
        else:
            status_value = "excluded_login"
        channels.append(
            {
                "platform": "mytv",
                "platform_channel_id": str(cid),
                "name": clean_text(ch.get("name")),
                "slug": str(ch.get("mytv_id") or cid),
                "channel_number": str(ch.get("display_order") or ""),
                "category": categories.get(str(ch.get("category_id")), ""),
                "logo": abs_url(ch.get("logo_web"), "https://mytv.com.vn/"),
                "is_free": 0,
                "is_drm": int(ch.get("drm") or 0),
                "need_login": 1,
                "stream_status": status_value,
                "stream_url": "",
                "stream_format": "",
                "stream_height": "",
                "stream_expires_local": "",
                "epg_days": sum(1 for d in DATES if day_counts.get(d)),
                **{f"programmes_{d}": day_counts.get(d, 0) for d in DATES},
                "total_programmes": sum(day_counts.values()),
                "source_page": "https://mytv.com.vn/truyen-hinh",
                "notes": play.get("error") or "",
                "product_id": ch.get("product_id"),
            }
        )
    channels.sort(key=lambda x: (int(x["channel_number"] or 0), x["name"]))
    return channels, schedules, play_candidates


# ---------------------------------------------------------------------------
# M3U + outputs
# ---------------------------------------------------------------------------

M3U_REFERERS = {
    "tv360": "https://tv360.vn/",
    "fptplay": "https://fptplay.vn/",
    "htv": "https://htv.vn/",
    "htv9": "https://htvm.htv.com.vn/",
    "vtvgo": "https://vtvgo.vn/",
    "mytv": "https://mytv.com.vn/",
}

PLATFORM_LABELS = {
    "tv360": "TV360",
    "fptplay": "FPT Play",
    "htv": "HTV",
    "vtvgo": "VTVgo",
    "mytv": "MyTV",
}

COMBINED_NOTES = [
    "One verified public stream per normalized channel name, preferring the longest remaining token.",
    "Ultra-short FPT Play and HTV7/HTV4 tokens are kept only in their per-platform playlists.",
    "Refresh with: python refresh_multi_playlists.py",
]


def m3u_escape(value: str) -> str:
    return str(value or "").replace('"', "'").replace("\n", " ").strip()


def build_m3u(
    rows: list[dict],
    title: str,
    referer_map: dict | None = None,
    notes: list[str] | None = None,
) -> str:
    lines = ["#EXTM3U", f"# {title} - generated {iso_local(GENERATED_AT)}"]
    for note in notes or []:
        lines.append(f"# {note}")
    for row in rows:
        name = m3u_escape(row["name"])
        group = m3u_escape(
            PLATFORM_LABELS.get(row["platform"], row["platform"])
            + (" / " + row["category"] if row.get("category") else "")
        )
        tvg_id = m3u_escape(f"{row['platform']}.{row['platform_channel_id']}")
        logo = m3u_escape(row.get("logo") or "")
        lines.append(
            f'#EXTINF:-1 tvg-id="{tvg_id}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
        )
        referer = (referer_map or M3U_REFERERS).get(row["platform"]) or M3U_REFERERS.get(row["platform"])
        if row["platform"] == "htv":
            referer = "https://htvm.htv.com.vn/" if row.get("platform_channel_id") == "2223" else "https://htv.vn/"
        if referer:
            lines.append(f"#EXTVLCOPT:http-referrer={referer}")
        lines.append(row["stream_url"])
    return "\n".join(lines) + "\n"


TV360_COLUMNS = [
    "platform", "platform_channel_id", "name", "slug", "category", "logo",
    "is_free", "is_drm", "need_login", "stream_status", "stream_url",
    "stream_format", "stream_height", "stream_expires_local", "epg_days",
    *[f"programmes_{d}" for d in DATES], "total_programmes", "source_page", "notes",
]


def set_dates(days: list[str]) -> None:
    """Set the active EPG window and rebuild the per-day CSV columns."""
    global DATES, TV360_COLUMNS
    DATES = list(days)
    TV360_COLUMNS = [
        "platform", "platform_channel_id", "name", "slug", "category", "logo",
        "is_free", "is_drm", "need_login", "stream_status", "stream_url",
        "stream_format", "stream_height", "stream_expires_local", "epg_days",
        *[f"programmes_{d}" for d in DATES], "total_programmes", "source_page", "notes",
    ]


SCHEDULE_COLUMNS = [
    "platform", "platform_channel_id", "channel_name", "date", "start_local",
    "end_local", "title", "description", "source_programme_id", "end_estimated",
]


def write_platform_outputs(platform: str, channels: list[dict], schedules: list[dict]) -> None:
    label = PLATFORM_LABELS[platform]
    write_csv(OUTPUT_DIR / f"{platform}_channels.csv", channels, TV360_COLUMNS)
    write_csv(OUTPUT_DIR / f"{platform}_schedule_3days.csv", schedules, SCHEDULE_COLUMNS)
    included = [c for c in channels if c.get("stream_status") == "included" and c.get("stream_url")]
    notes = []
    if platform == "fptplay":
        notes.append(
            "WARNING: FPT Play CDN tokens expire in about 2-3 minutes. "
            "Run refresh_multi_playlists.py, then open this playlist immediately."
        )
    elif platform == "htv":
        notes.append(
            "WARNING: HTV7/HTV4 JWTs expire in about 10 minutes; HTV9 has no parsed expiry. "
            "For a stable HTV7/HTV4/HTV9 use the TV360 playlist instead."
        )
    if not included:
        notes.append("No verified public stream in this refresh.")
    m3u_path = OUTPUT_DIR / f"{platform}_free_channels.m3u"
    if platform == "mytv":
        # MyTV is EPG-only. Remove any stale playlist from an earlier run.
        m3u_path.unlink(missing_ok=True)
    else:
        m3u = build_m3u(included, f"{label} free/public channels", notes=notes)
        m3u_path.write_text(m3u, encoding="utf-8")
    write_json(
        OUTPUT_DIR / f"{platform}_free_channels.json",
        {
            "platform": platform,
            "label": label,
            "generated_at": iso_local(GENERATED_AT),
            "timezone": TZ_NAME,
            "total_channels": len(channels),
            "included": len(included),
            "channels": channels,
        },
    )


MIN_COMBINED_TOKEN_MINUTES = 30
UNKNOWN_EXPIRY_MINUTES = 90


def dedupe_combined(channels: list[dict]) -> list[dict]:
    """Choose one stable public stream per normalized channel name.

    The combined playlist should stay playable for hours, not minutes.  It
    therefore prefers the stream with the longest remaining token and drops
    entries whose known token expires within MIN_COMBINED_TOKEN_MINUTES.
    Unknown expiries (for example HTV9's rkey URL) rank below a known
    multi-hour token but above the minute-long FPT/HTV JWT URLs.
    """
    order = {"htv": 0, "tv360": 1, "vtvgo": 2, "fptplay": 3, "mytv": 4}
    now = datetime.now(TZ)
    cutoff = now + timedelta(minutes=MIN_COMBINED_TOKEN_MINUTES)
    unknown_rank = now + timedelta(minutes=UNKNOWN_EXPIRY_MINUTES)

    def norm(name: str) -> str:
        text = name.upper()
        text = re.sub(r"\b(HD|FHD|UHD|4K|SD|VIP)\b", " ", text)
        text = re.sub(r"[^A-Z0-9À-Ỹ]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def expiry_rank(row: dict) -> datetime:
        value = row.get("stream_expires_local")
        parsed = None
        if value:
            try:
                parsed = datetime.fromisoformat(value)
            except Exception:
                parsed = None
        if parsed is None:
            parsed = stream_expiry(row.get("stream_url") or "")
        return parsed or unknown_rank

    best: dict[str, dict] = {}
    for row in channels:
        if row.get("stream_status") != "included" or not row.get("stream_url"):
            continue
        host = (urllib.parse.urlsplit(row["stream_url"]).hostname or "").lower()
        if "stg" in host or host in VTVGO_VLC_BLOCKED_HOSTS:
            continue
        key = norm(row["name"])
        if not key:
            continue
        rank = expiry_rank(row)
        if rank <= cutoff:
            continue
        current = best.get(key)
        if current is None:
            best[key] = row
            continue
        current_rank = expiry_rank(current)
        if rank > current_rank:
            best[key] = row
        elif rank == current_rank and order.get(row["platform"], 9) < order.get(current["platform"], 9):
            best[key] = row
    return sorted(best.values(), key=lambda r: (order.get(r["platform"], 9), r["name"]))


def build_outputs(
    tv360: tuple, fpt: tuple, htv: tuple, vtvgo: tuple, mytv: tuple
) -> dict:
    all_channels = tv360[0] + fpt[0] + htv[0] + vtvgo[0] + mytv[0]
    all_schedules = tv360[1] + fpt[1] + htv[1] + vtvgo[1] + mytv[1]
    all_schedules.sort(key=lambda r: (r["platform"], r["date"], r["start_local"], r["channel_name"]))

    write_csv(OUTPUT_DIR / "all_platform_channels.csv", all_channels, TV360_COLUMNS)
    write_csv(OUTPUT_DIR / "all_platform_schedule_3days.csv", all_schedules, SCHEDULE_COLUMNS)

    combined = dedupe_combined(all_channels)
    m3u = build_m3u(
        combined,
        "Combined free/public Vietnamese TV",
        notes=COMBINED_NOTES,
    )
    (OUTPUT_DIR / "all_free_channels.m3u").write_text(m3u, encoding="utf-8")

    per_platform = {}
    for platform, package in [
        ("tv360", tv360), ("fptplay", fpt), ("htv", htv), ("vtvgo", vtvgo), ("mytv", mytv)
    ]:
        per_platform[platform] = {
            "label": PLATFORM_LABELS[platform],
            "channels": len(package[0]),
            "programmes": len(package[1]),
            "included": sum(1 for c in package[0] if c.get("stream_status") == "included"),
        }

    payload = {
        "generated_at": iso_local(GENERATED_AT),
        "timezone": TZ_NAME,
        "window": {"from": DATES[0], "to": DATES[-1], "days": DATES},
        "sources": {
            "tv360": "https://tv360.vn/tv",
            "fptplay": "https://fptplay.vn/xem-truyen-hinh/",
            "htv": "https://htv.vn/truc-tuyen.htm",
            "vtvgo": "https://vtvgo.vn/",
            "mytv": "https://mytv.com.vn/truyen-hinh",
        },
        "summary": {
            "channels": len(all_channels),
            "programmes": len(all_schedules),
            "included_streams": sum(1 for c in all_channels if c.get("stream_status") == "included"),
            "combined_playlist_entries": len(combined),
            "per_platform": per_platform,
        },
        "channels": all_channels,
        "schedules": all_schedules,
    }
    write_json(OUTPUT_DIR / "all_platform_data.json", payload)
    return payload


def print_summary(payload: dict) -> None:
    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for platform, item in payload["summary"]["per_platform"].items():
        print(
            f"{item['label']:<10} channels={item['channels']:>4}  "
            f"programmes={item['programmes']:>6}  streams={item['included']:>3}"
        )
    print(
        f"TOTAL      channels={payload['summary']['channels']:>4}  "
        f"programmes={payload['summary']['programmes']:>6}  "
        f"streams={payload['summary']['included_streams']:>3}  "
        f"combined M3U={payload['summary']['combined_playlist_entries']}"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract multi-platform EPG and free/public streams."
    )
    parser.add_argument(
        "--start-date",
        help="First EPG date in YYYY-MM-DD; default is today in Asia/Ho_Chi_Minh.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=3,
        help="Number of EPG days to extract (default: 3).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    global GENERATED_AT
    args = parse_args(argv)
    if args.days < 1:
        print("--days must be at least 1", file=sys.stderr)
        return 2
    if args.start_date:
        try:
            start = datetime.strptime(args.start_date, "%Y-%m-%d")
        except ValueError:
            print("--start-date must be YYYY-MM-DD", file=sys.stderr)
            return 2
    else:
        start = datetime.now(TZ)
    set_dates(window_dates(start, args.days))
    GENERATED_AT = datetime.now(TZ)

    log(f"Window {DATES[0]} .. {DATES[-1]} ({TZ_NAME})")
    log(f"Output {OUTPUT_DIR}")

    tv360 = build_tv360()
    fpt = build_fptplay()
    htv = build_htv()
    vtvgo = build_vtvgo()
    mytv = build_mytv()

    for platform, package in [
        ("tv360", tv360), ("fptplay", fpt), ("htv", htv), ("vtvgo", vtvgo), ("mytv", mytv)
    ]:
        write_platform_outputs(platform, package[0], package[1])

    payload = build_outputs(tv360, fpt, htv, vtvgo, mytv)
    print_summary(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
