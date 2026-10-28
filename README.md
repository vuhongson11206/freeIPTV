# SCTV Online - channel/EPG export and free-channel M3U

Snapshot of **94 SCTV Online channels** and **9,228 programme rows** for
**2026-10-24 through 2026-10-26** (`Asia/Ho_Chi_Minh`, UTC+7), plus a
VLC-ready playlist of the **11 free live channels** whose streams were
verified as publicly playable.

Only channels marked `is_premium=no` are in the playlist. No account login,
premium entitlement, paywall or DRM bypass is used.

The playlist is also rebuilt by the unified multi-platform refresh
(`python refresh_multi_playlists.py`), and deployed automatically with the rest
of the project by GitHub Actions. See `README_MULTI_PLATFORM.md` for the
GitHub/Vercel setup.

## Playlist

`output/sctv_free_channels.m3u` - 11 free live channels:

| # | Channel | Resolution |
|---:|---|---|
| 1 | VTV1 | 1080p |
| 2 | QPVN | 1080p |
| 3 | ANTV | 720p |
| 4 | VTV5 | 1080p |
| 5 | Vietnam Today | 1080p |
| 6 | HTV7 | 720p |
| 7 | Đồng Tháp 1 | 1080p |
| 8 | Đắk Lắk | 720p |
| 9 | Cà Mau | 576p |
| 10 | An Giang | 576p |
| 11 | ON KIDS | 1080p |

### Play in VLC

Open VLC, then **Media -> Open File** and select
`output/sctv_free_channels.m3u`. Or from PowerShell:

```powershell
& 'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe' 'output\sctv_free_channels.m3u'
```

Tested with **VLC 3.0.20 on Windows**: all 11 entries select the adaptive/HLS
demux and decode video and audio. You can re-run the check with:

```powershell
python verify_vlc_playlist.py
```

Each playlist entry includes:

```
#EXTVLCOPT:http-referrer=https://sctvonline.vn/
```

The CDN answers requests without the site Referer with a redirect to the SCTV
homepage, which is why a plain URL opened in VLC previously fell through to the
MPEG-PS demux. Players that ignore `#EXTVLCOPT` must set the same Referer
manually (e.g. mpv `--http-header-fields="Referer: https://sctvonline.vn/"`).

### Expiry and refresh

The stream URLs are signed and expire. Most channels receive URLs valid for
about 30 days; Cà Mau currently receives a shorter window (about five days).
The exact expiry for each channel is recorded in
`output/sctv_free_channels.json` and
`output/sctv_free_channels_report.md`. The checked-in playlist was last
rebuilt on **2026-10-28 07:30 UTC+7**.

Re-run the builder to fetch fresh URLs, re-verify them with `ffprobe`, and
rewrite the M3U/JSON/report:

```powershell
python refresh_multi_playlists.py --sctv-only
python verify_vlc_playlist.py   # optional VLC smoke test
```

`--sctv-only` runs the same SCTV builder without touching the multi-platform
outputs. Running `python refresh_multi_playlists.py` without a flag refreshes
both datasets. The standalone command still works:

```powershell
python build_free_m3u.py
```

The builder reads the free-channel list from `output/sctv_channels.csv`, calls
the same anonymous player endpoint the public detail page uses, and only adds
streams that pass verification.

## Channel and EPG data

| File | Contents |
|---|---|
| `output/sctv_channels.csv` | 94 channels with slug, premium flag, logo, and per-day programme counts |
| `output/sctv_schedule_3days.csv` | 9,228 programme rows (24/10: 3,076; 25/10: 3,055; 26/10: 3,097) |
| `output/sctv_schedule.html` | Interactive viewer with search, filters, and day tabs |
| `output/sctv_channels_schedule.xlsx` | Formatted workbook with channels and schedules |
| `output/sctv_data.json` | Full structured dataset |
| `output/sctv_report.md` | EPG coverage and source-quality report |
| `output/sctv_coverage.csv` | Per-channel coverage summary |
| `output/sctv_slug_name_map.csv` | Slug -> display-name lookup |
| `output/sctv_free_channels.json` | Stream metadata, probe results, and status for all 15 free channels |
| `output/sctv_free_channels_report.md` | Playlist report: included channels, exclusions, expiry, refresh |

EPG coverage: **70/94** channels have all three days, **22** have none, and
**2** are partial (`vtvcab7-a4f4497a`, `vtvcab20-01ae8160`).

The four free 24/7 content channels (`THỂ THAO 24/7`, `Việt Nam 360`,
`PHIM VIỆT 24/7`, `VŨ TRỤ HÀI`) are excluded from the M3U: their player API
returns no linear play link (`Chương trình này không có link play`).

## Scripts

| Script | Purpose |
|---|---|
| `sctv_extract.py` | Scrape channels/EPG, write CSV/JSON/XLSX, build the HTML viewer |
| `sctv_report.py` | Build the coverage report and slug/name map |
| `build_free_m3u.py` | Fetch fresh free-channel stream URLs, verify with `ffprobe`, write M3U/JSON/report |
| `refresh_multi_playlists.py` | Unified refresh: multi-platform streams + SCTV playlist (`--skip-sctv`, `--sctv-only`) |
| `build_public.py` | Stage generated files and a landing page in `public/` for Vercel |
| `verify_vlc_playlist.py` | Open each playlist entry in VLC and confirm HLS demux + audio/video decoding |
| `sctv_test_streams.py` | Raw ffprobe probe of the 11 free live streams |

Requirements: Python 3.10+, `pip install -r requirements.txt`, `ffprobe` on
PATH (optional for the builder; it falls back to an HTTP playlist check), and
VLC for the smoke test.

## Notes

- The schedule snapshot keeps source rows as returned; no silent deduplication
  or time correction is applied.
- Some streams are geo-restricted to Vietnam by the provider.
- Use this data for personal, lawful purposes and respect SCTV's terms of
  service and content rights.
