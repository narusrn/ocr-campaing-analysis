import json
import re
import numpy as np
import pandas as pd
from pathlib import Path

DATA_PATH    = Path(__file__).parent / "data" / "Slips.xlsx"
_STORES_PATH = Path(__file__).parent / "config" / "stores_db.json"
_IGNORE_PATH = Path(__file__).parent / "config" / "ignore_db.json"

DEFAULT_IGNORE_KEYWORDS: list[str] = [
    "ส่วนลด", "discount", "coupon", "คูปอง",
    "ธนาคาร", "ทรูมันนี่", "truemoney", "true money",
]


def load_ignore_db() -> list[str]:
    if _IGNORE_PATH.exists():
        with open(_IGNORE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return list(DEFAULT_IGNORE_KEYWORDS)


def save_ignore_db(keywords: list[str]) -> None:
    with open(_IGNORE_PATH, "w", encoding="utf-8") as f:
        json.dump(keywords, f, ensure_ascii=False, indent=2)

CAMPAIGNS = {
    "PondsxAtlas":              "Pond's x Atlas",
    "BreezeComfortxTleFirstone":"Breeze Comfort x TleFirstone",
    "SunlightXProxieLuckyfan":  "Sunlight x Proxie Luckyfan",
}

DEFAULT_CHAIN_KEYWORDS: dict[str, list[str]] = {
    "7-Eleven":   ["7-eleven", "7eleven", "เซเว่น", "seven eleven", "cp all"],
    "CJ Express": ["cj express", "cjexpress", "ซีเจ"],
    "FamilyMart": ["familymart", "family mart", "แฟมิลี่มาร์ท", "แฟมิลี่"],
    "Lotus":      ["lotus", "โลตัส", "tesco"],
    "BigC":       ["big c", "bigc", "บิ๊กซี", "big-c"],
    "MaxValu":    ["maxvalu", "max valu", "แม็กซ์แวลู"],
    "Tops":       ["tops", "ท็อปส์", "top supermarket"],
    "Foodland":   ["foodland", "ฟู้ดแลนด์"],
    "Villa":      ["villa market", "วิลล่า"],
    "Gourmet":    ["gourmet market", "gourmet", "เกอร์เมต์"],
    "Home Fresh": ["home fresh", "fresh mart", "central fresh"],
    "Rimping":    ["rimping", "ริมปิง"],
    "CP AXTRA":   ["cp axtra", "axtra", "แม็คโคร", "makro", "macro"],
    "Watsons":    ["watsons", "watson", "วัตสัน"],
    "Boots":      ["boots", "บูทส์"],
    "Shopee":     ["shopee"],
    "Lazada":     ["lazada"],
    "TikTok":     ["tiktok", "tik tok", "tik-tok"],
    "Line Shop":  ["line shop", "line shopping"],
}
DEFAULT_ONLINE_CHAINS: set[str] = {"Shopee", "Lazada", "TikTok", "Line Shop"}

STORE_THRESHOLD = 0.1

_store_model    = None
_chain_vectors  = None
_chain_names    = None
_chain_kw_hash  = None


def load_stores_db() -> tuple[dict[str, list[str]], set[str]]:
    if _STORES_PATH.exists():
        with open(_STORES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        chains = data["chains"]
        online = set(data.get("online", []))
        # Auto-add new default chains that aren't in saved config yet
        for name, kws in DEFAULT_CHAIN_KEYWORDS.items():
            if name not in chains:
                chains[name] = kws
                if name in DEFAULT_ONLINE_CHAINS:
                    online.add(name)
        return chains, online
    return dict(DEFAULT_CHAIN_KEYWORDS), set(DEFAULT_ONLINE_CHAINS)


def save_stores_db(chains: dict[str, list[str]], online: set[str]) -> None:
    with open(_STORES_PATH, "w", encoding="utf-8") as f:
        json.dump({"chains": chains, "online": list(online)}, f, ensure_ascii=False, indent=2)


# Each entry: (name, r_range, f_range, m_range)  None = no constraint
RFM_SEGMENTS = [
    ("Champions",       (4, 5), (4, 5), None  ),
    ("Loyal Customers", None,   (3, 5), (3, 5)),
    ("Potential",       (3, 5), (1, 2), None  ),
    ("At Risk",         (1, 2), (3, 5), None  ),
    ("Lost",            (1, 1), (1, 1), None  ),
    ("Promising",       (3, 5), (3, 5), None  ),  # active+frequent but low spend (Loyal already took M3-5)
    ("Hibernating",     (1, 2), (1, 2), None  ),  # infrequent + long ago (Lost already took R1,F1)
]


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r'^[^a-z0-9ก-๙]+', '', s)
    s = re.sub(r'[^a-z0-9ก-๙]+$', '', s)
    s = re.sub(r'\s*[-–—]\s*', '-', s)
    s = re.sub(r'\s*\.\s*', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _get_store_model():
    global _store_model
    if _store_model is None:
        from sentence_transformers import SentenceTransformer
        _store_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _store_model


def _build_chain_vectors(chain_keywords: dict[str, list[str]]):
    global _chain_vectors, _chain_names, _chain_kw_hash
    import hashlib
    h = hashlib.md5(
        json.dumps(chain_keywords, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    if _chain_vectors is not None and _chain_kw_hash == h:
        return _chain_names, _chain_vectors
    model = _get_store_model()
    _chain_names = list(chain_keywords.keys())
    vecs = []
    for kws in chain_keywords.values():
        embs = model.encode([_normalize(k) for k in kws], show_progress_bar=False)
        vecs.append(embs.mean(axis=0))
    _chain_vectors = np.array(vecs)
    _chain_kw_hash = h
    return _chain_names, _chain_vectors


def _classify_chains(names: list, chain_keywords: dict[str, list[str]]) -> list[str]:
    """Batch-classify merchant names via cosine similarity against chain keyword embeddings."""
    model = _get_store_model()
    chain_names, chain_vecs = _build_chain_vectors(chain_keywords)

    unique = [n for n in dict.fromkeys(n for n in names if isinstance(n, str))]
    normalized = [_normalize(n) for n in unique]
    vecs = model.encode(normalized, batch_size=64, show_progress_bar=False)

    norms_c = np.linalg.norm(chain_vecs, axis=1, keepdims=True)
    norms_v = np.linalg.norm(vecs, axis=1, keepdims=True)
    sims = (vecs @ chain_vecs.T) / (norms_v * norms_c.T + 1e-9)

    lookup: dict[str, str] = {}
    for i, name in enumerate(unique):
        best_idx = int(np.argmax(sims[i]))
        lookup[name] = chain_names[best_idx] if sims[i][best_idx] >= STORE_THRESHOLD else "Other"

    return [lookup.get(n, "Other") if isinstance(n, str) else "Other" for n in names]


def load_data() -> dict[str, pd.DataFrame]:
    """Load all sheets, filter approved, add derived columns."""
    chain_keywords, online_chains = load_stores_db()
    ignore_kws = load_ignore_db()
    result = {}
    for sheet, display in CAMPAIGNS.items():
        df = pd.read_excel(DATA_PATH, sheet_name=sheet, engine="openpyxl")
        df["slip_created_at"] = pd.to_datetime(df["slip_created_at"], errors="coerce")
        df["slip_total"]      = pd.to_numeric(df["slip_total"],  errors="coerce")
        df["item_price"]      = pd.to_numeric(df["item_price"],  errors="coerce")
        df["item_amount"]     = pd.to_numeric(df["item_amount"], errors="coerce")

        _ignore_pat = "|".join(re.escape(k) for k in ignore_kws) if ignore_kws else None
        _ignored = df["item_name"].str.contains(_ignore_pat, case=False, na=False, regex=True) if _ignore_pat else pd.Series(False, index=df.index)
        df = df[
            (df["slip_status"] == "approve") &
            (df["item_verify"] == 1) &
            (df["item_price"] > 0) &
            (~_ignored)
        ].copy()

        df["date"]        = df["slip_created_at"].dt.date
        df["hour"]        = df["slip_created_at"].dt.hour
        df["day_of_week"] = df["slip_created_at"].dt.day_name()
        df["week"]        = df["slip_created_at"].dt.to_period("W").astype(str)

        df["store_chain"] = _classify_chains(df["merchantname"].tolist(), chain_keywords)
        df["channel"] = df["store_chain"].apply(
            lambda c: "Online" if c in online_chains else "Offline"
        )
        df["campaign"] = display
        result[display] = df
    return result


def load_promotion_slip_ids() -> set:
    """Return slip_ids of approved slips that contain a discount item
    (item_name contains 'ส่วนลด' or item_price < 0)."""
    result: set = set()
    for sheet in CAMPAIGNS:
        df = pd.read_excel(DATA_PATH, sheet_name=sheet, engine="openpyxl",
                           usecols=lambda c: c in ("slip_status", "slip_id", "item_name", "item_price"))
        df = df[df["slip_status"] == "approve"].copy()
        df["item_price"] = pd.to_numeric(df["item_price"], errors="coerce")
        promo = df[
            df["item_name"].str.contains("ส่วนลด", na=False) |
            (df["item_price"] < 0)
        ]
        result |= set(promo["slip_id"].dropna().unique())
    return result


def load_ocr_accuracy() -> dict[str, dict]:
    """OCR accuracy per campaign: % of all rows where item_name == item_ocrname."""
    result = {}
    for sheet, display in CAMPAIGNS.items():
        df = pd.read_excel(DATA_PATH, sheet_name=sheet, engine="openpyxl",
                           usecols=lambda c: c in ("slip_status", "item_name", "item_ocrname"))
        df = df[df["slip_status"] == "approve"]
        if "item_ocrname" not in df.columns or len(df) == 0:
            continue
        match = (df["item_name"] == df["item_ocrname"])
        result[display] = {"correct": int(match.sum()), "total": len(df)}
    return result


def get_slip_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset="slip_id")[
        ["slip_id", "member", "slip_total", "slip_created_at",
         "date", "hour", "day_of_week", "week",
         "store_chain", "channel", "campaign", "merchantname"]
    ].copy()


def compute_rfm(df: pd.DataFrame, ref_date=None) -> pd.DataFrame:
    slip_df = get_slip_df(df)
    if ref_date is None:
        ref_date = slip_df["slip_created_at"].max()

    rfm = slip_df.groupby("member").agg(
        last_purchase=("slip_created_at", "max"),
        frequency=("slip_id",            "count"),
        monetary=("slip_total",           "sum"),
    ).reset_index()
    rfm["recency_days"] = (ref_date - rfm["last_purchase"]).dt.days

    def score_col(series, ascending=True, labels=(1, 2, 3, 4, 5)):
        try:
            return pd.qcut(series.rank(method="first", ascending=ascending),
                           q=5, labels=labels).astype(int)
        except Exception:
            return pd.Series([3] * len(series), index=series.index)

    rfm["R"] = score_col(rfm["recency_days"], ascending=False)
    rfm["F"] = score_col(rfm["frequency"],    ascending=True)
    rfm["M"] = score_col(rfm["monetary"],     ascending=True)

    def _in(val, rng):
        return rng is None or (rng[0] <= val <= rng[1])

    def assign_segment(row):
        r, f, m = row["R"], row["F"], row["M"]
        for name, rr, fr, mr in RFM_SEGMENTS:
            if _in(r, rr) and _in(f, fr) and _in(m, mr):
                return name
        return "Others"

    rfm["segment"] = rfm.apply(assign_segment, axis=1)
    return rfm


def compute_basket_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cats = [c for c in df["category"].unique() if c != "อื่นๆ"]
    matrix = pd.DataFrame(0, index=cats, columns=cats)
    for _, grp in df.groupby("slip_id"):
        slip_cats = [c for c in grp["category"].unique() if c != "อื่นๆ"]
        for i, c1 in enumerate(slip_cats):
            for c2 in slip_cats[i:]:
                matrix.loc[c1, c2] += 1
                if c1 != c2:
                    matrix.loc[c2, c1] += 1
    return matrix
