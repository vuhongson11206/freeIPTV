# Multi-platform Vietnamese TV - EPG and free/public M3U

Snapshot of **548 platform-channel listings** and **48,751 programme rows** for **2026-10-27 through 2026-10-29** (`Asia/Ho_Chi_Minh`, UTC+7).

The combined playlist contains **146 deduplicated free channels**; **155 platform streams** passed an ffprobe audio/video check. Only public, non-DRM streams are included. No login, subscription, paywall or DRM bypass is used.

Generated: `2026-10-28T07:26:54+07:00`

## Coverage by platform

| Platform | Listed | EPG 27/10 | EPG 28/10 | EPG 29/10 | 3/3 days | Streams verified | M3U source |
|---|---:|---:|---:|---:|---:|---:|---:|
| TV360 | 176 | 7,816 | 7,717 | 1,314 | 23/176 | 101 | `tv360_free_channels.m3u` |
| FPT Play | 93 | 3,183 | 2,353 | 989 | 19/93 | 2 | `fptplay_free_channels.m3u` |
| HTV | 3 | 109 | 108 | 109 | 3/3 | 3 | `htv_free_channels.m3u` |
| VTVgo | 123 | 5,919 | 4,133 | 2,473 | 62/123 | 49 | `vtvgo_free_channels.m3u` |
| MyTV | 153 | 6,464 | 6,064 | 0 | 0/153 | 0 | — (EPG only) |
| **Total** | **548** | **23,491** | **20,375** | **4,885** | **107/548** | **155** | `all_free_channels.m3u` |

### Why 29/10 may be incomplete on some platforms

Provider publication of the third day is uneven. At capture time (`2026-10-28T07:26:54+07:00`), these were the 2026-10-29 row counts:

| Platform | Channels with data | Rows |
|---|---:|---:|
| TV360 | 23/176 | 1,314 |
| FPT Play | 19/93 | 989 |
| HTV | 3/3 | 109 |
| VTVgo | 62/123 | 2,473 |
| MyTV | 0/153 | 0 |

Channels without a row for that date are left empty; no rows are copied between platforms. Re-running `multi_extract.py` later fills them when the provider publishes.

## Playlists

| File | Entries | Notes |
|---|---:|---|
| `output/all_free_channels.m3u` | 146 | Combined, one longest-lived verified public stream per normalized channel name |
| `output/tv360_free_channels.m3u` | 101 | TV360 only; tokens last about 6 hours |
| `output/fptplay_free_channels.m3u` | 2 | FPT Play only; tokens expire in about 2-3 minutes - open immediately |
| `output/htv_free_channels.m3u` | 3 | HTV only; HTV7/HTV4 JWTs expire in about 10 minutes |
| `output/vtvgo_free_channels.m3u` | 49 | VTVgo only; tokens last about 1-15 hours (local channels may expire at 01:00) |
| — | 0 | MyTV is EPG-only; anonymous playback returns 401 |

Each entry carries `tvg-id`, `tvg-name`, `tvg-logo`, `group-title` and the platform Referer required by the CDN. Open the combined playlist in VLC via **Media -> Open File**.

The combined playlist contains TV360 (97), VTVgo (49) in this snapshot. It prefers one verified public stream per normalized channel name and the longest remaining token. Very short-lived FPT Play and HTV7/HTV4 tokens are kept only in their per-platform playlists; HTV7, HTV4 and HTV9 may still appear in the combined list through TV360's longer-lived tokens. The short-lived per-platform entries remain in `fptplay_free_channels.m3u` and `htv_free_channels.m3u`.

Combined-token expiry range in this snapshot: earliest **2026-10-28 11:29 UTC+7**, latest **2026-10-29 07:28 UTC+7**. Run `python refresh_multi_playlists.py` every 2-3 hours (or let the GitHub Actions workflow do it) to renew TV360 and VTVgo URLs. If you watch VTVgo local channels late at night, refresh after 01:00 because their current token may expire then.

