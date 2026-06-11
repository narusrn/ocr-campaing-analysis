import json
import re
from pathlib import Path

import numpy as np

_DB_PATH = Path(__file__).parent / "categories_db.json"

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "สกินแคร์/บิวตี้": [
        "ครีม", "โลชั่น", "เซรั่ม", "พอนด์ส", "face wash", "ซันสกรีน",
        "มอยส์เจอร์ไรเซอร์", "บีบีครีม", "ทำความสะอาดหน้า", "ไวท์เทนนิ่ง",
        "pond's", "ponds", "age miracle", "white beauty",
    ],
    "ผงซักฟอก/น้ำยา": [
        "เบรซ", "ผงซักฟอก", "น้ำยาล้างจาน", "ซันไลท์", "ปรับผ้านุ่ม", "คอมฟอร์ท",
        "breeze", "sunlight", "comfort", "downy", "เปาปุ้นจิ้น", "แฟ้บ",
        "น้ำยาซักผ้า", "softener", "detergent",
    ],
    "อาหารสด": [
        "หมู", "ไก่", "ปลา", "ผัก", "ไข่", "กุ้ง", "เนื้อ", "หมูสับ", "ไก่ย่าง",
        "ผักสด", "ผลไม้", "กล้วย", "แอปเปิ้ล",
    ],
    "อาหารสำเร็จรูป": [
        "มาม่า", "ข้าวกล่อง", "แซนวิช", "ไส้กรอก", "บะหมี่", "ข้าวต้ม",
        "ลูกชิ้น", "สุกี้", "อาหารกระป๋อง", "โจ๊ก", "ซีเล็ค",
    ],
    "เครื่องดื่ม": [
        "น้ำเปล่า", "นม", "กาแฟ", "โค้ก", "น้ำผลไม้", "ชา", "เบียร์", "เครื่องดื่ม",
        "เป๊ปซี่", "ฟันต้า", "นมกล่อง", "โอเลี้ยง", "ชาเขียว", "สิงห์", "ช้าง",
    ],
    "ขนม/ของกินเล่น": [
        "ขนมปัง", "คุกกี้", "มันฝรั่ง", "เลย์", "ช็อกโกแลต", "ทอฟฟี่",
        "วาฟเฟิล", "ป๊อปคอร์น", "เยลลี่", "ลูกอม", "สแน็ค", "ขนม",
    ],
    "ของใช้ในบ้าน": [
        "ทิชชู่", "สบู่", "ยาสีฟัน", "แชมพู", "ครีมนวด", "น้ำยาปรับผ้านุ่ม",
        "กระดาษชำระ", "หลอดไฟ", "ถุงขยะ", "สก็อตช์เทป",
    ],
}

THRESHOLD = 0.1

_model = None
_cat_vectors = None
_cat_names = None


def load_categories_db() -> dict[str, list[str]]:
    """Load categories from JSON file, falling back to defaults."""
    if _DB_PATH.exists():
        with open(_DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CATEGORIES)


def save_categories_db(cats: dict[str, list[str]]) -> None:
    """Persist categories to JSON file."""
    with open(_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)


def reset_cache() -> None:
    """Force category vectors to rebuild on next classify call (after DB change)."""
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
    for examples in cats.values():
        embs = model.encode([preprocess_name(e) for e in examples])
        vecs.append(embs.mean(axis=0))
    _cat_vectors = np.array(vecs)
    return _cat_names, _cat_vectors


def classify_items(item_names: list[str], threshold: float = THRESHOLD):
    """
    Returns list of (category, similarity_score) tuples.
    Items below threshold get category "อื่นๆ".
    """
    model = _load_model()
    cat_names, cat_vectors = _build_category_vectors(model)

    cleaned = [preprocess_name(n) for n in item_names]
    vecs = model.encode(cleaned, batch_size=64, show_progress_bar=False)

    norms_cat = np.linalg.norm(cat_vectors, axis=1, keepdims=True)
    norms_item = np.linalg.norm(vecs, axis=1, keepdims=True)
    # cosine similarity: (n_items, n_cats)
    sims = (vecs @ cat_vectors.T) / (norms_item * norms_cat.T + 1e-9)

    results = []
    for i in range(len(item_names)):
        best_idx = int(np.argmax(sims[i]))
        best_score = float(sims[i][best_idx])
        if best_score < threshold:
            results.append(("อื่นๆ", best_score))
        else:
            results.append((cat_names[best_idx], best_score))
    return results


def add_categories_to_df(df, item_col: str = "item_name"):
    """Add 'category' and 'cat_score' columns to df (modifies in-place, returns df)."""
    names = df[item_col].fillna("").tolist()
    results = classify_items(names)
    df["category"] = [r[0] for r in results]
    df["cat_score"] = [r[1] for r in results]
    return df
