import json
import re
import unicodedata
from pathlib import Path

import numpy as np

_DB_PATH     = Path(__file__).parent / "categories_db.json"
_BRANDS_PATH = Path(__file__).parent / "brands_db.json"

# Global brand → keyword list (config once, reference by name in categories)
DEFAULT_BRANDS: dict[str, list[str]] = {
    "Pond's":    ["พอนด์ส", "พอนด์", "ponds", "pond"],
    "Dove":      ["โดฟ", "dove"],
    "Vaseline":  ["วาสลีน", "vaseline"],
    "Lux":       ["ลักซ์", "lux"],
    "Rexona":    ["รีโซน่า", "rexona"],
    "Breeze":    ["เบรซ", "breeze"],
    "Sunlight":  ["ซันไลท์", "sunlight"],
    "Comfort":   ["คอมฟอร์ท", "comfort"],
    "Downy":     ["ดาวนี่", "downy"],
    "Coca-Cola": ["โค้ก", "coke", "coca-cola", "coca cola"],
    "Pepsi":     ["เป๊ปซี่", "pepsi"],
    "สิงห์":     ["สิงห์", "singha"],
    "ช้าง":      ["ช้าง", "chang"],
    "Lipton":    ["ลิปตัน", "lipton"],
    "Milo":      ["ไมโล", "milo"],
    "มาม่า":     ["มาม่า", "mama"],
    "ไวไว":      ["ไวไว", "wai wai", "waiwai"],
    "ซีเล็ค":    ["ซีเล็ค", "selecta"],
    "เลย์":      ["เลย์", "lay's", "lays"],
    "โอริโอ้":   ["โอริโอ้", "oreo"],
    "คิทแคท":   ["คิทแคท", "kit kat", "kitkat"],
    "Pocky":     ["ป๊อกกี้", "pocky"],
    "Clear":     ["เคลียร์", "clear"],
    "Colgate":   ["คอลเกต", "colgate"],
    "Signal":    ["ซิกแนล", "signal"],
    "AXE":       ["แอ็กซ์", "axe"],
}

