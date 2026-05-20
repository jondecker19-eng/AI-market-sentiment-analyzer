from __future__ import annotations

import email.utils
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "8010"))
ROOT = Path(__file__).resolve().parent

WATCHLIST = [
    "AAPL", "TSLA", "NVDA", "MSFT", "META", "AMZN", "GOOGL", "AMD", "NFLX", "JPM", "V", "WMT", "DIS", "PFE", "XOM", "COIN",
    "GME", "AMC", "MSTR", "PLTR", "RIVN", "LCID", "NIO", "BABA", "HOOD", "RDDT", "SMCI", "DJT", "SNAP", "INTC", "PYPL", "BA",
]
COMPARE = ["AAPL", "MSFT", "GOOGL", "NVDA", "AMD", "JPM", "V", "XOM"]

COMPANY_FALLBACKS = {
    "AAPL": ("Apple Inc.", "Technology", "$3.22T"),
    "TSLA": ("Tesla, Inc.", "Consumer Cyclical", "$588.4B"),
    "NVDA": ("NVIDIA Corporation", "Semiconductors", "$3.44T"),
    "MSFT": ("Microsoft Corporation", "Technology", "$3.15T"),
    "META": ("Meta Platforms, Inc.", "Communication Services", "$1.19T"),
    "AMZN": ("Amazon.com, Inc.", "Consumer Cyclical", "$1.95T"),
    "GOOGL": ("Alphabet Inc.", "Communication Services", "$2.16T"),
    "AMD": ("Advanced Micro Devices, Inc.", "Semiconductors", "$256.7B"),
    "NFLX": ("Netflix, Inc.", "Communication Services", "$276.5B"),
    "JPM": ("JPMorgan Chase & Co.", "Financial Services", "$586.2B"),
    "V": ("Visa Inc.", "Financial Services", "$563.8B"),
    "WMT": ("Walmart Inc.", "Consumer Defensive", "$553.7B"),
    "DIS": ("The Walt Disney Company", "Communication Services", "$184.9B"),
    "PFE": ("Pfizer Inc.", "Healthcare", "$161.1B"),
    "XOM": ("Exxon Mobil Corporation", "Energy", "$521.4B"),
    "COIN": ("Coinbase Global, Inc.", "Financial Technology", "$55.3B"),
    "GME": ("GameStop Corp.", "Specialty Retail", "N/A"),
    "AMC": ("AMC Entertainment Holdings, Inc.", "Entertainment", "N/A"),
    "MSTR": ("MicroStrategy Incorporated", "Bitcoin Treasury / Software", "N/A"),
    "PLTR": ("Palantir Technologies Inc.", "Data Analytics / AI", "N/A"),
    "RIVN": ("Rivian Automotive, Inc.", "Electric Vehicles", "N/A"),
    "LCID": ("Lucid Group, Inc.", "Electric Vehicles", "N/A"),
    "NIO": ("NIO Inc.", "Electric Vehicles", "N/A"),
    "BABA": ("Alibaba Group Holding Limited", "Chinese Internet / E-commerce", "N/A"),
    "HOOD": ("Robinhood Markets, Inc.", "Brokerage / Fintech", "N/A"),
    "RDDT": ("Reddit, Inc.", "Social Media", "N/A"),
    "SMCI": ("Super Micro Computer, Inc.", "AI Servers / Hardware", "N/A"),
    "DJT": ("Trump Media & Technology Group Corp.", "Media / Social Platform", "N/A"),
    "SNAP": ("Snap Inc.", "Social Media", "N/A"),
    "INTC": ("Intel Corporation", "Semiconductors", "N/A"),
    "PYPL": ("PayPal Holdings, Inc.", "Payments / Fintech", "N/A"),
    "BA": ("The Boeing Company", "Aerospace / Defense", "N/A"),
}

POSITIVE = {
    "beat", "beats", "bullish", "buy", "upgrade", "upgraded", "growth", "profit", "profits", "record",
    "surge", "surges", "rally", "rises", "gain", "gains", "strong", "outperform", "optimistic", "boost",
    "raises", "resilient", "expands", "expansion", "higher", "tops", "rebound", "opportunity", "likes",
    "largest", "adds", "added", "accumulates", "increases", "increased", "positive", "winner", "wins",
    "advance", "advances", "breakout", "momentum", "confidence", "leader", "leadership", "bought",
    "buys", "purchases", "purchased", "acquires", "acquired", "boosted", "boosts",
}

