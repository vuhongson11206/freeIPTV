#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCTV Online - channel list + 3-day EPG extractor
Source page: https://sctvonline.vn/page/truyen-hinh-ecb1ec92

Discovered endpoints:
  Ribbons (channel list):
    https://apicdn.sctvonline.vn/tenants/sctv/tenant_pages/truyen-hinh-ecb1ec92/ribbons/?limit=50
  EPG:
    https://apicdn.sctvonline.vn/backend/cm/epg/?channel_id={slug}&schedule_date=YYYY-MM-DD&timezone=Asia/Ho_Chi_Minh
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path

API = "https://apicdn.sctvonline.vn"
PAGE_SLUG = "truyen-hinh-ecb1ec92"
TZ = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh (UTC+7, no DST)
HDRS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://sctvonline.vn",
    "Referer": "https://sctvonline.vn/",
}
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "epg_raw"
OUT_DIR = BASE_DIR / "output"


def http_json(url: str, retries: int = 4, timeout: int = 60):
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=HDRS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(0.6 * (2 ** (attempt - 1)))
    raise last_err


def fetch_ribbons():
    url = f"{API}/tenants/sctv/tenant_pages/{PAGE_SLUG}/ribbons/?limit=50"
    return http_json(url)


def build_channels(page_data):
    """Flatten all channel ribbons, dedupe by slug, keep ribbon order."""
    channels = {}
    order = 0
    for rb in page_data.get("ribbons", []):
        rb_name = (rb.get("name") or "").strip()
        if not rb_name.lower().startswith("kênh"):
            continue
        for item in rb.get("items", []):
            if item.get("type") != 5:
                continue
            slug = item.get("slug")
            if not slug:
                continue
            if slug not in channels:
                badges = item.get("badges") or []
                tier = item.get("min_sub_tier") or {}
                images = item.get("images") or {}
                channels[slug] = {
                    "slug": slug,
                    "name": item.get("title") or "",
                    "origin_title": item.get("origin_title") or "",
                    "categories": [],
                    "ribbon_order": rb.get("odr", 999),
                    "first_seen_order": order,
                    "is_live": "content-live" in badges,
                    "is_premium": bool(item.get("is_premium")),
                    "payment_type": item.get("payment_type"),
                    "min_tier": tier.get("display_name") or tier.get("name") or "",
                    "min_tier_level": tier.get("tier"),
                    "logo": images.get("thumbnail") or images.get("banner") or "",
                    "badges": badges,
                    "detail_url": f"https://sctvonline.vn/detail/{slug}",
                }
                order += 1
            if rb_name not in channels[slug]["categories"]:
                channels[slug]["categories"].append(rb_name)

    result = list(channels.values())
    result.sort(key=lambda c: (c["ribbon_order"], c["first_seen_order"]))
    return result


def epg_url(slug: str, date: str) -> str:
    q = urllib.parse.urlencode({
        "channel_id": slug,
        "schedule_date": date,
        "timezone": "Asia/Ho_Chi_Minh",
    })
    return f"{API}/backend/cm/epg/?{q}"


def fetch_epg(slug: str, date: str, force: bool = False):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"{slug}__{date}.json"
    if cache.exists() and not force:
        try:
            with cache.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    data = http_json(epg_url(slug, date))
    if cache.exists():
        try:
            cache.unlink()
        except OSError:
            pass
    with cache.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data


def local_dt(ts):
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), TZ)


