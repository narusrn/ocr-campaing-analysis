"""LLM-powered campaign insight summary using OpenAI API."""
import os

import pandas as pd


_MODEL = "gpt-5.2"

_SYSTEM_PROMPT = """You are a Senior Marketing Strategy Consultant and Data Storytelling Expert specializing in FMCG digital campaigns.

Your task is to analyze the campaign performance dataset provided and generate an executive-level marketing insight report.

Your objective is NOT to simply summarize numbers.

Instead, identify meaningful patterns, explain WHY they happened, connect findings with marketing principles, and provide practical recommendations that business stakeholders can act on.

The report should read like a presentation prepared by a Strategy Director for Brand Managers — a true EXECUTIVE SUMMARY: tight and scannable in under 90 seconds. Maximum 3 sections, 2 bullets each. Skip any section without strong evidence. No padding, no filler.

----------------------------------------------------
GENERAL WRITING STYLE
----------------------------------------------------

- Professional, concise and insightful
- Positive and opportunity-focused
- Celebrate successful campaigns before mentioning improvement opportunities
- Avoid sounding overly critical
- Every insight must be supported by evidence from the dataset
- Never fabricate numbers
- If evidence is insufficient, explicitly state that
- Use business language instead of statistical jargon
- Keep paragraphs short and easy to read — 1-2 sentences, never a wall of text
- Organize every section with bullet points, max 2 per section
- Skip a section entirely rather than including it with weak or padded content
- Total output must not exceed 150 words

----------------------------------------------------
FORMATTING
----------------------------------------------------

Use Markdown fully to make this easy to scan, not just plain bullets:

- Use `###` for every section heading above — never `#` or `##`, they render too large
- Bullet points, not paragraphs, wherever possible
- **Bold** important numbers and campaign/brand names
- Use a `>` blockquote for the single most important takeaway of the whole report
- Use a small Markdown table when comparing 2 or more campaigns/brands on the same metrics side by side
- Use *italics* for supporting context or caveats
- A `---` divider between major sections is fine if it improves scannability

Every bullet must reference the specific number(s) behind it inline instead of a separate reference block — keep it inline, not a separate citation section.

----------------------------------------------------
WRITING TONE

Write like a McKinsey, BCG, Bain or Deloitte strategy consultant presenting a one-page executive summary to senior marketing executives — dense with signal, zero filler.

Avoid generic statements.

Every insight should implicitly answer "so what" and "what should we do next" without spelling out the question.

Whenever possible, connect multiple metrics together instead of discussing each KPI separately.

Prioritize actionable business insights over descriptive statistics.

Respond in English."""


def _fmt_thb(v: float) -> str:
    return f"฿{v:,.2f}"


def _get_api_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
    except Exception:
        return os.environ.get("OPENAI_API_KEY", "")


def _call_llm(user_content: str) -> str:
    api_key = _get_api_key()
    if not api_key:
        return "⚠️ ไม่พบ OPENAI_API_KEY ใน `.streamlit/secrets.toml`"
    try:
        from openai import OpenAI  # noqa: PLC0415
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=_MODEL,
            max_completion_tokens=512,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
        )
        return _strip_fence(resp.choices[0].message.content)
    except Exception as exc:  # noqa: BLE001
        return f"❌ Error: {exc}"


def _strip_fence(text: str) -> str:
    import re
    return re.sub(r'^```[a-z]*\n?', '', text.strip()).rstrip('`').strip()


def highlight_insight(md_text: str) -> str:
    """Convert LLM markdown to highlighted HTML (no external package needed)."""
    import re

    def _bold(s: str) -> str:
        return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)

    html_lines: list[str] = []
    for line in md_text.split("\n"):
        if line.startswith("### "):
            html_lines.append(
                f'<h4 style="color:#0d1b35;margin:16px 0 5px;font-size:14px;'
                f'font-weight:700;letter-spacing:.5px">{_bold(line[4:])}</h4>'
            )
        elif line.startswith("- "):
            html_lines.append(
                f'<li style="margin:4px 0 4px 18px;color:#0d1b35">{_bold(line[2:])}</li>'
            )
        elif line.strip():
            html_lines.append(
                f'<p style="margin:5px 0;color:#0d1b35">{_bold(line)}</p>'
            )

    html = "\n".join(html_lines)

    html = re.sub(r'(฿[\d,]+(?:\.\d+)?)',
                  r'<span style="color:#00A3E0;font-weight:700">\1</span>', html)
    html = re.sub(r'(\b\d+(?:\.\d+)?%)',
                  r'<span style="color:#FFD100;font-weight:700">\1</span>', html)
    html = re.sub(r'(\b\d{1,2}:\d{2}(?:\s*น\.)?)',
                  r'<span style="color:#00C896;font-weight:700">\1</span>', html)
    html = re.sub(r'(?<![฿\d,])(\b\d{1,3}(?:,\d{3})+\b)',
                  r'<span style="color:#E4002B;font-weight:700">\1</span>', html)
    return html


