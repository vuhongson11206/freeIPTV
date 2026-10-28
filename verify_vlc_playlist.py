#!/usr/bin/env python3
"""
Smoke-test output/sctv_free_channels.m3u in VLC, one channel at a time.

For every playlist entry this script writes a temporary single-entry M3U
(preserving #EXTVLCOPT lines), opens it with VLC in dummy mode for a few
seconds, and checks the VLC log for:

  - the adaptive (HLS) demux,
  - a video decoder,
  - an audio decoder.

That proves VLC actually received and decoded media, not just that the URL
returned HTTP 200.

Usage:
    python verify_vlc_playlist.py                 # all entries
    python verify_vlc_playlist.py vtv1 ca-mau     # substring filter

Exit code 0 only if every tested entry played.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
M3U_PATH = BASE_DIR / "output" / "sctv_free_channels.m3u"
LOG_DIR = Path(tempfile.gettempdir()) / "opencode"

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


def test_entry(vlc: Path, entry: dict, index: int) -> dict:
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
        str(vlc),
        "-I",
        "dummy",
        "--vout=dummy",
        "--aout=dummy",
        f"--run-time={RUN_SECONDS}",
        "--play-and-exit",
        "--no-media-library",
        "--no-one-instance",
        "--file-logging",
        f"--logfile={log_path}",
        "--verbose=2",
        str(temp_m3u),
    ]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS
        )
        returncode = completed.returncode
    except subprocess.TimeoutExpired:
        returncode = None

    log = read_log(log_path) if log_path.exists() else ""
    lower = log.lower()
    checks = {
        "adaptive_demux": 'using demux module "adaptive"' in lower,
        "video_decoder": "using video decoder module" in lower,
        "audio_decoder": "using audio decoder module" in lower,
        "no_redirect_to_site": "page/truyen-hinh-ecb1ec92" not in lower,
    }
    return {
        "name": entry["name"],
        "ok": all(checks.values()),
        "returncode": returncode,
        "checks": checks,
        "log": str(log_path),
        "m3u": str(temp_m3u),
        "error_tail": [
            line
            for line in log.splitlines()
            if "error" in line.lower() or "failed" in line.lower()
        ][-3:],
    }


def main(argv: list[str]) -> int:
    if not M3U_PATH.exists():
        print(f"Missing playlist: {M3U_PATH}", file=sys.stderr)
        return 1

    entries = parse_m3u(M3U_PATH)
    filters = [arg.lower() for arg in argv]
    if filters:
        entries = [
            entry
            for entry in entries
            if any(token in entry["name"].lower() for token in filters)
        ]
    if not entries:
        print("No matching entries.", file=sys.stderr)
        return 1

    vlc = find_vlc()
    print(f"VLC: {vlc}")
    print(f"Playlist: {M3U_PATH}")
    print(f"Entries to test: {len(entries)}")
    print()

    results = []
    for index, entry in enumerate(entries, start=1):
        print(f"[{index:2}/{len(entries)}] {entry['name']} ... ", end="", flush=True)
        result = test_entry(vlc, entry, index)
        results.append(result)
        if result["ok"]:
            print("PLAYED (adaptive HLS, video+audio decoded)")
        else:
            failed = [name for name, passed in result["checks"].items() if not passed]
            print(f"FAILED: {', '.join(failed)}")
            for line in result["error_tail"]:
                print(f"    {line}")

    passed = sum(1 for result in results if result["ok"])
    print()
    print(f"Passed: {passed}/{len(results)}")
    if passed != len(results):
        print("Logs and temporary playlists are in:", LOG_DIR)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
