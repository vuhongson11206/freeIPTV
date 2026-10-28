#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a readable Markdown report and a slug -> display-name map from the extracted data."""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR = BASE_DIR / "output"

REPORT = OUT_DIR / "sctv_report.md"
MAP_CSV = OUT_DIR / "sctv_slug_name_map.csv"


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def esc(value):
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def num(value):
    return f"{int(value):,}".replace(",", ".")


def date_label(iso):
    return f"{iso[8:10]}/{iso[5:7]}"


def main():
    channels = read_csv(OUT_DIR / "sctv_channels.csv")
    schedule = read_csv(OUT_DIR / "sctv_schedule_3days.csv")
    data = json.loads((OUT_DIR / "sctv_data.json").read_text(encoding="utf-8"))
    dates = data["dates"]
    days = [date_label(d) for d in dates]

    for r in channels:
        r["_cats"] = r["categories"].split(" | ") if r["categories"] else []
        r["_primary"] = r["_cats"][0] if r["_cats"] else "Khác"
        r["_counts"] = [int(r[f"programs_{d}"] or 0) for d in dates]

    total_programs = len(schedule)
    per_day = Counter(r["schedule_date"] for r in schedule)
    live = sum(1 for r in channels if r["is_live"] == "yes")
    premium = sum(1 for r in channels if r["is_premium"] == "yes")
    full = sum(1 for r in channels if r["has_epg_3days"] == "yes")
    none = [r for r in channels if all(v == 0 for v in r["_counts"])]
    partial = [r for r in channels if any(v == 0 for v in r["_counts"]) and r not in none]
    missing = none + partial

    primary_counts = Counter(r["_primary"] for r in channels)
    category_counts = Counter(cat for r in channels for cat in r["_cats"])
    group_order = []
    for r in channels:
        if r["_primary"] not in group_order:
            group_order.append(r["_primary"])

    # A handful of source slugs are legacy / mismatched. Keep this list explicit.
    mismatch_slugs = [
        "vtv6-69452026",
        "vtvcab-on-golf",
        "th-hau-giang-ac0ec36d",
        "dai-pt-th-binh-thuan",
        "bao-va-pt-th-lam-dong-ltv3",
        "sctv19-cb98949a",
        "carttoon-network-bc24942a",
    ]
    by_slug = {r["channel_slug"]: r for r in channels}

    # Source data quirks
    exact_dups = Counter(
        (r["channel_slug"], r["schedule_date"], r["start_at"], r["end_at"], r["title"])
        for r in schedule
    )
    dup_rows = sum(v - 1 for v in exact_dups.values() if v > 1)
    blank_titles = [r for r in schedule if not r["title"].strip()]
    zero_duration = [r for r in schedule if float(r["duration_min"] or 0) <= 0]
    vtv3 = by_slug.get("vtv3-hd-d605e3bf")
    vtv3_day2 = int(vtv3["programs_" + dates[1]]) if vtv3 else 0

    lines = []
    add = lines.append

    add("# SCTV Online — Danh sách kênh và lịch phát sóng 3 ngày")
    add("")
    add(f"- **Trang nguồn:** https://sctvonline.vn/page/truyen-hinh-ecb1ec92")
    add(f"- **Thời điểm trích xuất:** {data.get('generated_at', '')} (UTC+7)")
    add(f"- **Múi giờ:** Asia/Ho_Chi_Minh (UTC+7, không có DST)")
    add(f"- **Khoảng ngày:** {dates[0]} → {dates[-1]} ({', '.join(days)})")
    add(f"- **Kênh/nội dung:** {len(channels)} unique · **Chương trình:** {num(total_programs)}")
    add("")

    add("## Tổng quan")
    add("")
    add(f"- Kênh live: **{live}**; nội dung 24/7 không gắn live: **{len(channels) - live}**")
    add(f"- Kênh premium (theo trường `is_premium` của nguồn): **{premium}**")
    add(f"- Kênh có đủ EPG cả 3 ngày: **{full}/{len(channels)}**")
    add(f"- Kênh thiếu ít nhất 1 ngày: **{len(missing)}** "
        f"(**{len(none)}** không có EPG ngày nào, **{len(partial)}** thiếu một phần)")
    add("- Chương trình theo ngày: " + " · ".join(
        f"{date_label(d)}: **{num(per_day.get(d, 0))}**" for d in dates))
    add("")

    add("### Theo nhóm (mỗi kênh tính theo ribbon đầu tiên)")
    add("")
    add("| Nhóm | Số kênh |")
    add("|---|---:|")
    for group in group_order:
        add(f"| {esc(group)} | {primary_counts[group]} |")
    add(f"| **Tổng unique** | **{len(channels)}** |")
    add("")
    add(f"> Bảng trên đếm mỗi kênh một lần ({len(channels)}). Nếu đếm theo từng ribbon sẽ là "
        f"{sum(category_counts.values())} lượt vì có "
        f"{sum(1 for r in channels if len(r['_cats']) > 1)} kênh nằm trong 2 ribbon. "
        "Bảng dưới đây xếp mỗi kênh vào ribbon xuất hiện đầu tiên; cột `categories` "
        "trong file CSV liệt kê đầy đủ.")
    add("")

    add("## Danh sách kênh (slug → tên hiển thị)")
    add("")
    add("Ký hiệu: `LIVE` = kênh phát trực tiếp; `24/7` = nội dung 24/7 không gắn badge live. "
        "`*` = kênh xuất hiện ở nhiều ribbon. Số trong 3 cột ngày là số chương trình EPG.")
    add("")

    head = "| Tên hiển thị | Slug | Loại | VIP | " + " | ".join(days) + " | Tổng |"
    sep = "|---|---|---|:---:|" + "|".join("---:" for _ in dates) + "|---:|"
    for group in group_order:
        group_rows = [r for r in channels if r["_primary"] == group]
        add(f"### {group} ({len(group_rows)} kênh)")
        add("")
        add(head)
        add(sep)
        for r in group_rows:
            name = esc(r["channel_name"]) + (" *" if len(r["_cats"]) > 1 else "")
            kind = "LIVE" if r["is_live"] == "yes" else "24/7"
            vip = "VIP" if r["is_premium"] == "yes" else "—"
            add(f"| {name} | `{r['channel_slug']}` | {kind} | {vip} | "
                + " | ".join(str(v) for v in r["_counts"])
                + f" | {num(r['programs_total'])} |")
        add("")

    multi = [r for r in channels if len(r["_cats"]) > 1]
    if multi:
        add("Các kênh nằm trong nhiều ribbon:")
        add("")
        for r in multi:
            add(f"- `{r['channel_slug']}` — " + " · ".join(r["_cats"]))
        add("")

    add("## Kênh thiếu EPG trong 3 ngày")
    add("")
    add("| Kênh | Slug | " + " | ".join(days) + " |")
    add("|---|---|" + "|".join("---:" for _ in dates) + "|")
    for r in missing:
        add(f"| {esc(r['channel_name'])} | `{r['channel_slug']}` | "
            + " | ".join(str(v) for v in r["_counts"]) + " |")
    add("")
    none_breakdown = {
        "kênh nước ngoài": sum(1 for r in none if r["_primary"] == "Kênh nước ngoài"),
        "kênh địa phương": sum(1 for r in none if r["_primary"] == "Kênh Địa Phương"),
        "kênh SCTV": sum(1 for r in none if "Kênh SCTV" in r["_cats"]),
        "kênh VTVcab": sum(1 for r in none if r["_primary"] == "Kênh VTVcab"),
    }
    none_detail = ", ".join(f"{v} {k}" for k, v in none_breakdown.items() if v)
    add(f"> {len(none)} kênh không có bất kỳ chương trình nào trong 3 ngày"
        + (f": {none_detail}" if none_detail else "")
        + ". Nguồn không trả EPG cho các kênh này.")
    add("")

    add("## Lưu ý về slug và tên hiển thị")
    add("")
    add("Một số slug là slug cũ/không còn khớp với tên hiển thị hiện tại:")
    add("")
    add("| Slug | Tên hiển thị | Ghi chú |")
    add("|---|---|---|")
    notes = {
        "vtv6-69452026": "Slug gốc của VTV6 nhưng hiển thị là VTV10; VTV6 hiện dùng slug `vtv6`.",
        "vtvcab-on-golf": "Hiển thị ON SPORTS NEWS; ON GOLF dùng slug `vtvcab-on-golf-1`.",
        "th-hau-giang-ac0ec36d": "Slug Hậu Giang, hiển thị Truyền hình Cần Thơ 2.",
        "dai-pt-th-binh-thuan": "Slug Bình Thuận, hiển thị TH LÂM ĐỒNG 2.",
        "bao-va-pt-th-lam-dong-ltv3": "Slug LTV3, hiển thị Báo và PT-TH Lâm Đồng (LTV1).",
        "sctv19-cb98949a": "Slug chứa `sctv19` nhưng hiển thị SCTV20; SCTV19 dùng `sctv19-bf00bd02`.",
        "carttoon-network-bc24942a": "Slug viết sai `carttoon`, hiển thị Cartoon Network.",
    }
    for slug in mismatch_slugs:
        r = by_slug.get(slug)
        if r:
            add(f"| `{slug}` | {esc(r['channel_name'])} | {notes.get(slug, '')} |")
    add("")

    add("## Chất lượng dữ liệu nguồn")
    add("")
    add(f"- Có **{dup_rows}** dòng trùng khít (cùng kênh/ngày/giờ/tên) — tập trung ở VTV3 ngày {days[1]}.")
    add(f"- VTV3 ngày {days[1]} có **{vtv3_day2}** mục, cao bất thường so với 2 ngày còn lại; "
        "nguồn trả về hai timeline chồng giờ cho ngày này.")
    blank_note = ""
    if blank_titles:
        b = blank_titles[0]
        blank_note = (f" (ví dụ: {b['channel_name']}, {date_label(b['schedule_date'])} "
                      f"{b['start_time']}–{b['end_time']})")
    add(f"- **{len(blank_titles)}** chương trình có tiêu đề rỗng{blank_note}.")
    zero_note = ""
    if zero_duration:
        z = zero_duration[0]
        zero_dates = ", ".join(sorted({date_label(x["schedule_date"]) for x in zero_duration}))
        if len({x["schedule_date"] for x in zero_duration}) > 1:
            zero_note = f" ({z['channel_name']}, {z['start_time']} các ngày {zero_dates})"
        else:
            zero_note = (f" ({z['channel_name']}, {z['start_time']} ngày "
                         f"{date_label(z['schedule_date'])})")
    add(f"- **{len(zero_duration)}** chương trình có thời lượng 0 phút{zero_note}.")
    add("- Dữ liệu được giữ nguyên như API trả về, không tự ý xoá dòng trùng hay sửa giờ.")
    add("")

    add("## Vì sao chọn 24–26/10/2026")
    add("")
    add("Tại thời điểm trích xuất, API EPG chỉ có lịch cho các ngày đã/đang diễn ra. "
        "Kiểm tra riêng ngày 27–28/10/2026: chỉ 4 kênh 24/7 có dữ liệu "
        "(THỂ THAO 24/7, Việt Nam 360, PHIM VIỆT 24/7, VŨ TRỤ HÀI), 90 kênh live còn lại "
        "trả về 0 chương trình. Vì vậy 24–26/10 là 3 ngày liên tiếp gần nhất có EPG đầy đủ.")
    add("")

    add("## API đã dùng")
    add("")
    add("```text")
    add("Ribbons (danh sách kênh):")
    add("https://apicdn.sctvonline.vn/tenants/sctv/tenant_pages/truyen-hinh-ecb1ec92/ribbons/?limit=50")
    add("")
    add("EPG:")
    add("https://apicdn.sctvonline.vn/backend/cm/epg/?channel_id={slug}&schedule_date=YYYY-MM-DD&timezone=Asia/Ho_Chi_Minh")
    add("```")
    add("")

    add("## File dữ liệu")
    add("")
    add("| File | Nội dung |")
    add("|---|---|")
    add("| `sctv_channels.csv` | 94 kênh: tên, slug, nhóm, live/premium, logo, số chương trình từng ngày, tổng, cờ đủ 3 ngày |")
    add("| `sctv_slug_name_map.csv` | Map tra cứu nhanh `channel_slug` → `channel_name` (sắp theo slug) |")
    add("| `sctv_schedule_3days.csv` | 9.228 dòng lịch: ngày, kênh, giờ bắt đầu/kết thúc, tiêu đề, mô tả, thời lượng, link play |")
    add("| `sctv_coverage.csv` | Số chương trình mỗi kênh × mỗi ngày |")
    add("| `sctv_data.json` | Toàn bộ dữ liệu có cấu trúc (channels, coverage, schedule theo ngày/slug) |")
    add("| `sctv_channels_schedule.xlsx` | Workbook: sheet Kênh + 3 sheet lịch theo ngày + sheet Tổng hợp |")
    add("| `sctv_schedule.html` | Viewer tương tác: chọn ngày, tìm kênh/chương trình, lọc nhóm, xem tất cả kênh |")
    add("")
    add("Mở `sctv_schedule.html` trực tiếp bằng trình duyệt (file tự chứa dữ liệu, không cần server).")
    add("")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Dedicated lookup file, sorted by slug.
    map_fields = [
        "channel_slug", "channel_name", "categories", "is_live", "is_premium", "min_tier",
        *[f"programs_{d}" for d in dates], "programs_total", "days_with_epg", "has_epg_3days",
        "detail_url",
    ]
    map_rows = sorted(channels, key=lambda r: r["channel_slug"].casefold())
    write_csv(MAP_CSV, map_rows, map_fields)

    print(f"Wrote {REPORT} ({len(lines)} lines)")
    print(f"Wrote {MAP_CSV} ({len(map_rows)} rows)")
    print()
    print(f"Channels: {len(channels)} | Programs: {num(total_programs)} | "
          f"Full 3-day EPG: {full} | Missing >=1 day: {len(missing)}")


if __name__ == "__main__":
    main()
