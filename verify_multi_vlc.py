#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VLC smoke test for the multi-platform playlists.

For every entry, open a temporary single-entry M3U in VLC dummy mode and check
that VLC selected the adaptive (HLS) demux and decoded both video and audio.

Usage:
    python verify_multi_vlc.py                          # combined playlist, all entries
    python verify_multi_vlc.py --m3u output/htv_free_channels.m3u
    python verify_multi_vlc.py vtv1 htv7                # substring filter
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_M3U = BASE_DIR / "output" / "all_free_channels.m3u"
LOG_DIR = Path(tempfile.gettempdir()) / "opencode" / "multi_vlc"

VLC_CANDIDATES = [
    Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe"),
    Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"),
]
RUN_SECONDS = 10
TIMEOUT_SECONDS = 60


def find_vlc() -> Path:
    for path in VLC_CANDIDATES:
        if path.exists():
            return path
    raise SystemExit("VLC not found in the usual Program Files locations.")


def parse_m3u(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    entries: list[dict] = []
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#EXTINF"):
            if current:
                entries.append(current)
            name = stripped.rsplit(",", 1)[-1].strip()
            current = {"name": name, "lines": [stripped], "url": None}
        elif current is not None:
            if stripped.startswith("#EXTVLCOPT"):
                current["lines"].append(stripped)
            elif stripped and not stripped.startswith("#"):
                current["url"] = stripped
                entries.append(current)
                current = None
    if current:
        entries.append(current)
    return [entry for entry in entries if entry["url"]]


def read_log(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", "replace")
    return data.decode("utf-8-sig", "replace")


def test_entry(vlc: Path, entry: dict, index: int, run_seconds: int, timeout_seconds: int) -> dict:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", entry["name"])[:40].strip("_")
    temp_m3u = LOG_DIR / f"vlc_entry_{index:02d}_{safe}.m3u"
    log_path = LOG_DIR / f"vlc_entry_{index:02d}_{safe}.log"
    temp_m3u.write_text(
        "\n".join(["#EXTM3U", *entry["lines"], entry["url"]]) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    log_path.unlink(missing_ok=True)
    command = [
        str(vlc), "--no-crashdump", "-I", "dummy", "--vout=dummy", "--aout=dummy",
        f"--run-time={run_seconds}", "--play-and-exit", "--no-media-library",
        "--no-one-instance", "--file-logging", f"--logfile={log_path}",
        "--verbose=2", str(temp_m3u),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
        returncode = completed.returncode
    except subprocess.TimeoutExpired:
        returncode = None
    log = read_log(log_path) if log_path.exists() else ""
    lower = log.lower()
    checks = {
        "adaptive_demux": 'using demux module "adaptive"' in lower,
        "video_decoder": "using video decoder module" in lower,
        "audio_decoder": "using audio decoder module" in lower,
    }
    return {
        "name": entry["name"],
        "ok": all(checks.values()),
        "returncode": returncode,
        "checks": checks,
        "log": str(log_path),
        "error_tail": [line for line in log.splitlines() if "error" in line.lower() or "failed" in line.lower()][-3:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--m3u", default=str(DEFAULT_M3U))
    parser.add_argument("--run-seconds", type=int, default=RUN_SECONDS)
    parser.add_argument("--timeout-seconds", type=int, default=TIMEOUT_SECONDS)
    parser.add_argument("filters", nargs="*")
    args = parser.parse_args()
    path = Path(args.m3u)
    if not path.is_absolute():
        path = BASE_DIR / path
    if not path.exists():
        print(f"Missing playlist: {path}", file=sys.stderr)
        return 1
    entries = parse_m3u(path)
    filters = [item.lower() for item in args.filters]
    if filters:
        entries = [entry for entry in entries if any(token in entry["name"].lower() for token in filters)]
    if not entries:
        print("No matching entries.", file=sys.stderr)
        return 1
    vlc = find_vlc()
    print(f"VLC: {vlc}")
    print(f"Playlist: {path}")
    print(f"Entries: {len(entries)}")
    results = []
    for index, entry in enumerate(entries, start=1):
        print(f"[{index:2}/{len(entries)}] {entry['name']} ... ", end="", flush=True)
        result = test_entry(vlc, entry, index, args.run_seconds, args.timeout_seconds)
        results.append(result)
        if result["ok"]:
            print("PLAYED")
        else:
            failed = [name for name, passed in result["checks"].items() if not passed]
            print("FAILED: " + ", ".join(failed))
            for line in result["error_tail"]:
                print("    " + line)
    passed = sum(1 for result in results if result["ok"])
    print(f"\nPassed: {passed}/{len(results)}")
    if passed != len(results):
        print("Logs:", LOG_DIR)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
