# Multi-platform Vietnamese TV — 3-day EPG and free/public M3U

Snapshot of **548 platform-channel listings** and **48,751 programme rows** for
**2026-10-27 through 2026-10-29** (`Asia/Ho_Chi_Minh`, UTC+7), plus VLC-ready
playlists for **151 platform streams** in the checked-in source-only snapshot.
The combined playlist has **144 entries** (98 TV360 + 46 VTVgo).

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

| Platform | Listings | EPG 27/10 | EPG 28/10 | EPG 29/10 | 3/3 days | Included streams |
|---|---:|---:|---:|---:|---:|---:|
| TV360 | 176 | 7,816 | 7,717 | 1,314 | 23/176 | 101 |
| FPT Play | 93 | 3,183 | 2,353 | 989 | 19/93 | 0 |
| HTV | 3 | 109 | 108 | 109 | 3/3 | 3 |
| VTVgo | 123 | 5,919 | 4,133 | 2,473 | 62/123 | 47 |
| MyTV | 153 | 6,464 | 6,064 | 0 | 0/153 | 0 |
| **Total** | **548** | **23,491** | **20,375** | **4,885** | **107/548** | **151** |

The figures above describe the latest source-only snapshot. The GitHub Actions
full rebuild refreshes the window to the current day plus two days whenever it
runs, so the generated `multi_platform_report.md` and web viewer always describe
the latest run. Third-day publication is uneven while providers publish it:
channels without a row for that date are left empty; no rows are copied
between platforms. Re-running the extractor later fills them when the provider
publishes.

The included-stream counts come from the source-only refresh: the provider's
public URL is kept after the free/non-DRM and VLC-host checks, without an
`ffprobe` media probe from the CI runner. FPT Play's short-lived tokens are not
usable from the US runner, and the combined playlist deliberately excludes
them.

## Playlists

| File | Entries | Token lifetime | Notes |
|---|---:|---|---|
| `output/all_free_channels.m3u` | 144 | hours | Combined playlist, one longest-lived source per normalized channel name |
| `output/tv360_free_channels.m3u` | 101 | ~6 hours | TV360 only |
| `output/fptplay_free_channels.m3u` | 0 | ~2-3 minutes | FPT Play only; empty when the US runner cannot get a token |
| `output/htv_free_channels.m3u` | 3 | HTV9 unknown, HTV7/HTV4 ~10 minutes | HTV only; open immediately after refresh |
| `output/vtvgo_free_channels.m3u` | 47 | ~1-15 hours | VTVgo only; local/VTV6 tokens can expire at 01:00 |
| `output/sctv_free_channels.m3u` | 11 | weeks (signed URL) | SCTV free/public channels; rebuilt by the same refresh command |
| MyTV | 0 | n/a | EPG only; anonymous playback returns `401 nologin_play_channel` |

The combined playlist contains **98 TV360 + 46 VTVgo** entries in the
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
| FPT Play | 0 | 91 | 0 | 0 | 2 |
| HTV | 3 | 0 | 0 | 0 | 0 |
| VTVgo | 47 | 62 | 0 | 0 | 14 |
| MyTV | 0 | 77 | 57 | 19 | 0 |
| **Total** | **151** | **253** | **85** | **33** | **26** |

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
  unreliable and stay in the EPG dataset but not in the playlists. VLC 3.0.24
  receives a fatal TLS alert from `vtvgolive-ott3`, `vtvgolive-liveh34`,
  `vtvgolive-liveh12` and `vtvgolive-vtclc`, so those hosts are blocked for
  playlists even when `ffprobe`/OpenSSL can read them. Provincial channels use
  the broadcasters' own public CDNs (`luuchieu.truyenhinhso.vn`,
  `kenhdp-vtvgo.vtvdigital.vn`) or the verified Hà Tĩnh fallback instead.
  Quảng Ngãi 1 is EPG-only because its only remaining source returns HTTP 400.
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
- Later refreshes added streams. The checked-in snapshot now has **144 combined
  entries (98 TV360 + 46 VTVgo)**. A full `ffprobe` sweep from Vietnam opened
  142/144; the two failures were transient `rr1-ateme` TLS resets and both
  opened in VLC on retry.