### Short-lived tokens

Static/unsigned replacements were tested and rejected by the CDNs, so the tokens cannot be removed. Measured lifetimes:

| Platform | Token lifetime | Handling |
|---|---|---|
| TV360 | about 6 hours | Included in combined M3U; refreshed every 3 hours |
| VTVgo | about 1-15 hours; local/VTV6 tokens can expire at 01:00 | Included in combined M3U; refresh after midnight if watching local channels |
| HTV9 | `rkey` URL, no parsed expiry | Included per-platform; TV360 copy used in combined |
| HTV7 / HTV4 | about 10 minutes (JWT `exp`) | Per-platform only; open immediately after refresh |
| FPT Play | about 2-3 minutes (`sign` epoch) | Per-platform only; open immediately after refresh |
| MyTV | n/a | No anonymous playback; EPG only |

## Stream inclusions and exclusions

| Status | Channels | Meaning |
|---|---:|---|
| `excluded_login` | 253 | Excluded: login required |
| `included` | 155 | Included in M3U (verified) |
| `excluded_paid` | 85 | Excluded: paid/premium |
| `excluded_drm` | 33 | Excluded: DRM |
| `excluded_no_stream` | 22 | No public stream / probe failed |

### Included channels by platform

**TV360** (101)

| Channel | Resolution | Expiry (UTC+7) |
|---|---:|---|
| VTV1 | 1080p | 2026-10-28T13:26:54+07:00 |
| HTV4 | 1080p | 2026-10-28T13:26:54+07:00 |
| HTVC gia đình | 1080p | 2026-10-28T13:26:54+07:00 |
| HTVC phụ Nữ | 1080p | 2026-10-28T13:26:54+07:00 |
| HTVC thuần việt | 1080p | 2026-10-28T13:26:57+07:00 |
| HTVC phim truyện HD | 1080p | 2026-10-28T13:26:57+07:00 |
| QPVN HD | 1080p | 2026-10-28T13:26:57+07:00 |
| ANTV | 1080p | 2026-10-28T13:26:57+07:00 |
| Vĩnh Long 1 | 1080p | 2026-10-28T13:27:00+07:00 |
| Vĩnh Long 2 | 1080p | 2026-10-28T13:27:00+07:00 |
| Hà Nội 1 | 1080p | 2026-10-28T13:27:03+07:00 |
| Hà Nội 2 | 1080p | 2026-10-28T13:27:03+07:00 |
| An Giang 2 | 1080p | 2026-10-28T13:27:06+07:00 |
| Bắc Ninh | 1080p | 2026-10-28T13:27:06+07:00 |
| Lâm Đồng 2 | 1080p | 2026-10-28T13:27:09+07:00 |
| Cà Mau | 1080p | 2026-10-28T13:27:09+07:00 |
| Cần Thơ 1 | 1080p | 2026-10-28T13:27:09+07:00 |
| Cao Bằng | 1080p | 2026-10-28T13:27:09+07:00 |
| Đà Nẵng 1 | 1080p | 2026-10-28T13:27:09+07:00 |
| Đắk Lắk | 1080p | 2026-10-28T13:27:12+07:00 |
| Điện Biên | 1080p | 2026-10-28T13:27:12+07:00 |
| Đồng Nai 1 | 1080p | 2026-10-28T13:27:12+07:00 |
| Đồng Tháp 1 | 1080p | 2026-10-28T13:27:12+07:00 |
| Hà Tĩnh | 1080p | 2026-10-28T13:27:15+07:00 |
| Hải Phòng 3 | 1080p | 2026-10-28T13:27:15+07:00 |
| Hải Phòng | 1080p | 2026-10-28T13:27:15+07:00 |
| Cần Thơ 2 | 1080p | 2026-10-28T13:27:15+07:00 |
| Huế | 1080p | 2026-10-28T13:27:18+07:00 |
| Hưng Yên | 1080p | 2026-10-28T13:27:21+07:00 |
| Khánh Hòa | 1080p | 2026-10-28T13:27:21+07:00 |
| An Giang 1 | 1080p | 2026-10-28T13:27:21+07:00 |
| Lai Châu | 1080p | 2026-10-28T13:27:21+07:00 |
| Lâm Đồng 1 | 1080p | 2026-10-28T13:27:21+07:00 |
| Lạng Sơn | 1080p | 2026-10-28T13:27:24+07:00 |
| Lào Cai | 1080p | 2026-10-28T13:27:24+07:00 |
| Tây Ninh 1 | 1080p | 2026-10-28T13:27:24+07:00 |
| Nghệ An | 1080p | 2026-10-28T13:27:24+07:00 |
| Ninh Bình | 1080p | 2026-10-28T13:27:24+07:00 |
| Khánh Hòa 1 | 1080p | 2026-10-28T13:27:27+07:00 |
| Phú Thọ | 1080p | 2026-10-28T13:27:27+07:00 |
| Đà Nẵng 2 | 1080p | 2026-10-28T13:27:27+07:00 |
| Quảng Ngãi | 1080p | 2026-10-28T13:27:27+07:00 |
| Quảng Ninh 1 | 1080p | 2026-10-28T13:27:30+07:00 |
| Quảng Trị | 1080p | 2026-10-28T13:27:30+07:00 |
| Cần Thơ 3 | 1080p | 2026-10-28T13:27:30+07:00 |
| Sơn La | 1080p | 2026-10-28T13:27:30+07:00 |
| Thái Nguyên | 1080p | 2026-10-28T13:27:33+07:00 |
| Thanh Hóa | 1080p | 2026-10-28T13:27:33+07:00 |
| Đồng Tháp 2 | 1080p | 2026-10-28T13:27:33+07:00 |
| Vĩnh Long 5 | 1080p | 2026-10-28T13:27:33+07:00 |
| Tuyên Quang | 1080p | 2026-10-28T13:27:33+07:00 |
| France 24 | 1080p | 2026-10-28T13:27:33+07:00 |
| NHK | 1080p | 2026-10-28T13:27:36+07:00 |
| DW | 1080p | 2026-10-28T13:27:36+07:00 |
| VTV5 | 1080p | 2026-10-28T13:27:39+07:00 |
| Arirang | 1080p | 2026-10-28T12:51:39+07:00 |
| Channel News Asia | 1080p | 2026-10-28T13:27:39+07:00 |
| HTVC+ Channel B | 1080p | 2026-10-28T13:27:39+07:00 |
| HTVC du lịch & cuộc sống | 1080p | 2026-10-28T13:27:39+07:00 |
| Quảng Ninh 3 | 1080p | 2026-10-28T13:27:39+07:00 |
| O2TV | 1080p | 2026-10-28T13:27:42+07:00 |
| An Viên HD | 1080p | 2026-10-28T13:27:42+07:00 |
| VTVcab10 - On Cine HD | 1080p | 2026-10-28T13:27:42+07:00 |
| VTVcab19 – Vie Dramas | 1080p | 2026-10-28T13:27:45+07:00 |
| VTVcab 8 Bibi SD | 1080p | 2026-10-28T13:27:45+07:00 |
| VTVcab 21- Cartoon Kids HD | 1080p | 2026-10-28T13:27:45+07:00 |
| VTVcab 1 - Vie Giải Trí HD | 1080p | 2026-10-28T13:27:45+07:00 |
| Vtvcab 4 – On Movies | 1080p | 2026-10-28T13:27:45+07:00 |
| VTVcab 5 - E Channel HD | 1080p | 2026-10-28T13:27:48+07:00 |
| VTVcab 12 - StyleTV HD | 1080p | 2026-10-28T13:27:48+07:00 |
| VTVcab15 – On Music | 1080p | 2026-10-28T13:27:48+07:00 |
| Vtvcab17 – Trending TV | 1080p | 2026-10-28T13:27:48+07:00 |
| VTVcab 20 - V Family HD | 1080p | 2026-10-28T13:27:51+07:00 |
| VTVcab 22 - Life TV HD | 1080p | 2026-10-28T13:27:51+07:00 |
| VTVcab 9 - InfoTV HD | 1080p | 2026-10-28T13:27:51+07:00 |
| HTV1 | 1080p | 2026-10-28T13:27:51+07:00 |
| HTV2 | 1080p | 2026-10-28T13:27:54+07:00 |
| HTV3 | 1080p | 2026-10-28T13:27:54+07:00 |
| HTV7 HD | 1080p | 2026-10-28T13:27:54+07:00 |
| HTV9 HD | 1080p | 2026-10-28T13:27:54+07:00 |
| SCTV2 - Today TV | 1080p | 2026-10-28T13:27:54+07:00 |
| KBS World | 1080p | 2026-10-28T13:27:57+07:00 |
| AFN HD | 1080p | 2026-10-28T13:27:57+07:00 |
| Outdoor HD | 1080p | 2026-10-28T13:27:57+07:00 |
| Vĩnh Long 3 | 1080p | 2026-10-28T13:28:00+07:00 |
| Vĩnh Long 4 | 1080p | 2026-10-28T13:28:00+07:00 |
| SCTV6 | 1080p | 2026-10-28T13:28:00+07:00 |
| Đồng Nai | 1080p | 2026-10-28T13:28:03+07:00 |
| TV5 | 1080p | 2026-10-28T13:28:03+07:00 |
| CNBC | 1080p | 2026-10-28T13:28:03+07:00 |
| History HD | 1080p | 2026-10-28T13:28:03+07:00 |
| Kix | 1080p | 2026-10-28T13:28:06+07:00 |
| FM96 | 1080p | 2026-10-28T13:28:06+07:00 |
| VIETNAM TODAY HD | 1080p | 2026-10-28T13:28:06+07:00 |
| Livestream 01 | 1080p | 2026-10-29T07:28:06+07:00 |
| France 24 SD | 576p | 2026-10-28T13:28:09+07:00 |
| VOH AM610 | 1080p | 2026-10-28T13:28:09+07:00 |
| VOH FM99 | 1080p | 2026-10-28T13:28:09+07:00 |
| VOH FM87 | 1080p | 2026-10-28T13:28:09+07:00 |
| VOH FM95 | 1080p | 2026-10-28T12:52:12+07:00 |
| VOH FM92 Radio | 1080p | 2026-10-28T13:28:12+07:00 |

