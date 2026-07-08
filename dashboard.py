import subprocess
from pathlib import Path

import streamlit as st
import pandas as pd


def _git_persist(*filenames: str) -> None:
    """Commit and push config files to GitHub so they survive Streamlit Cloud reboots."""
    try:
        token = st.secrets.get("GITHUB_TOKEN", "")
    except Exception:
        return  # local dev — no secrets file
    if not token:
        return

    cwd = Path(__file__).parent
    repo = "https://narusrn:{}@github.com/narusrn/ocr-campaing-analysis.git".format(token)
    run  = lambda *cmd: subprocess.run(list(cmd), cwd=cwd, capture_output=True)

    run("git", "config", "user.email", "bot@streamlit.app")
    run("git", "config", "user.name",  "Streamlit Config Bot")
    run("git", "remote", "set-url", "origin", repo)
    for f in filenames:
        run("git", "add", f)
    run("git", "commit", "-m", f"chore: save config {', '.join(filenames)}", "--allow-empty")
    run("git", "push", "origin", "main")

import echarts_helper as ec
from data_loader import (load_data, get_slip_df, compute_rfm, compute_basket_matrix,
                         load_stores_db, save_stores_db,
                         DEFAULT_CHAIN_KEYWORDS, DEFAULT_ONLINE_CHAINS,
                         load_ignore_db, save_ignore_db, DEFAULT_IGNORE_KEYWORDS)
from categorizer import (add_categories_to_df, preprocess_name,
                         load_categories_db, save_categories_db,
                         load_brands_db, save_brands_db,
                         reset_cache, DEFAULT_CATEGORIES, DEFAULT_BRANDS)
from network_viz import render_item_network, render_legend, CAT_COLORS
from llm_summary import (build_context, generate_summary,
                          build_products_context, generate_products_summary,
                          build_rfm_context, generate_rfm_summary,
                          highlight_insight)

st.set_page_config(
    page_title="Campaign OCR Analytics",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded",
)

PALETTE = ec.PALETTE
SEGMENT_COLORS = ec.SEGMENT_COLORS



# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"], .stMarkdown, .stText,
button, input, textarea, select, label {
    font-family: 'Sarabun', sans-serif !important;
}

