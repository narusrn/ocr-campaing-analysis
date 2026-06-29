"""ECharts rendering helpers — CDN-based, no package required."""
import json
import re
import uuid
import streamlit.components.v1 as components

PALETTE = ["#0064F0", "#FB654E", "#00C896", "#F0C800", "#182B45", "#D19E36"]
SEGMENT_COLORS = {
    "Champions":       "#00C896",
    "Loyal Customers": "#0064F0",
    "Potential":       "#F0C800",
    "Promising":       "#00A3E0",
    "At Risk":         "#FB654E",
    "Hibernating":     "#D19E36",
    "Lost":            "#A3AAB5",
}

_CDN = "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
_S, _E = "__ECJS__", "__ECEND__"


class JS:
    """Raw JavaScript expression — not JSON-string-encoded."""
    def __init__(self, code: str):
        self.code = code


def _default(o):
    if isinstance(o, JS):
        return f"{_S}{o.code}{_E}"
    raise TypeError(type(o))


def _dump(obj: dict) -> str:
    raw = json.dumps(obj, default=_default, ensure_ascii=False)
    return re.sub(
        '"' + _S + r'(.*?)' + _E + '"',
        lambda m: m.group(1).replace('\\"', '"').replace("\\n", "\n"),
        raw, flags=re.DOTALL,
    )


def _html(opt: dict, height: int) -> str:
    cid = "ec" + uuid.uuid4().hex[:8]
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>html,body{margin:0;padding:0;background:#ffffff;overflow:hidden}'
        f'#{cid}{{width:100%;height:{height}px}}</style></head>'
        f'<body><div id="{cid}"></div>'
        f'<script src="{_CDN}"></script>'
        '<script>(function(){'
        f'var c=echarts.init(document.getElementById("{cid}"),null,{{renderer:"canvas"}});'
        f'c.setOption({_dump(opt)});'
        'window.addEventListener("resize",function(){c.resize()});'
        '})();</script></body></html>'
    )


def render(opt: dict, height: int = 340):
    components.html(_html(opt, height), height=height + 10, scrolling=False)


# ── Shared sub-dicts ───────────────────────────────────────────────────────────
def _tt(**kw):
    return {"backgroundColor": "#ffffff", "borderColor": "#E4E7ED",
            "textStyle": {"color": "#182B45", "fontSize": 12}, **kw}


def _cat_ax(data, rotate=0):
    return {"type": "category", "data": [str(d) for d in data],
            "axisLine": {"lineStyle": {"color": "#BDD0F0"}}, "axisTick": {"show": False},
            "axisLabel": {"color": "#7C8DA0", "fontSize": 10, "rotate": rotate},
            "splitLine": {"show": False}}


def _val_ax(currency=False):
    if currency:
        fmt = JS("function(v){if(v>=1e6)return'฿'+(v/1e6).toFixed(1)+'M';"
                 "if(v>=1e3)return'฿'+(v/1e3).toFixed(0)+'K';return'฿'+v;}")
    else:
        fmt = JS("function(v){return v.toLocaleString()}")
    return {"type": "value",
            "splitLine": {"lineStyle": {"color": "#C4D8F8", "type": "dashed"}},
            "axisLine": {"show": False}, "axisTick": {"show": False},
            "axisLabel": {"color": "#7C8DA0", "fontSize": 10, "formatter": fmt}}


# ── Chart builders ─────────────────────────────────────────────────────────────
def bar_v(categories, values, color=None, height=280, currency=False, rotate=0):
    """Vertical bar chart."""
    color = color or PALETTE[0]
    if currency:
        lbl = JS("function(p){if(p.value>=1e6)return'฿'+(p.value/1e6).toFixed(1)+'M';"
                 "if(p.value>=1e3)return'฿'+(p.value/1e3).toFixed(0)+'K';"
                 "return'฿'+p.value.toLocaleString();}")
    else:
        lbl = JS("function(p){return p.value.toLocaleString()}")
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 28, "bottom": 20, "left": 8, "right": 8},
        "xAxis": _cat_ax(categories, rotate=rotate),
        "yAxis": _val_ax(currency),
        "series": [{"type": "bar", "data": [float(v) for v in values],
                    "itemStyle": {"color": color, "borderRadius": [4, 4, 0, 0]},
                    "barMaxWidth": 52,
                    "label": {"show": True, "position": "top",
                              "color": "#3D4F66", "fontSize": 9, "formatter": lbl}}],
        "tooltip": {"trigger": "axis", **_tt()},
    }, height)


