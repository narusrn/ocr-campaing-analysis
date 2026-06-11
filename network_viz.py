"""
Interactive network graph visualization using PyVis + NetworkX.
Two modes:
  - Category network  : nodes = product categories, edges = co-occurrence in same slip
  - Item network      : nodes = top-N individual items, edges = bought together
"""
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from categorizer import preprocess_name

# ── Colors ────────────────────────────────────────────────────────────────────
CAT_COLORS = {
    "สกินแคร์/บิวตี้":   "#E8425A",
    "ผงซักฟอก/น้ำยา":   "#00A3E0",
    "อาหารสด":           "#00C896",
    "อาหารสำเร็จรูป":    "#FFD100",
    "เครื่องดื่ม":       "#00D2D3",
    "ขนม/ของกินเล่น":    "#E4002B",
    "ของใช้ในบ้าน":      "#9B6DD6",
    "อื่นๆ":             "#94b4cc",
}

_PYVIS_OPTIONS = """
{
  "nodes": {
    "borderWidth": 2,
    "borderWidthSelected": 4,
    "shadow": {"enabled": true, "color": "rgba(0,163,224,0.25)", "size": 22, "x": 0, "y": 0},
    "font": {"color": "#182B45", "size": 13, "face": "Inter,sans-serif",
             "strokeWidth": 3, "strokeColor": "#F4F6FB"}
  },
  "edges": {
    "color": {"inherit": false, "color": "#E4E7ED",
              "highlight": "#00A3E0", "hover": "#00A3E0", "opacity": 0.9},
    "smooth": {"enabled": true, "type": "continuous", "roundness": 0.35},
    "hoverWidth": 3, "selectionWidth": 3
  },
  "physics": {
    "enabled": true,
    "barnesHut": {
      "gravitationalConstant": -12000, "centralGravity": 0.25,
      "springLength": 170, "springConstant": 0.04,
      "damping": 0.09, "avoidOverlap": 0.6
    },
    "stabilization": {"enabled": true, "iterations": 250, "updateInterval": 25}
  },
  "interaction": {
    "hover": true, "tooltipDelay": 80,
    "multiselect": true, "navigationButtons": false,
    "keyboard": {"enabled": true}
  }
}
"""

# ── Light HTML wrapper ────────────────────────────────────────────────────────
_DARK_STYLE = """
<style>
body, html { background: #ffffff !important; margin: 0; }
#mynetwork { background: #ffffff !important; }
.vis-tooltip {
    background: #ffffff !important;
    border: 1px solid #E4E7ED !important;
    color: #182B45 !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
    font-family: Inter, sans-serif !important;
    font-size: 13px !important;
    max-width: 280px;
    box-shadow: 0 4px 16px rgba(0,100,200,0.1);
}
.vis-button { display: none; }
</style>
"""


def _make_net(height: int) -> Network:
    net = Network(height=f"{height}px", width="100%",
                  bgcolor="#ffffff", font_color="#182B45", notebook=False)
    net.set_options(_PYVIS_OPTIONS)
    return net


def _render(net: Network, height: int):
    raw = net.generate_html()
    # Inject dark style after <head>
    html = raw.replace("<head>", "<head>" + _DARK_STYLE, 1)
    components.html(html, height=height + 20, scrolling=False)