# categories: brands = list of brand names (keywords looked up from brands_db)
DEFAULT_CATEGORIES: dict = {
    "สกินแคร์/บิวตี้": {
        "keywords": [
            "ครีม", "โลชั่น", "เซรั่ม", "พอนด์ส", "face wash", "ซันสกรีน",
            "มอยส์เจอร์ไรเซอร์", "บีบีครีม", "ทำความสะอาดหน้า", "ไวท์เทนนิ่ง",
            "pond's", "ponds", "age miracle", "white beauty",
        ],
        "brands": ["Pond's", "Dove", "Vaseline", "Lux", "Rexona"],
        "sku_types": {
            "เซรั่ม":            ["serum", "เซรั่ม"],
            "ครีมกลางวัน":      ["day cream", "เดย์ครีม", "day"],
            "ครีมกลางคืน":      ["night cream", "ไนท์ครีม", "night"],
            "ครีมบำรุง":        ["moisturizer", "มอยส์เจอร์", "lotion", "โลชั่น", "body"],
            "เฟสวอช":           ["face wash", "foam", "โฟม", "facial"],
            "ซันสกรีน":         ["sunscreen", "ซันสกรีน", "spf", "กันแดด"],
            "บีบีครีม/รองพื้น": ["bb cream", "บีบี", "foundation", "รองพื้น"],
        },
    },
    "ผงซักฟอก/น้ำยา": {
        "keywords": [
            "เบรซ", "ผงซักฟอก", "น้ำยาล้างจาน", "ซันไลท์", "ปรับผ้านุ่ม", "คอมฟอร์ท",
            "breeze", "sunlight", "comfort", "downy", "เปาปุ้นจิ้น", "แฟ้บ",
            "น้ำยาซักผ้า", "softener", "detergent",
        ],
        "brands": ["Breeze", "Sunlight", "Comfort", "Downy"],
        "sku_types": {
            "ผงซักฟอก":          ["ผงซักฟอก", "detergent", "washing powder"],
            "น้ำยาล้างจาน":      ["น้ำยาล้างจาน", "dish", "dishwash", "จาน"],
            "น้ำยาปรับผ้านุ่ม":  ["ปรับผ้านุ่ม", "softener", "fabric"],
            "น้ำยาซักผ้า":       ["น้ำยาซักผ้า", "liquid detergent"],
        },
    },
    "อาหารสด": {
        "keywords": [
            "หมู", "ไก่", "ปลา", "ผัก", "ไข่", "กุ้ง", "เนื้อ", "หมูสับ", "ไก่ย่าง",
            "ผักสด", "ผลไม้", "กล้วย", "แอปเปิ้ล",
        ],
        "brands": [],
        "sku_types": {
            "เนื้อสัตว์": ["หมู", "ไก่", "เนื้อ", "กุ้ง", "ปลา", "หมูสับ"],
            "ผัก":        ["ผัก", "ผักสด", "ผักบุ้ง", "กะหล่ำ"],
            "ผลไม้":      ["ผลไม้", "กล้วย", "แอปเปิ้ล", "ส้ม", "มะม่วง"],
            "ไข่":        ["ไข่"],
        },
    },
    "อาหารสำเร็จรูป": {
        "keywords": [
            "มาม่า", "ข้าวกล่อง", "แซนวิช", "ไส้กรอก", "บะหมี่", "ข้าวต้ม",
            "ลูกชิ้น", "สุกี้", "อาหารกระป๋อง", "โจ๊ก", "ซีเล็ค",
        ],
        "brands": ["มาม่า", "ไวไว", "ซีเล็ค"],
        "sku_types": {
            "บะหมี่กึ่งสำเร็จรูป": ["บะหมี่", "instant noodle", "โจ๊ก"],
            "ข้าวกล่อง":           ["ข้าวกล่อง", "ข้าว"],
            "ลูกชิ้น/ไส้กรอก":    ["ลูกชิ้น", "ไส้กรอก", "sausage"],
            "อาหารกระป๋อง":        ["กระป๋อง", "tuna", "ทูน่า"],
        },
    },
    "เครื่องดื่ม": {
        "keywords": [
            "น้ำเปล่า", "นม", "กาแฟ", "โค้ก", "น้ำผลไม้", "ชา", "เบียร์", "เครื่องดื่ม",
            "เป๊ปซี่", "ฟันต้า", "นมกล่อง", "โอเลี้ยง", "ชาเขียว", "สิงห์", "ช้าง",
        ],
        "brands": ["Coca-Cola", "Pepsi", "สิงห์", "ช้าง", "Lipton", "Milo"],
        "sku_types": {
            "น้ำเปล่า":  ["น้ำเปล่า", "water", "น้ำดื่ม"],
            "นม":        ["นม", "milk", "นมกล่อง", "นมถุง"],
            "กาแฟ":      ["กาแฟ", "coffee", "โอเลี้ยง", "latte"],
            "น้ำอัดลม":  ["โค้ก", "เป๊ปซี่", "ฟันต้า", "soda", "น้ำอัดลม"],
            "ชาเขียว":   ["ชาเขียว", "green tea", "ชา"],
            "เบียร์":    ["เบียร์", "beer", "สิงห์", "ช้าง"],
            "น้ำผลไม้":  ["น้ำผลไม้", "juice"],
        },
    },
    "ขนม/ของกินเล่น": {
        "keywords": [
            "ขนมปัง", "คุกกี้", "มันฝรั่ง", "เลย์", "ช็อกโกแลต", "ทอฟฟี่",
            "วาฟเฟิล", "ป๊อปคอร์น", "เยลลี่", "ลูกอม", "สแน็ค", "ขนม",
        ],
        "brands": ["เลย์", "โอริโอ้", "คิทแคท", "Pocky"],
        "sku_types": {
            "มันฝรั่งทอด":   ["มันฝรั่ง", "chips", "เลย์"],
            "ช็อกโกแลต":    ["ช็อกโกแลต", "chocolate", "kitkat"],
            "คุกกี้":        ["คุกกี้", "cookie", "โอริโอ้"],
            "ขนมปัง":        ["ขนมปัง", "bread"],
            "ลูกอม/เยลลี่":  ["ลูกอม", "เยลลี่", "candy", "gummy"],
        },
    },
    "ของใช้ในบ้าน": {
        "keywords": [
            "ทิชชู่", "สบู่", "ยาสีฟัน", "แชมพู", "ครีมนวด", "น้ำยาปรับผ้านุ่ม",
            "กระดาษชำระ", "หลอดไฟ", "ถุงขยะ", "สก็อตช์เทป",
        ],
        "brands": ["Clear", "Dove", "Colgate", "Signal", "AXE"],
        "sku_types": {
            "แชมพู":             ["แชมพู", "shampoo"],
            "ครีมนวดผม":        ["ครีมนวด", "conditioner"],
            "สบู่/เจลอาบน้ำ":   ["สบู่", "soap", "shower", "body wash"],
            "ยาสีฟัน":          ["ยาสีฟัน", "toothpaste", "colgate"],
            "ทิชชู่/กระดาษ":    ["ทิชชู่", "กระดาษชำระ", "tissue"],
            "ถุงขยะ":           ["ถุงขยะ", "garbage bag", "ถุง"],
        },
    },
}

THRESHOLD       = 0.1
BRAND_THRESHOLD = 0.25
SKU_THRESHOLD   = 0.25

_model      = None
_cat_vectors = None
_cat_names  = None