**FPT Play** (2)

| Channel | Resolution | Expiry (UTC+7) |
|---|---:|---|
| Chuỗi Thể thao & Giải trí | 1080p | 2026-10-28T07:28:42+07:00 |
| VTV1 HD | 1080p | 2026-10-28T07:28:42+07:00 |

**HTV** (3)

| Channel | Resolution | Expiry (UTC+7) |
|---|---:|---|
| HTV9 | 1080p | - |
| HTV7 | 1080p | 2026-10-28T07:34:47+07:00 |
| HTV4 | 720p | 2026-10-28T07:34:59+07:00 |

**VTVgo** (49)

| Channel | Resolution | Expiry (UTC+7) |
|---|---:|---|
| VTV1 | 720p | 2026-10-28T23:29:00+07:00 |
| VTV2 | 720p | 2026-10-28T23:29:00+07:00 |
| VTV3 | 720p | 2026-10-28T23:29:00+07:00 |
| VTV4 | 720p | 2026-10-28T23:29:00+07:00 |
| VTV5 | 720p | 2026-10-28T23:29:00+07:00 |
| VTV10 | 720p | 2026-10-28T23:29:02+07:00 |
| VTV5 Tây Nam Bộ | 720p | 2026-10-28T23:29:02+07:00 |
| VTV6 | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Hà Nội 2 | 720p | 2026-10-29T01:00:00+07:00 |
| VTV7 | 720p | 2026-10-28T23:29:03+07:00 |
| VTV8 | 360p | 2026-10-28T23:29:04+07:00 |
| VTV9 | 720p | 2026-10-28T23:29:04+07:00 |
| Truyền hình Công an Nhân dân | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Quốc phòng Việt Nam | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Hà Nội 1 | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Quảng Ninh 1 | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Quảng Ninh 3 | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Nghệ An | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Khánh Hòa | 720p | 2026-10-29T01:00:00+07:00 |
| Đài PTTH tỉnh Thừa Thiên Huế | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Đồng Tháp 1 | 720p | 2026-10-29T01:00:00+07:00 |
| VTV5 Tây Nguyên | 720p | 2026-10-28T23:29:08+07:00 |
| Truyền hình Đà Nẵng 1 | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Thanh Hóa | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Ninh Bình | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Hưng Yên | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Cà Mau | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Bắc Ninh | 720p | 2026-10-28T11:29:10+07:00 |
| Truyền hình Đắk Lắk | 1080p | - |
| Truyền hình Lâm Đồng | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Lai Châu | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Phú Thọ | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Điện Biên | 720p | - |
| Truyền hình An Giang | 720p | 2026-10-28T11:29:13+07:00 |
| Truyền hình Đồng Nai 1 | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Tuyên Quang | 720p | 2026-10-28T11:29:14+07:00 |
| Truyền hình Quảng Trị | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Thái Nguyên | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Cần Thơ 1 | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Lào Cai | 720p | 2026-10-28T11:29:18+07:00 |
| Truyền hình Sơn La | 720p | - |
| Truyền hình Tây Ninh 1 | 480p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Lạng Sơn | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Hà Tĩnh | 720p | - |
| Truyền hình Hải Phòng | 720p | 2026-10-29T01:00:00+07:00 |
| Truyền hình Cao Bằng | 720p | 2026-10-28T11:29:24+07:00 |
| Truyền hình Vĩnh Long 1 | 720p | 2026-10-28T13:29:25+07:00 |
| Truyền hình HTV9 | 720p | 2026-10-29T01:00:00+07:00 |
| VIETNAM TODAY | 720p | 2026-10-28T13:29:26+07:00 |