- The source-only playlist was also checked in VLC 3.0.24 for the channels that
  previously failed: Ninh Bình, Phú Thọ, Thanh Hóa, Đồng Tháp, Hà Tĩnh, Sơn La,
  Tuyên Quang, Cao Bằng, Lào Cai, Vĩnh Long 1, An Giang 2 and Cà Mau all opened
  successfully. No `liveh34`, `liveh12`, `ott3`, `vtclc`, `vod-` or `lsm-` URL
  remains in the combined playlist.
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
python refresh_multi_playlists.py --skip-sctv     # multi-platform only
python refresh_multi_playlists.py --sctv-only     # SCTV playlist only
python refresh_multi_playlists.py --source-only   # keep provider URLs, no media probe
```

`--source-only` is the mode used by GitHub Actions. It still calls the
providers' anonymous playback APIs, applies the free/non-DRM checks and drops
known-bad VLC hosts, but it does not run `ffprobe` against the media. Use it
when the refresh machine is outside Vietnam and the CDNs refuse to serve that
IP. It does **not** bypass geo-blocking: viewers still connect directly to the
public CDN from their own network. The SCTV playlist is preserved rather than
rebuilt, because SCTV verification is also geo-sensitive.

A full rebuild in source-only mode also carries forward a still-valid URL from
the previous `output/all_platform_data.json` when the provider API returns no
fresh link. This prevents a US runner from replacing a working playlist with a
handful of channels. It cannot create new URLs: TV360 tokens last about six
hours and VTVgo tokens 4-16 hours, so carried-forward entries expire unless a
machine in Vietnam refreshes them. The workflow still checks the entry count
before deploying, so an expired snapshot is not published silently.

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

- every 3 hours — refresh stream URLs in source-only mode, preserve the SCTV
  playlist, stage `public/`, deploy to Vercel;
- daily at 01:30 UTC+7 — run `multi_extract.py` first to rebuild the current
  3-day EPG, then run the same source-only refresh and deployment;
- manually — **Actions → Refresh playlists and deploy → Run workflow**, with an
  optional `full_rebuild` checkbox.

The job sets `IPTV_SOURCE_ONLY=1`, so both the full rebuild and the refresh
keep the provider-advertised URLs without probing the media from the US runner.
The validation step fails the job if the combined playlist drops below 100
entries, if any blocked host (`liveh34`, `liveh12`, `ott3`, `vtclc`, `vod-`,
`lsm-`) survives, or if the preserved SCTV playlist is empty.

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
   - `VERCEL_TOKEN` — Vercel **Account Settings → Tokens**, scope **Full
     Account**. A project-scoped token is rejected by the CLI when it retrieves
     the project.
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
The source-only mode avoids treating that as proof that the provider URL is
invalid: it keeps the public URL that the provider's own player advertises and
lets the viewer's player connect from Vietnam. This is not a proxy, VPN or
geo-bypass, and no login/premium/DRM check is skipped.

The trade-off is that CI cannot confirm that a URL currently returns media.
The host blocklist and expiry checks reduce the risk, but a provider can still
retire a URL between refreshes. More importantly, the US runner cannot obtain
fresh TV360/VTVgo playback URLs at all when those endpoints are geo-blocked;
carrying the previous URLs forward only postpones their expiry. For unattended
24/7 freshness, the robust upgrade is a small Vietnamese VPS, either running
the normal (non-source-only) refresh on a schedule or acting as a self-hosted
GitHub Actions runner. The workflow and Vercel deployment stay the same. The
project does not depend on the user's personal PC.

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
