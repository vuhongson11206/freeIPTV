import json, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

API = "https://apicdn.sctvonline.vn/backend/cm/epg/"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}
TZ = timezone(timedelta(hours=7))

def get(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

for slug in ["vtv1-hd-72574f3e", "vtv6", "htv7-96634500", "the-thao-24-7", "viet-nam-360"]:
    for date in ["2026-10-26", "2026-10-27", "2026-10-28"]:
        q = urllib.parse.urlencode({"channel_id": slug, "schedule_date": date, "timezone": "Asia/Ho_Chi_Minh"})
        try:
            d = get(API + "?" + q)
            items = d.get("items", [])
            if items:
                first = datetime.fromtimestamp(items[0]["start_at"], TZ)
                last = datetime.fromtimestamp(items[-1]["end_at"], TZ)
                print(f"{slug:45} {date} -> {len(items):3} items | {first:%Y-%m-%d %H:%M} -> {last:%Y-%m-%d %H:%M} | first: {items[0]['title']}")
            else:
                print(f"{slug:45} {date} -> 0 items | keys={list(d.keys())}")
        except Exception as e:
            print(f"{slug:45} {date} -> ERROR {e}")