## Platform notes

- **TV360** - channel catalogue from the public `tv360.vn/tv` page; 3-day EPG from `get-live-schedule`; free streams from `composite/get-link`. The CDN rotates between `fo-hlc`, `rr1-ateme`, `livestream` and VOD-style hosts; each URL is probed and retried before inclusion.
- **FPT Play** - 93 EPG channels from the signed public `api.fptplay.net` endpoints. Although many channels have `is_vip=0`, only 2 returned a public, playable HLS stream in this snapshot; the rest remain in the EPG dataset but not in the M3U. The playable FPT URLs expire in about 2-3 minutes, so they are kept in `fptplay_free_channels.m3u` but not in the combined playlist.
- **HTV** - 3 channels listed on `htv.vn/truc-tuyen.htm` (HTV9, HTV7, HTV4); 3 have verified public HLS. HTV9 uses the HTVm share endpoint with an HMAC timestamp; HTV7/HTV4 use the public HTVC iframe JWPlayer URL. HTV7/HTV4 JWTs expire in about 10 minutes, so the combined playlist prefers their TV360 equivalents.
- **VTVgo** - 123 unique catalogue channels, 61 not requiring login and 49 with a verified stream. EPG follows the same 3-day window; the third day can be partial while the provider publishes it. Playback is requested only for anonymous channels and only `sourceModes[0].isVip=0` clear HLS is kept. Every advertised HLS source for a channel is probed and the first working one is kept, so a broken primary CDN can fall back to the provider's backup. The seven `VTVgo · ...` theme channels use `fast-channel-stg.vtvdigital.vn`, a staging host rather than the production CDN. Two full VLC sweeps opened 0/7 and 4/7 of them, so they are unreliable; they stay in the EPG dataset but are excluded from the playlists. The `vtvgolive-ott3.vtvdigital.vn` host fails the TLS handshake in VLC and is blocked for playlists; Hà Tĩnh uses a verified public fallback CDN, while Gia Lai has no alternative and is EPG-only.
- **MyTV** - 153 EPG channels. Every tested anonymous playback request, including VTV1, ANTV, HTV9 and international channels, returned `401 nologin_play_channel`. MyTV is therefore **EPG-only**; no MyTV URL is placed in any playlist. The extractor renews the anonymous MyTV token when it collects EPG; the stream refresher leaves MyTV untouched.