def parse_epg(slug: str, date: str, data: dict):
    rows = []
    for item in data.get("items", []) or []:
        start = local_dt(item.get("start_at"))
        end = local_dt(item.get("end_at"))
        if start is None or end is None:
            continue
        duration = (end - start).total_seconds() / 60.0
        rows.append({
            "schedule_date": date,
            "channel_slug": slug,
            "start_at": start.isoformat(sep=" "),
            "end_at": end.isoformat(sep=" "),
            "start_date": start.strftime("%Y-%m-%d"),
            "start_time": start.strftime("%H:%M"),
            "end_date": end.strftime("%Y-%m-%d"),
            "end_time": end.strftime("%H:%M"),
            "duration_min": round(duration, 1),
            "title": item.get("title") or "",
            "description": item.get("description") or item.get("short_description") or "",
            "epg_id": item.get("id") or "",
            "epg_slug": item.get("slug") or "",
            "is_blackout": item.get("is_blackout", 0),
            "link_play": item.get("link_play") or "",
            "content_ref": item.get("content_ref") or "",
            "play_date": item.get("play_date") or "",
        })
    rows.sort(key=lambda r: (r["start_at"], r["title"]))
    return rows


def fmt_duration(minutes: float):
    if minutes < 0:
        return ""
    m = int(round(minutes))
    h, mm = divmod(m, 60)
    if h:
        return f"{h}h{mm:02d}"
    return f"{mm}m"