NEGATIVE = {
    "miss", "misses", "bearish", "sell", "downgrade", "downgraded", "slump", "falls", "fall", "drops",
    "drop", "loss", "losses", "weak", "lawsuit", "probe", "warning", "cuts", "cut", "risk", "risks",
    "concern", "concerns", "pressure", "lower", "declines", "slowdown", "volatile", "debt", "avoid",
    "caution", "cautious", "shakeup", "uncertainty", "trouble", "struggles", "struggle", "negative",
    "underperform", "headwind", "headwinds", "break", "breaks", "sells", "sold", "reduced", "reduces",
    "lessened", "trimmed", "trims", "decreases", "decreased",
}

POSITIVE_PHRASES = {
    "price target": 0.18,
    "raises price": 0.35,
    "stock holdings": 0.22,
    "largest position": 0.25,
    "shares bought": 0.34,
    "shares acquired": 0.34,
    "boosts stock": 0.34,
    "boosted by": 0.3,
    "new position": 0.26,
    "new investment": 0.26,
    "buy rating": 0.35,
    "strong buy": 0.45,
    "top pick": 0.35,
    "key insights": 0.12,
    "satellite connectivity advances": 0.22,
    "beats expectations": 0.5,
    "record high": 0.4,
    "make-or-break": 0.12,
}

NEGATIVE_PHRASES = {
    "rating downgrade": 0.45,
    "downgrade": 0.35,
    "don't go": 0.35,
    "price cut": 0.32,
    "cuts target": 0.35,
    "sell rating": 0.45,
    "under pressure": 0.35,
    "class action": 0.4,
    "major shakeup": 0.28,
    "make-or-break": 0.12,
    "shares sold": 0.34,
    "stock position reduced": 0.36,
    "stock position cut": 0.36,
    "cuts stock holdings": 0.42,
    "sells shares": 0.34,
    "trims stake": 0.32,
    "decreases stock holdings": 0.36,
    "holdings lessened": 0.34,
}

STOPWORDS = {
    "about", "after", "again", "ahead", "amid", "and", "are", "as", "at", "be", "but", "by", "for",
    "from", "has", "have", "how", "in", "inc", "into", "is", "it", "its", "market", "markets", "new",
    "news", "of", "on", "or", "over", "says", "share", "shares", "stock", "stocks", "the", "this",
    "to", "today", "up", "us", "why", "with",
}

CACHE: dict[str, tuple[float, object]] = {}


def cached(key: str, ttl: int, loader):
    now = time.time()
    hit = CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    value = loader()
    CACHE[key] = (now, value)
    return value


def fetch_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MarketSentimentAnalyzer/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MarketSentimentAnalyzer/1.0"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return response.read().decode("utf-8", errors="replace")


def yahoo_chart(symbol: str, days: int) -> dict:
    range_days = max(5, min(90, days + 7))
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={range_days}d&interval=1d"
    data = fetch_json(url)
    result = (data.get("chart", {}).get("result") or [{}])[0]
    meta = result.get("meta", {})
    timestamps = result.get("timestamp") or []
    quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    closes = quotes.get("close") or []
    history = []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        history.append({
            "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
            "close": round(float(close), 2),
        })
    history = history[-max(2, days):]
    price = meta.get("regularMarketPrice") or (history[-1]["close"] if history else None)
    previous = meta.get("chartPreviousClose") or (history[-2]["close"] if len(history) > 1 else price)
    change_pct = ((price - previous) / previous * 100) if price and previous else 0
    return {
        "price": round(float(price), 2) if price else None,
        "changePct": round(change_pct, 2),
        "currency": meta.get("currency", "USD"),
        "history": history,
    }


def company_info(symbol: str) -> dict:
    fallback_name, fallback_sector, fallback_cap = COMPANY_FALLBACKS.get(symbol, (symbol, "Public Equity", "N/A"))
    return {
        "name": fallback_name,
        "sector": fallback_sector,
        "marketCap": fallback_cap,
    }