## Verification

Streams are probed with `ffprobe` during extraction and refresh. The initial snapshot was also checked in VLC 3.0.21 with the dummy video/audio output; that manual sweep covered the TV360 and VTVgo entries in the combined playlist at the time.
- Current combined playlist: **146** entries (TV360 97, VTVgo 49).
- VLC must be run with `--no-crashdump`; a leftover crash-reporter dialog from a force-killed process blocks later launches and produces false failures.

## Data files

| File | Contents |
|---|---|
| `output/all_platform_channels.csv` | One row per platform-channel with EPG counts, stream status, URL and expiry |
| `output/all_platform_schedule_3days.csv` | Normalized programme rows for all platforms |
| `output/all_platform_data.json` | Full structured channels + schedules |
| `output/all_platform_epg.xml` | XMLTV EPG using the same tvg-id values as the M3Us |
| `output/all_platform_schedule.html` | Interactive viewer with platform/date/search filters |
| `output/platform_coverage.csv` | Coverage summary per platform-channel |
| `output/unique_channels.csv` | Deduplicated channel list with source platforms and best public stream |
| `output/{platform}_channels.csv` | Per-platform channel metadata |
| `output/{platform}_schedule_3days.csv` | Per-platform schedule rows |
| `output/{platform}_free_channels.json` | Per-platform stream/probe details |
| `output/sctv_free_channels.m3u` | SCTV free/public playlist, refreshed by the same command |
| `output/stream_refresh_status.json` | Last refresh time, counts and expiry range |

