import json, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

API = "https://apicdn.sctvonline.vn/backend/cm/epg/"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}

def get(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

for tz in ["UTC", "Etc/UTC", "Asia/Ho_Chi_Minh", "Asia/Bangkok", "Asia/Saigon"]:
    for date in ["2026-10-26", "2026-10-27", "2026-10-28"]:
        q = urllib.parse.urlencode({"channel_id": "vtv1-hd-72574f3e", "schedule_date": date, "timezone": tz})
        d = get(API + "?" + q)
        items = d.get("items", [])
        if items:
            # show UTC and +7
            f = datetime.fromtimestamp(items[0]["start_at"], timezone.utc)
            l = datetime.fromtimestamp(items[-1]["end_at"], timezone.utc)
            print(f"{tz:20} {date} -> {len(items):3} | UTC {f:%m-%d %H:%M} -> {l:%m-%d %H:%M} | {items[0]['title']}")
        else:
            print(f"{tz:20} {date} -> 0")
