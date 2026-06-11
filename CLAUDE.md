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

## Configuration

**Data source** — hardcoded in [data_loader.py:6](data_loader.py):
```python
DATA_PATH = r"C:\Users\User\Downloads\Slips.xlsx"
```
The Excel file has one sheet per campaign (keys in the `CAMPAIGNS` dict at line 9).

**OpenAI API key** — stored in [.streamlit/secrets.toml](.streamlit/secrets.toml):
```toml
OPENAI_API_KEY = "sk-..."
```

**Streamlit theme** — [.streamlit/config.toml](.streamlit/config.toml). Primary color is `#00A3E0` (Unilever blue). All chart colors follow `PALETTE` and `SEGMENT_COLORS` defined in [echarts_helper.py](echarts_helper.py).

## Architecture

The app is a single-page Streamlit dashboard with four tabs driven by `dashboard.py`. Data flows in one direction: load → filter → display.

### Data pipeline (`data_loader.py`)
- `load_data()` reads all campaign sheets from Excel, filters to `slip_status == "approve"`, adds derived columns (`date`, `hour`, `day_of_week`, `store_chain`, `channel`), and returns `{campaign_display_name: DataFrame}`.
- Store chain matching uses regex against normalized merchant names. Config is persisted to `stores_db.json` and editable from the UI (Categories tab).
- `get_slip_df(df)` deduplicates to slip-level (one row per slip). The main DataFrames are item-level (one row per line item).
- `compute_rfm(df)` produces R/F/M quintile scores and assigns segments per `RFM_SEGMENTS` list (order matters — first match wins).

### Category classification (`categorizer.py`)
- Uses `sentence-transformers` model `paraphrase-multilingual-MiniLM-L12-v2` (multilingual, handles Thai + English).
- Category keyword embeddings are averaged per category, then cosine similarity is used to assign items. Threshold is `0.35` — items below get `"อื่นๆ"`.
- Model and vectors are module-level globals, lazy-loaded on first call. Call `reset_cache()` after changing categories to force a rebuild.
- Category keywords are persisted to `categories_db.json` and editable from the UI.

### Chart rendering (`echarts_helper.py`)
- All charts use Apache ECharts loaded from CDN, rendered as `<iframe>` via `streamlit.components.v1.html`.
- `JS()` wrapper class allows raw JavaScript expressions to be embedded in the JSON option dict (used for formatters, symbol sizes). The `_dump()` function handles the JSON serialization of `JS` objects.

### Network visualization (`network_viz.py`)
- `render_item_network()` builds a NetworkX graph of top-N items by frequency, then renders with PyVis. Nodes are colored by category using `CAT_COLORS`.
- The HTML output from PyVis is patched to inject custom CSS before being sent to `components.html`.

### AI summaries (`llm_summary.py`)
- Three context builders (`build_context`, `build_products_context`, `build_rfm_context`) extract aggregated metrics from DataFrames into plain dicts.
- Each sends a Thai-language prompt to `gpt-4o-mini` and returns markdown text.
- `highlight_insight()` converts the markdown response to colored HTML — no external markdown library.

### Caching strategy
- `@st.cache_data` on `get_all_data()`, `get_categorized()`, and the three AI insight functions.
- AI insight cache key includes campaign names + date range. Changing filters triggers a new API call.
- `get_categorized()` uses the campaign name as discriminator key to keep one cached result per campaign.
- After saving categories or store chains from the UI, the relevant caches are cleared via `.clear()` and `st.rerun()`.

### Persistent state (JSON files)
| File | Purpose | Managed by |
|------|---------|------------|
| `categories_db.json` | Category → keyword lists | `categorizer.py` |
| `stores_db.json` | Store chain → keyword/regex lists + online set | `data_loader.py` |

Both files are auto-created on first save; defaults are defined as module-level dicts in their respective modules. New default entries are auto-merged into existing saved configs on load.