/* ── Scrollbar ──────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #D6E4F7; }
::-webkit-scrollbar-thumb { background: #7AAAE0; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #0064F0; }

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #F0F5FF !important;
    border-right: 1px solid #BDD0F0;
    box-shadow: 0px 1px 2px 0px #0000000f, 0px 1px 3px 0px #0000001a;
}

/* ── Tabs ─────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 2px solid #BDD0F0;
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #3D4F66;
    font-size: 14px;
    font-weight: 600;
    padding: 8px 20px;
    border-radius: 8px 8px 0 0;
    border: none;
    transition: color 0.18s, background 0.18s;
}
.stTabs [data-baseweb="tab"]:hover {
    background: rgba(0,100,240,0.05);
    color: #182B45;
}
.stTabs [aria-selected="true"] {
    background: rgba(0,100,240,0.06) !important;
    color: #0064F0 !important;
    border-bottom: 2.5px solid #0064F0 !important;
}

/* ── KPI cards ────────────────────────────────────────────────────── */
.kpi-card {
    background: #ffffff;
    border-radius: 12px;
    padding: 18px 22px;
    margin-bottom: 12px;
    border: 1px solid #E4E7ED;
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0px 4px 6px -2px #00000008, 0px 12px 16px -4px #00000014;
}
.kpi-label {
    color: #3362B0; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
}
.kpi-value { color: #182B45; font-size: 28px; font-weight: 700; line-height: 1.2; }
.kpi-sub   { color: #7C8DA0; font-size: 12px; margin-top: 4px; }

/* ── Section titles ───────────────────────────────────────────────── */
.section-title {
    color: #0064F0; font-size: 11px; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1.5px;
    border-bottom: 2px solid #BDD0F0;
    padding-bottom: 6px; margin: 22px 0 12px;
    display: flex; align-items: center; gap: 8px;
}

/* ── AI Insight card ──────────────────────────────────────────────── */
.insight-card {
    background: linear-gradient(135deg, #e4f9ff 0%, #ccf4ff 100%);
    border: 1px solid #b8e8f8;
    border-left: 3px solid #0064F0;
    border-radius: 12px;
    padding: 20px 24px;
    margin: 4px 0 16px;
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a;
}

/* ── Expanders ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #ffffff;
    border: 1px solid #E4E7ED;
    border-radius: 12px;
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a;
    transition: box-shadow 0.18s;
    overflow: hidden;
}
[data-testid="stExpander"]:hover {
    box-shadow: 0px 4px 6px -2px #00000008, 0px 12px 16px -4px #00000014;
}

/* ── Buttons ──────────────────────────────────────────────────────── */
[data-testid="stButton"] > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 14px;
    border: 1px solid #E4E7ED;
    background: #ffffff;
    color: #182B45;
    transition: all 0.18s ease;
    box-shadow: 0px 1px 2px 0px #0000000d;
}
[data-testid="stButton"] > button:hover {
    border-color: #0064F0;
    background: #0064F0;
    color: #ffffff;
    transform: translateY(-1px);
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a;
}
[data-testid="stButton"] > button[kind="primary"],
[data-testid="stBaseButton-primary"] {
    background: #0064F0 !important;
    border-color: transparent !important;
    color: #fff !important;
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a !important;
}
[data-testid="stButton"] > button[kind="primary"]:hover,
[data-testid="stBaseButton-primary"]:hover {
    background: #0050c0 !important;
    box-shadow: 0px 4px 6px -2px #00000008, 0px 12px 16px -4px #00000014 !important;
    transform: translateY(-1px);
}

/* ── Text inputs & text areas ─────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea,
[data-testid="stNumberInput"] input {
    background: #F8F9FC !important;
    border: 1px solid #E4E7ED !important;
    border-radius: 8px !important;
    color: #182B45 !important;
    transition: border-color 0.18s, box-shadow 0.18s;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: #0064F0 !important;
    box-shadow: 0 0 0 3px rgba(0,100,240,0.14) !important;
    outline: none;
}

/* ── Selectbox / Multiselect ──────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-baseweb="select"] > div {
    background: #F8F9FC !important;
    border-color: #E4E7ED !important;
    border-radius: 8px !important;
}

/* ── Dataframe ────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #E4E7ED;
    box-shadow: 0px 2px 4px -2px #0000000f, 0px 4px 8px -2px #0000001a;
}

/* ── iframes (ECharts / PyVis) ────────────────────────────────────── */
iframe {
    border-radius: 12px;
    border: 1px solid #BDD0F0 !important;
    box-shadow: 0px 4px 6px -2px #00000010, 0px 12px 16px -4px #0064F018;
}

/* ── Alerts ───────────────────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px;
    border-left-width: 3px;
}

/* ── Dividers ─────────────────────────────────────────────────────── */
hr {
    border-color: #E4E7ED !important;
    margin: 20px 0 !important;
}

/* ── Checkboxes & Radios ──────────────────────────────────────────── */
[data-testid="stRadio"] label span,
[data-testid="stCheckbox"] label span { color: #182B45; }

/* ── Captions ─────────────────────────────────────────────────────── */
[data-testid="stCaptionContainer"] p {
    color: #3362B0 !important;
    font-size: 12px;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def kpi(label, value, sub="", color="#0064F0"):
    st.markdown(
        f'<div class="kpi-card" style="border-left:4px solid {color}">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'<div class="kpi-sub">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def section(title):
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)


def chart_title(label):
    st.markdown(
        f'<p style="font-size:12px;font-weight:700;color:#3362B0;'
        f'text-transform:uppercase;letter-spacing:.8px;margin:0 0 0px">{label}</p>',
        unsafe_allow_html=True,
    )


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Loading data...")
def get_all_data():
    return load_data()


@st.cache_data(show_spinner="AI กำลังวิเคราะห์ข้อมูล...")
def get_insight(ctx_key: str, ctx_json: str) -> str:
    import json
    _ = ctx_key
    return generate_summary(json.loads(ctx_json))


@st.cache_data(show_spinner="AI กำลังวิเคราะห์สินค้า...")
def get_product_insight(ctx_key: str, ctx_json: str) -> str:
    import json
    _ = ctx_key
    return generate_products_summary(json.loads(ctx_json))


@st.cache_data(show_spinner="AI กำลังวิเคราะห์ลูกค้า...")
def get_rfm_insight(ctx_key: str, ctx_json: str) -> str:
    import json
    _ = ctx_key
    return generate_rfm_summary(json.loads(ctx_json))


@st.cache_data(show_spinner="Computing categories (first run ~1 min)...")
def get_categorized(key, _df):
    _ = key  # cache discriminator: one entry per campaign
    return add_categories_to_df(_df.copy())


# ── Sidebar ───────────────────────────────────────────────────────────────────
all_data = get_all_data()
campaign_names = list(all_data.keys())

with st.sidebar:
    st.markdown("### 📊 Campaign Analytics")
    st.divider()

    selected = st.multiselect(
        "Campaign", campaign_names, default=campaign_names, key="camp_filter"
    )
    if not selected:
        st.warning("Select at least one campaign.")
        st.stop()

    st.divider()

    all_dates = pd.concat([get_slip_df(d)["slip_created_at"] for d in all_data.values()])
    min_d, max_d = all_dates.min().date(), all_dates.max().date()
    date_range = st.date_input("Date Range", (min_d, max_d), min_value=min_d, max_value=max_d)
    d_from = date_range[0] if len(date_range) > 0 else min_d
    d_to   = date_range[1] if len(date_range) > 1 else max_d

    st.divider()
    st.caption("Approved slips only")


# ── Filter ────────────────────────────────────────────────────────────────────
def filter_df(df):
    slip = get_slip_df(df)
    valid = slip[
        (slip["slip_created_at"].dt.date >= d_from) &
        (slip["slip_created_at"].dt.date <= d_to)
    ]["slip_id"]
    return df[df["slip_id"].isin(valid)].copy()


filtered = {c: filter_df(all_data[c]) for c in selected}


# ═════════════════════════════════════════════════════════════════════════════
# Tab 1 — Overview  (Performance + Time & Location)
# ═════════════════════════════════════════════════════════════════════════════
def tab_overview():
    all_slip  = pd.concat([get_slip_df(d) for d in filtered.values()])
    all_items = pd.concat(filtered.values())  # item-level for revenue (item_verify==1 only)

    # ── AI Insights (auto-generate, cached per filter state) ─────────────────
    section("AI CAMPAIGN INSIGHTS")
    import json as _json
    ctx      = build_context(all_slip, filtered)
    ctx_json = _json.dumps(ctx, ensure_ascii=False, default=str, sort_keys=True)
    ctx_key  = f"{'-'.join(sorted(filtered.keys()))}|{d_from}|{d_to}"
    raw_text = get_insight(ctx_key, ctx_json)
    st.markdown(
        f'<div class="insight-card">{highlight_insight(raw_text)}</div>',
        unsafe_allow_html=True,
    )

    # KPI row
    c = st.columns(5)
    for col, label, val, color in zip(c, [
        "Total Revenue", "Total Orders", "Unique Members", "Avg Basket", "Campaigns"
    ], [
        f"฿{all_items['item_price'].sum():,.2f}",
        f"{all_slip['slip_id'].nunique():,}",
        f"{all_slip['member'].nunique():,}",
        f"฿{all_items.groupby('slip_id')['item_price'].sum().mean():,.2f}",
        str(len(filtered)),
    ], PALETTE):
        with col:
            kpi(label, val, color=color)

    # Daily revenue trend — multi-series area
    section("DAILY REVENUE TREND")
    series_list = []
    for i, (name, df) in enumerate(filtered.items()):
        d = df.groupby("date")["item_price"].sum().reset_index().sort_values("date")
        series_list.append({
            "name": name,
            "dates": [str(r) for r in d["date"]],
            "values": d["item_price"].tolist(),
            "color": PALETTE[i % len(PALETTE)],
        })
    ec.area_line(series_list, height=300)

    # Campaign comparison 4-up
    section("CAMPAIGN COMPARISON")
    summary = [{
        "Campaign": name,
        "Revenue":    float(df["item_price"].sum()),
        "Orders":     int(df["slip_id"].nunique()),
        "Members":    int(df["member"].nunique()),
        "Avg Basket": float(df.groupby("slip_id")["item_price"].sum().mean()),
    } for name, df in filtered.items()]
    sdf = pd.DataFrame(summary)
    cats = sdf["Campaign"].str.split(" x ").str[0].tolist()

    c1, c2, c3 = st.columns([1.1, 1.6, 1.1])
    with c1:
        chart_title("Revenue (฿)")
        ec.bar_v(cats, sdf["Revenue"].tolist(), color=PALETTE[0], height=260, currency=True)
    with c2:
        chart_title("Orders  &  Unique Members")
        ec.bar_v_multi(cats, [
            {"name": "Orders",   "values": sdf["Orders"].tolist(),  "color": PALETTE[1]},
            {"name": "Members",  "values": sdf["Members"].tolist(), "color": PALETTE[2]},
        ], height=260)
    with c3:
        chart_title("Avg Basket (฿)")
        ec.bar_v(cats, sdf["Avg Basket"].tolist(), color=PALETTE[3], height=260, currency=True)

    # ── Time & Location ───────────────────────────────────────────────────────
    section("ORDER HEATMAP — DAY × HOUR")
    heat = all_slip.groupby(["day_of_week", "hour"])["slip_id"].count().reset_index()
    heat.columns = ["day", "hour", "orders"]
    heat["day"] = pd.Categorical(heat["day"], categories=DAY_ORDER, ordered=True)
    pivot = (heat.pivot(index="day", columns="hour", values="orders")
                 .reindex(DAY_ORDER).fillna(0))
    pivot.index = DAY_ABBR

    hours = list(range(24))
    matrix = [
        [int(pivot.loc[day, h]) if h in pivot.columns else 0 for h in hours]
        for day in DAY_ABBR
    ]
    ec.heatmap_grid(x_labels=[str(h) for h in hours], y_labels=DAY_ABBR,
                    matrix=matrix, height=260)

    c1, c2 = st.columns(2)
    with c1:
        section("ORDERS BY HOUR")
        hour_counts = all_slip.groupby("hour")["slip_id"].count().reindex(range(24), fill_value=0)
        ec.bar_v(categories=[f"{h}:00" for h in range(24)],
                 values=hour_counts.tolist(), color=PALETTE[0], height=240)

    with c2:
        section("ORDERS BY DAY OF WEEK")
        dow_counts = (all_slip.groupby("day_of_week")["slip_id"]
                              .count().reindex(DAY_ORDER, fill_value=0))
        ec.bar_v(categories=DAY_ABBR, values=dow_counts.tolist(),
                 color=PALETTE[2], height=240)

    section("CHANNEL & STORE ANALYSIS")
    c3, c4 = st.columns([1, 2])

    with c3:
        chan = all_items.groupby("channel")["item_price"].sum().reset_index()
        ec.donut(labels=chan["channel"].tolist(),
                 values=chan["item_price"].round(0).astype(int).tolist(),
                 colors=[PALETTE[0], PALETTE[2]], height=280)
        st.caption("Revenue: Online vs Offline")

    with c4:
        chain = (all_items.groupby("store_chain")["item_price"].sum()
                          .reset_index().sort_values("item_price"))
        ec.bar_h(categories=chain["store_chain"].tolist(),
                 values=chain["item_price"].round(0).astype(int).tolist(),
                 color=PALETTE[1], height=280, currency=True)
        st.caption("Revenue by Store Chain (฿)")

    # Review unmatched merchant names
    other_rows = all_items[all_items["store_chain"] == "Other"]
    other_slips = all_slip[all_slip["store_chain"] == "Other"]
    if not other_rows.empty:
        other_pct = len(other_slips) / len(all_slip) * 100
        with st.expander(
            f"🔍 Other Stores — {len(other_slips):,} slips ({other_pct:.1f}%) ยังไม่ถูก match",
            expanded=False,
        ):
            tbl = (
                other_rows.groupby("merchantname")
                .agg(slips=("slip_id", "nunique"), revenue=("item_price", "sum"))
                .reset_index()
                .sort_values("slips", ascending=False)
                .rename(columns={"merchantname": "Merchant Name",
                                 "slips": "# Slips", "revenue": "Revenue (฿)"})
            )
            tbl["Revenue (฿)"] = tbl["Revenue (฿)"].apply(lambda v: f"฿{v:,.2f}")
            st.caption("เพิ่ม keyword ใน CHAIN_KEYWORDS ใน data_loader.py แล้ว restart")
            st.dataframe(tbl.head(100), hide_index=True, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# Tab 2 — Products
# ═════════════════════════════════════════════════════════════════════════════
def tab_products():
    _brands_db = load_brands_db()
    def _campaign_brand(campaign: str) -> str:
        low = campaign.lower()
        for bname, kws in _brands_db.items():
            if any(k.lower() in low for k in kws):
                return bname
        return campaign

    cat_dfs = {}
    for name, df in filtered.items():
        cdf = get_categorized(name, df).copy()
        cdf.loc[cdf["brand"] == "อื่นๆ", "brand"] = _campaign_brand(name)
        cat_dfs[name] = cdf
    combined = pd.concat(cat_dfs.values())

    # Guard: clear stale cache if brand/sku_type columns missing (old cached DFs)
    if "brand" not in combined.columns or "sku_type" not in combined.columns:
        get_categorized.clear()
        st.rerun()

    if st.button("🔄 Reload Classification", help="ใช้หลัง Save config ใน Categories tab เพื่อ re-classify ใหม่"):
        get_categorized.clear()
        st.rerun()

    # ── AI Insights ───────────────────────────────────────────────────────────
    section("AI PRODUCT INSIGHTS")
    import json as _json
    p_ctx     = build_products_context(combined)
    p_ctx_key = f"prod|{'-'.join(sorted(filtered.keys()))}|{d_from}|{d_to}"
    p_raw     = get_product_insight(p_ctx_key, _json.dumps(p_ctx, ensure_ascii=False, default=str))
    st.markdown(
        f'<div class="insight-card">{highlight_insight(p_raw)}</div>',
        unsafe_allow_html=True,
    )

    section("CATEGORY BREAKDOWN")
    c1, c2 = st.columns(2)

    with c1:
        rev = (combined.groupby("category")["item_price"].sum()
                       .reset_index().sort_values("item_price"))
        ec.bar_h(
            categories=rev["category"].tolist(),
            values=rev["item_price"].round(0).astype(int).tolist(),
            color=PALETTE[0], height=320, currency=True,
        )
        st.caption("Revenue by Category (฿)")

    with c2:
        cnt = combined["category"].value_counts().reset_index()
        cnt.columns = ["category", "count"]
        ec.donut(cnt["category"].tolist(), cnt["count"].tolist(), height=320, currency=False)
        st.caption("Item Distribution by Category")

    # ── Brand & SKU Type Breakdown ────────────────────────────────────────────
    section("BRAND & SKU TYPE BREAKDOWN")
    col_brand, col_sku = st.columns(2)

    with col_brand:
        chart_title("Brand — Revenue Share (Top 10)")
        br = (combined.groupby("brand")["item_price"]
              .agg(revenue="sum", count="count")
              .reset_index().sort_values("revenue", ascending=False))
        top_br   = br.head(10)
        rest_br  = br.iloc[10:]
        if not rest_br.empty:
            other_row = pd.DataFrame([{"brand": "อื่นๆ",
                                       "revenue": rest_br["revenue"].sum(),
                                       "count":   rest_br["count"].sum()}])
            top_br = pd.concat([top_br, other_row], ignore_index=True)
        ec.donut(
            labels=top_br["brand"].tolist(),
            values=top_br["revenue"].round(0).astype(int).tolist(),
            height=340,
            show_count=True,
        )

    with col_sku:
        chart_title("SKU Type — Revenue (Top 10)")
        sk_known = combined[combined["sku_type"] != "อื่นๆ"]
        if sk_known.empty:
            st.info("ไม่มีข้อมูล — config SKU Types ใน Categories tab")
        else:
            sk = (sk_known.groupby("sku_type")["item_price"]
                  .agg(revenue="sum", count="count")
                  .reset_index().sort_values("revenue", ascending=False).head(10))
            ec.bar_v(
                categories=sk["sku_type"].tolist(),
                values=sk["revenue"].round(0).astype(int).tolist(),
                color=PALETTE[0],
                height=340,
                currency=True,
                rotate=30,
            )
        unc_sku = combined[combined["sku_type"] == "อื่นๆ"]
        if not unc_sku.empty:
            unc_pct = len(unc_sku) / len(combined) * 100
            with st.expander(
                f"🔍 ยังไม่ระบุ SKU Type — {len(unc_sku):,} items ({unc_pct:.0f}%) · คลิกเพื่อดูและเพิ่ม keyword",
                expanded=False,
            ):
                st.caption("item_name ที่พบบ่อยสุด — นำ keyword ไปเพิ่มใน Categories tab › SKU Types")
                top_unk = (unc_sku.groupby(["category", "item_name"])["item_price"]
                           .agg(count="count", revenue="sum")
                           .reset_index().sort_values("count", ascending=False).head(40))
                st.dataframe(
                    top_unk.rename(columns={"category": "Category", "item_name": "Item Name",
                                            "count": "Count", "revenue": "Revenue (฿)"}),
                    use_container_width=True, hide_index=True,
                )

    # ── Network / Heatmap toggle ──────────────────────────────────────────────
    section("PRODUCT NETWORK & CO-OCCURRENCE")
    render_legend()

    view_mode = st.radio(
        "Visualization",
        ["🌐 Network Graph", "🔥 Co-occurrence Heatmap"],
        horizontal=True, key="viz_mode",
    )

    if view_mode == "🌐 Network Graph":
        col_a, col_b = st.columns([1, 3])
        with col_a:
            top_n    = st.slider("Top N items", 20, 120, 60, 10, key="top_n")
            min_edge = st.slider("Min co-occurrence", 1, 10, 2, 1, key="min_edge")
        with col_b:
            st.caption(
                "Nodes = individual products · "
                "Color = category · "
                "Edge = bought in same slip · "
                "Node size = frequency"
            )
        render_item_network(combined, top_n=top_n, min_edge=min_edge, height=600)

    else:
        matrix = compute_basket_matrix(combined)
        if not matrix.empty:
            hours_matrix = matrix.values.tolist()
            ec.heatmap_grid(
                x_labels=matrix.columns.tolist(),
                y_labels=matrix.index.tolist(),
                matrix=hours_matrix,
                height=380,
            )
            st.caption("# Slips containing both categories simultaneously")

    # Top combos
    section("TOP CATEGORY COMBINATIONS")
    combos = []
    for df in cat_dfs.values():
        for _, grp in df.groupby("slip_id"):
            cats = sorted({c for c in grp["category"] if c != "อื่นๆ"})
            for i in range(len(cats)):
                for j in range(i + 1, len(cats)):
                    combos.append(f"{cats[i]}  +  {cats[j]}")
    if combos:
        cdf = pd.Series(combos).value_counts().head(12).reset_index()
        cdf.columns = ["combo", "count"]
        cdf = cdf.sort_values("count")
        ec.bar_h(
            categories=cdf["combo"].tolist(),
            values=cdf["count"].tolist(),
            color=PALETTE[2],
            height=max(300, len(cdf) * 38),
        )
        st.caption("# Slips containing both categories")

    # Uncategorized review
    with st.expander("🔍 Uncategorized Items — review and add keywords to categorizer.py", expanded=False):
        unc = combined[combined["category"] == "อื่นๆ"].copy()
        unc["item_clean"] = unc["item_name"].apply(preprocess_name)
        tbl = (
            unc.groupby("item_clean")
            .agg(count=("item_name", "count"),
                 avg_score=("cat_score", "mean"),
                 avg_price=("item_price", "mean"))
            .reset_index()
            .sort_values("count", ascending=False)
            .rename(columns={"item_clean": "Item (cleaned)", "count": "Occurrences",
                             "avg_score": "Best Similarity", "avg_price": "Avg Price (฿)"})
        )
        pct = len(unc) / len(combined) * 100 if len(combined) else 0
        st.caption(
            f"{len(unc):,} uncategorized rows ({pct:.1f}%) — "
            "add to `categorizer.py → CATEGORIES` then restart"
        )
        st.dataframe(tbl.head(200), hide_index=True, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# Tab 3 — Customers RFM
# ═════════════════════════════════════════════════════════════════════════════
def tab_customers():
    rfm_camp = st.selectbox("Campaign", list(filtered.keys()), key="rfm_camp")
    rfm = compute_rfm(filtered[rfm_camp])
    segs = rfm["segment"].value_counts()
    total = len(rfm)

    # Segment KPIs
    seg_list = list(SEGMENT_COLORS.items())
    cols = st.columns(len(seg_list))
    for col, (seg, color) in zip(cols, seg_list):
        cnt = int(segs.get(seg, 0))
        with col:
            kpi(seg, str(cnt), sub=f"{cnt/total*100:.1f}%", color=color)

    # ── AI Insights ───────────────────────────────────────────────────────────
    section("AI CUSTOMER INSIGHTS")
    import json as _json
    r_ctx     = build_rfm_context(rfm, rfm_camp)
    r_ctx_key = f"rfm|{rfm_camp}|{d_from}|{d_to}"
    r_raw     = get_rfm_insight(r_ctx_key, _json.dumps(r_ctx, ensure_ascii=False, default=str))
    st.markdown(
        f'<div class="insight-card">{highlight_insight(r_raw)}</div>',
        unsafe_allow_html=True,
    )

    section("SEGMENT DISTRIBUTION & RFM MAP")

    SEG_DEFS = {
        "Champions":       ("#00C896", "R4-5 · F4-5",        "ซื้อล่าสุด + บ่อยมาก — กลุ่ม VIP ที่ดีที่สุด"),
        "Loyal Customers": ("#0064F0", "F3-5 · M3-5",        "ซื้อบ่อยและใช้เงินสูง — รักษาความสัมพันธ์ไว้"),
        "Potential":       ("#F0C800", "R3-5 · F1-2",        "ซื้อล่าสุดแต่ยังไม่บ่อย — โอกาส convert เป็น Loyal"),
        "Promising":       ("#00A3E0", "R3-5 · F3-5 · M1-2", "ซื้อบ่อย+ล่าสุด แต่ยอดต่ำ — กระตุ้นให้ใช้จ่ายมากขึ้น"),
        "At Risk":         ("#FB654E", "R1-2 · F3-5",        "เคยซื้อบ่อยแต่หายไปนาน — ต้องรีบดึงกลับ"),
        "Hibernating":     ("#D19E36", "R1-2 · F1-2",        "ไม่ค่อยซื้อและนานมากแล้ว — อาจต้องการแรงจูงใจ"),
        "Lost":            ("#A3AAB5", "R1 · F1",            "ซื้อน้อยและนานมากแล้ว — ยาก win back"),
    }
    with st.expander("📖 Segment Definitions", expanded=True):
        rows = "".join(
            f'<tr>'
            f'<td style="padding:6px 10px;white-space:nowrap">'
            f'<span style="display:inline-block;width:10px;height:10px;border-radius:50%;'
            f'background:{color};margin-right:6px;vertical-align:middle"></span>'
            f'<strong style="color:#182B45">{seg}</strong></td>'
            f'<td style="padding:6px 10px;color:#3362B0;font-size:12px;white-space:nowrap">{criteria}</td>'
            f'<td style="padding:6px 10px;color:#3D4F66;font-size:12px">{desc}</td>'
            f'</tr>'
            for seg, (color, criteria, desc) in SEG_DEFS.items()
        )
        st.markdown(
            f'<table style="border-collapse:collapse;width:100%;font-family:Sarabun,sans-serif">'
            f'<thead><tr style="border-bottom:2px solid #BDD0F0">'
            f'<th style="padding:6px 10px;text-align:left;color:#3362B0;font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px">Segment</th>'
            f'<th style="padding:6px 10px;text-align:left;color:#3362B0;font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px">R · F · M Score</th>'
            f'<th style="padding:6px 10px;text-align:left;color:#3362B0;font-size:11px;'
            f'text-transform:uppercase;letter-spacing:1px">ความหมาย</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>',
            unsafe_allow_html=True,
        )

    c1, c2 = st.columns([1, 2])

    with c1:
        seg_df = rfm["segment"].value_counts().reset_index()
        seg_df.columns = ["segment", "count"]
        ec.donut(
            labels=seg_df["segment"].tolist(),
            values=seg_df["count"].tolist(),
            colors=[SEGMENT_COLORS.get(s, "#8b9dc3") for s in seg_df["segment"]],
            height=340,
            show_count=True,
            currency=False,
        )

    with c2:
        segments_data = {}
        for seg, grp in rfm.groupby("segment"):
            segments_data[str(seg)] = list(zip(
                grp["frequency"].tolist(),
                grp["recency_days"].tolist(),
                grp["monetary"].tolist(),
                grp["member"].tolist(),
            ))
        ec.bubble_scatter(segments_data, height=340)

    section("TOP 10 MEMBERS BY SPEND")
    top = rfm.nlargest(10, "monetary")[
        ["member", "monetary", "frequency", "recency_days", "R", "F", "M", "segment"]
    ].copy()
    top["monetary"] = top["monetary"].apply(lambda x: f"฿{x:,.2f}")
    top["member"]   = top["member"].str[:20] + "…"
    top.columns = ["Member ID", "Total Spend", "Orders", "Days Since Last", "R", "F", "M", "Segment"]
    st.dataframe(top, hide_index=True, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# Tab 4 — Customer Segments
# ═════════════════════════════════════════════════════════════════════════════
def tab_segments():
    from segment_helper import (CHANNEL_SEGMENTS, ONLINE_SEGMENT,
                                compute_segments, load_category_segments)

    cat_dfs = {}
    for name, df in filtered.items():
        cdf = get_categorized(name, df)
        if "category" not in cdf.columns:
            get_categorized.clear()
            st.rerun()
        cat_dfs[name] = cdf
    cat_df = pd.concat(cat_dfs.values())

    segs          = compute_segments(cat_df)
    total_members = int(cat_df["member"].nunique())

    # ── Retail Channel ────────────────────────────────────────────────────
    section("🏪 RETAIL CHANNEL PREFERENCE")
    ch_names = list(CHANNEL_SEGMENTS.keys()) + [ONLINE_SEGMENT]
    nz_ch    = sorted(
        [(n, len(segs[n]["members"]), segs[n]["revenue"]) for n in ch_names if segs[n]["members"]],
        key=lambda x: x[1],
    )
    if not nz_ch:
        st.info("ไม่พบข้อมูลช่องทางการขาย")
    else:
        chart_title("MEMBER COUNT & REVENUE BY CHANNEL")
        ec.bar_h_dual(
            categories=[x[0] for x in nz_ch],
            revenues=[x[2] for x in nz_ch],
            counts=[x[1] for x in nz_ch],
            height=max(240, len(nz_ch) * 56 + 100),
        )

    # ── Category Affinity ─────────────────────────────────────────────────
    section("🛒 CATEGORY AFFINITY")
    cat_names = list(dict.fromkeys(r["segment"] for r in load_category_segments()))
    nz_cat    = sorted(
        [(n, len(segs[n]["members"]), segs[n]["revenue"]) for n in cat_names if segs[n]["members"]],
        key=lambda x: x[1],
    )
    if not nz_cat:
        st.info("ไม่พบข้อมูลหมวดหมู่สินค้า")
    else:
        chart_title("MEMBER COUNT & REVENUE BY CATEGORY AFFINITY")
        ec.bar_h_dual(
            categories=[x[0] for x in nz_cat],
            revenues=[x[2] for x in nz_cat],
            counts=[x[1] for x in nz_cat],
            height=max(280, len(nz_cat) * 56 + 100),
        )

    # ── Shopper Behavior ──────────────────────────────────────────────────
    section("⚡ SHOPPER BEHAVIOR")
    heavy_cnt = len(segs["Heavy Shopper"]["members"])
    bulk_cnt  = len(segs["Bulk Shopper"]["members"])
    other_cnt = total_members - len(segs["Heavy Shopper"]["members"] | segs["Bulk Shopper"]["members"])

    col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
    with col_kpi1:
        kpi("Total Members", f"{total_members:,}", color=PALETTE[0])
    with col_kpi2:
        sub_h = f"{heavy_cnt / total_members * 100:.1f}% · spend ≥ 80th percentile" if total_members else "n/a"
        kpi("Heavy Shopper", f"{heavy_cnt:,}", sub=sub_h, color=PALETTE[2])
    with col_kpi3:
        sub_b = f"{bulk_cnt / total_members * 100:.1f}% · item qty ≥ 3" if total_members else "n/a"
        kpi("Bulk Shopper", f"{bulk_cnt:,}", sub=sub_b, color=PALETTE[1])

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        chart_title("BEHAVIOR SEGMENT DISTRIBUTION")
        ec.donut(
            labels=["Heavy Shopper", "Bulk Shopper", "Others"],
            values=[heavy_cnt, bulk_cnt, max(other_cnt, 0)],
            colors=[PALETTE[2], PALETTE[1], PALETTE[4]],
            height=300,
            show_count=True,
            currency=False,
        )
    with col_d2:
        chart_title("BEHAVIOR SEGMENT — REVENUE SHARE")
        ec.donut(
            labels=["Heavy Shopper", "Bulk Shopper"],
            values=[segs["Heavy Shopper"]["revenue"], segs["Bulk Shopper"]["revenue"]],
            colors=[PALETTE[2], PALETTE[1]],
            height=300,
            show_count=False,
            currency=True,
        )


DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_ABBR  = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ═════════════════════════════════════════════════════════════════════════════
# Tab 5 — Categories Management
# ═════════════════════════════════════════════════════════════════════════════
@st.fragment
def tab_categories():
    from segment_helper import load_category_segments, save_category_segments  # noqa: PLC0415

    for key, default in [
        ("brands_working", load_brands_db),
        ("cats_working",   load_categories_db),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default()
    for key in ("brands_gen", "cats_gen", "stores_gen", "segs_gen"):
        if key not in st.session_state:
            st.session_state[key] = 0
    if "stores_working" not in st.session_state:
        _c, _o = load_stores_db()
        st.session_state.stores_working = _c
        st.session_state.stores_online  = _o
    if "segs_working" not in st.session_state or not isinstance(st.session_state.segs_working, list):
        st.session_state.segs_working = load_category_segments()
    if "ignore_working" not in st.session_state:
        st.session_state.ignore_working = load_ignore_db()

    brands   = st.session_state.brands_working
    bgen     = st.session_state.brands_gen
    cats     = st.session_state.cats_working
    gen      = st.session_state.cats_gen
    stores   = st.session_state.stores_working
    s_online = st.session_state.stores_online
    sgen     = st.session_state.stores_gen
    segs_cfg = st.session_state.segs_working
    segs_gen = st.session_state.segs_gen

    inner = st.tabs(["🏷️ Brands", "📦 Categories", "🏪 Store Chains", "🎯 Segments", "🚫 Ignore"])

    # ══════════════════════════════════════════════════════════════════════════
    # Brands
    # ══════════════════════════════════════════════════════════════════════════
    with inner[0]:
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.caption(f"{len(brands)} brands · keyword ระบุ brand จากชื่อสินค้า · คั่นด้วย |")
        with c2:
            brands_save = st.button("💾 Save", type="primary", key="brands_save", use_container_width=True)
        with c3:
            brands_reset = st.button("↺ Reset", key="brands_reset", use_container_width=True)

        edited_brands = st.data_editor(
            pd.DataFrame([{"Brand": k, "Keywords (| คั่น)": "|".join(v)} for k, v in brands.items()]),
            use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "Brand":             st.column_config.TextColumn(width="small"),
                "Keywords (| คั่น)": st.column_config.TextColumn(width="large"),
            },
            key=f"brand_editor_{bgen}",
        )

        if brands_save:
            new_brands: dict = {}
            for _, row in edited_brands.iterrows():
                bn = str(row.get("Brand", "") or "").strip()
                bk = [k.strip() for k in str(row.get("Keywords (| คั่น)", "") or "").split("|") if k.strip()]
                if bn and bk:
                    new_brands[bn] = bk
            save_brands_db(new_brands)
            reset_cache()
            get_categorized.clear()
            st.session_state.brands_working = new_brands
            st.session_state.brands_gen = bgen + 1
            _git_persist("brands_db.json")
            st.success(f"Saved {len(new_brands)} brands")
            st.rerun(scope="fragment")

        if brands_reset:
            new_brands = dict(DEFAULT_BRANDS)
            save_brands_db(new_brands)
            reset_cache()
            get_categorized.clear()
            st.session_state.brands_working = new_brands
            st.session_state.brands_gen = bgen + 1
            st.rerun(scope="fragment")

    # ══════════════════════════════════════════════════════════════════════════
    # Categories
    # ══════════════════════════════════════════════════════════════════════════
    with inner[1]:
        render_legend()
        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
        with c1:
            sel_cat = st.selectbox(
                "Category", list(cats.keys()), key="cat_sel_box", label_visibility="collapsed"
            )
        with c2:
            cat_save = st.button("💾 Save", type="primary", key="cat_save", use_container_width=True)
        with c3:
            cat_reload = st.button("🔄 Reload", key="cat_reload", use_container_width=True,
                                   help="ล้าง classification cache")
        with c4:
            cats_reset = st.button("↺ Reset All", key="cats_reset", use_container_width=True)

        if sel_cat:
            cd          = cats[sel_cat] if isinstance(cats[sel_cat], dict) else {"keywords": cats[sel_cat], "brands": [], "sku_types": {}}
            kws_list    = cd.get("keywords", [])
            brands_list = cd.get("brands", [])
            sku_dict    = cd.get("sku_types", {})
            color = CAT_COLORS.get(sel_cat, "#8b9dc3")
            dot   = (f'<span style="display:inline-block;width:10px;height:10px;'
                     f'border-radius:50%;background:{color};margin-right:6px"></span>')
            st.markdown(
                dot + f"**{sel_cat}** &nbsp;·&nbsp; {len(kws_list)} keywords · {len(sku_dict)} SKU types",
                unsafe_allow_html=True,
            )

            c_kw, c_sku = st.columns(2)
            with c_kw:
                st.caption("Keywords — ML ใช้จัด category")
                kw_ret = st.data_editor(
                    pd.DataFrame({"Keyword": kws_list}),
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    key=f"kw_{gen}_{sel_cat}",
                )
                sel_br = st.multiselect(
                    "Brands ใน category นี้",
                    options=sorted(brands.keys()),
                    default=[b for b in brands_list if b in brands],
                    key=f"ms_br_{gen}_{sel_cat}",
                )

            with c_sku:
                st.caption("SKU Types — sub-category สินค้า")
                sku_ret = st.data_editor(
                    pd.DataFrame([{"SKU Name": k, "Keywords (| คั่น)": "|".join(v)}
                                  for k, v in sku_dict.items()]),
                    num_rows="dynamic", use_container_width=True, hide_index=True,
                    column_config={
                        "SKU Name":          st.column_config.TextColumn(width="small"),
                        "Keywords (| คั่น)": st.column_config.TextColumn(width="large"),
                    },
                    key=f"sk_{gen}_{sel_cat}",
                )

            c_del, _ = st.columns([1, 5])
            with c_del:
                if st.button(f"🗑️ ลบ '{sel_cat}'", key=f"del_cat_{gen}_{sel_cat}"):
                    del st.session_state.cats_working[sel_cat]
                    st.rerun(scope="fragment")

            if cat_save:
                kws  = [str(r.get("Keyword", "") or "").strip() for _, r in kw_ret.iterrows()
                        if str(r.get("Keyword", "") or "").strip()]
                skud = {}
                for _, r in sku_ret.iterrows():
                    sn = str(r.get("SKU Name", "") or "").strip()
                    sv = [k.strip() for k in str(r.get("Keywords (| คั่น)", "") or "").split("|") if k.strip()]
                    if sn and sv:
                        skud[sn] = sv
                if not kws:
                    st.warning("ต้องมีอย่างน้อย 1 keyword")
                else:
                    st.session_state.cats_working[sel_cat] = {
                        "keywords": kws, "brands": sel_br, "sku_types": skud
                    }
                    save_categories_db(st.session_state.cats_working)
                    reset_cache()
                    get_categorized.clear()
                    st.session_state.cats_gen = gen + 1
                    _git_persist("categories_db.json")
                    st.success(f"Saved '{sel_cat}'")
                    st.rerun(scope="fragment")

        if cat_reload:
            reset_cache()
            get_categorized.clear()
            st.success("Cache cleared — classification will rerun on next visit")
            st.rerun(scope="fragment")

        if cats_reset:
            new_cats = dict(DEFAULT_CATEGORIES)
            save_categories_db(new_cats)
            reset_cache()
            get_categorized.clear()
            st.session_state.cats_working = new_cats
            st.session_state.cats_gen = gen + 1
            st.rerun(scope="fragment")

        st.divider()
        st.caption("➕ เพิ่ม category ใหม่")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            new_name = st.text_input("ชื่อ category", key="new_cat_name", placeholder="เช่น ยา/สุขภาพ")
        with c2:
            new_kws = st.text_area("Keywords (one per line)", key="new_cat_kws",
                                   height=80, placeholder="panadol\nยาพาราเซตามอล")
        with c3:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("➕ Add", key="add_cat_btn", use_container_width=True):
                name = new_name.strip()
                kws  = [k.strip() for k in new_kws.splitlines() if k.strip()]
                if name and kws:
                    st.session_state.cats_working[name] = {"keywords": kws, "brands": [], "sku_types": {}}
                    for k in ("new_cat_name", "new_cat_kws"):
                        st.session_state.pop(k, None)
                    st.rerun(scope="fragment")
                else:
                    st.warning("ใส่ชื่อ category และ keyword อย่างน้อย 1 บรรทัด")

    # ══════════════════════════════════════════════════════════════════════════
    # Store Chains
    # ══════════════════════════════════════════════════════════════════════════
    with inner[2]:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            n_online = sum(1 for n in stores if n in s_online)
            st.caption(f"{len(stores)} chains · {n_online} online / {len(stores)-n_online} offline")
        with c2:
            chain_save = st.button("💾 Save", type="primary", key="chain_save", use_container_width=True)
        with c3:
            chain_reset = st.button("↺ Defaults", key="chain_reset", use_container_width=True)

        sel_chain = st.selectbox(
            "Store Chain", list(stores.keys()), key="chain_sel_box", label_visibility="collapsed"
        )

        if sel_chain:
            is_online = sel_chain in s_online
            c_chk, _ = st.columns([2, 4])
            with c_chk:
                new_is_online = st.checkbox("🌐 Online channel", value=is_online,
                                            key=f"sonl_{sgen}_{sel_chain}")
            chain_kw_ret = st.data_editor(
                pd.DataFrame({"Keyword / Regex": stores[sel_chain]}),
                num_rows="dynamic", use_container_width=True, hide_index=True,
                key=f"sta_{sgen}_{sel_chain}",
                column_config={"Keyword / Regex": st.column_config.TextColumn(
                    help="รองรับ Regex · เช่น: lotus|โลตัส · (?=.*ซี)(?=.*พี) · ^7-eleven"
                )},
            )
            c_del3, _ = st.columns([1, 5])
            with c_del3:
                if st.button(f"🗑️ ลบ '{sel_chain}'", key=f"sdel_{sgen}_{sel_chain}"):
                    del st.session_state.stores_working[sel_chain]
                    st.session_state.stores_online.discard(sel_chain)
                    st.rerun(scope="fragment")

            if chain_save:
                kws = [str(r.get("Keyword / Regex", "") or "").strip()
                       for _, r in chain_kw_ret.iterrows()
                       if str(r.get("Keyword / Regex", "") or "").strip()]
                if kws:
                    st.session_state.stores_working[sel_chain] = kws
                    if new_is_online:
                        st.session_state.stores_online.add(sel_chain)
                    else:
                        st.session_state.stores_online.discard(sel_chain)
                    save_stores_db(st.session_state.stores_working, st.session_state.stores_online)
                    get_all_data.clear()
                    st.session_state.stores_gen = sgen + 1
                    _git_persist("stores_db.json")
                    st.success(f"Saved '{sel_chain}'")
                    st.rerun(scope="fragment")

        if chain_reset:
            new_chains = dict(DEFAULT_CHAIN_KEYWORDS)
            new_online = set(DEFAULT_ONLINE_CHAINS)
            save_stores_db(new_chains, new_online)
            get_all_data.clear()
            st.session_state.stores_working = new_chains
            st.session_state.stores_online  = new_online
            st.session_state.stores_gen     = sgen + 1
            st.rerun(scope="fragment")

        st.divider()
        st.caption("➕ เพิ่ม store chain ใหม่")
        c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
        with c1:
            new_sname = st.text_input("Chain name", key="new_store_name", placeholder="e.g. Makro")
        with c2:
            new_skws = st.text_area("Keywords (one per line)", key="new_store_kws",
                                    height=80, placeholder="makro\nแม็คโคร")
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            new_sonline = st.checkbox("Online", key="new_store_online")
        with c4:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("➕ Add", key="add_store_btn", use_container_width=True):
                sn  = new_sname.strip()
                kws = [k.strip() for k in new_skws.splitlines() if k.strip()]
                if sn and kws:
                    st.session_state.stores_working[sn] = kws
                    if new_sonline:
                        st.session_state.stores_online.add(sn)
                    for k in ("new_store_name", "new_store_kws", "new_store_online"):
                        st.session_state.pop(k, None)
                    st.rerun(scope="fragment")
                else:
                    st.warning("ใส่ชื่อ chain และ keyword")

    # ══════════════════════════════════════════════════════════════════════════
    # Segments
    # ══════════════════════════════════════════════════════════════════════════
    with inner[3]:
        c1, c2 = st.columns([5, 1])
        with c1:
            n_unique = len({r["segment"] for r in segs_cfg})
            st.caption(f"{n_unique} segments · {len(segs_cfg)} rules · SKU ว่าง = ทั้ง category")
        with c2:
            seg_save = st.button("💾 Save", type="primary", key="seg_save", use_container_width=True)

        all_sku_opts = [""] + sorted({
            sku
            for cd in cats.values() if isinstance(cd, dict)
            for sku in cd.get("sku_types", {}).keys()
        })
        segs_df = pd.DataFrame(segs_cfg or [{"segment": "", "category": "", "sku_type": ""}])
        for col in ("segment", "category", "sku_type"):
            if col not in segs_df.columns:
                segs_df[col] = ""

        edited_segs = st.data_editor(
            segs_df, use_container_width=True, hide_index=True, num_rows="dynamic",
            column_config={
                "segment":  st.column_config.TextColumn("Segment Name", width="medium"),
                "category": st.column_config.SelectboxColumn(
                    "Category", options=list(cats.keys()), width="medium"
                ),
                "sku_type": st.column_config.SelectboxColumn(
                    "SKU Type (ว่าง = ทั้ง category)", options=all_sku_opts, width="medium"
                ),
            },
            key=f"seg_editor_{segs_gen}",
        )

        if seg_save:
            new_segs: list = []
            for _, row in edited_segs.iterrows():
                sname    = str(row.get("segment",  "") or "").strip()
                cat_name = str(row.get("category", "") or "").strip()
                sku      = str(row.get("sku_type", "") or "").strip()
                if sname and cat_name:
                    new_segs.append({"segment": sname, "category": cat_name, "sku_type": sku})
            save_category_segments(new_segs)
            st.session_state.segs_working = new_segs
            st.session_state.segs_gen     = segs_gen + 1
            _git_persist("segments_db.json")
            st.success(f"Saved — {len(new_segs)} rules ({len({r['segment'] for r in new_segs})} segments)")
            st.rerun(scope="fragment")

    # ══════════════════════════════════════════════════════════════════════════
    # Ignore
    # ══════════════════════════════════════════════════════════════════════════
    with inner[4]:
        c1, c2, c3 = st.columns([4, 1, 1])
        with c1:
            st.caption("item_name ที่มี keyword เหล่านี้จะถูกกรองออกก่อน pipeline ทั้งหมด")
        with c2:
            ig_save = st.button("💾 Save & Apply", type="primary", key="ig_save", use_container_width=True)
        with c3:
            ig_reset = st.button("↺ Defaults", key="ig_reset", use_container_width=True)

        ig_val    = " | ".join(st.session_state.ignore_working)
        ig_edited = st.text_input("Keywords (| คั่น)", value=ig_val, key="ig_input",
                                  placeholder="ส่วนลด | discount | ธนาคาร | ทรูมันนี่")

        if ig_save:
            new_ig = [k.strip() for k in ig_edited.split("|") if k.strip()]
            save_ignore_db(new_ig)
            get_all_data.clear()
            st.session_state.ignore_working = new_ig
            _git_persist("ignore_db.json")
            st.success(f"Saved {len(new_ig)} ignore keywords")
            st.rerun(scope="fragment")

        if ig_reset:
            save_ignore_db(list(DEFAULT_IGNORE_KEYWORDS))
            get_all_data.clear()
            st.session_state.ignore_working = list(DEFAULT_IGNORE_KEYWORDS)
            st.rerun(scope="fragment")

# ═════════════════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════════════════
st.markdown(
    "<h1 style='margin-bottom:0'>📊 Campaign OCR Analytics</h1>"
    f"<p style='color:#3362B0;margin-top:4px'>"
    f"{' · '.join(selected)}  |  {d_from} → {d_to}  |  Approved slips only</p>",
    unsafe_allow_html=True,
)

tabs = st.tabs(["📊 Overview", "🛒 Products", "👥 Customers RFM", "🎯 Segments", "⚙️ Categories"])

with tabs[0]:
    tab_overview()
with tabs[1]:
    tab_products()
with tabs[2]:
    tab_customers()
with tabs[3]:
    tab_segments()
with tabs[4]:
    tab_categories()