def google_news(symbol: str, company_name: str, max_items: int) -> list[dict]:
    query = urllib.parse.quote(f"{symbol} {company_name} stock")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    xml_text = fetch_text(url)
    root = ET.fromstring(xml_text)
    items = []
    for item in root.findall(".//item")[:max_items]:
        title = text_of(item, "title")
        source_node = item.find("source")
        source = source_node.text if source_node is not None and source_node.text else "Google News"
        published_raw = text_of(item, "pubDate")
        published = published_raw
        score, label = score_text(title)
        items.append({
            "title": title,
            "source": source,
            "kind": "News",
            "url": text_of(item, "link"),
            "published": published,
            "score": score,
            "label": label,
        })
    return items


def reddit_posts(symbol: str, company_name: str, max_items: int) -> list[dict]:
    query = urllib.parse.quote(f"{symbol} stock")
    url = f"https://www.reddit.com/search.rss?q={query}&sort=new&t=month"
    try:
        xml_text = fetch_text(url)
    except Exception:
        return []
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    company_terms = [part for part in re.findall(r"[a-zA-Z0-9]+", company_name.lower()) if len(part) > 3]
    for entry in root.findall("atom:entry", ns):
        title = atom_text(entry, "title", ns)
        title_lower = title.lower()
        if symbol.lower() not in title_lower and not any(term in title_lower for term in company_terms[:2]):
            continue
        published = atom_text(entry, "updated", ns) or atom_text(entry, "published", ns)
        link_node = entry.find("atom:link", ns)
        url_value = link_node.attrib.get("href", "") if link_node is not None else ""
        score, label = score_text(title)
        items.append({
            "title": title,
            "source": "Reddit",
            "kind": "Reddit",
            "url": url_value,
            "published": published,
            "score": score,
            "label": label,
        })
        if len(items) >= max_items:
            break
    return items


