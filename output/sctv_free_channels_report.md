# SCTV Online - Free Channels M3U

- Generated: **2026-10-28T07:30:30+07:00** (Asia/Ho_Chi_Minh)
- Source: <https://sctvonline.vn>
- Free channels found: **15**
- Verified live streams in playlist: **11**
- Free VOD-only channels (not in playlist): **4**
- Unavailable / unplayable: **0**
- Playlist: `sctv_free_channels.m3u`
- Earliest signed-URL expiry: **2026-11-02 07:30 UTC+07:00** (Đài PT-TH CÀ MAU)

Only channels with `is_premium=no` are included. No account login,
premium entitlement, paywall or DRM bypass is used.

## Playlist channels

| # | Channel | Resolution | Signed URL expires | Stream |
|---:|---|---|---|---|
| 1 | VTV1 | 1080p | 2026-11-27 07:29 UTC+07:00 | [HLS](https://e11.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/jRgCpgzW3VyoRIGzWDZHcA/1795739377/anonymous/live/vtv1/master.m3u8) |
| 2 | Truyền hình Quốc phòng Việt Nam- QPVN | 1080p | 2026-11-27 07:29 UTC+07:00 | [HLS](https://e15.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/d28tT5pEnPCp8jT060wnmA/1795739385/anonymous/live/quocphongvn/master.m3u8) |
| 3 | Truyền hình Công an nhân dân - ANTV | 720p | 2026-11-27 07:29 UTC+07:00 | [HLS](https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/yWVPZHls9NwCmaZXiM_AuA/1795739393/anonymous/live/hls/antv/index.m3u8) |
| 4 | VTV5-Truyền hình dân tộc | 1080p | 2026-11-27 07:29 UTC+07:00 | [HLS](https://e10.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/J2etFtMR4CYvZpZwhTDz8Q/1795739395/anonymous/live/vtv5/master.m3u8) |
| 5 | Kênh truyền hình đối ngoại quốc gia - Vietnam Today | 1080p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/-bXStkB26U1N11Z8CA96AQ/1795739401/anonymous/live/hls/vntoday/index.m3u8) |
| 6 | HTV7 | 720p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e2.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/Ly2qPv2UHW-q58qK2FO_5w/1795739405/anonymous/live/abr_hls/htv7/master.m3u8) |
| 7 | Truyền hình Đồng Tháp 1 | 1080p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e15.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/1btOKWn9s8CEDQEZUIo0UQ/1795739408/anonymous/live/thdt1/master.m3u8) |
| 8 | Đài Phát thanh và Truyền hình Đắk Lắk | 720p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/nKwnL1ewnvNfeP3_9Fjh_w/1795739414/anonymous/live/hls/thdaklak/index.m3u8) |
| 9 | Đài PT-TH CÀ MAU | 576p | 2026-11-02 07:30 UTC+07:00 | [HLS](https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/rcmvcAy4t5E_w0HyRiF3FA/1793579416/anonymous/live:fingerprint/hls/thcamau/index.m3u8) |
| 10 | Truyền hình An Giang | 576p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e3.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/CtVPRQAz_zHGFd9exwsvcQ/1795739422/anonymous/live/hls/angiang/index.m3u8) |
| 11 | VTVcab - ON KIDS | 1080p | 2026-11-27 07:30 UTC+07:00 | [HLS](https://e10.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/W3Fc7s5Bw6huC389npyy7g/1795739423/anonymous/live/vtvcab21/master.m3u8) |

## Free channels excluded from the playlist

| Channel | Slug | Reason |
|---|---|---|
| THỂ THAO 24/7 | `the-thao-24-7` | Free VOD channel - no linear stream - Chương trình này không có link play. Xin thử lại |
| Việt Nam 360 | `viet-nam-360` | Free VOD channel - no linear stream - Chương trình này không có link play. Xin thử lại |
| PHIM VIỆT 24/7 | `man-anh-viet` | Free VOD channel - no linear stream - Chương trình này không có link play. Xin thử lại |
| VŨ TRỤ HÀI | `cuoi-lien-luc-dia` | Free VOD channel - no linear stream - Chương trình này không có link play. Xin thử lại |

## Refresh

The CDN URLs are signed and expire. Re-run:

```powershell
python refresh_multi_playlists.py --sctv-only
```

Or run the standalone builder:

```powershell
python build_free_m3u.py
```

The script:

1. Reads the free-channel list from `output/sctv_channels.csv`.
2. Calls the same anonymous player endpoint as the public detail page.
3. Verifies each live HLS URL with `ffprobe` before writing it.
4. Rewrites the M3U, JSON data and this report.
5. Optionally run `python verify_vlc_playlist.py` to open every entry in
   VLC and confirm the adaptive/HLS demux and audio/video decoding.

Requirements: Python 3.10+ and `ffprobe` on PATH (optional; without it
the script falls back to an HTTP playlist check).

## Notes

- The playlist uses standard HLS (`#EXTM3U` + `master.m3u8`).
- Each entry carries `#EXTVLCOPT:http-referrer=https://sctvonline.vn/`.
  The CDN rejects requests without the site Referer and redirects them to
  the SCTV homepage. Tested with VLC 3.0.20 on Windows: opening the M3U
  selects the adaptive/HLS demux and plays video and audio.
- Players that ignore `#EXTVLCOPT` need the same Referer set manually.
- Check the `Signed URL expires` column: some channels (currently Cà Mau)
  receive shorter-lived URLs than the others.
- `tvg-id` is the SCTV channel slug; `tvg-logo` comes from the channel list.
- Some streams are geo-restricted to Vietnam by the provider.
- The four 24/7 content channels (`THỂ THAO 24/7`, `Việt Nam 360`,
  `PHIM VIỆT 24/7`, `VŨ TRỤ HÀI`) are free but VOD-only; they do not expose
  a linear live stream, so they are not in the M3U.

