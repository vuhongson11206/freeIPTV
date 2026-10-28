import json, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import sctv_extract as sx

page = sx.fetch_ribbons()
channels = sx.build_channels(page)
dates = ["2026-10-27", "2026-10-28"]
counts = {}
errors = []
with ThreadPoolExecutor(max_workers=8) as ex:
    futs = {ex.submit(sx.fetch_epg, c["slug"], d): (c["slug"], d) for c in channels for d in dates}
    for fut in as_completed(futs):
        slug, d = futs[fut]
        try:
            data = fut.result()
            counts[(slug, d)] = len(data.get("items", []) or [])
        except Exception as e:
            counts[(slug, d)] = 0
            errors.append((slug, d, str(e)))

for d in dates:
    total = sum(counts.get((c["slug"], d), 0) for c in channels)
    with_data = [c for c in channels if counts.get((c["slug"], d), 0) > 0]
    print(f"{d}: {total} programs, {len(with_data)}/{len(channels)} channels with data")
    for c in with_data:
        print(f"   {c['name']} ({c['slug']}): {counts[(c['slug'], d)]}")
print("errors:", errors[:10])
