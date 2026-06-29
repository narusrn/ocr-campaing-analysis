import json
import re
from pathlib import Path

import numpy as np

_DB_PATH = Path(__file__).parent / "categories_db.json"

# Nested schema: {category: {keywords, brands, sku_types}}
DEFAULT_CATEGORIES: dict = {
    "สกินแคร์/บิวตี้": {
        "keywords": [
            "ครีม", "โลชั่น", "เซรั่ม", "พอนด์ส", "face wash", "ซันสกรีน",
            "มอยส์เจอร์ไรเซอร์", "บีบีครีม", "ทำความสะอาดหน้า", "ไวท์เทนนิ่ง",
            "pond's", "ponds", "age miracle", "white beauty",
        ],
        "brands": {
            "Pond's":   ["พอนด์ส", "พอนด์", "ponds", "pond"],
            "Dove":     ["โดฟ", "dove"],
            "Vaseline": ["วาสลีน", "vaseline"],
            "Lux":      ["ลักซ์", "lux"],
            "Rexona":   ["รีโซน่า", "rexona"],
        },
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
        "brands": {
            "Breeze":   ["เบรซ", "breeze"],
            "Sunlight": ["ซันไลท์", "sunlight"],
            "Comfort":  ["คอมฟอร์ท", "comfort"],
            "Downy":    ["ดาวนี่", "downy"],
        },
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
        "brands": {},
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
        "brands": {
            "มาม่า":  ["มาม่า", "mama"],
            "ไวไว":   ["ไวไว", "wai wai", "waiwai"],
            "ซีเล็ค": ["ซีเล็ค", "selecta"],
        },
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
        "brands": {
            "Coca-Cola": ["โค้ก", "coke", "coca-cola", "coca cola"],
            "Pepsi":     ["เป๊ปซี่", "pepsi"],
            "สิงห์":     ["สิงห์", "singha"],
            "ช้าง":      ["ช้าง", "chang"],
            "Lipton":    ["ลิปตัน", "lipton"],
            "Milo":      ["ไมโล", "milo"],
        },
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
        "brands": {
            "เลย์":    ["เลย์", "lay's", "lays"],
            "โอริโอ้": ["โอริโอ้", "oreo"],
            "คิทแคท": ["คิทแคท", "kit kat", "kitkat"],
            "Pocky":   ["ป๊อกกี้", "pocky"],
        },
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
        "brands": {
            "Clear":   ["เคลียร์", "clear"],
            "Dove":    ["โดฟ", "dove"],
            "Colgate": ["คอลเกต", "colgate"],
            "Signal":  ["ซิกแนล", "signal"],
            "AXE":     ["แอ็กซ์", "axe"],
        },
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

THRESHOLD = 0.1

_model = None
_cat_vectors = None
_cat_names = None

_THAI_SPACE_RE = re.compile(r'(?<=[฀-๿])\s+(?=[฀-๿])')


def load_categories_db() -> dict:
    if _DB_PATH.exists():
        with open(_DB_PATH, encoding="utf-8") as f:
            saved = json.load(f)
        # Migrate old flat format {cat: [kw, ...]} → new nested format
        migrated = {}
        for cat, val in saved.items():
            if isinstance(val, list):
                migrated[cat] = {"keywords": val, "brands": {}, "sku_types": {}}
            else:
                migrated[cat] = val
        # Merge new default categories not present in saved file
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
    _cat_names = None


def preprocess_name(text: str) -> str:
    """Remove spaces between consecutive Thai characters (OCR artifact)."""
    if not isinstance(text, str):
        return ""
    text = re.sub(r'(?<=[฀-๿])\s+(?=[฀-๿])', '', text)
    return text.strip()


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


def _match_in_cat(name: str, category: str, cats_db: dict, field: str) -> str:
    """Substring match name against {label: [keywords]} within a category's field."""
    cat_data = cats_db.get(category, {})
    if not isinstance(cat_data, dict):
        return "อื่นๆ"
    mapping = cat_data.get(field, {})
    if not mapping:
        return "อื่นๆ"
    cleaned = _THAI_SPACE_RE.sub('', (name or "")).lower()
    for label, kws in mapping.items():
        if any(k.lower() in cleaned for k in kws):
            return label
    return "อื่นๆ"


def classify_items(item_names: list[str], threshold: float = THRESHOLD):
    """Returns list of (category, similarity_score) tuples. Items below threshold → 'อื่นๆ'."""
    model = _load_model()
    cat_names, cat_vectors = _build_category_vectors(model)

    cleaned = [preprocess_name(n) for n in item_names]
    vecs = model.encode(cleaned, batch_size=64, show_progress_bar=False)

    norms_cat = np.linalg.norm(cat_vectors, axis=1, keepdims=True)
    norms_item = np.linalg.norm(vecs, axis=1, keepdims=True)
    sims = (vecs @ cat_vectors.T) / (norms_item * norms_cat.T + 1e-9)

    results = []
    for i in range(len(item_names)):
        best_idx = int(np.argmax(sims[i]))
        best_score = float(sims[i][best_idx])
        results.append(
            (cat_names[best_idx], best_score) if best_score >= threshold
            else ("อื่นๆ", best_score)
        )
    return results


def add_categories_to_df(df, item_col: str = "item_name"):
    """Add category, cat_score, brand, sku_type columns. Returns df."""
    names = df[item_col].fillna("").tolist()

    # 1. Category via ML cosine similarity
    results = classify_items(names)
    categories = [r[0] for r in results]
    df["category"]  = categories
    df["cat_score"] = [r[1] for r in results]

    # 2. Brand + SKU type scoped to each item's category (substring match)
    cats_db = load_categories_db()
    df["brand"]    = [_match_in_cat(n, c, cats_db, "brands")    for n, c in zip(names, categories)]
    df["sku_type"] = [_match_in_cat(n, c, cats_db, "sku_types") for n, c in zip(names, categories)]
    return df
