"""Customer segment definitions and classification for the Segments tab."""
import pandas as pd

CHANNEL_SEGMENTS: dict[str, list[str]] = {
    "Convenience Store Shopper": ["7-Eleven", "FamilyMart", "CJ Express"],
    "Hypermarket Shopper":       ["Lotus", "BigC", "MaxValu"],
    "Premium Retail Shopper":    ["Tops", "Gourmet", "Villa", "Foodland", "Rimping", "Home Fresh"],
    "Drug Store Shopper":        ["Watsons", "Boots"],
    "Wholesale Shopper":         ["CP AXTRA"],
}
ONLINE_SEGMENT = "Online Shopper"

CATEGORY_SEGMENTS: dict[str, dict] = {
    "Skincare Shopper":     {"category": "สกินแคร์/บิวตี้",  "sku_types": None},
    "Hair Care Shopper":    {"category": "ของใช้ในบ้าน",      "sku_types": {"แชมพู", "ครีมนวดผม"}},
    "Oral Care Shopper":    {"category": "ของใช้ในบ้าน",      "sku_types": {"ยาสีฟัน"}},
    "Laundry Shopper":      {"category": "ผงซักฟอก/น้ำยา",   "sku_types": {"ผงซักฟอก", "น้ำยาซักผ้า"}},
    "Fabric Care Shopper":  {"category": "ผงซักฟอก/น้ำยา",   "sku_types": {"น้ำยาปรับผ้านุ่ม"}},
    "Dishwash Shopper":     {"category": "ผงซักฟอก/น้ำยา",   "sku_types": {"น้ำยาล้างจาน"}},
    "Snack Shopper":        {"category": "ขนม/ของกินเล่น",    "sku_types": None},
    "Beverage Shopper":     {"category": "เครื่องดื่ม",       "sku_types": None},
    "Ready to Eat Shopper": {"category": "อาหารสำเร็จรูป",    "sku_types": None},
}

HEAVY_PCTILE = 0.8
BULK_QTY     = 3


def compute_segments(df: pd.DataFrame) -> dict[str, dict]:
    """
    Classify members into named segments.

    Returns dict[segment_name, {"members": set[str], "revenue": float}]
    revenue for channel/category = spend on those qualifying rows.
    revenue for behavior = full spend of qualifying members.
    """
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

    # ── Category Affinity ─────────────────────────────────────────────────
    for seg_name, spec in CATEGORY_SEGMENTS.items():
        mask = df["category"] == spec["category"]
        if spec["sku_types"] is not None:
            mask = mask & df["sku_type"].isin(spec["sku_types"])
        sub = df[mask]
        result[seg_name] = {
            "members": set(sub["member"].dropna().unique()),
            "revenue": float(sub["item_price"].sum()),
        }

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
