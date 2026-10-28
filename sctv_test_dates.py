import json, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

API = "https://apicdn.sctvonline.vn/backend/cm/epg/"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}
TZ = timezone(timedelta(hours=7))

def get(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def show(slug, params):
    q = urllib.parse.urlencode(params)
    try:
        d = get(API + "?" + q)
        items = d.get("items", [])
        if items:
            first = datetime.fromtimestamp(items[0]["start_at"], TZ)
            last = datetime.fromtimestamp(items[-1]["end_at"], TZ)
            print(f"{slug:30} {params} -> {len(items):3} | {first:%m-%d %H:%M} -> {last:%m-%d %H:%M} | {items[0]['title']}")
        else:
            print(f"{slug:30} {params} -> 0 | metadata={d.get('metadata')}")
    except Exception as e:
        print(f"{slug:30} {params} -> ERROR {e}")

for slug in ["vtv1-hd-72574f3e", "vtv6", "htv7-96634500"]:
    for date in ["2026-10-24", "2026-10-25", "2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29"]:
        show(slug, {"channel_id": slug, "schedule_date": date, "timezone": "Asia/Ho_Chi_Minh"})
    print()

print("--- alternate params ---")
for params in [
    {"channel_id":"vtv1-hd-72574f3e","schedule_date":"2026-10-27","timezone":"Asia/Bangkok"},
    {"channel_id":"vtv1-hd-72574f3e","date":"2026-10-27","timezone":"Asia/Ho_Chi_Minh"},
    {"channel_id":"vtv1-hd-72574f3e","schedule_date":"2026-10-27"},
    {"channel_id":"vtv1-hd-72574f3e","start_date":"2026-10-27","end_date":"2026-10-29","timezone":"Asia/Ho_Chi_Minh"},
    {"channel_id":"vtv1-hd-72574f3e","from_date":"2026-10-27","to_date":"2026-10-29","timezone":"Asia/Ho_Chi_Minh"},
    {"channel_id":"vtv1-hd-72574f3e","schedule_date":"2026-10-27","number_of_days":3,"timezone":"Asia/Ho_Chi_Minh"},
]:
    show("vtv1", params)