# ── Overview ──────────────────────────────────────────────────────────────────
def build_context(all_slip: pd.DataFrame, filtered: dict) -> dict:
    campaigns = {}
    for name, df in filtered.items():
        campaigns[name] = {
            "revenue":    round(float(df["item_price"].sum()), 2),
            "orders":     int(df["slip_id"].nunique()),
            "members":    int(df["member"].nunique()),
            "avg_basket": round(float(df.groupby("slip_id")["item_price"].sum().mean()), 2),
        }

    hour_counts = all_slip.groupby("hour")["slip_id"].count()
    peak_hour   = int(hour_counts.idxmax()) if not hour_counts.empty else 0
    dow_counts  = all_slip.groupby("day_of_week")["slip_id"].count()
    peak_day    = str(dow_counts.idxmax()) if not dow_counts.empty else ""

    all_items   = pd.concat(filtered.values())
    chan        = all_items.groupby("channel")["item_price"].sum()
    total_rev   = float(chan.sum()) or 1
    online_pct  = round(float(chan.get("Online", 0)) / total_rev * 100, 1)
    offline_pct = round(100 - online_pct, 1)

    chain = (all_items.groupby("store_chain")["item_price"]
             .sum().sort_values(ascending=False).head(3))
    top_stores = {str(k): round(float(v), 2) for k, v in chain.items()}

    return {
        "campaigns":     campaigns,
        "peak_hour":     peak_hour,
        "peak_day":      peak_day,
        "online_pct":    online_pct,
        "offline_pct":   offline_pct,
        "top_stores":    top_stores,
        "total_revenue": round(float(all_items["item_price"].sum()), 2),
        "total_orders":  int(all_items["slip_id"].nunique()),
    }


def generate_summary(ctx: dict) -> str:
    camp_lines = "\n".join(
        f"  - {name}: revenue {_fmt_thb(v['revenue'])} | orders {v['orders']:,} | "
        f"members {v['members']:,} | avg basket {_fmt_thb(v['avg_basket'])}"
        for name, v in ctx["campaigns"].items()
    )
    store_lines = "\n".join(
        f"  - {s}: {_fmt_thb(rev)}" for s, rev in ctx["top_stores"].items()
    )
    return _call_llm(f"""=== Campaign Performance ===
{camp_lines}

Total revenue: {_fmt_thb(ctx['total_revenue'])} | Total orders: {ctx['total_orders']:,}

=== Shopping Timing ===
Peak hour: {ctx['peak_hour']}:00 | Peak day: {ctx['peak_day']}

=== Channel Split ===
Online: {ctx['online_pct']}% | Offline: {ctx['offline_pct']}%

=== Top 3 Stores by Revenue ===
{store_lines}""")


# ── Products ──────────────────────────────────────────────────────────────────
def build_products_context(combined: pd.DataFrame) -> dict:
    cat_rev = (combined.groupby("category")["item_price"].sum()
               .sort_values(ascending=False))
    cat_cnt = combined["category"].value_counts()

    top_items = (combined[combined["category"] != "อื่นๆ"]
                 .groupby("item_name")
                 .agg(count=("item_price", "count"), revenue=("item_price", "sum"))
                 .sort_values("count", ascending=False)
                 .head(8))

    total   = len(combined)
    unc     = len(combined[combined["category"] == "อื่นๆ"])
    unc_pct = round(unc / total * 100, 1) if total else 0

    return {
        "top_categories_revenue": {str(k): round(float(v), 0) for k, v in cat_rev.head(5).items()},
        "top_categories_count":   {str(k): int(v) for k, v in cat_cnt.head(5).items()},
        "top_items": {
            str(k): {"count": int(r["count"]), "revenue": round(float(r["revenue"]), 0)}
            for k, r in top_items.iterrows()
        },
        "uncategorized_pct": unc_pct,
        "total_items": total,
    }


