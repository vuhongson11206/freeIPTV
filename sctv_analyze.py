import json, urllib.request, sys, io

API = "https://apicdn.sctvonline.vn"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}

def get(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

url = API + "/tenants/sctv/tenant_pages/truyen-hinh-ecb1ec92/ribbons/?limit=50"
data = get(url)
print("Page:", data.get("name"))
for rb in data.get("ribbons", []):
    items = rb.get("items", [])
    print(f"\n== {rb.get('name')} | type={rb.get('type')} | items={len(items)} | odr={rb.get('odr')}")
    for it in items:
        print(f"  {it.get('slug')} | {it.get('title')} | badges={it.get('badges')} | premium={it.get('is_premium')} | type={it.get('type')}")
