"""Customer segment definitions and classification for the Segments tab."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
import pandas as pd

_SEGMENTS_PATH = Path(__file__).parent / "config" / "segments_db.json"

CHANNEL_SEGMENTS: dict[str, list[str]] = {
    "Convenience Store Shopper": ["7-Eleven", "FamilyMart", "CJ Express"],
    "Hypermarket Shopper":       ["Lotus", "BigC", "MaxValu"],
    "Premium Retail Shopper":    ["Tops", "Gourmet", "Villa", "Foodland", "Rimping", "Home Fresh"],
    "Drug Store Shopper":        ["Watsons", "Boots"],
    "Wholesale Shopper":         ["CP AXTRA"],
}
ONLINE_SEGMENT = "Online Shopper"

# list of {segment, category, sku_type} — one row per rule, same segment name = union
_DEFAULT_CATEGORY_SEGMENTS: list[dict] = [
    {"segment": "Skincare Shopper",     "category": "สกินแคร์/บิวตี้",  "sku_type": ""},
    {"segment": "Hair Care Shopper",    "category": "ของใช้ในบ้าน",      "sku_type": "แชมพู"},
    {"segment": "Hair Care Shopper",    "category": "ของใช้ในบ้าน",      "sku_type": "ครีมนวดผม"},
    {"segment": "Oral Care Shopper",    "category": "ของใช้ในบ้าน",      "sku_type": "ยาสีฟัน"},
    {"segment": "Laundry Shopper",      "category": "ผงซักฟอก/น้ำยา",   "sku_type": "ผงซักฟอก"},
    {"segment": "Laundry Shopper",      "category": "ผงซักฟอก/น้ำยา",   "sku_type": "น้ำยาซักผ้า"},
    {"segment": "Fabric Care Shopper",  "category": "ผงซักฟอก/น้ำยา",   "sku_type": "น้ำยาปรับผ้านุ่ม"},
    {"segment": "Dishwash Shopper",     "category": "ผงซักฟอก/น้ำยา",   "sku_type": "น้ำยาล้างจาน"},
    {"segment": "Snack Shopper",        "category": "ขนม/ของกินเล่น",    "sku_type": ""},
    {"segment": "Beverage Shopper",     "category": "เครื่องดื่ม",       "sku_type": ""},
    {"segment": "Ready to Eat Shopper", "category": "อาหารสำเร็จรูป",    "sku_type": ""},
]

HEAVY_PCTILE = 0.8
BULK_QTY     = 3


def load_category_segments() -> list[dict]:
    if not _SEGMENTS_PATH.exists():
        return list(_DEFAULT_CATEGORY_SEGMENTS)
    try:
        saved = json.loads(_SEGMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, list):
            return saved
        # migrate from old dict format {name: {category, sku_types}}
        rows: list[dict] = []
        for name, spec in saved.items():
            skus = spec.get("sku_types") or [""]
            for sku in skus:
                rows.append({"segment": name, "category": spec["category"], "sku_type": sku or ""})
        return rows
    except Exception:
        return list(_DEFAULT_CATEGORY_SEGMENTS)


def save_category_segments(data: list[dict]) -> None:
    _SEGMENTS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def compute_segments(df: pd.DataFrame) -> dict[str, dict]:
    """Returns dict[segment_name, {"members": set[str], "revenue": float}]"""
    result: dict[str, dict] = {}

    # ── Retail Channel ────────────────────────────────────────────────────
    for seg_name, chains in CHANNEL_SEGMENTS.items():
        sub = df[df["store_chain"].isin(chains)]
        result[seg_name] = {
            "members": set(sub["member"].dropna().unique()),
            "revenue": float(sub["item_price"].sum()),
        }

    online_sub = df[df["channel"] == "Online"]
    result[ONLINE_SEGMENT] = {
        "members": set(online_sub["member"].dropna().unique()),
        "revenue": float(online_sub["item_price"].sum()),
    }

    # ── Category Affinity — group rows by segment name, union members ─────
    seg_groups: dict[str, list[dict]] = defaultdict(list)
    for row in load_category_segments():
        seg_groups[row["segment"]].append(row)

    for seg_name, rows in seg_groups.items():
        members: set = set()
        revenue = 0.0
        for row in rows:
            mask = df["category"] == row["category"]
            if row.get("sku_type"):
                mask = mask & (df["sku_type"] == row["sku_type"])
            sub = df[mask]
            members |= set(sub["member"].dropna().unique())
            revenue += float(sub["item_price"].sum())
        result[seg_name] = {"members": members, "revenue": revenue}

    # ── Shopper Behavior ──────────────────────────────────────────────────
    member_spend = df.groupby("member")["item_price"].sum()
    heavy_set: set = set()
    if len(member_spend) > 0:
        threshold = member_spend.quantile(HEAVY_PCTILE)
        heavy_set = set(member_spend[member_spend >= threshold].index)
    result["Heavy Shopper"] = {
        "members": heavy_set,
        "revenue": float(df[df["member"].isin(heavy_set)]["item_price"].sum()),
    }

    bulk_set = set(df[df["item_amount"] >= BULK_QTY]["member"].dropna().unique())
    result["Bulk Shopper"] = {
        "members": bulk_set,
        "revenue": float(df[df["member"].isin(bulk_set)]["item_price"].sum()),
    }

    return result