def bar_h(categories, values, color=None, height=300, currency=False, counts=None):
    """Horizontal bar chart. counts: optional list shown in tooltip alongside values."""
    color = color or PALETTE[0]
    if currency:
        lbl = JS("function(p){if(p.value>=1e6)return'฿'+(p.value/1e6).toFixed(1)+'M';"
                 "if(p.value>=1e3)return'฿'+(p.value/1e3).toFixed(0)+'K';"
                 "return'฿'+p.value.toLocaleString();}")
    else:
        lbl = JS("function(p){return p.value>=1e6?(p.value/1e6).toFixed(1)+'M':"
                 "p.value>=1e3?(p.value/1e3).toFixed(0)+'K':p.value.toLocaleString()}")

    if counts is not None:
        data = [{"value": float(v), "count": int(c)} for v, c in zip(values, counts)]
        tooltip = {"trigger": "axis", **_tt(), "formatter": JS(
            "function(params){"
            "var d=params[0];"
            "var rev=d.data.value>=1e6?'฿'+(d.data.value/1e6).toFixed(1)+'M':"
            "d.data.value>=1e3?'฿'+(d.data.value/1e3).toFixed(0)+'K':"
            "'฿'+d.data.value.toLocaleString();"
            "return d.marker+d.name+'<br>Revenue: <b>'+rev+'</b><br>Count: <b>'+d.data.count.toLocaleString()+'</b>';}"
        )}
    else:
        data = [float(v) for v in values]
        tooltip = {"trigger": "axis", **_tt()}

    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 8, "bottom": 8, "left": 8, "right": 80},
        "xAxis": _val_ax(currency),
        "yAxis": {"type": "category", "data": [str(c) for c in categories],
                  "axisLine": {"lineStyle": {"color": "#BDD0F0"}}, "axisTick": {"show": False},
                  "axisLabel": {"color": "#182B45", "fontSize": 10}},
        "series": [{"type": "bar", "data": data,
                    "itemStyle": {"color": color, "borderRadius": [0, 4, 4, 0]},
                    "barMaxWidth": 28,
                    "label": {"show": True, "position": "right",
                              "color": "#3D4F66", "fontSize": 9, "formatter": lbl}}],
        "tooltip": tooltip,
    }, height)


def bar_h_dual(categories, revenues, counts, height=320):
    """Horizontal bar with dual x-axis: Revenue (bottom, ฿) + Count (top)."""
    lbl_rev = JS("function(p){if(p.value>=1e6)return'฿'+(p.value/1e6).toFixed(1)+'M';"
                 "if(p.value>=1e3)return'฿'+(p.value/1e3).toFixed(0)+'K';"
                 "return'฿'+p.value.toLocaleString();}")
    lbl_cnt = JS("function(p){return p.value.toLocaleString()}")
    ydata = [str(c) for c in categories]
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 40, "bottom": 36, "left": 8, "right": 90},
        "xAxis": [
            {"type": "value", "position": "bottom",
             "splitLine": {"lineStyle": {"color": "#C4D8F8", "type": "dashed"}},
             "axisLine": {"show": False}, "axisTick": {"show": False},
             "axisLabel": {"color": "#7C8DA0", "fontSize": 9,
                           "formatter": JS("function(v){return v>=1e6?'฿'+(v/1e6).toFixed(1)+'M':"
                                           "v>=1e3?'฿'+(v/1e3).toFixed(0)+'K':'฿'+v}")}},
            {"type": "value", "position": "top",
             "splitLine": {"show": False},
             "axisLine": {"show": False}, "axisTick": {"show": False},
             "axisLabel": {"color": "#7C8DA0", "fontSize": 9,
                           "formatter": JS("function(v){return v.toLocaleString()}")}},
        ],
        "yAxis": {"type": "category", "data": ydata,
                  "axisLine": {"lineStyle": {"color": "#BDD0F0"}}, "axisTick": {"show": False},
                  "axisLabel": {"color": "#182B45", "fontSize": 10}},
        "legend": {"data": ["Revenue (฿)", "Count"], "top": 4,
                   "textStyle": {"color": "#3D4F66", "fontSize": 11}},
        "series": [
            {"name": "Revenue (฿)", "type": "bar", "xAxisIndex": 0,
             "data": [float(v) for v in revenues],
             "itemStyle": {"color": PALETTE[0], "borderRadius": [0, 4, 4, 0]},
             "barMaxWidth": 18,
             "label": {"show": True, "position": "right", "color": "#3D4F66", "fontSize": 9,
                       "formatter": lbl_rev}},
            {"name": "Count", "type": "bar", "xAxisIndex": 1,
             "data": [float(v) for v in counts],
             "itemStyle": {"color": PALETTE[2], "borderRadius": [0, 4, 4, 0]},
             "barMaxWidth": 18,
             "label": {"show": True, "position": "right", "color": "#3D4F66", "fontSize": 9,
                       "formatter": lbl_cnt}},
        ],
        "tooltip": {"trigger": "axis", **_tt(), "formatter": JS(
            "function(params){"
            "var s=params[0].axisValue+'<br>';"
            "params.forEach(function(p){"
            "if(p.seriesName==='Revenue (฿)'){"
            "s+=p.marker+'Revenue: ฿'+p.value.toLocaleString('th-TH',{maximumFractionDigits:0})+'<br>';}"
            "else{s+=p.marker+'Count: '+p.value.toLocaleString()+'<br>';}"
            "});return s;}"
        )},
    }, height)


