import json, urllib.request

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}

def get(url):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

url = "https://apicdn.sctvonline.vn/tenants/sctv/tenant_platforms/sctv-mobile/documents/by_type/0/"
d = get(url)
print(type(d), list(d.keys()) if isinstance(d, dict) else len(d))
print(json.dumps(d, ensure_ascii=False)[:5000])