# ── Category Network ──────────────────────────────────────────────────────────
def render_category_network(df, height: int = 580):
    """
    Nodes  = product categories (size ∝ item count, color per category)
    Edges  = number of slips containing both categories (width ∝ co-occurrence)
    """
    from data_loader import compute_basket_matrix

    matrix = compute_basket_matrix(df)
    if matrix.empty:
        st.info("Not enough categorized data for network.")
        return

    cat_counts = (df[df["category"] != "อื่นๆ"]["category"].value_counts())

    G = nx.Graph()
    for cat in matrix.index:
        if cat == "อื่นๆ":
            continue
        cnt = int(cat_counts.get(cat, 1))
        color = CAT_COLORS.get(cat, "#8b9dc3")
        G.add_node(
            cat,
            label=cat,
            size=max(22, min(65, cnt / 4)),
            color={"background": color, "border": color,
                   "highlight": {"background": color, "border": "#ffffff"},
                   "hover": {"background": color, "border": "#ffffff"}},
            title=f"<b>{cat}</b><br>Items: {cnt:,}",
        )

    max_co = max(
        (int(matrix.loc[c1, c2])
         for c1 in matrix.index for c2 in matrix.columns
         if c1 < c2 and c1 != "อื่นๆ" and c2 != "อื่นๆ"),
        default=1,
    )
    for c1 in matrix.index:
        for c2 in matrix.columns:
            if c1 >= c2 or c1 == "อื่นๆ" or c2 == "อื่นๆ":
                continue
            weight = int(matrix.loc[c1, c2])
            if weight == 0:
                continue
            G.add_edge(
                c1, c2,
                weight=weight,
                width=max(1.5, min(12, weight / max_co * 12)),
                title=f"<b>{c1}</b> ↔ <b>{c2}</b><br>Co-purchased: {weight:,} slips",
            )

    net = _make_net(height)
    net.from_nx(G)
    _render(net, height)


# ── Item Network ──────────────────────────────────────────────────────────────
def render_item_network(df, top_n: int = 60, min_edge: int = 2, height: int = 620):
    """
    Nodes  = top-N items by frequency (size ∝ frequency, color per category)
    Edges  = bought in the same slip at least min_edge times (width ∝ co-occurrence)
    """
    work = df[df["category"] != "อื่นๆ"].copy()
    work["item_clean"] = work["item_name"].apply(preprocess_name)

    top_items = set(work["item_clean"].value_counts().head(top_n).index)
    work = work[work["item_clean"].isin(top_items)]

    freq   = work["item_clean"].value_counts()
    cat_map = (work.drop_duplicates("item_clean")
                   .set_index("item_clean")["category"].to_dict())
    rev_map = (work.groupby("item_clean")["item_price"]
                   .sum().to_dict())

    # Build co-occurrence
    edges: dict[tuple, int] = {}
    for _, grp in work.groupby("slip_id"):
        items = list(set(grp["item_clean"].tolist()))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                key = tuple(sorted([items[i], items[j]]))
                edges[key] = edges.get(key, 0) + 1

    G = nx.Graph()
    max_freq = max(freq.values, default=1)
    for item in top_items:
        cnt   = int(freq.get(item, 1))
        cat   = cat_map.get(item, "อื่นๆ")
        rev   = float(rev_map.get(item, 0))
        color = CAT_COLORS.get(cat, "#8b9dc3")
        # Truncate long Thai names for readability
        label = (item[:18] + "…") if len(item) > 20 else item
        G.add_node(
            item,
            label=label,
            size=max(14, min(50, cnt / max_freq * 50)),
            color={"background": color, "border": color,
                   "highlight": {"background": color, "border": "#ffffff"},
                   "hover": {"background": color, "border": "#ffffff"}},
            title=(
                f"<b>{label}</b><br>"
                f"Category: {cat}<br>"
                f"Frequency: {cnt:,}<br>"
                f"Total revenue: ฿{rev:,.0f}"
            ),
            group=cat,
        )

    max_edge = max(edges.values(), default=1)
    for (i1, i2), w in edges.items():
        if w < min_edge:
            continue
        G.add_edge(
            i1, i2,
            weight=w,
            width=max(0.8, min(10, w / max_edge * 10)),
            title=f"Co-purchased: {w} slips",
        )

    net = _make_net(height)
    net.from_nx(G)
    _render(net, height)


# ── Legend helper ─────────────────────────────────────────────────────────────
def render_legend():
    """Render a small color legend for categories."""
    badges = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'margin:3px 6px 3px 0;background:#1a1f35;border-radius:20px;'
        f'padding:3px 10px 3px 8px;font-size:12px;color:#F4F6FB">'
        f'<span style="width:10px;height:10px;border-radius:50%;'
        f'background:{color};flex-shrink:0"></span>{cat}</span>'
        for cat, color in CAT_COLORS.items()
        if cat != "อื่นๆ"
    )
    st.markdown(
        f'<div style="margin:6px 0 14px">{badges}</div>',
        unsafe_allow_html=True,
    )
