from __future__ import annotations

import html
from datetime import datetime

import pandas as pd
import streamlit as st

from server import COMPARE, WATCHLIST, analyze_symbol, comparison


st.set_page_config(
    page_title="Market Sentiment Analyzer",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
      .block-container { padding-top: 1.4rem; max-width: 1420px; }
      [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 14px 16px;
      }
      .section-title {
        color: #8b949e;
        border-bottom: 1px solid #30363d;
        padding-bottom: 8px;
        margin: 22px 0 12px;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .headline-card {
        border: 1px solid #30363d;
        border-left-width: 4px;
        border-radius: 8px;
        padding: 12px 14px;
        margin-bottom: 10px;
        background: #111827;
      }
      .headline-card.Bullish { border-left-color: #00c896; }
      .headline-card.Bearish { border-left-color: #ff4b6e; }
      .headline-card.Neutral { border-left-color: #94a3b8; }
      .headline-meta {
        color: #8b949e;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 12px;
        margin-top: 6px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300, show_spinner=False)
def load_analysis(symbol: str, days: int, max_items: int, include_news: bool, include_reddit: bool) -> dict:
    data = analyze_symbol(symbol, days, max_items, include_news, include_reddit)
    data["comparison"] = comparison(days, max_items, include_news, include_reddit)
    return data


def label_color(label: str) -> str:
    return {"Bullish": "#00c896", "Bearish": "#ff4b6e", "Neutral": "#94a3b8"}.get(label, "#94a3b8")


def fmt_price(value: float | None) -> str:
    return f"${value:,.2f}" if value is not None else "N/A"


def render_distribution(stats: dict) -> None:
    rows = [
        ("Bullish", stats.get("bullish", 0), "#00c896"),
        ("Neutral", stats.get("neutral", 0), "#94a3b8"),
        ("Bearish", stats.get("bearish", 0), "#ff4b6e"),
    ]
    max_value = max([row[1] for row in rows] + [1])
    for label, value, color in rows:
        pct = value / max_value * 100
        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns: 88px 1fr 42px; align-items:center; gap:12px; margin:12px 0;">
              <div style="font-family:ui-monospace,Menlo,monospace;">{label}</div>
              <div style="height:24px; background:#0d1117; border-radius:6px; overflow:hidden;">
                <div style="height:100%; width:{pct:.1f}%; background:{color};"></div>
              </div>
              <div style="font-family:ui-monospace,Menlo,monospace;">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_headlines(items: list[dict], label: str | None = None) -> None:
    selected = [item for item in items if label is None or item.get("label") == label]
    if not selected:
        st.caption("No items found for this filter.")
        return

    for item in selected[:30]:
        item_label = item.get("label", "Neutral")
        title = html.escape(item.get("title", "(Untitled)"))
        url = item.get("url", "")
        source = html.escape(item.get("source", "Source"))
        kind = html.escape(item.get("kind", "Item"))
        published = html.escape(format_published(item.get("published", "")))
        link = f'<a href="{html.escape(url)}" target="_blank" rel="noopener noreferrer">{title}</a>' if url else title
        st.markdown(
            f"""
            <div class="headline-card {item_label}">
              <div>{link}
                <span style="color:{label_color(item_label)}; font-family:ui-monospace,Menlo,monospace; font-size:12px;">
                  {item_label}
                </span>
              </div>
              <div class="headline-meta">{kind} · {source} · {published}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def format_published(value: str) -> str:
    if not value:
        return "Live"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%b %d, %H:%M")
    except ValueError:
        return value[:25]


with st.sidebar:
    st.markdown("## Market Sentiment")
    symbol = st.text_input("Ticker symbol", value="AAPL", max_chars=12).upper().strip() or "AAPL"

    st.caption("Quick picks")
    cols = st.columns(4)
    for idx, ticker in enumerate(WATCHLIST):
        if cols[idx % 4].button(ticker, key=f"ticker_{ticker}", use_container_width=True):
            symbol = ticker

    st.divider()
    days = st.slider("Lookback days", 1, 30, 7)
    max_items = st.slider("Max items", 10, 80, 40, step=5)
    include_news = st.toggle("Include Google News", value=True)
    include_reddit = st.toggle("Include Reddit", value=True)

    st.caption("Live sources: Yahoo Finance chart data, Google News RSS, Reddit public search RSS.")


with st.spinner(f"Loading live sentiment for {symbol}..."):
    data = load_analysis(symbol, days, max_items, include_news, include_reddit)

stats = data["stats"]
quote = data["quote"]
company = data["company"]
price = quote.get("price")
change = quote.get("changePct", 0)
dominant = stats.get("dominant", "Neutral")

st.title(f"{data['symbol']} · {company.get('name', data['symbol'])}")
st.caption(f"{company.get('sector', 'Public Equity')} · Updated from live market/news sources")

metric_cols = st.columns(6)
metric_cols[0].metric("Current Price", fmt_price(price), f"{change:+.2f}% {quote.get('currency', 'USD')}")
metric_cols[1].metric("Sentiment Score", f"{stats.get('aggregateScore', 0):+.3f}", dominant)
metric_cols[2].metric("Bullish Signals", stats.get("bullish", 0), f"{stats.get('bullish', 0) / max(1, stats.get('total', 0)):.0%}")
metric_cols[3].metric("Bearish Signals", stats.get("bearish", 0), f"{stats.get('bearish', 0) / max(1, stats.get('total', 0)):.0%}")
metric_cols[4].metric("Sources Analysed", stats.get("total", 0), "News + Reddit" if include_news and include_reddit else "News" if include_news else "Reddit" if include_reddit else "None")
metric_cols[5].metric("Market Cap", company.get("marketCap", "N/A"))

st.markdown('<div class="section-title">Sentiment Overview</div>', unsafe_allow_html=True)
left, right = st.columns([1, 1.5])
with left:
    st.progress((stats.get("aggregateScore", 0) + 1) / 2)
    st.caption("Bearish ← Neutral → Bullish")
with right:
    render_distribution(stats)

st.markdown('<div class="section-title">Multi-stock Radar Comparison</div>', unsafe_allow_html=True)
comparison_df = pd.DataFrame(data.get("comparison", []))
if not comparison_df.empty:
    st.bar_chart(comparison_df.set_index("symbol")["score"])
else:
    st.caption("No comparison data available.")

st.markdown('<div class="section-title">AI-style Market Summary</div>', unsafe_allow_html=True)
st.info(data.get("summary", "No summary available."))

price_history = pd.DataFrame(quote.get("history", []))
if not price_history.empty:
    st.markdown('<div class="section-title">Live Price History</div>', unsafe_allow_html=True)
    st.line_chart(price_history.set_index("date")["close"])

keywords = data.get("keywords", [])
st.markdown('<div class="section-title">Top Keywords</div>', unsafe_allow_html=True)
if keywords:
    st.write(" · ".join(keywords))
else:
    st.caption("No keywords available.")

st.markdown('<div class="section-title">Recent News and Reddit Items</div>', unsafe_allow_html=True)
tab_all, tab_bull, tab_bear = st.tabs(["All", "Bullish", "Bearish"])
with tab_all:
    render_headlines(data.get("items", []))
with tab_bull:
    render_headlines(data.get("items", []), "Bullish")
with tab_bear:
    render_headlines(data.get("items", []), "Bearish")
