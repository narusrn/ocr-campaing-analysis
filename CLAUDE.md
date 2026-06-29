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
```

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
- Category keyword embeddings are averaged per category; cosine similarity assigns items. Threshold is `0.1` — items below get `"อื่นๆ"`.
- Model and vectors are module-level globals, lazy-loaded on first call. Call `reset_cache()` after changing categories to force a rebuild.
- `preprocess_name()` strips spaces between consecutive Thai characters (OCR artifact).
- Category keywords are persisted to `categories_db.json` and editable from the UI (Categories tab).

### Chart rendering (`echarts_helper.py`)
- All charts use Apache ECharts loaded from CDN, rendered as `<iframe>` via `streamlit.components.v1.html`.
- `JS()` wrapper class allows raw JavaScript expressions inside the JSON option dict (used for formatters, symbol sizes). `_dump()` handles serialization of `JS` objects.

### Network visualization (`network_viz.py`)
- `render_item_network()` builds a NetworkX graph of top-N items by frequency, renders with PyVis. Nodes are colored by category using `CAT_COLORS`.
- HTML output from PyVis is patched to inject custom CSS before passing to `components.html`.

### AI summaries (`llm_summary.py`)
- Three context builders (`build_context`, `build_products_context`, `build_rfm_context`) extract aggregated metrics into plain dicts.
- Each sends a Thai-language prompt to `gpt-4o-mini` and returns markdown text.
- `highlight_insight()` converts the markdown response to colored HTML — no external markdown library.

### Caching strategy
- `@st.cache_data` on `get_all_data()`, `get_categorized()`, and the three AI insight functions.
- AI insight cache key includes campaign names + date range. Changing filters triggers a new API call.
- `get_categorized()` uses the campaign name as discriminator key (one cached result per campaign).
- After saving categories or store chains from the UI, caches are cleared via `.clear()` and `st.rerun()`.

### Persistent state (JSON files)
| File | Purpose | Managed by |
|------|---------|------------|
| `categories_db.json` | Category → keyword lists | `categorizer.py` |
| `stores_db.json` | Store chain → keyword lists + online set | `data_loader.py` |

Both files are auto-created on first save; defaults are module-level dicts in their respective modules. New default entries are auto-merged into existing saved configs on load.

### Tab layout
| Tab | Function | Content |
|-----|----------|---------|
| Overview | `tab_overview()` | KPIs, revenue trend, campaign comparison, time heatmap, channel/store breakdown |
| Products | `tab_products()` | Category breakdown, item network graph, co-occurrence heatmap, top combos |
| Customers RFM | `tab_customers()` | Segment KPIs, donut + bubble scatter, top members table |
| Categories | `tab_categories()` | Category keyword editor **and** store chain keyword editor |