def area_line(series_list, height=300):
    """
    Multi-series area line.
    series_list: [{"name": str, "dates": [str], "values": [float], "color": str}]
    """
    all_dates = sorted({d for s in series_list for d in s["dates"]})
    echarts_series = []
    for s in series_list:
        dv = dict(zip(s["dates"], s["values"]))
        r = int(s["color"][1:3], 16)
        g = int(s["color"][3:5], 16)
        b = int(s["color"][5:7], 16)
        echarts_series.append({
            "name": s["name"], "type": "line", "smooth": True, "symbol": "none",
            "data": [dv.get(d) for d in all_dates],
            "lineStyle": {"color": s["color"], "width": 2.5},
            "areaStyle": {"color": f"rgba({r},{g},{b},0.10)"},
            "itemStyle": {"color": s["color"]},
        })
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 30, "bottom": 48, "left": 12, "right": 12},
        "xAxis": _cat_ax(all_dates, rotate=30),
        "yAxis": _val_ax(currency=True),
        "legend": {"data": [s["name"] for s in series_list],
                   "textStyle": {"color": "#3D4F66"}, "bottom": 0},
        "series": echarts_series,
        "tooltip": {
            "trigger": "axis", **_tt(),
            "formatter": JS(
                "function(params){"
                "var s=params[0].axisValue+'<br>';"
                "params.forEach(function(p){"
                "if(p.value==null)return;"
                "s+=p.marker+p.seriesName+': ฿'+p.value.toLocaleString('th-TH',{maximumFractionDigits:0})+'<br>';"
                "});return s;}"
            ),
        },
    }, height)


def donut(labels, values, colors=None, height=320, show_count=False):
    """Donut / pie chart. show_count=True adds raw count + % to each slice label."""
    pal = (colors or PALETTE) * 4
    _fmt = ("function(p){var v=p.value;"
            "var s=v>=1e6?'\\u0e3f'+(v/1e6).toFixed(1)+'M':v>=1e3?'\\u0e3f'+(v/1e3).toFixed(0)+'K':'\\u0e3f'+v;"
            "return p.name+' '+s+' ('+p.percent.toFixed(0)+'%)'}")
    label_cfg = {"color": "#182B45", "fontSize": 11}
    if show_count:
        label_cfg["formatter"] = JS(_fmt)
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "series": [{"type": "pie", "radius": ["42%", "68%"], "center": ["42%", "50%"],
                    "data": [{"name": str(l), "value": float(v),
                              "itemStyle": {"color": pal[i]}}
                             for i, (l, v) in enumerate(zip(labels, values))],
                    "label": label_cfg,
                    "labelLine": {"lineStyle": {"color": "#7a9dc0"}},
                    "itemStyle": {"borderColor": "#E8EFF9", "borderWidth": 2}}],
        "legend": {"orient": "vertical", "right": "4%", "top": "center",
                   "textStyle": {"color": "#3D4F66", "fontSize": 11},
                   "data": [str(l) for l in labels]},
        "tooltip": {**_tt(), "formatter": JS(_fmt)},
    }, height)


