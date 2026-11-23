# Macro · Crypto — iPad dashboard

A full-screen page made for the iPad (landscape and portrait). It shows the main indicator charts for crypto and the dollar (DXY).

## Tabs

| Tab | Charts |
| --- | --- |
| **Dollar vs Crypto** | BTC vs DXY (overlay), DXY + RSI, US 10-year yield, USD/JPY (carry trade) |
| **Dominance & Rotation** | USDT.D + RSI, BTC.D, ETH/BTC, OTHERS.D |
| **Liquidité & Risque** | TOTAL, USDT market cap (stablecoins), Nasdaq 100 vs BTC, Gold |
| **Signaux** | Fear & Greed (30 days), BTC dominance, stablecoin dominance, 24h total market cap, technical gauges (DXY / BTC / USDT.D), reading guide |

- **Auto / 4H / 1J / 1S**: timeframe for every chart ("Auto" uses each chart's recommended timeframe).
- **⤢**: opens a chart full screen.
- **Mode écran**: cycles through the tabs every 60 s and keeps the screen on (iPadOS 16.4+).

The charts are live TradingView widgets. The KPIs come from alternative.me (Fear & Greed) and CoinGecko and refresh every 5 minutes.

## Putting it on the iPad

1. Host the page with **GitHub Pages**: *Settings → Pages → Deploy from a branch*, select the branch and the `/ (root)` folder.
2. Open the URL in **Safari** on the iPad → Share → **Add to Home Screen**.
3. Launch it from the icon: it opens full screen with no Safari bar.

## Customising

Everything is set in the `TABS`, `TICKER` and `TA_SYMBOLS` arrays at the top of the `<script>` in `index.html`. Any TradingView symbol works (`EXCHANGE:TICKER` format), along with its title and reading note.