def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_html(path: Path, channels, schedule, dates, source_page, note):
    # Compact payload for the viewer
    payload = {
        "dates": dates,
        "channels": [
            {
                "slug": c["slug"],
                "name": c["name"],
                "categories": c["categories"],
                "is_live": c["is_live"],
                "is_premium": c["is_premium"],
                "logo": c["logo"],
                "detail_url": c["detail_url"],
            }
            for c in channels
        ],
        "schedule": {
            d: {
                slug: [
                    {
                        "s": r["start_time"],
                        "e": r["end_time"],
                        "sd": r["start_date"],
                        "ed": r["end_date"],
                        "t": r["title"],
                        "dur": r["duration_min"],
                    }
                    for r in rows
                ]
                for slug, rows in per_channel.items()
            }
            for d, per_channel in schedule.items()
        },
        "note": note,
        "source_page": source_page,
    }
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    html = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lịch phát sóng SCTV Online - 3 ngày</title>
<style>
  :root{--bg:#0f1115;--panel:#171a21;--panel2:#1e222b;--line:#2a3040;--text:#e8ecf3;--muted:#9aa4b6;--accent:#e72d30;--accent2:#ff5a5d;--chip:#262c38;}
  *{box-sizing:border-box}
  body{margin:0;background:linear-gradient(180deg,#0b0d11 0,#12151b 220px,#12151b 100%);color:var(--text);font:14px/1.45 "Segoe UI",Roboto,Arial,sans-serif}
  header{padding:22px 26px 14px;border-bottom:1px solid var(--line);background:rgba(15,17,21,.92);position:sticky;top:0;z-index:20;backdrop-filter:blur(8px)}
  h1{margin:0 0 4px;font-size:22px;letter-spacing:.2px}
  .sub{color:var(--muted);font-size:13px}
  .sub a{color:#7fb3ff;text-decoration:none}
  .toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-top:14px}
  .tabs{display:flex;gap:6px;flex-wrap:wrap}
  .tab{border:1px solid var(--line);background:var(--panel);color:var(--text);padding:8px 12px;border-radius:8px;cursor:pointer;font-size:13px}
  .tab.active{background:var(--accent);border-color:var(--accent);font-weight:600}
  input,select{background:var(--panel);border:1px solid var(--line);color:var(--text);padding:9px 11px;border-radius:8px;font-size:13px;outline:none}
  input{min-width:260px}
  input:focus,select:focus{border-color:#4a6fa5}
  .stats{margin-left:auto;color:var(--muted);font-size:12px;white-space:nowrap}
  main{display:grid;grid-template-columns:320px 1fr;gap:18px;padding:18px 26px 40px;max-width:1700px;margin:0 auto}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
  .panel h2{margin:0;padding:13px 15px;font-size:14px;color:#cfd7e6;border-bottom:1px solid var(--line);background:var(--panel2)}
  #channelList{max-height:calc(100vh - 250px);overflow:auto}
  .ch{display:flex;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid #202634;cursor:pointer}
  .ch:hover{background:#202633}
  .ch.active{background:#2a1a1c;box-shadow:inset 3px 0 0 var(--accent)}
  .ch img{width:48px;height:29px;object-fit:contain;background:#0b0d11;border-radius:4px;flex:0 0 auto}
  .ch .nm{font-weight:600;font-size:13px}
  .ch .cat{color:var(--muted);font-size:11px;margin-top:2px}
  .ch .cnt{margin-left:auto;color:var(--muted);font-size:11px;white-space:nowrap}
  .badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:99px;background:var(--chip);color:#b9c3d4;margin-left:6px;vertical-align:middle}
  .badge.live{background:#1f3a2b;color:#7ee2a8}
  .badge.vip{background:#3a2a12;color:#ffcc80}
  #schedule{padding:0}
  .sched-head{display:flex;align-items:center;gap:12px;padding:14px 16px;border-bottom:1px solid var(--line);background:var(--panel2)}
  .sched-head img{width:64px;height:38px;object-fit:contain;background:#0b0d11;border-radius:5px}
  .sched-head h3{margin:0;font-size:17px}
  .sched-head .meta{color:var(--muted);font-size:12px;margin-top:2px}
  .prog{display:grid;grid-template-columns:86px 1fr 64px;gap:12px;padding:11px 16px;border-bottom:1px solid #202634;align-items:start}
  .prog:hover{background:#1b202a}
  .prog .time{font-variant-numeric:tabular-nums;color:#c8d3e5;font-weight:600;font-size:12px;padding-top:2px}
  .prog .time small{display:block;color:var(--muted);font-weight:400;font-size:10px}
  .prog .ttl{font-size:13px}
  .prog .dur{color:var(--muted);font-size:11px;text-align:right;padding-top:2px}
  .prog.now{background:#241a1b}
  .prog.now .ttl{color:#ff9a9c}
  .all-table{width:100%;border-collapse:collapse;font-size:12px}
  .all-table th{position:sticky;top:0;background:var(--panel2);text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);color:#cfd7e6;z-index:2}
  .all-table td{padding:8px 12px;border-bottom:1px solid #202634;vertical-align:top}
  .all-table tr:hover td{background:#1b202a}
  .all-table .t{white-space:nowrap;color:#c8d3e5;font-variant-numeric:tabular-nums}
  .all-table .c{white-space:nowrap;font-weight:600}
  .all-table .p{min-width:260px}
  .empty{padding:40px 20px;text-align:center;color:var(--muted)}
  .note{margin-top:10px;color:var(--muted);font-size:12px}
  .scroll{max-height:calc(100vh - 330px);overflow:auto}
  @media(max-width:900px){main{grid-template-columns:1fr;padding:12px}#channelList{max-height:300px}.stats{margin-left:0;width:100%}header{padding:16px}}
</style>
</head>
<body>
<header>
  <h1>Lịch phát sóng SCTV Online</h1>
  <div class="sub">Nguồn: <a href="__SOURCE__" target="_blank" rel="noopener">__SOURCE__</a> · Múi giờ Asia/Ho_Chi_Minh (UTC+7) · __NOTE__</div>
  <div class="toolbar">
    <div class="tabs" id="dateTabs"></div>
    <input id="search" type="search" placeholder="Tìm kênh hoặc chương trình…">
    <select id="category"><option value="">Tất cả nhóm kênh</option></select>
    <button class="tab" id="allBtn">Xem tất cả kênh</button>
    <span class="stats" id="stats"></span>
  </div>
</header>
<main>
  <section class="panel">
    <h2>Danh sách kênh (<span id="chCount"></span>)</h2>
    <div id="channelList"></div>
  </section>
  <section class="panel" id="schedule"></section>
</main>
<script>
const DATA = __DATA__;
const state = { date: DATA.dates[DATA.dates.length-1], slug: null, q: "", cat: "", all: false };
const fmtDate = d => { const [y,m,dd]=d.split("-"); return `${dd}/${m}/${y}`; };
const dayLabel = d => { const [y,m,dd]=d.split("-"); const dt=new Date(+y,+m-1,+dd); const wd=["CN","T2","T3","T4","T5","T6","T7"][dt.getDay()]; return `${wd} · ${dd}/${m}`; };
const esc = s => String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const scheduleFor = (slug,date) => (DATA.schedule[date]||{})[slug]||[];
const channelBySlug = Object.fromEntries(DATA.channels.map(c=>[c.slug,c]));

function init(){
  const tabs=document.getElementById("dateTabs");
  DATA.dates.forEach(d=>{
    const b=document.createElement("button"); b.className="tab"+(d===state.date?" active":"");
    b.textContent=dayLabel(d); b.onclick=()=>{state.date=d;state.all=false;render();};
    tabs.appendChild(b);
  });
  const cats=[...new Set(DATA.channels.flatMap(c=>c.categories))];
  const sel=document.getElementById("category");
  cats.forEach(c=>{const o=document.createElement("option");o.value=c;o.textContent=c;sel.appendChild(o);});
  sel.onchange=e=>{state.cat=e.target.value;render();};
  document.getElementById("search").oninput=e=>{state.q=e.target.value.trim().toLowerCase();render();};
  document.getElementById("allBtn").onclick=()=>{state.all=!state.all;render();};
  render();
}

function render(){
  document.querySelectorAll("#dateTabs .tab").forEach((b,i)=>b.classList.toggle("active",DATA.dates[i]===state.date));
  const q=state.q, cat=state.cat;
  const chans=DATA.channels.filter(c=>(!cat||c.categories.includes(cat))&&(!q||c.name.toLowerCase().includes(q)||c.slug.includes(q)||c.categories.join(" ").toLowerCase().includes(q)));
  const chCount=document.getElementById("chCount"); chCount.textContent=chans.length;
  const stats=document.getElementById("stats");
  let total=0; DATA.channels.forEach(c=>total+=scheduleFor(c.slug,state.date).length);
  stats.textContent=`${total.toLocaleString("vi-VN")} chương trình · ${chans.length}/${DATA.channels.length} kênh`;
  const list=document.getElementById("channelList");
  if(!chans.length){list.innerHTML='<div class="empty">Không tìm thấy kênh.</div>';}
  else{
    list.innerHTML=chans.map(c=>{
      const n=scheduleFor(c.slug,state.date).length;
      return `<div class="ch ${state.slug===c.slug&&!state.all?"active":""}" data-slug="${esc(c.slug)}">
        <img src="${esc(c.logo)}" alt="" loading="lazy" onerror="this.style.visibility='hidden'">
        <div><div class="nm">${esc(c.name)}${c.is_live?'<span class="badge live">LIVE</span>':''}${c.is_premium?'<span class="badge vip">VIP</span>':''}</div><div class="cat">${esc(c.categories.join(" · "))}</div></div>
        <div class="cnt">${n} CT</div></div>`;
    }).join("");
    list.querySelectorAll(".ch").forEach(el=>el.onclick=()=>{state.slug=el.dataset.slug;state.all=false;render();});
  }
  const sched=document.getElementById("schedule");
  if(state.all){ renderAll(sched); return; }
  if(!state.slug){ state.slug=(chans[0]||DATA.channels[0])?.slug; }
  const c=channelBySlug[state.slug];
  if(!c){sched.innerHTML='<div class="empty">Chọn một kênh.</div>';return;}
  const rows=scheduleFor(c.slug,state.date);
  sched.innerHTML=`<div class="sched-head"><img src="${esc(c.logo)}" alt="" onerror="this.style.visibility='hidden'">
    <div><h3>${esc(c.name)}</h3><div class="meta">${esc(c.categories.join(" · "))} · ${esc(c.slug)} · ${fmtDate(state.date)}</div></div></div>
    <div class="scroll">${rows.length?rows.map(r=>{
      const now=isNow(r);
      return `<div class="prog ${now?"now":""}"><div class="time">${esc(r.s)}<small>${esc(r.e)}</small></div>
      <div class="ttl">${esc(r.t)}${now?' <span class="badge live">ĐANG PHÁT</span>':''}</div>
      <div class="dur">${fmtDur(r.dur)}</div></div>`;
    }).join(""):'<div class="empty">Chưa có lịch phát sóng cho kênh này trong ngày đã chọn.</div>'}</div>`;
}

function isNow(r){
  const now=new Date(Date.now()+7*3600*1000);
  const today=now.toISOString().slice(0,10);
  if(state.date!==today) return false;
  const hh=String(now.getUTCHours()).padStart(2,"0"), mm=String(now.getUTCMinutes()).padStart(2,"0");
  const t=`${hh}:${mm}`;
  if(r.sd<today) return r.ed>today || t<r.e;   // started before today
  if(r.ed>today) return t>=r.s;                // crosses midnight into tomorrow
  return r.s<=t && t<r.e;
}

function fmtDur(m){m=Math.round(m||0);const h=Math.floor(m/60),mm=m%60;return h?`${h}h${String(mm).padStart(2,"0")}`:`${mm}m`;}

function renderAll(container){
  const rows=[];
  const chans=DATA.channels.filter(c=>(!state.cat||c.categories.includes(state.cat))&&(!state.q||c.name.toLowerCase().includes(state.q)||c.slug.includes(state.q)));
  chans.forEach(c=>scheduleFor(c.slug,state.date).forEach(r=>rows.push({c,r})));
  rows.sort((a,b)=>a.r.s.localeCompare(b.r.s)||a.c.name.localeCompare(b.c.name));
  container.innerHTML=`<div class="sched-head"><div><h3>Tất cả kênh · ${fmtDate(state.date)}</h3><div class="meta">${rows.length.toLocaleString("vi-VN")} chương trình</div></div></div>
  <div class="scroll"><table class="all-table"><thead><tr><th>Giờ</th><th>Kênh</th><th>Chương trình</th><th>Thời lượng</th></tr></thead><tbody>
  ${rows.map(({c,r})=>`<tr><td class="t">${esc(r.s)}–${esc(r.e)}</td><td class="c">${esc(c.name)}</td><td class="p">${esc(r.t)}</td><td>${fmtDur(r.dur)}</td></tr>`).join("")}
  </tbody></table></div>`;
}

init();
</script>
</body>
</html>"""
    html = html.replace("__SOURCE__", source_page).replace("__NOTE__", note).replace("__DATA__", data_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dates", nargs="+", default=["2026-10-24", "2026-10-25", "2026-10-26"],
                    help="Schedule dates YYYY-MM-DD (default: latest 3 complete days)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="Ignore cached raw EPG files")
    args = ap.parse_args()

    dates = sorted(args.dates)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] Fetching channel ribbons…", flush=True)
    page = fetch_ribbons()
    channels = build_channels(page)
    print(f"      {len(channels)} unique channels / contents", flush=True)

    print(f"[2/4] Fetching EPG for {len(channels)} channels × {len(dates)} days = {len(channels)*len(dates)} requests…", flush=True)
    raw = {}
    errors = []
    tasks = [(c["slug"], d) for c in channels for d in dates]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(fetch_epg, slug, d, args.force): (slug, d) for slug, d in tasks}
        done = 0
        for fut in as_completed(futs):
            slug, d = futs[fut]
            done += 1
            try:
                raw[(slug, d)] = fut.result()
            except Exception as e:
                raw[(slug, d)] = {"items": [], "error": str(e)}
                errors.append({"slug": slug, "date": d, "error": str(e)})
            if done % 25 == 0 or done == len(futs):
                print(f"      {done}/{len(futs)} done", flush=True)
    if errors:
        print(f"      {len(errors)} request(s) failed", flush=True)
        for e in errors[:20]:
            print(f"        {e['slug']} {e['date']}: {e['error']}", flush=True)

    print(f"[3/4] Parsing schedules…", flush=True)
    schedule = {d: {} for d in dates}
    all_rows = []
    coverage = []
    for c in channels:
        for d in dates:
            rows = parse_epg(c["slug"], d, raw.get((c["slug"], d), {}))
            schedule[d][c["slug"]] = rows
            all_rows.extend(rows)
        counts = {d: len(schedule[d][c["slug"]]) for d in dates}
        coverage.append({"slug": c["slug"], "name": c["name"], **counts})

    # Attach channel metadata to rows
    by_slug = {c["slug"]: c for c in channels}
    for r in all_rows:
        c = by_slug[r["channel_slug"]]
        r["channel_name"] = c["name"]
        r["category"] = " | ".join(c["categories"])
        r["is_live"] = "yes" if c["is_live"] else "no"
        r["is_premium"] = "yes" if c["is_premium"] else "no"
        r["min_tier"] = c["min_tier"]
        r["duration_human"] = fmt_duration(r["duration_min"])

    all_rows.sort(key=lambda r: (r["schedule_date"], r["start_at"], r["channel_name"]))

    # Channels CSV
    ch_rows = []
    for c in channels:
        counts = {d: len(schedule[d][c["slug"]]) for d in dates}
        ch_rows.append({
            "channel_name": c["name"],
            "channel_slug": c["slug"],
            "categories": " | ".join(c["categories"]),
            "is_live": "yes" if c["is_live"] else "no",
            "is_premium": "yes" if c["is_premium"] else "no",
            "min_tier": c["min_tier"],
            "min_tier_level": c["min_tier_level"] if c["min_tier_level"] is not None else "",
            "logo_url": c["logo"],
            "detail_url": c["detail_url"],
            "badges": " | ".join(c["badges"]),
            **{f"programs_{d}": counts[d] for d in dates},
            "programs_total": sum(counts.values()),
            "days_with_epg": sum(1 for d in dates if counts[d] > 0),
            "has_epg_3days": "yes" if all(counts[d] > 0 for d in dates) else "no",
        })

    write_csv(OUT_DIR / "sctv_channels.csv", ch_rows, list(ch_rows[0].keys()))
    write_csv(OUT_DIR / "sctv_schedule_3days.csv", all_rows, [
        "schedule_date", "channel_name", "channel_slug", "category",
        "start_at", "end_at", "start_date", "start_time", "end_date", "end_time",
        "duration_min", "duration_human", "title", "description",
        "is_live", "is_premium", "min_tier", "epg_id", "epg_slug",
        "is_blackout", "link_play", "content_ref", "play_date",
    ])

    # JSON
    json_data = {
        "source": f"https://sctvonline.vn/page/{PAGE_SLUG}",
        "api": {
            "ribbons": f"{API}/tenants/sctv/tenant_pages/{PAGE_SLUG}/ribbons/?limit=50",
            "epg": f"{API}/backend/cm/epg/?channel_id={{slug}}&schedule_date={{date}}&timezone=Asia/Ho_Chi_Minh",
        },
        "generated_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": "Asia/Ho_Chi_Minh",
        "dates": dates,
        "channel_count": len(channels),
        "program_count": len(all_rows),
        "channels": channels,
        "coverage": coverage,
        "schedule": schedule,
    }
    with (OUT_DIR / "sctv_data.json").open("w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=1)

    # Excel
    try:
        make_excel(OUT_DIR / "sctv_channels_schedule.xlsx", ch_rows, all_rows, dates)
        excel_note = "OK"
    except Exception as e:
        print(f"      Excel export skipped: {e}", flush=True)
        excel_note = "skipped"

    # HTML
    note = f"{len(channels)} kênh · {len(all_rows):,} chương trình · {dates[0]} → {dates[-1]}"
    write_html(OUT_DIR / "sctv_schedule.html", channels, schedule, dates,
               f"https://sctvonline.vn/page/{PAGE_SLUG}", note)

    # Coverage report
    cov_lines = ["channel_name,channel_slug," + ",".join(dates)]
    for c in coverage:
        cov_lines.append(f'"{c["name"]}",{c["slug"]},' + ",".join(str(c[d]) for d in dates))
    (OUT_DIR / "sctv_coverage.csv").write_text("\ufeff" + "\n".join(cov_lines), encoding="utf-8")

    print(f"[4/4] Done. Output in {OUT_DIR}", flush=True)
    print(f"      Channels: {len(channels)} | Programs: {len(all_rows)} | Excel: {excel_note}", flush=True)

    # Summary to console
    print("\nChannels by category:", flush=True)
    for cat in sorted({c for ch in channels for c in ch["categories"]}):
        n = sum(1 for ch in channels if cat in ch["categories"])
        print(f"  {cat}: {n}", flush=True)
    print("\nPrograms per day:", flush=True)
    for d in dates:
        print(f"  {d}: {sum(len(v) for v in schedule[d].values())}", flush=True)
    missing = [c for c in coverage if any(c[d] == 0 for d in dates)]
    print(f"Channels missing at least one day: {len(missing)}", flush=True)
    for c in missing[:30]:
        print(f"  {c['name']} ({c['slug']}): " + ", ".join(f"{d}={c[d]}" for d in dates), flush=True)


def make_excel(path, ch_rows, all_rows, dates):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Kênh"
    headers = list(ch_rows[0].keys())
    ws.append(headers)
    for r in ch_rows:
        ws.append([r.get(h, "") for h in headers])
    style_sheet(ws, headers, [34, 42, 48, 8, 9, 10, 8, 55, 55, 30, 10, 10, 10, 14, 12, 12])
    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    for d in dates:
        ws2 = wb.create_sheet(f"Lịch {d[8:10]}-{d[5:7]}")
        h2 = ["Giờ bắt đầu", "Giờ kết thúc", "Kênh", "Slug", "Nhóm kênh", "Chương trình", "Thời lượng (phút)", "Thời lượng", "Mô tả", "LIVE", "VIP"]
        ws2.append(h2)
        rows = [r for r in all_rows if r["schedule_date"] == d]
        rows.sort(key=lambda r: (r["start_at"], r["channel_name"]))
        for r in rows:
            ws2.append([
                r["start_time"], r["end_time"], r["channel_name"], r["channel_slug"],
                r["category"], r["title"], r["duration_min"], r["duration_human"],
                r["description"], r["is_live"], r["is_premium"],
            ])
        style_sheet(ws2, h2, [12, 12, 34, 42, 48, 60, 14, 12, 40, 8, 8], wrap_cols={6, 9})
        ws2.auto_filter.ref = ws2.dimensions
        ws2.freeze_panes = "A2"

    # Combined sheet
    ws3 = wb.create_sheet("Tổng hợp")
    h3 = ["Ngày", "Bắt đầu", "Kết thúc", "Kênh", "Slug", "Nhóm kênh", "Chương trình", "Thời lượng (phút)"]
    ws3.append(h3)
    for r in all_rows:
        ws3.append([r["schedule_date"], r["start_time"], r["end_time"], r["channel_name"], r["channel_slug"], r["category"], r["title"], r["duration_min"]])
    style_sheet(ws3, h3, [12, 10, 10, 34, 42, 46, 60, 14], wrap_cols={7})
    ws3.auto_filter.ref = ws3.dimensions
    ws3.freeze_panes = "A2"

    wb.save(path)


def style_sheet(ws, headers, widths, wrap_cols=None):
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    header_fill = PatternFill("solid", fgColor="1F2937")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    thin = Side(style="thin", color="D9DEE8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border
    ws.row_dimensions[1].height = 30
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    wrap_cols = wrap_cols or set()
    for row in ws.iter_rows(min_row=2):
        for idx, cell in enumerate(row, 1):
            cell.border = border
            cell.alignment = Alignment(vertical="top", wrap_text=(idx in wrap_cols))


if __name__ == "__main__":
    main()