def treemap(labels, revenues, counts=None, height=340):
    """Treemap sized by revenue. counts shown in tooltip if provided."""
    data = []
    for i, (lbl, rev) in enumerate(zip(labels, revenues)):
        item = {
            "name": str(lbl),
            "value": float(rev),
            "itemStyle": {"color": PALETTE[i % len(PALETTE)]},
        }
        if counts is not None:
            item["count"] = int(counts[i])
        data.append(item)

    if counts is not None:
        tt_fmt = JS(
            "function(p){"
            "var rev=p.value>=1e6?'฿'+(p.value/1e6).toFixed(1)+'M':"
            "p.value>=1e3?'฿'+(p.value/1e3).toFixed(0)+'K':"
            "'฿'+p.value.toLocaleString();"
            "return p.marker+'<b>'+p.name+'</b><br>Revenue: <b>'+rev+'</b><br>Count: <b>'+p.data.count.toLocaleString()+'</b>';}"
        )
    else:
        tt_fmt = JS(
            "function(p){"
            "var rev=p.value>=1e6?'฿'+(p.value/1e6).toFixed(1)+'M':"
            "p.value>=1e3?'฿'+(p.value/1e3).toFixed(0)+'K':"
            "'฿'+p.value.toLocaleString();"
            "return p.marker+'<b>'+p.name+'</b><br>Revenue: <b>'+rev+'</b>';}"
        )

    lbl_fmt = JS(
        "function(p){"
        "var rev=p.value>=1e6?'฿'+(p.value/1e6).toFixed(1)+'M':"
        "p.value>=1e3?'฿'+(p.value/1e3).toFixed(0)+'K':"
        "'฿'+p.value.toLocaleString();"
        "return p.name+'\\n'+rev;}"
    )

    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#ffffff"},
        "series": [{
            "type": "treemap",
            "data": data,
            "width": "100%", "height": "100%",
            "roam": False,
            "nodeClick": False,
            "breadcrumb": {"show": False},
            "label": {
                "show": True,
                "formatter": lbl_fmt,
                "fontSize": 11, "fontWeight": "bold",
                "color": "#ffffff",
                "overflow": "truncate",
            },
            "itemStyle": {"borderColor": "#ffffff", "borderWidth": 2, "gapWidth": 2},
            "emphasis": {"itemStyle": {"shadowBlur": 8, "shadowColor": "rgba(0,0,0,0.3)"}},
        }],
        "tooltip": {**_tt(), "formatter": tt_fmt},
    }, height)


def heatmap_grid(x_labels, y_labels, matrix, height=300):
    """
    Grid heatmap.
    matrix: list[list[number]] — matrix[row_y][col_x]
    """
    data = [[xi, yi, int(matrix[yi][xi])]
            for yi in range(len(y_labels)) for xi in range(len(x_labels))
            if matrix[yi][xi]]
    max_v = max((d[2] for d in data), default=1)
    yl_js = json.dumps([str(y) for y in y_labels], ensure_ascii=False)
    xl_js = json.dumps([str(x) for x in x_labels], ensure_ascii=False)
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 10, "bottom": 56, "left": 12, "right": 16},
        "xAxis": {"type": "category", "data": [str(x) for x in x_labels],
                  "axisLine": {"lineStyle": {"color": "#BDD0F0"}}, "axisTick": {"show": False},
                  "axisLabel": {"color": "#7C8DA0", "fontSize": 9}, "splitArea": {"show": False}},
        "yAxis": {"type": "category", "data": [str(y) for y in y_labels],
                  "axisLine": {"lineStyle": {"color": "#BDD0F0"}}, "axisTick": {"show": False},
                  "axisLabel": {"color": "#7C8DA0", "fontSize": 9}, "splitArea": {"show": False}},
        "visualMap": {"min": 0, "max": max_v, "calculable": True,
                      "orient": "horizontal", "bottom": 0, "left": "center",
                      "textStyle": {"color": "#7C8DA0", "fontSize": 9},
                      "inRange": {"color": ["#E4002B", "#FF9999", "#FFEE88", "#88DD88", "#1B7A2E"]}},
        "series": [{"type": "heatmap", "data": data,
                    "itemStyle": {"borderColor": "#E8EFF9", "borderWidth": 1},
                    "label": {"show": True, "color": "#ffffff", "fontSize": 8},
                    "emphasis": {"itemStyle": {"shadowBlur": 10, "shadowColor": "rgba(0,163,224,0.4)"}}}],
        "tooltip": {"trigger": "item", **_tt(), "formatter": JS(
            f"function(p){{return'<b>'+{yl_js}[p.data[1]]+'</b> × <b>'"
            f"+{xl_js}[p.data[0]]+'</b><br>Count: '+p.data[2];}}"
        )},
    }, height)


