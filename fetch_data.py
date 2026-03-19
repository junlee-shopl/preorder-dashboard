"""
fetch_data.py — Shopl Pre-order API → data.json
Usage: python fetch_data.py
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timezone

# ── Config ──────────────────────────────────────────────────────────────────
CAMPAIGN_ID  = "26b704cf-8b77-4c07-bbe3-c79bc8c9ba8c"
AUTH_KEY     = os.environ.get("SHOPL_AUTH_KEY", "")
BASE_URL     = "https://dashboard.shoplworks.com"
START_DATE   = "2026-02-26"
END_DATE     = "2026-03-17"
PAGE_SIZE    = 500
CAMPAIGN_NAME = "Pre-order Galaxy S26 Series & Galaxy Buds4 Series"

# SKU → price (IDR), extracted from Excel master data
SKU_PRICE = {
    "SM-S948BZKCXID": 24499000, "SM-S948BZWCXID": 24499000,
    "SM-S948BZVCXID": 24499000, "SM-S948BLBCXID": 24499000,
    "SM-S948BZWQXID": 27499000, "SM-S948BZVQXID": 27499000,
    "SM-S948BZKQXID": 27499000, "SM-S948BLBQXID": 27499000,
    "SM-S947BZKCXID": 19499000, "SM-S947BZWCXID": 19499000,
    "SM-S947BZVCXID": 19499000, "SM-S947BLBCXID": 19499000,
    "SM-S942BZKQXID": 16499000, "SM-S942BZWQXID": 16499000,
    "SM-S942BZVQXID": 16499000, "SM-S942BLBQXID": 16499000,
    "SM-R640NZKAXSE": 3999000,  "SM-R640NZWAXSE": 3399150,
    "SM-R540NZKAXSE": 2549150,  "SM-R540NZWAXSE": 2549150,
}

PRODUCT_GROUPS = [
    "Galaxy S26 Ultra", "Galaxy S26 Plus", "Galaxy S26",
    "Galaxy Buds4 Pro", "Galaxy Buds4",
]

# ── Helpers ──────────────────────────────────────────────────────────────────
def extract_product_group(promotion_name: str) -> str:
    for g in PRODUCT_GROUPS:
        if g in promotion_name:
            return g
    return promotion_name

def fetch_page(page: int) -> dict:
    url = (
        f"{BASE_URL}/api/po/campaign/{CAMPAIGN_ID}/orders"
        f"?authKey={AUTH_KEY}&page={page}&pageSize={PAGE_SIZE}"
        f"&startDate={START_DATE}&endDate={END_DATE}"
    )
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())["body"]

def map_record(r: dict, batch_map: dict) -> dict:
    dt = r.get("orderDate", "") or ""          # "2026-02-26 09:12:34"
    date_part = dt[:10] if dt else ""
    time_part = dt[11:16] if len(dt) >= 16 else ""

    pickup_dt  = r.get("pickUpDt") or ""
    pickup_date = pickup_dt[:10]  if pickup_dt else ""
    pickup_time = pickup_dt[11:16] if len(pickup_dt) >= 16 else ""

    return {
        "date":         date_part,
        "time":         time_part,
        "batch":        batch_map.get(r["batchId"], "Batch 1"),
        "productGroup": extract_product_group(r.get("promotionName", "")),
        "price":        SKU_PRICE.get(r.get("productSKU", ""), 0),
        "distributor":  r.get("retailerName", ""),
        "status":       "Sudah diambil" if r.get("orderStatus") == "DONE" else "Belum diambil",
        "pickupDate":   pickup_date,
        "pickupTime":   pickup_time,
    }

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    if not AUTH_KEY:
        raise EnvironmentError("SHOPL_AUTH_KEY environment variable is not set.")
    print("Fetching page 0 ...")
    first = fetch_page(0)
    total_elements = first["totalElements"]
    total_pages    = math.ceil(total_elements / PAGE_SIZE)
    print(f"Total: {total_elements:,} records over {total_pages} pages")

    all_content = list(first["content"])

    for page in range(1, total_pages):
        print(f"  page {page}/{total_pages - 1} ...", end="\r")
        body = fetch_page(page)
        all_content.extend(body["content"])

    print(f"\nFetched {len(all_content):,} records")

    # Build batch_map: sort unique batchIds by their earliest orderDate → Batch 1, 2, ...
    batch_earliest: dict[str, str] = {}
    for r in all_content:
        bid = r["batchId"]
        dt  = r.get("orderDate", "") or ""
        if bid not in batch_earliest or dt < batch_earliest[bid]:
            batch_earliest[bid] = dt
    sorted_batches = sorted(batch_earliest, key=lambda b: batch_earliest[b])
    batch_map = {bid: f"Batch {i+1}" for i, bid in enumerate(sorted_batches)}
    print("Batch mapping:", {v: batch_earliest[k][:10] for k, v in batch_map.items()})

    # Map records
    records = [map_record(r, batch_map) for r in all_content]

    # Derive period
    dates = sorted(set(r["date"] for r in records if r["date"]))
    period = f"{dates[0]} ~ {dates[-1]}" if dates else f"{START_DATE} ~ {END_DATE}"

    output = {
        "name":       CAMPAIGN_NAME,
        "period":     period,
        "updatedAt":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records":    records,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = len(json.dumps(output, separators=(",", ":"))) / 1024
    picked  = sum(1 for r in records if r["status"] == "Sudah diambil")
    print(f"data.json saved — {len(records):,} records, {size_kb:.0f} KB")
    print(f"Pickup rate: {picked/len(records)*100:.1f}% ({picked:,}/{len(records):,})")

if __name__ == "__main__":
    main()