def generate_products_summary(ctx: dict) -> str:
    cat_rev_lines = "\n".join(
        f"  - {k}: {_fmt_thb(v)}" for k, v in ctx["top_categories_revenue"].items()
    )
    item_lines = "\n".join(
        f"  - {k}: {v['count']:,} purchases | {_fmt_thb(v['revenue'])}"
        for k, v in ctx["top_items"].items()
    )
    return _call_llm(f"""=== Top 5 Categories by Revenue ===
{cat_rev_lines}

=== Top 8 Best-Selling Items ===
{item_lines}

=== Coverage ===
Categorized: {100 - ctx['uncategorized_pct']:.1f}% | Uncategorized: {ctx['uncategorized_pct']}%
Total items: {ctx['total_items']:,}""")


# ── RFM ───────────────────────────────────────────────────────────────────────
def build_rfm_context(rfm: pd.DataFrame, campaign: str) -> dict:
    segs = (rfm.groupby("segment")
            .agg(count=("member",        "count"),
                 revenue=("monetary",    "sum"),
                 avg_spend=("monetary",  "mean"),
                 avg_freq=("frequency",  "mean"),
                 avg_rec=("recency_days","mean"))
            .round(1)
            .to_dict(orient="index"))
    total = len(rfm)
    return {
        "campaign":      campaign,
        "total_members": total,
        "segments": {
            seg: {
                "count":     int(v["count"]),
                "pct":       round(v["count"] / total * 100, 1),
                "revenue":   round(float(v["revenue"]), 0),
                "avg_spend": round(float(v["avg_spend"]), 0),
                "avg_freq":  round(float(v["avg_freq"]), 1),
                "avg_rec":   round(float(v["avg_rec"]), 0),
            }
            for seg, v in segs.items()
        },
    }


def generate_rfm_summary(ctx: dict) -> str:
    seg_lines = "\n".join(
        f"  - {seg} ({v['pct']}%, {v['count']:,} members): "
        f"revenue {_fmt_thb(v['revenue'])} | avg spend {_fmt_thb(v['avg_spend'])} | "
        f"avg orders {v['avg_freq']} | last purchase {v['avg_rec']:.0f} days ago"
        for seg, v in ctx["segments"].items()
    )
    return _call_llm(f"""Campaign: {ctx['campaign']}
Total members: {ctx['total_members']:,}

=== RFM Segments ===
{seg_lines}""")


# ── Segments ──────────────────────────────────────────────────────────────────
def build_segments_context(segs: dict, total_members: int, campaigns: list[str]) -> dict:
    groups = {
        "channel":  ["Convenience Store Shopper", "Hypermarket Shopper", "Premium Retail Shopper",
                     "Drug Store Shopper", "Wholesale Shopper", "Online Shopper"],
        "affinity": ["Skincare Shopper", "Hair Care Shopper", "Oral Care Shopper",
                     "Laundry Shopper", "Fabric Care Shopper", "Dishwash Shopper",
                     "Snack Shopper", "Beverage Shopper", "Ready to Eat Shopper"],
        "behavior": ["Heavy Shopper", "Bulk Shopper", "Promotion Shopper"],
    }
    out: dict = {"campaigns": campaigns, "total_members": total_members, "groups": {}}
    for grp, names in groups.items():
        rows = {}
        for n in names:
            if n not in segs:
                continue
            d = segs[n]
            cnt = len(d["members"])
            if cnt == 0:
                continue
            rows[n] = {
                "count":   cnt,
                "pct":     round(cnt / total_members * 100, 1) if total_members else 0,
                "revenue": round(d["revenue"], 0),
            }
        out["groups"][grp] = dict(sorted(rows.items(), key=lambda x: -x[1]["count"]))
    return out


def generate_segments_summary(ctx: dict) -> str:
    def _fmt_group(rows: dict) -> str:
        return "\n".join(
            f"  - {n}: {v['pct']}%, {v['count']:,} members, revenue {_fmt_thb(v['revenue'])}"
            for n, v in rows.items()
        ) or "  - (no data)"

    return _call_llm(f"""Campaign(s): {', '.join(ctx['campaigns'])}
Total unique members: {ctx['total_members']:,}

=== Retail Channel ===
{_fmt_group(ctx['groups'].get('channel', {}))}

=== Category Affinity ===
{_fmt_group(ctx['groups'].get('affinity', {}))}

=== Shopper Behavior ===
{_fmt_group(ctx['groups'].get('behavior', {}))}""")