def parse_published(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def atom_text(node: ET.Element, name: str, ns: dict[str, str]) -> str:
    child = node.find(f"atom:{name}", ns)
    return child.text.strip() if child is not None and child.text else ""


def filter_by_lookback(items: list[dict], days: int, max_items: int) -> list[dict]:
    cutoff = time.time() - days * 86400
    filtered = []
    for item in items:
        published = parse_published(item.get("published", ""))
        if published is None or published.timestamp() >= cutoff:
            filtered.append(item)
    return filtered[:max_items]


def text_of(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return child.text.strip() if child is not None and child.text else ""


def score_text(text: str) -> tuple[float, str]:
    lowered = text.lower()
    words = re.findall(r"[a-zA-Z][a-zA-Z'-]+", lowered)
    pos = sum(0.22 for word in words if word in POSITIVE)
    neg = sum(0.22 for word in words if word in NEGATIVE)

    for phrase, weight in POSITIVE_PHRASES.items():
        if phrase in lowered:
            pos += weight
    for phrase, weight in NEGATIVE_PHRASES.items():
        if phrase in lowered:
            neg += weight

    if "?" in text:
        neg += 0.08
    if re.search(r"\b(up|higher|jumps?|rises?|gains?)\b", lowered):
        pos += 0.18
    if re.search(r"\b(down|lower|falls?|drops?|slides?)\b", lowered):
        neg += 0.18

    raw = pos - neg
    if raw == 0 and words:
        # Finance headlines are often terse and omit sentiment adjectives. Give
        # position-building/forecast headlines a small directional nudge.
        if any(word in words for word in {"holdings", "position", "forecast", "quote", "target"}):
            raw = 0.11
        elif any(word in words for word in {"report", "shakeup", "probe", "trial"}):
            raw = -0.11

    score = max(-1, min(1, raw))
    if score >= 0.1:
        return round(score, 3), "Bullish"
    if score <= -0.1:
        return round(score, 3), "Bearish"
    return 0, "Neutral"


def aggregate(items: list[dict]) -> dict:
    total = len(items)
    if not total:
        return {"total": 0, "aggregateScore": 0, "bullish": 0, "bearish": 0, "neutral": 0, "dominant": "Neutral"}
    bullish = sum(1 for item in items if item["label"] == "Bullish")
    bearish = sum(1 for item in items if item["label"] == "Bearish")
    neutral = total - bullish - bearish
    aggregate_score = sum(float(item["score"]) for item in items) / total
    dominant = "Bullish" if aggregate_score > 0.05 else "Bearish" if aggregate_score < -0.05 else "Neutral"
    return {
        "total": total,
        "aggregateScore": round(aggregate_score, 3),
        "bullish": bullish,
        "bearish": bearish,
        "neutral": neutral,
        "dominant": dominant,
    }


def keywords(items: list[dict], limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for item in items:
        for word in re.findall(r"[a-zA-Z][a-zA-Z'-]+", item.get("title", "").lower()):
            if len(word) < 4 or word in STOPWORDS:
                continue
            counts[word] = counts.get(word, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]]


def summary(symbol: str, company: dict, stats: dict, keys: list[str], days: int, source_label: str) -> str:
    direction = {
        "Bullish": "constructive",
        "Bearish": "cautious",
        "Neutral": "balanced",
    }.get(stats["dominant"], "balanced")
    keyword_text = ", ".join(keys[:5]) if keys else "the latest headlines"
    return (
        f"{symbol} sentiment is {direction} over the last {days} day{'s' if days != 1 else ''}, "
        f"based on {stats['total']} live {source_label} items. The aggregate sentiment score is "
        f"{stats['aggregateScore']:+.3f}, with {stats['bullish']} bullish, {stats['bearish']} bearish, "
        f"and {stats['neutral']} neutral signals. Current discussion is clustering around {keyword_text}."
    )


def analyze_symbol(symbol: str, days: int, max_items: int, include_news: bool, include_reddit: bool) -> dict:
    symbol = clean_symbol(symbol)
    quote = company_info(symbol)
    chart = cached(f"chart:{symbol}:{days}", 300, lambda: yahoo_chart(symbol, days))
    fetch_limit = max(max_items, 80)
    raw_items = []
    if include_news:
        raw_items.extend(cached(f"news:{symbol}:{fetch_limit}", 300, lambda: google_news(symbol, quote["name"], fetch_limit)))
    if include_reddit:
        raw_items.extend(cached(f"reddit:{symbol}:{fetch_limit}", 300, lambda: reddit_posts(symbol, quote["name"], fetch_limit)))
    raw_items.sort(key=lambda item: parse_published(item.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    items = filter_by_lookback(raw_items, days, max_items)
    stats = aggregate(items)
    keys = keywords(items)
    source_label = "news and Reddit" if include_news and include_reddit else "news" if include_news else "Reddit" if include_reddit else "source"
    return {
        "symbol": symbol,
        "company": quote,
        "quote": chart,
        "items": items,
        "stats": stats,
        "keywords": keys,
        "summary": summary(symbol, quote, stats, keys, days, source_label),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def comparison(days: int, max_items: int, include_news: bool, include_reddit: bool) -> list[dict]:
    results = []
    for symbol in COMPARE:
        try:
            data = analyze_symbol(symbol, days, min(max_items, 20), include_news, include_reddit)
            results.append({
                "symbol": symbol,
                "score": data["stats"]["aggregateScore"],
                "total": data["stats"]["total"],
                "dominant": data["stats"]["dominant"],
            })
        except Exception:
            results.append({"symbol": symbol, "score": 0, "total": 0, "dominant": "Neutral"})
    return results


def format_market_cap(value) -> str:
    if not value:
        return "N/A"
    value = float(value)
    units = [(1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M")]
    for divisor, suffix in units:
        if abs(value) >= divisor:
            return f"${value / divisor:.2f}{suffix}"
    return f"${value:,.0f}"


def clean_symbol(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9.-]", "", value.upper())[:12]
    return cleaned or "AAPL"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/analyze":
            self.handle_analyze(parsed)
            return
        super().do_GET()

    def handle_analyze(self, parsed):
        params = urllib.parse.parse_qs(parsed.query)
        symbol = clean_symbol(params.get("symbol", ["AAPL"])[0])
        days = max(1, min(30, int(params.get("days", ["7"])[0])))
        max_items = max(5, min(80, int(params.get("max_items", ["40"])[0])))
        include_news = params.get("news", ["1"])[0] != "0"
        include_reddit = params.get("reddit", ["1"])[0] != "0"
        try:
            payload = analyze_symbol(symbol, days, max_items, include_news, include_reddit)
            payload["comparison"] = comparison(days, max_items, include_news, include_reddit)
            self.write_json(200, payload)
        except Exception as exc:
            self.write_json(502, {"error": "Live market data is unavailable right now.", "detail": str(exc)})

    def write_json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print(f"Market Sentiment Analyzer running at http://{HOST}:{PORT}/")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