def bar_v_multi(categories, series_list, height=280, currency=False):
    """
    Grouped vertical bar chart.
    series_list: [{"name": str, "values": [float], "color": str}]
    """
    if currency:
        lbl = JS("function(p){if(p.value>=1e6)return'฿'+(p.value/1e6).toFixed(1)+'M';"
                 "if(p.value>=1e3)return'฿'+(p.value/1e3).toFixed(0)+'K';"
                 "return'฿'+p.value.toLocaleString();}")
    else:
        lbl = JS("function(p){return p.value.toLocaleString()}")
    series = []
    for s in series_list:
        series.append({
            "name": s["name"], "type": "bar",
            "data": [float(v) for v in s["values"]],
            "itemStyle": {"color": s["color"], "borderRadius": [4, 4, 0, 0]},
            "barMaxWidth": 36,
            "label": {"show": True, "position": "top",
                      "color": "#3D4F66", "fontSize": 9, "formatter": lbl},
        })
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 36, "bottom": 20, "left": 8, "right": 8},
        "xAxis": _cat_ax(categories),
        "yAxis": _val_ax(currency),
        "legend": {"data": [s["name"] for s in series_list], "top": 0,
                   "textStyle": {"color": "#3D4F66", "fontSize": 11}},
        "series": series,
        "tooltip": {"trigger": "axis", **_tt()},
    }, height)


def bubble_scatter(segments_data, height=360):
    """
    RFM bubble scatter.
    segments_data: {segment: [(frequency, recency_days, monetary, member_id), ...]}
    """
    all_m = [p[2] for pts in segments_data.values() for p in pts]
    max_m = max(all_m, default=1)
    series = []
    for seg, pts in segments_data.items():
        color = SEGMENT_COLORS.get(seg, "#3D4F66")
        series.append({
            "name": seg, "type": "scatter",
            "data": [[int(p[0]), int(p[1]), float(p[2]), str(p[3])] for p in pts],
            "symbolSize": JS(f"function(d){{return Math.max(8,Math.sqrt(d[2]/{max_m})*55)}}"),
            "itemStyle": {"color": color, "opacity": 0.82},
        })
    render({
        "backgroundColor": "#ffffff", "textStyle": {"color": "#3D4F66"},
        "grid": {"containLabel": True, "top": 24, "bottom": 44, "left": 12, "right": 12},
        "xAxis": {"type": "value", "name": "Frequency",
                  "nameTextStyle": {"color": "#3D4F66"},
                  "splitLine": {"lineStyle": {"color": "#C4D8F8", "type": "dashed"}},
                  "axisLine": {"show": False}, "axisLabel": {"color": "#3D4F66"}},
        "yAxis": {"type": "value", "name": "Recency (days ago)", "inverse": True,
                  "nameTextStyle": {"color": "#3D4F66"},
                  "splitLine": {"lineStyle": {"color": "#C4D8F8", "type": "dashed"}},
                  "axisLine": {"show": False}, "axisLabel": {"color": "#3D4F66"}},
        "legend": {"data": list(segments_data.keys()), "bottom": 0,
                   "textStyle": {"color": "#3D4F66"}},
        "series": series,
        "tooltip": {"trigger": "item", **_tt(), "formatter": JS(
            "function(p){return'<b>'+p.data[3]+'</b><br>'"
            "+p.marker+' Segment: '+p.seriesName+'<br>'"
            "+'Frequency: '+p.data[0]+'<br>'"
            "+'Recency: '+p.data[1]+' days<br>'"
            "+'Spend: ฿'+p.data[2].toLocaleString('th-TH',{maximumFractionDigits:0});}"
        )},
    }, height)
