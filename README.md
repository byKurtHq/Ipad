# Macro · Crypto — iPad dashboard

Full-screen animated dashboard ("motion design") for crypto and the dollar (DXY), built for the iPad.

## `index.html` — Indicators (home page)

| Tile | What it shows | Source |
| --- | --- | --- |
| Bitcoin · live | Real-time price (flashes on every move), 24h range, 7-day curve | Binance (WebSocket) |
| Dollar Index · DXY | DXY recomputed from ECB exchange rates, gap to its 50-day MA, 30-day BTC/DXY correlation | Frankfurter (ECB) |
| Market regime | Composite risk-on / risk-off score: dollar, BTC trend, sentiment, liquidity | computed |
| Fear & Greed | Gauge + yesterday / 7 days / 30 days | alternative.me |
| BTC derivatives | Funding rate, open interest (7 days), long/short ratio | Binance Futures (OKX as fallback) |
| Dominance & rotation | BTC / ETH / stablecoins / others shares, ETH/BTC over 90 days | CoinGecko, Binance |
| Altseason index | % of the top 50 alts outperforming BTC over 30 days + leaders | CoinGecko |
| Bitcoin cycle | Mayer Multiple, 200-week MA, Pi Cycle Top, RSI 14 | Binance |
| Liquidity & calendar | Stablecoin supply (30 days), live FOMC countdown, halving | DefiLlama, mempool.space |
| News | French crypto + macro feed, auto-scrolling, tagged Macro / ETF / Regulation… | Cointelegraph FR, Journal du Coin, Cryptoast, Investing FR (via rss2json) |

Price bar at the bottom: BTC, ETH, SOL, XRP, BNB, DOGE, Gold (PAXG), DXY, Fear & Greed.

- Tap or slide a finger across a curve to read a value.
- Tap the news feed to scroll it by hand (auto-scroll resumes after 30 s).
- **Écran allumé** (keep screen on): stops the iPad from going to sleep.

## Detail views

Tap any tile to open a full-screen panel (zoom animation) with:
- **interactive charts** with time ranges (24 h → several years), moving averages, zones and history;
- the **current reading** of the indicator (e.g. "Bullish trend", "Leverage rising", "Phase 3/4 of the rotation");
- the **key figures** (performance over several periods, highs/lows, averages, thresholds);
- **how to read it**: benchmarks and explanations.

Examples: DXY components and their 1-month effect, rolling BTC/DXY correlation, reconstructed history of the regime score, funding / open interest / long-short history, full ranking of the top 50 altcoins vs BTC, Mayer Multiple / Pi Cycle / 200-week MA / RSI, the main stablecoins, the Fed calendar and the state of the Bitcoin network.

The code lives in `details.js` and `details.css`.

## `charts.html` — Charts

The TradingView version (live charts grouped into tabs), reachable from the **Graphiques** button.

## Customising

At the top of the `<script>` in `index.html`: `TAPE` (price bar), `FEEDS` (news RSS feeds), `FOMC` (Fed dates — the 2027 dates need adding).

The indicators are reading aids, not investment advice.
