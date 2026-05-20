const fallbackSymbols = ["AAPL", "TSLA", "NVDA", "MSFT", "META", "AMZN", "GOOGL", "AMD"];
let activeFilter = "all";
let currentData = null;
let updateTimer = null;

const el = (id) => document.getElementById(id);
const clamp = (num, min, max) => Math.max(min, Math.min(max, num));

function getControls() {
  return {
    symbol: (el("tickerInput").value.trim().toUpperCase() || "AAPL").replace(/[^A-Z0-9.-]/g, ""),
    days: Number(el("daysRange").value),
    maxItems: Number(el("itemsRange").value),
    includeNews: el("newsToggle").checked,
    includeReddit: el("redditToggle").checked,
  };
}

async function updateDashboard() {
  const controls = getControls();
  el("tickerInput").value = controls.symbol;
  setLoading(true);

  try {
    const params = new URLSearchParams({
      symbol: controls.symbol,
      days: String(controls.days),
      max_items: String(controls.maxItems),
      news: controls.includeNews ? "1" : "0",
      reddit: controls.includeReddit ? "1" : "0",
    });
    const response = await fetch(`/api/analyze?${params.toString()}`, { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || payload.error || "Unable to load live data.");
    currentData = payload;
    renderDashboard(payload);
  } catch (error) {
    renderError(error);
  } finally {
    setLoading(false);
  }
}

function renderDashboard(data) {
  const stats = data.stats;
  const quote = data.quote;
  const company = data.company;
  const price = quote.price;
  const change = quote.changePct;

  el("tickerSymbol").textContent = data.symbol;
  el("companyName").textContent = `${company.name} - ${company.sector || "Public Equity"}`;
  el("currentPrice").textContent = price ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A";
  el("priceChange").textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;
  el("priceChange").className = `change ${change >= 0 ? "positive" : "negative"}`;
  el("priceMetric").textContent = price ? `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "N/A";
  el("priceMetricDelta").textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}% ${quote.currency || "USD"}`;
  el("priceMetricDelta").className = change >= 0 ? "positive" : "negative";

  el("scoreMetric").textContent = `${stats.aggregateScore >= 0 ? "+" : ""}${stats.aggregateScore.toFixed(3)}`;
  el("dominantMetric").textContent = stats.dominant;
  el("bullMetric").textContent = stats.bullish;
  el("bearMetric").textContent = stats.bearish;
  el("bullPctMetric").textContent = stats.total ? `${Math.round((stats.bullish / stats.total) * 100)}%` : "0%";
  el("bearPctMetric").textContent = stats.total ? `${Math.round((stats.bearish / stats.total) * 100)}%` : "0%";
  el("sourcesMetric").textContent = stats.total;
  el("capMetric").textContent = company.marketCap || "N/A";
  const enabledSources = [
    el("newsToggle").checked && "Google News",
    el("redditToggle").checked && "Reddit",
  ].filter(Boolean);
  document.querySelector(".metrics article:nth-child(5) em").textContent = enabledSources.length ? enabledSources.join(" + ") : "Sources disabled";

  el("summaryText").textContent = data.summary;
  renderKeywords(data.keywords);
  renderHeadlines(data.items);
  drawGauge(stats.aggregateScore);
  drawDistribution(stats);
  drawPriceChart(data.quote.history, stats.aggregateScore, getControls().days);
  drawSources(stats);
  drawCompare(data.comparison || []);
}

function setLoading(isLoading) {
  el("refreshButton").disabled = isLoading;
  el("refreshButton").textContent = isLoading ? "Loading Live Data..." : "Refresh Analysis";
  document.body.classList.toggle("is-loading", isLoading);
}

function renderError(error) {
  const message = location.protocol === "file:"
    ? "Open the site through the live server at http://127.0.0.1:8010/ so the API can run."
    : error.message;
  el("summaryText").textContent = message;
  el("priceMetric").textContent = "N/A";
  el("priceMetricDelta").textContent = "Live API";
  el("priceMetricDelta").className = "";
  el("sourcesMetric").textContent = "0";
  renderHeadlines([]);
  renderKeywords([]);
  drawGauge(0);
  drawDistribution({ bullish: 0, neutral: 0, bearish: 0 });
  drawPriceChart([], 0, getControls().days);
  drawSources({ bullish: 0, neutral: 0, bearish: 0 });
  drawCompare([]);
}

function renderKeywords(words) {
  el("keywordCloud").innerHTML = "";
  const safeWords = words.length ? words : ["live", "market", "news", "price", "sentiment"];
  safeWords.forEach((word, index) => {
    const node = document.createElement("span");
    node.textContent = word;
    node.style.borderColor = index < 3 ? "rgba(0, 200, 150, 0.55)" : index > 5 ? "rgba(255, 75, 110, 0.45)" : "var(--border)";
    el("keywordCloud").appendChild(node);
  });
}

function renderHeadlines(items) {
  const feed = el("headlineFeed");
  feed.innerHTML = "";
  const filtered = items.filter((item) => activeFilter === "all" || item.label === activeFilter);
  if (!filtered.length) {
    const empty = document.createElement("article");
    empty.className = "headline-card neutral";
    empty.innerHTML = "<h3>No live items found for this filter.</h3><div class=\"meta\">Try another ticker or enable a source.</div>";
    feed.appendChild(empty);
    return;
  }

  filtered.slice(0, 24).forEach((item) => {
    const card = document.createElement("article");
    card.className = `headline-card ${item.label.toLowerCase()}`;
    const link = item.url ? `<a href="${escapeAttr(item.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.title)}</a>` : escapeHtml(item.title);
    card.innerHTML = `
      <h3>${link}<span class="badge ${item.label}">${item.label}</span></h3>
      <div class="meta">${escapeHtml(item.source || "News")} - ${escapeHtml(formatPublished(item.published))}</div>
    `;
    feed.appendChild(card);
  });
}

function drawGauge(score) {
  const angle = 180 + ((clamp(score, -1, 1) + 1) / 2) * 180;
  const needle = polarToPoint(180, 170, 88, angle);
  el("gaugeChart").innerHTML = `
    <svg viewBox="0 0 360 220" role="img" aria-label="Sentiment score ${score.toFixed(3)}">
      <path d="M 72 170 A 108 108 0 0 1 143 69" fill="none" stroke="#ff4b6e" stroke-width="22" stroke-linecap="round"/>
      <path d="M 143 69 A 108 108 0 0 1 217 69" fill="none" stroke="#94a3b8" stroke-width="22" stroke-linecap="round"/>
      <path d="M 217 69 A 108 108 0 0 1 288 170" fill="none" stroke="#00c896" stroke-width="22" stroke-linecap="round"/>
      <line x1="180" y1="170" x2="${needle.x.toFixed(1)}" y2="${needle.y.toFixed(1)}" stroke="#f0b429" stroke-width="5" stroke-linecap="round"/>
      <circle cx="180" cy="170" r="7" fill="#f0b429"/>
      <text x="180" y="137" text-anchor="middle" fill="#e6edf3" font-size="30" font-weight="700" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${score >= 0 ? "+" : ""}${score.toFixed(3)}</text>
      <text x="54" y="207" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">BEARISH</text>
      <text x="180" y="207" text-anchor="middle" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">NEUTRAL</text>
      <text x="306" y="207" text-anchor="end" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">BULLISH</text>
    </svg>
  `;
}

function drawDistribution(stats) {
  const labels = ["Bullish", "Neutral", "Bearish"];
  const values = [stats.bullish || 0, stats.neutral || 0, stats.bearish || 0];
  const colors = ["#00c896", "#94a3b8", "#ff4b6e"];
  const max = Math.max(...values, 1);
  const bars = values.map((value, index) => {
    const y = 56 + index * 62;
    const width = 470 * (value / max);
    return `
      <text x="16" y="${y + 20}" fill="#c9d1d9" font-size="14" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${labels[index]}</text>
      <rect x="112" y="${y}" width="500" height="30" rx="6" fill="#0d1117"/>
      <rect x="112" y="${y}" width="${width.toFixed(1)}" height="30" rx="6" fill="${colors[index]}" opacity="0.92"/>
      <text x="${Math.min(626, 126 + width).toFixed(1)}" y="${y + 20}" fill="#c9d1d9" font-size="13" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${value}</text>
    `;
  }).join("");
  el("distributionChart").innerHTML = `<svg viewBox="0 0 660 260" role="img" aria-label="Signal distribution">${bars}</svg>`;
}

function drawPriceChart(history, score, days) {
  const closes = history.map((point) => point.close).filter((value) => Number.isFinite(value));
  const values = closes.length >= 2 ? closes : [0, 0];
  const sentiments = values.map((_, i) => score + Math.sin(i / 2.8) * 0.08);
  const grid = [0, 1, 2, 3, 4].map((i) => `<line x1="20" y1="${52 + i * 52}" x2="700" y2="${52 + i * 52}" stroke="#30363d"/>`).join("");
  el("priceChart").innerHTML = `
    <svg viewBox="0 0 720 320" role="img" aria-label="Live price history">
      ${grid}
      <path d="${linePath(values, 20, 52, 680, 208)}" fill="none" stroke="#58a6ff" stroke-width="3"/>
      <path d="${linePath(sentiments, 20, 52, 680, 208)}" fill="none" stroke="#f0b429" stroke-width="3"/>
      <text x="20" y="24" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${days}D Live Price</text>
      <line x1="132" y1="20" x2="152" y2="20" stroke="#58a6ff" stroke-width="4"/>
      <text x="174" y="24" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">Headline Sentiment</text>
      <line x1="326" y1="20" x2="346" y2="20" stroke="#f0b429" stroke-width="4"/>
    </svg>
  `;
}

function drawSources(stats) {
  const total = Math.max(1, stats.total || 0);
  const bullishAngle = ((stats.bullish || 0) / total) * 360;
  el("sourceChart").innerHTML = `
    <svg viewBox="0 0 420 260" role="img" aria-label="Source breakdown">
      <circle cx="210" cy="118" r="76" fill="none" stroke="#94a3b8" stroke-width="48"/>
      <circle cx="210" cy="118" r="76" fill="none" stroke="#00c896" stroke-width="48"
        stroke-dasharray="${(bullishAngle / 360 * 477.5).toFixed(1)} 477.5" transform="rotate(-90 210 118)"/>
      <circle cx="210" cy="118" r="42" fill="#161b22"/>
      <text x="104" y="226" fill="#c9d1d9" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">Bullish</text>
      <rect x="166" y="217" width="18" height="8" fill="#00c896"/>
      <text x="212" y="226" fill="#c9d1d9" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">Other</text>
      <rect x="260" y="217" width="18" height="8" fill="#94a3b8"/>
    </svg>
  `;
}

function drawCompare(items) {
  const data = items.length ? items : fallbackSymbols.map((symbol) => ({ symbol, score: 0, total: 0 }));
  const maxScore = 0.65;
  const step = data.length > 1 ? 680 / (data.length - 1) : 0;
  const bars = data.map((item, index) => {
    const x = 40 + index * step;
    const score = clamp(Number(item.score) || 0, -maxScore, maxScore);
    const barH = Math.abs(score) / maxScore * 120;
    const y = score >= 0 ? 180 - barH : 180;
    return `
      <rect x="${x - 20}" y="${y.toFixed(1)}" width="40" height="${barH.toFixed(1)}" rx="6" fill="${score >= 0 ? "#00c896" : "#ff4b6e"}"/>
      <text x="${x}" y="${score >= 0 ? y - 12 : y + barH + 24}" text-anchor="middle" fill="#c9d1d9" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${score >= 0 ? "+" : ""}${score.toFixed(2)}</text>
      <text x="${x}" y="314" text-anchor="middle" fill="#c9d1d9" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${item.symbol}</text>
      <text x="${x}" y="333" text-anchor="middle" fill="#8b949e" font-size="10" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">${item.total || 0} ITEMS</text>
    `;
  }).join("");
  el("compareChart").innerHTML = `
    <svg viewBox="0 0 760 360" role="img" aria-label="Live multi-stock sentiment comparison">
      <text x="40" y="32" fill="#8b949e" font-size="12" font-family="ui-monospace, SFMono-Regular, Menlo, monospace">LIVE COMPARISON</text>
      <line x1="40" y1="180" x2="720" y2="180" stroke="#30363d"/>
      ${bars}
    </svg>
  `;
}

function linePath(values, x, y, width, height) {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values.map((value, index) => {
    const px = x + index * (width / Math.max(1, values.length - 1));
    const py = y + (1 - (value - min) / span) * height;
    return `${index === 0 ? "M" : "L"} ${px.toFixed(1)} ${py.toFixed(1)}`;
  }).join(" ");
}

function polarToPoint(cx, cy, radius, angleDegrees) {
  const angle = (angleDegrees * Math.PI) / 180;
  return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
}

function formatPublished(value) {
  if (!value) return "Live news";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  })[char]);
}

function escapeAttr(value) {
  return escapeHtml(value).replace(/`/g, "&#096;");
}

document.querySelectorAll("[data-symbol]").forEach((button) => {
  button.addEventListener("click", () => {
    el("tickerInput").value = button.dataset.symbol;
    updateDashboard();
  });
});

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((node) => node.classList.remove("active"));
    button.classList.add("active");
    activeFilter = button.dataset.filter;
    if (currentData) renderHeadlines(currentData.items);
  });
});

["tickerInput", "engineSelect", "daysRange", "itemsRange", "newsToggle", "redditToggle"].forEach((id) => {
  el(id).addEventListener("input", () => {
    el("daysValue").textContent = el("daysRange").value;
    el("itemsValue").textContent = el("itemsRange").value;
    scheduleUpdate();
  });
});

el("refreshButton").addEventListener("click", updateDashboard);
updateDashboard();

function scheduleUpdate() {
  window.clearTimeout(updateTimer);
  updateTimer = window.setTimeout(updateDashboard, 450);
}
