import json, subprocess, time
from pathlib import Path

base = Path(r"C:\Users\VHSON\Documents\Default Project")
streams = [
    ("VTV1", "vtv1-hd-72574f3e", "https://e11.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/g6jUlDzQmJHgqzOYM-MWfg/1795622332/anonymous/live/vtv1/master.m3u8"),
    ("Truyền hình Quốc phòng Việt Nam- QPVN", "qpvn-fea05134", "https://e15.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/jLFcQO236OLAuHn9O16bfA/1795622346/anonymous/live/quocphongvn/master.m3u8"),
    ("Truyền hình Công an nhân dân - ANTV", "antv-1debf072", "https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/C6j0yDlfzvOYVAEua78YOg/1795622356/anonymous/live/hls/antv/index.m3u8"),
    ("VTV5-Truyền hình dân tộc", "vtv5-truyen-hinh-dan-toc", "https://e10.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/qDkcUscaXpPHwn6wXFKMJw/1795622410/anonymous/live/vtv5/master.m3u8"),
    ("Kênh truyền hình đối ngoại quốc gia - Vietnam Today", "kenh-truyen-hinh-doi-ngoai-quoc-gia-vietnam-today", "https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/PgXf5ca0Nxqkwycn0nPKMw/1795622391/anonymous/live/hls/vntoday/index.m3u8"),
    ("HTV7", "htv7-96634500", "https://e2.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/9Y1kYZPzb3yJTbj8qCqO1Q/1795622438/anonymous/live/abr_hls/htv7/master.m3u8"),
    ("Truyền hình Đồng Tháp 1", "th-dong-thap-1-8f098772", "https://e15.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/t1F8ApKK8U5_R3ETSM8NCw/1795622444/anonymous/live/thdt1/master.m3u8"),
    ("Đài Phát thanh và Truyền hình Đắk Lắk", "dai-phat-thanh-va-truyen-hinh-dak-lak", "https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/irWBHolT8mMn9CV7MChJoQ/1795622455/anonymous/live/hls/thdaklak/index.m3u8"),
    ("Đài PT-TH CÀ MAU", "dai-pt-th-ca-mau", "https://e8.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/8zoAnF4xBWkrNsBufcbb4w/1793462464/anonymous/live:fingerprint/hls/thcamau/index.m3u8"),
    ("Truyền hình An Giang", "th-an-giang-e2b64bbf", "https://e3.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/2/Pf-FRGsYd3bVHnTiB_DeBw/1795622474/anonymous/live/hls/angiang/index.m3u8"),
    ("VTVcab - ON KIDS", "vtvcab-on-kids", "https://e10.endpoint.cdn.sctvonline.vn/cdn-secure/v1/sctvonline/1/T5LJP2xkMTKaEH-vXI0vXQ/1795622490/anonymous/live/vtvcab21/master.m3u8"),
]

results = []
for name, slug, url in streams:
    cmd = [
        "ffprobe", "-v", "error", "-rw_timeout", "20000000",
        "-user_agent", "VLC/3.0.21 LibVLC/3.0.21",
        "-headers", "Referer: https://sctvonline.vn/\r\n",
        "-show_entries", "stream=index,codec_name,codec_type,width,height",
        "-show_entries", "format=format_name,duration",
        "-of", "json", url,
    ]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        elapsed = round(time.time() - t0, 1)
        info = None
        if p.returncode == 0 and p.stdout.strip():
            info = json.loads(p.stdout)
        stream_info = []
        if info:
            for s in info.get("streams", []):
                stream_info.append({
                    "type": s.get("codec_type"),
                    "codec": s.get("codec_name"),
                    "size": f"{s.get('width')}x{s.get('height')}" if s.get("width") else None,
                })
        results.append({
            "name": name, "slug": slug, "url": url,
            "ok": p.returncode == 0 and bool(stream_info),
            "returncode": p.returncode,
            "elapsed_s": elapsed,
            "streams": stream_info,
            "format": (info or {}).get("format", {}).get("format_name"),
            "error": (p.stderr or "").strip().splitlines()[-1][:300] if p.returncode != 0 and p.stderr.strip() else None,
        })
        print(f"{'OK ' if results[-1]['ok'] else 'ERR'} {name} [{elapsed}s] {stream_info}")
    except subprocess.TimeoutExpired:
        results.append({"name": name, "slug": slug, "url": url, "ok": False, "returncode": None, "elapsed_s": 45, "streams": [], "error": "ffprobe timeout"})
        print("TIMEOUT", name)

(base / "output/sctv_free_stream_tests.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print("\nOK:", sum(1 for r in results if r["ok"]), "/", len(results))
