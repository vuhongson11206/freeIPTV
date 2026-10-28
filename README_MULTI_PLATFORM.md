# Multi-platform Vietnamese TV — 3-day EPG and free/public M3U

Snapshot of **548 platform-channel listings** and **48,751 programme rows** for
**2026-10-27 through 2026-10-29** (`Asia/Ho_Chi_Minh`, UTC+7), plus VLC-ready
playlists for the **155 platform streams** in the checked-in snapshot that
passed a public, non-DRM audio/video probe.

The repository is also wired for automatic operation: GitHub Actions refreshes
the stream URLs every three hours, rebuilds the 3-day EPG daily for the current
window, and deploys `all_platform_epg.xml`, `all_free_channels.m3u`, the web
viewer and the SCTV playlist to Vercel. See
[GitHub Actions and Vercel](#github-actions-and-vercel).

Sources:

- TV360 — <https://tv360.vn/tv>
- FPT Play — <https://fptplay.vn/xem-truyen-hinh/>
- HTV — <https://htv.vn/truc-tuyen.htm>
- VTVgo — <https://vtvgo.vn/>
- MyTV — <https://mytv.com.vn/truyen-hinh>

Only the same anonymous public endpoints used by the providers' web players are
called. There is no login, subscription, paywall, geo-restriction or DRM bypass.
MyTV is **EPG-only** because every tested anonymous playback request requires a
logged-in account.

## Quick start

After the first GitHub Actions deployment, the generated files are available at
`https://<your-project>.vercel.app/`:

- `https://<your-project>.vercel.app/all_free_channels.m3u` — combined playlist
- `https://<your-project>.vercel.app/all_platform_epg.xml` — XMLTV EPG
- `https://<your-project>.vercel.app/all_platform_schedule.html` — web viewer
- `https://<your-project>.vercel.app/sctv_free_channels.m3u` — SCTV playlist

Locally, open the combined playlist in VLC:

```powershell
& 'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe' 'output\all_free_channels.m3u'
```

Or in VLC use **Media -> Open File** and select `output/all_free_channels.m3u`.
The per-platform playlists are in the same folder.

For EPG-aware players, load `output/all_platform_epg.xml` (XMLTV) together with
the M3U. Every M3U entry has a `tvg-id` of the form
`{platform}.{platform_channel_id}`, which matches the XMLTV channel id. The M3Us
also carry `tvg-name`, `tvg-logo`, `group-title` and the `http-referrer` option
needed by each CDN.

Browse the schedule in a browser:

```powershell
start output\all_platform_schedule.html
```

The viewer has platform tabs, date tabs for the current 3-day window, channel
search, channel selection and a note when a platform has not published a date.

## Coverage

| Platform | Listings | EPG 27/10 | EPG 28/10 | EPG 29/10 | 3/3 days | Verified streams |
|---|---:|---:|---:|---:|---:|---:|
| TV360 | 176 | 7,816 | 7,717 | 1,314 | 23/176 | 101 |
| FPT Play | 93 | 3,183 | 2,353 | 989 | 19/93 | 2 |
| HTV | 3 | 109 | 108 | 109 | 3/3 | 3 |
| VTVgo | 123 | 5,919 | 4,133 | 2,473 | 62/123 | 49 |
| MyTV | 153 | 6,464 | 6,064 | 0 | 0/153 | 0 |
| **Total** | **548** | **23,491** | **20,375** | **4,885** | **107/548** | **155** |

The figures above describe the initial 2026-10-28 snapshot. The GitHub Actions
full rebuild refreshes the window to the current day plus two days whenever it
runs, so the generated `multi_platform_report.md` and web viewer always describe
the latest run. Third-day publication is uneven while providers publish it:
channels without a row for that date are left empty; no rows are copied
between platforms. Re-running the extractor later fills them when the provider
publishes.

## Playlists

| File | Entries | Token lifetime | Notes |
|---|---:|---|---|
| `output/all_free_channels.m3u` | 146 | hours | Combined playlist, one longest-lived verified stream per normalized channel name |
| `output/tv360_free_channels.m3u` | 101 | ~6 hours | TV360 only |
| `output/fptplay_free_channels.m3u` | 2 | ~2-3 minutes | FPT Play only; open immediately after refresh |
| `output/htv_free_channels.m3u` | 3 | HTV9 unknown, HTV7/HTV4 ~10 minutes | HTV only; open immediately after refresh |
| `output/vtvgo_free_channels.m3u` | 49 | ~1-15 hours | VTVgo only; local/VTV6 tokens can expire at 01:00 |
| `output/sctv_free_channels.m3u` | 11 | weeks (signed URL) | SCTV free/public channels; rebuilt by the same refresh command |
| MyTV | 0 | n/a | EPG only; anonymous playback returns `401 nologin_play_channel` |

The combined playlist contains **97 TV360 + 49 VTVgo** entries in the
checked-in snapshot. It deliberately excludes FPT Play and HTV7/HTV4 because
those CDN tokens last only minutes and cannot be kept fresh by a normal refresh
task. HTV7, HTV4 and HTV9 are still represented in the combined playlist through
TV360's roughly six-hour URLs. The short-lived FPT/HTV files remain available
separately for immediate use.

Static, unsigned versions of the FPT and HTV URLs were tested and rejected by
the CDNs with HTTP 403, so the tokens cannot simply be removed.

## Exclusions

| Platform | Included | Login required | Paid/premium | DRM | No public stream |
|---|---:|---:|---:|---:|---:|
| TV360 | 101 | 23 | 28 | 14 | 10 |
| FPT Play | 2 | 91 | 0 | 0 | 0 |
| HTV | 3 | 0 | 0 | 0 | 0 |
| VTVgo | 49 | 62 | 0 | 0 | 12 |
| MyTV | 0 | 77 | 57 | 19 | 0 |
| **Total** | **155** | **253** | **85** | **33** | **22** |

Notable cases:

- **FPT Play** — 91 channels are listed with EPG but their public stream
  endpoint returns HTTP 401 even when `is_vip=0`. Only VTV1 HD and the
  `fpt-play` promo channel returned a public 200 HLS stream.
- **MyTV** — all tested anonymous playback calls, including VTV1, ANTV, HTV9
  and international channels, require login. No MyTV stream is placed in any
  playlist.
- **VTVgo** — 62 channels require login. Seven `VTVgo · ...` theme channels
  point at `fast-channel-stg.vtvdigital.vn`, a staging host rather than the
  production CDN; two full VLC sweeps opened 0/7 and 4/7 of them, so they are
  unreliable and stay in the EPG dataset but not in the playlists. The
  `vtvgolive-ott3.vtvdigital.vn` host fails the TLS handshake in VLC, so it is
  blocked for playlists; Hà Tĩnh uses its verified public fallback CDN, while
  Gia Lai has no alternative and is EPG-only.
- **TV360** — paid, login-only and DRM channels keep their EPG rows but are
  excluded from the M3U.
- **HTV** — all three public channels are playable and have EPG for all three
  days, but the HTV7/HTV4 JWT is short-lived.

## Verification

The initial snapshot was checked in VLC 3.0.21 with the dummy video/audio
output:

- All 96 TV360 entries present in the combined playlist at that time opened in
  a full sweep. `AFN HD` failed once because the harness checked too early and
  passed on a 20-second retest.
- The then 48-entry VTVgo playlist opened 40/48 in the first sweep. With a
  longer 20-second window, six of the eight failures passed; Hà Tĩnh's primary
  host failed but its public fallback CDN opened; Gia Lai's only source failed
  TLS and was removed.
- Later refreshes added streams. The checked-in snapshot now has **146 combined
  entries (97 TV360 + 49 VTVgo)**; every included URL passed the automated
  `ffprobe` audio/video check, while the VLC sweep above covers the earlier
  96 + 47 set.
- VLC runs must use `--no-crashdump`. A leftover "VLC crash reporting" window
  from a force-killed process blocks later launches and makes every entry look
  like a failure.

## Refresh

Refresh the stream URLs, multi-platform outputs **and** the SCTV playlist in one
command (the EPG snapshot is kept):

```powershell
python refresh_multi_playlists.py
```

This re-probes the public stream endpoints, rewrites the per-platform and
combined M3Us, updates the JSON/CSV metadata, regenerates the report/XMLTV/HTML
viewer, and rebuilds `output/sctv_free_channels.m3u` from
`output/sctv_channels.csv`.

Useful flags:

```powershell
python refresh_multi_playlists.py --skip-sctv   # multi-platform only
python refresh_multi_playlists.py --sctv-only   # SCTV playlist only
```

The Windows wrapper forwards the same flags:

```powershell
.\refresh_multi_playlists.cmd --skip-sctv
```

To re-extract the EPG for the current 3-day window:

```powershell
python multi_extract.py
python multi_report.py
```

`multi_extract.py` starts the window on today's date in `Asia/Ho_Chi_Minh` by
default. Override it with `--start-date YYYY-MM-DD` and `--days N`.

### GitHub Actions and Vercel

The workflow in `.github/workflows/refresh.yml` runs automatically:

- every 3 hours — refresh stream URLs, rebuild outputs and the SCTV playlist,
  stage `public/`, deploy to Vercel;
- daily at 01:30 UTC+7 — run `multi_extract.py` first to rebuild the current
  3-day EPG, then run the same refresh and deployment;
- manually — **Actions → Refresh playlists and deploy → Run workflow**, with an
  optional `full_rebuild` checkbox.

To enable deployment:

1. Put the project in a GitHub repository. If Git is not installed locally,
   the simplest route is GitHub Desktop:
   - install it from <https://desktop.github.com/>;
   - **File → Add Local Repository**, select this folder, and choose
     **create a repository** when prompted;
   - review the changes. `.gitignore` keeps `data/`, `public/`, `.vercel/`
     and caches out of the commit;
   - commit and **Publish repository**.

   Alternatively, create an empty repository on GitHub and use
   **Add file → Upload files** in the browser. Upload the project files but
   **not** `data/`, `public/`, `__pycache__/`, `CpuScan/` or
   `cpuscan_after_pair.png`; `public/` is generated in CI.

2. Create the Vercel project. In the Vercel dashboard choose **Add New →
   Project**. You can import the GitHub repository, but the first Git build
   may fail because `public/` is generated and gitignored; that is expected.
   If the dashboard offers **Deploy without Git**, that also works.
   `vercel.json` disables Git-triggered deployments, so later pushes will not
   start duplicate builds.

3. Copy the two IDs:
   - **Project ID** — project → **Settings → General → Project ID**.
   - **Org ID** — team settings → **General → Team ID**; for a personal
     account use the account ID shown in **Account Settings**, or run
     `vercel link` once on a machine with Node.js and read `orgId` from
     `.vercel/project.json`.

4. In GitHub, open **Settings → Secrets and variables → Actions** and add:
   - `VERCEL_TOKEN` — Vercel **Account Settings → Tokens**.
   - `VERCEL_ORG_ID`
   - `VERCEL_PROJECT_ID`

5. Open **Actions → Refresh playlists and deploy → Run workflow**. Tick
   `full_rebuild` for the first run so the EPG window starts at today's date.
   Check the job summary for the deployment URL. If the secrets are absent,
   the workflow still generates and uploads `public/` as an artifact, but
   skips the Vercel step.

`vercel.json` sets the M3U/XML content types and cache headers.
`build_public.py` copies the generated files plus a landing page into `public/`.
The `git.deploymentEnabled=false` setting prevents a push from triggering a
second, unrelated Vercel build.

GitHub-hosted runners are outside Vietnam. Some providers may geo-block those
addresses, so a CI run can verify fewer streams than a local run in Vietnam.
The workflow does not use any geo-bypass; it only calls the same anonymous
public endpoints as the providers' web players.

GitHub may pause scheduled workflows after a long period without repository
activity. Re-enable or manually run the workflow from the Actions tab if that
happens.

### Optional local scheduler

The old Windows Scheduled Task is still included:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_refresh_task.ps1
```

It runs `refresh_multi_playlists.py` every 3 hours with the project folder as
the working directory. Remove it with:

```powershell
Unregister-ScheduledTask -TaskName "MultiPlatformIPTVRefresh" -Confirm:$false
```

Token behaviour:

| Platform | Observed lifetime | Recommendation |
|---|---|---|
| TV360 | ~6 hours | 3-hour scheduled refresh is sufficient |
| VTVgo | ~1-15 hours; local/VTV6 can expire at 01:00 | Refresh after 01:00 if watching local channels |
| HTV9 | `rkey` URL, no parsed expiry | Refresh before use |
| HTV7/HTV4 | ~10 minutes | Run refresh, then open the HTV playlist immediately |
| FPT Play | ~2-3 minutes | Run refresh, then open the FPT playlist immediately |
| MyTV | n/a | No public playback |

If a short-lived per-platform playlist matters, run `refresh_multi_playlists.py`
immediately before opening it. The combined playlist is the stable option.

## Files

| File | Contents |
|---|---|
| `output/all_platform_channels.csv` | One row per platform-channel with EPG counts, stream status, URL and expiry |
| `output/all_platform_schedule_3days.csv` | All 48,751 normalized programme rows |
| `output/all_platform_data.json` | Structured channels + schedules |
| `output/all_platform_epg.xml` | XMLTV EPG, 548 channels / 48,751 programmes |
| `output/all_platform_schedule.html` | Interactive EPG viewer |
| `output/platform_coverage.csv` | Coverage per platform-channel |
| `output/unique_channels.csv` | 374 deduplicated channel names with source platforms and best stream |
| `output/tv360_*`, `output/fptplay_*`, `output/htv_*`, `output/vtvgo_*`, `output/mytv_*` | Per-platform channels, schedule, stream JSON and M3U where applicable |
| `output/multi_platform_report.md` | Human-readable coverage, stream and refresh report |
| `output/sctv_free_channels.m3u` | SCTV free/public playlist rebuilt by `refresh_multi_playlists.py` |
| `output/stream_refresh_status.json` | Last refresh time, counts, SCTV result and token expiry range |
| `build_public.py` | Stage generated files, landing page and `vercel.json` in `public/` |
| `.github/workflows/refresh.yml` | Scheduled refresh, daily EPG rebuild, validation and Vercel deploy |
| `requirements.txt` | Python dependencies (`cryptography`; `openpyxl` for SCTV XLSX export) |
| `vercel.json` | Static hosting headers, content types and cache policy |

## Method and compliance

- Catalogues, schedules and playback URLs come from the providers' public web
  endpoints, using the same anonymous requests a browser makes.
- A channel is placed in an M3U only when the public playback response is clear
  (non-DRM) and `ffprobe` reads a video stream from the returned HLS URL.
- No credentials, cookies, subscription tokens, paywall logic, geo bypass or
  DRM decryption are used.
- EPG rows are kept as each provider publishes them. HTV and MyTV publish start
  times without end times; their end times are derived from the next programme
  (last programme +30 minutes) and flagged with `end_estimated=yes`.
- The completed SCTV EPG dataset remains in place: `output/sctv_data.json`,
  `output/sctv_schedule_3days.csv`, `README.md` and the SCTV extractor scripts
  are unchanged. The unified refresh only rebuilds the SCTV free-channel
  playlist from the existing `output/sctv_channels.csv`.

Use for personal, lawful purposes and respect each provider's terms of service.