_THAI_SPACE_RE  = re.compile(r'(?<=[฀-๿])\s+(?=[฀-๿])')
_MULTI_SPACE_RE = re.compile(r'\s+')


def _clean(text: str) -> str:
    """Normalize item name for keyword matching:
    1. NFC normalize (fix OCR combining-char byte order)
    2. remove spaces between Thai chars (OCR artifact: โ ด ฟ → โดฟ)
    3. collapse all remaining whitespace to single space
    4. strip and lowercase
    """
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize('NFC', text)
    t = _THAI_SPACE_RE.sub('', t)
    t = _MULTI_SPACE_RE.sub(' ', t)
    return t.strip().lower()


# ── Persistence ───────────────────────────────────────────────────────────────

def load_brands_db() -> dict[str, list[str]]:
    if _BRANDS_PATH.exists():
        with open(_BRANDS_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        for name, kws in DEFAULT_BRANDS.items():
            if name not in saved:
                saved[name] = kws
        return saved
    return dict(DEFAULT_BRANDS)


def save_brands_db(brands: dict[str, list[str]]) -> None:
    with open(_BRANDS_PATH, "w", encoding="utf-8") as f:
        json.dump(brands, f, ensure_ascii=False, indent=2)


def load_categories_db() -> dict:
    if _DB_PATH.exists():
        with open(_DB_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        migrated = {}
        for cat, val in saved.items():
            if isinstance(val, list):
                # v1 flat → v3
                migrated[cat] = {"keywords": val, "brands": [], "sku_types": {}}
            elif isinstance(val, dict):
                brands = val.get("brands", [])
                if isinstance(brands, dict):
                    # v2 (brands as {name: [kws]}) → v3 (brands as [name, ...])
                    val["brands"] = list(brands.keys())
                migrated[cat] = val
            else:
                migrated[cat] = val
        for cat, val in DEFAULT_CATEGORIES.items():
            if cat not in migrated:
                migrated[cat] = val
        return migrated
    return dict(DEFAULT_CATEGORIES)


def save_categories_db(cats: dict) -> None:
    with open(_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)


def reset_cache() -> None:
    global _cat_vectors, _cat_names
    _cat_vectors = None
    _cat_names   = None


# ── Text preprocessing ────────────────────────────────────────────────────────

def preprocess_name(text: str) -> str:
    """Remove spaces between consecutive Thai characters (OCR artifact)."""
    if not isinstance(text, str):
        return ""
    return re.sub(r'(?<=[฀-๿])\s+(?=[฀-๿])', '', text).strip()


# ── ML category classification ────────────────────────────────────────────────

def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _model


def _build_category_vectors(model):
    global _cat_vectors, _cat_names
    if _cat_vectors is not None:
        return _cat_names, _cat_vectors
    cats = load_categories_db()
    _cat_names = list(cats.keys())
    vecs = []
    for cat_data in cats.values():
        kws = cat_data["keywords"] if isinstance(cat_data, dict) else cat_data
        embs = model.encode([preprocess_name(e) for e in kws])
        vecs.append(embs.mean(axis=0))
    _cat_vectors = np.array(vecs)
    return _cat_names, _cat_vectors


def classify_items(item_names: list[str], threshold: float = THRESHOLD):
    """Returns list of (category, score) tuples. Items below threshold → 'อื่นๆ'."""
    model = _load_model()
    cat_names, cat_vectors = _build_category_vectors(model)

    cleaned    = [preprocess_name(n) for n in item_names]
    vecs       = model.encode(cleaned, batch_size=64, show_progress_bar=False)
    norms_cat  = np.linalg.norm(cat_vectors, axis=1, keepdims=True)
    norms_item = np.linalg.norm(vecs, axis=1, keepdims=True)
    sims       = (vecs @ cat_vectors.T) / (norms_item * norms_cat.T + 1e-9)

    results = []
    for i in range(len(item_names)):
        best_idx   = int(np.argmax(sims[i]))
        best_score = float(sims[i][best_idx])
        results.append(
            (cat_names[best_idx], best_score) if best_score >= threshold
            else ("อื่นๆ", best_score)
        )
    return results


# ── Keyword matching ──────────────────────────────────────────────────────────

def _match_brand(name: str, category: str, cats_db: dict, brands_db: dict) -> str:
    """Lookup category's brand list, then check global brands_db keywords."""
    cat_data    = cats_db.get(category, {})
    brand_names = cat_data.get("brands", []) if isinstance(cat_data, dict) else []
    cleaned = _clean(name)
    for brand_name in brand_names:
        kws = brands_db.get(brand_name, [])
        if any(k.lower() in cleaned for k in kws):
            return brand_name
    return "อื่นๆ"


def _match_in_cat(name: str, category: str, cats_db: dict, field: str) -> str:
    """Substring match within a category's sku_types field."""
    cat_data = cats_db.get(category, {})
    if not isinstance(cat_data, dict):
        return "อื่นๆ"
    mapping = cat_data.get(field, {})
    if not mapping:
        return "อื่นๆ"
    cleaned = _clean(name)
    for label, kws in mapping.items():
        if any(k.lower() in cleaned for k in kws):
            return label
    return "อื่นๆ"


# ── Keyword-first category pre-pass ──────────────────────────────────────────

def _keyword_classify(name: str, cats_db: dict) -> str | None:
    """Substring match against category keywords. Returns category or None."""
    cleaned = _clean(name)
    for cat, cat_data in cats_db.items():
        kws = cat_data["keywords"] if isinstance(cat_data, dict) else cat_data
        if any(k.lower() in cleaned for k in kws):
            return cat
    return None


# ── ML fallback for brand / SKU type ─────────────────────────────────────────

def _ml_fill(results: list, all_vecs, categories: list,
             cats_db: dict, brands_db: dict | None, field: str) -> None:
    """In-place: for items still 'อื่นๆ', assign via cosine similarity."""
    from collections import defaultdict
    model     = _load_model()
    threshold = BRAND_THRESHOLD if field == "brands" else SKU_THRESHOLD

    by_cat: dict[str, list[int]] = defaultdict(list)
    for i, r in enumerate(results):
        if r == "อื่นๆ":
            by_cat[categories[i]].append(i)

    for cat, indices in by_cat.items():
        cd = cats_db.get(cat, {})
        if not isinstance(cd, dict):
            continue
        if field == "brands":
            brand_names = cd.get("brands", [])
            labels_kws  = {b: brands_db.get(b, []) for b in brand_names if brands_db and brands_db.get(b)}
        else:
            labels_kws = cd.get("sku_types", {})
        if not labels_kws:
            continue

        label_list = list(labels_kws.keys())
        lvecs = np.array([
            model.encode([_clean(k) for k in kws], show_progress_bar=False).mean(axis=0)
            for kws in labels_kws.values()
        ])
        ivecs   = all_vecs[np.array(indices)]
        norms_i = np.linalg.norm(ivecs,  axis=1, keepdims=True)
        norms_l = np.linalg.norm(lvecs,  axis=1, keepdims=True)
        sims    = (ivecs @ lvecs.T) / (norms_i * norms_l.T + 1e-9)

        for j, idx in enumerate(indices):
            best = int(np.argmax(sims[j]))
            if sims[j][best] >= threshold:
                results[idx] = label_list[best]


# ── Main entry point ──────────────────────────────────────────────────────────

def add_categories_to_df(df, item_col: str = "item_name"):
    """Add category, cat_score, brand, sku_type columns. Returns df."""
    names     = df[item_col].fillna("").tolist()
    cats_db   = load_categories_db()
    brands_db = load_brands_db()
    model     = _load_model()

    # Encode ALL names once — shared by category ML, brand ML, SKU ML
    all_vecs = model.encode([_clean(n) for n in names], batch_size=64, show_progress_bar=False)

    # ── Category: keyword pre-pass then ML ───────────────────────────────────
    kw_cats  = [_keyword_classify(n, cats_db) for n in names]
    needs_ml = [i for i, c in enumerate(kw_cats) if c is None]
    if needs_ml:
        cat_names, cat_vecs = _build_category_vectors(model)
        sub      = all_vecs[np.array(needs_ml)]
        norms_c  = np.linalg.norm(cat_vecs, axis=1, keepdims=True)
        norms_s  = np.linalg.norm(sub,      axis=1, keepdims=True)
        sims     = (sub @ cat_vecs.T) / (norms_s * norms_c.T + 1e-9)
        for j, i in enumerate(needs_ml):
            best  = int(np.argmax(sims[j]))
            score = float(sims[j][best])
            kw_cats[i] = (cat_names[best] if score >= THRESHOLD else "อื่นๆ", score)

    categories, cat_scores = [], []
    for c in kw_cats:
        if isinstance(c, tuple):
            categories.append(c[0]); cat_scores.append(c[1])
        else:
            categories.append(c);    cat_scores.append(1.0)

    # ── Brand: keyword then ML ────────────────────────────────────────────────
    brands = [_match_brand(n, c, cats_db, brands_db) for n, c in zip(names, categories)]
    _ml_fill(brands, all_vecs, categories, cats_db, brands_db, "brands")

    # ── SKU type: keyword then ML ─────────────────────────────────────────────
    skus = [_match_in_cat(n, c, cats_db, "sku_types") for n, c in zip(names, categories)]
    _ml_fill(skus, all_vecs, categories, cats_db, None, "sku_types")

    df["category"]  = categories
    df["cat_score"] = cat_scores
    df["brand"]     = brands
    df["sku_type"]  = skus
    return df
