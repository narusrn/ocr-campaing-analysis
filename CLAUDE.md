# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
streamlit run dashboard.py
```

Install dependencies first:
```bash
pip install -r requirements.txt
```

There are no automated tests. Verify changes by running the app.

## Configuration

**Data source** — `data_loader.py:7`:
```python
DATA_PATH = Path(__file__).parent / "data" / "Slips.xlsx"
```
The file lives at `data/Slips.xlsx` inside the project. Each Excel sheet maps to a campaign via the `CAMPAIGNS` dict (sheet name → display name, `data_loader.py:10`).

**OpenAI API key** — `.streamlit/secrets.toml`:
```toml
OPENAI_API_KEY = "sk-..."
GITHUB_TOKEN = "ghp_..."
```

`GITHUB_TOKEN` requires a fine-grained token with **Contents: Read and write** on the repo. It enables `_git_persist()` in `dashboard.py` to commit JSON config files back to GitHub on every Save, so config survives Streamlit Cloud reboots (ephemeral filesystem).

**Streamlit theme** — `.streamlit/config.toml`. Primary color is `#00A3E0` (Unilever blue). All chart colors follow `PALETTE` and `SEGMENT_COLORS` in `echarts_helper.py`.

## Architecture

Single-page Streamlit dashboard (`dashboard.py`) with four tabs. Data flows one way: load → filter → display. No ORM, no service layer.

### Data pipeline (`data_loader.py`)
- `load_data()` reads all campaign sheets, filters to `slip_status == "approve"` **and** `item_verify == 1`, adds derived columns (`date`, `hour`, `day_of_week`, `store_chain`, `channel`), returns `{display_name: DataFrame}`.
- Store chain classification uses the same sentence-transformers model as `categorizer.py` (lazy-loaded into its own module-level globals). `_classify_chains()` batches all merchant names, computes cosine similarity against keyword embeddings per chain, assigns the best match if `>= STORE_THRESHOLD (0.1)`, else `"Other"`. `_normalize()` does regex-based string cleaning before encoding.
- `get_slip_df(df)` deduplicates to slip-level (one row per slip). Main DataFrames are item-level.
- `compute_rfm(df)` produces R/F/M quintile scores and assigns segments per `RFM_SEGMENTS` (order matters — first match wins).
- `compute_basket_matrix(df)` builds a symmetric category × category co-occurrence count matrix (used by the heatmap in the Products tab).

### Category classification (`categorizer.py`)
- Uses `sentence-transformers` model `paraphrase-multilingual-MiniLM-L12-v2` (multilingual, handles Thai + English).
- Classification pipeline per item: **keyword substring pre-pass** (`_keyword_classify`) → ML cosine similarity fallback. Same pattern for brand and SKU type.
- `_clean(text)` NFC-normalizes, removes Thai-Thai spaces (OCR artifact), lowercases — used before both keyword matching and ML encoding.
- All item names are encoded **once** in `add_categories_to_df()`; the same vectors are reused for category, brand, and SKU type classification.
- Category threshold `THRESHOLD = 0.1`; brand/SKU thresholds `BRAND_THRESHOLD = SKU_THRESHOLD = 0.25`.
- Brand names are all English. `_BRAND_RENAME` migrates any Thai keys found in saved JSON on load and auto-saves the fixed file.
- Brand keywords live in `brands_db.json` (global lookup). Category `brands` field is a list of brand names (keys into `brands_db`).
- Model and category vectors are module-level globals, lazy-loaded. Call `reset_cache()` after changing categories to force a rebuild.
- `preprocess_name()` strips spaces between consecutive Thai characters (legacy; `_clean()` is the preferred normalizer now).

### Chart rendering (`echarts_helper.py`)
- All charts use Apache ECharts loaded from CDN, rendered as `<iframe>` via `streamlit.components.v1.html`.
- `JS()` wrapper class allows raw JavaScript expressions inside the JSON option dict (used for formatters, symbol sizes). `_dump()` handles serialization of `JS` objects.

### Network visualization (`network_viz.py`)
- `render_item_network()` builds a NetworkX graph of top-N items by frequency, renders with PyVis. Nodes are colored by category using `CAT_COLORS`.
- HTML output from PyVis is patched to inject custom CSS before passing to `components.html`.

### AI summaries (`llm_summary.py`)
- Three context builders (`build_context`, `build_products_context`, `build_rfm_context`) extract aggregated metrics into plain dicts.
- Each sends a Thai-language prompt to `gpt-4o-mini` and returns markdown text.
- `_strip_fence()` removes markdown code fences that `gpt-4o-mini` sometimes wraps responses in before passing to `highlight_insight()`.
- `highlight_insight()` converts the markdown response to colored HTML — no external markdown library.

### Caching strategy
- `@st.cache_data` on `get_all_data()`, `get_categorized()`, and the three AI insight functions.
- AI insight cache key includes campaign names + date range. Changing filters triggers a new API call.
- `get_categorized()` uses the campaign name as discriminator key (one cached result per campaign).
- After saving categories or store chains from the UI, caches are cleared via `.clear()` and `st.rerun()`.

### Persistent state (JSON files)
| File | Purpose | Managed by |
|------|---------|------------|
| `categories_db.json` | Category → keywords, brand list, SKU types | `categorizer.py` |
| `brands_db.json` | Brand name → keyword list (global lookup) | `categorizer.py` |
| `stores_db.json` | Store chain → keyword lists + online set | `data_loader.py` |
| `ignore_db.json` | Item name substrings to exclude from pipeline | `data_loader.py` |

All files are committed to git and auto-created on first save if missing. New default entries are auto-merged into existing saved configs on load. On Streamlit Cloud, `_git_persist()` pushes changes back to GitHub on each Save so config survives reboots.

**Data filter** (`load_data()`): rows must satisfy `slip_status == "approve"` AND `item_verify == 1` AND `item_price > 0` AND item name must not match any keyword in `ignore_db.json` (default: ส่วนลด, ธนาคาร, ทรูมันนี่, etc.).

### Tab layout
| Tab | Function | Content |
|-----|----------|---------|
| Overview | `tab_overview()` | KPIs, revenue trend, campaign comparison, time heatmap, channel/store breakdown |
| Products | `tab_products()` | Category breakdown, brand/SKU donuts (top 10 + อื่นๆ), item network graph, co-occurrence heatmap |
| Customers RFM | `tab_customers()` | Segment KPIs, donut + bubble scatter, top members table |
| Categories | `tab_categories()` | Category/brand keyword editor, store chain editor, ignore keywords editor |

**Products tab notes:**
- Brand and SKU type charts show top 10 only; remainder grouped as อื่นๆ.
- Unclassified items (`brand == "อื่นๆ"`) fall back to the campaign's own brand name (matched via `brands_db` against the campaign display name).
- SKU types are edited as textarea with format `Name = kw1|kw2` per line.
- `🔄 Reload Classification` button clears `get_categorized` cache and reruns.

**Streamlit Cloud deploy notes:**
- Reboot ≠ Rerun. Reboot kills the process and redeploys from git; Rerun re-executes the already-deployed code.
- Auto-deploy from GitHub push takes ~1-2 minutes.