## Refresh

Unified local refresh (stream URLs + SCTV playlist):

```powershell
python refresh_multi_playlists.py
```

The EPG snapshot is kept; stream URLs are re-probed and the per-platform and combined M3Us, XMLTV, HTML viewer, report and SCTV playlist are rebuilt. Use `--skip-sctv` to refresh only the multi-platform outputs or `--sctv-only` to rebuild only the SCTV playlist.

Full EPG re-extraction for the current 3-day window:

```powershell
python multi_extract.py
python multi_report.py
```

GitHub Actions runs the unified refresh every three hours and a full EPG rebuild daily. Configure `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` secrets to deploy the staged `public/` folder to Vercel. See `README_MULTI_PLATFORM.md`.

Optional local fallback: register the included Windows Scheduled Task with `powershell -ExecutionPolicy Bypass -File .\setup_refresh_task.ps1`.

## Method and compliance

The extractor calls the same public, anonymous endpoints used by the providers' web players. It does not log in, purchase entitlements, bypass geo/paywall checks, decrypt protected media or remove DRM. A channel is included only when the public endpoint returns a clear HLS URL and ffprobe successfully decodes a video stream.

EPG rows are kept as returned by each source. HTV and MyTV publish start times without explicit end times, so their end times are derived from the next programme (last programme +30 minutes) and flagged in the `end_estimated` column. No schedule rows are shared between platforms.

Use for personal, lawful purposes and respect each provider's terms.
