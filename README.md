# AI Agent Lens

**A TradingView indicator built for AI agents.**

Indicators were built for human eyes: colors, arrows, lines. An AI agent can't trade on colors. AI Agent Lens breaks down every closed candle into clean, structured JSON and sends it to any AI agent the moment the candle closes. Your agent reads the chart candle by candle, understands the context, and turns it into clear trading signals. You make the final call.

It works with any agent. It's built to shine with long-horizon reasoning models like **Claude Fable 5.2**.

Open source · MIT license · Pine Script v6 · No repainting

---

## Two versions

| File | Type | Use it when |
|---|---|---|
| [ai-agent-lens.pine](ai-agent-lens.pine) | Indicator | You want the chart readout and one JSON packet per candle for your agent |
| [ai-agent-lens-strategy.pine](ai-agent-lens-strategy.pine) | **Strategy with alerts** | You also want backtests in the Strategy Tester, real entry/stop/target orders, order-fill alerts for a bot, and **pluggable signal modules** you can extend |

The strategy keeps everything the indicator sends and adds votes from its signal modules, filters, fills and performance to the packet. Adding a new entry idea is three lines in marked spots; nothing else changes. Full guide: [docs/STRATEGY.md](docs/STRATEGY.md) (Persian summary: [docs/STRATEGY.fa.md](docs/STRATEGY.fa.md)).

---

## What your agent receives on every candle

One JSON packet per closed candle with everything a trader looks at:

- **Candle breakdown:** body, wicks, range versus ATR, where it closed in its range, gap, pattern (engulfing, hammer, doji, inside bar and more)
- **The last 5 candles** in the same format, so the agent reads the sequence, not one bar
- **Regime:** `TREND_UP`, `TREND_DOWN`, `RANGE` or `HIGH_VOLATILITY`
- **Trend:** EMA 20/50/200 stack, 200 EMA slope, higher-timeframe bias
- **Momentum and strength:** RSI, MACD histogram, ADX, DI+ and DI-
- **Volume and volatility:** relative volume, ATR, ATR percentile
- **Structure:** swing highs and lows, breakouts and breakdowns
- **Levels:** previous day high and low, VWAP
- **Long and short scores (0 to 100)** with the five factors behind each score
- **Risk map:** entry, ATR stop, 1.5R and 3R targets, and live trade status

Full field list: [docs/PACKET_SCHEMA.md](docs/PACKET_SCHEMA.md) · Example: [examples/sample_packet.json](examples/sample_packet.json)

---

## How it works

```
 TradingView chart                 Your AI agent                    You
 ┌───────────────────┐  webhook   ┌──────────────────────────┐    ┌──────────────┐
 │  AI Agent Lens    │ ─────────► │ reads the JSON packet    │ ─► │ signal:      │
 │  closes a candle, │  JSON per  │ breaks down the candles  │    │ LONG / SHORT │
 │  builds a packet  │  candle    │ applies your rules       │    │ WAIT / SKIP  │
 └───────────────────┘            └──────────────────────────┘    │ entry, stop, │
                                                                  │ targets, why │
                                                                  └──────────────┘
```

1. The indicator runs on your TradingView chart and calculates everything on each closed candle.
2. One TradingView alert sends the packet to your agent's webhook URL.
3. Your agent (Claude Code with Fable 5.2, an n8n flow, your own bot) reads it with the prompt in [agent/AGENT_PROMPT.md](agent/AGENT_PROMPT.md) and returns a signal: decision, confidence, entry, stop, targets, position size, invalidation and why it could fail.

---

## Quick start

### Step 1. Add the indicator to TradingView (1 minute)

1. Open [ai-agent-lens.pine](ai-agent-lens.pine) and copy all of it.
2. In TradingView, open the **Pine Editor** at the bottom of the chart.
3. Delete the default code, paste, and click **Save**, then **Add to chart**.

You'll see the EMA ribbon, key levels, swing points and structure breaks, ▲ LONG / ▼ SHORT score labels, position boxes for every setup, and the **Agent Readout** panel on the right.

### Step 2. Create one alert (1 minute)

1. Open the alert dialog (clock icon, or `Alt + A`).
2. **Condition:** `AI Agent Lens` → `Any alert() function call`.
3. **Notifications:** tick **Webhook URL** and paste your agent's URL (Step 3).
4. Leave the message box as it is. The indicator writes the message itself.
5. Click **Create**.

One alert covers one chart (one symbol on one timeframe). Repeat it for every chart you want your agent to watch.

> Webhook alerts need a paid TradingView plan with two-factor authentication turned on. On the Essential and Plus plans, alerts expire after 2 months, so recreate them when they do.

### Step 3. Connect your agent

Pick one.

#### Option A: Claude Code with Fable 5.2 (recommended)

```bash
git clone https://github.com/roan-maverick/tradingview-indicator-for-ai-agents
cd tradingview-indicator-for-ai-agents

# 1. Start the receiver (Python 3, no installs)
python3 examples/webhook_receiver.py --port 8080 --token YOUR_SECRET

# 2. In a second terminal, give it a public HTTPS address
cloudflared tunnel --url http://localhost:8080
```

Your webhook URL for Step 2 is:

```
https://<your-tunnel-address>/webhook?token=YOUR_SECRET
```

Every packet is saved to `packets/latest.json`, `packets/latest/<SYMBOL>_<TF>.json` and `packets/history.jsonl`.

Now open Claude Code in the same folder:

```bash
claude
```

and ask:

```
Use agent/AGENT_PROMPT.md as your instructions. Read packets/latest.json
and give me the signal for this candle.
```

More things to ask:

```
Read every file in packets/latest/ and rank the charts by setup quality.

Combine the HYPE 1h and 4h packets: the 4h sets direction, the 1h sets timing.

Read the last 50 lines of packets/history.jsonl for BTC and tell me how
the momentum and structure changed over the session.
```

#### Option B: No-code (n8n, Make, Zapier)

1. Create a **Webhook** trigger and copy its URL into the TradingView alert.
2. Add an **AI** step (Claude or any LLM). Use the block in [agent/AGENT_PROMPT.md](agent/AGENT_PROMPT.md) as the system prompt and the webhook body as the user message.
3. Send the reply to Telegram, Discord, Slack or email.

#### Option C: Your own bot

Point the webhook at your server. The body is plain JSON with the schema `ai-agent-lens/v1`. Check the `schema` field, then use the fields directly or pass the packet to your model with the agent prompt.

---

### Using the strategy instead

1. Paste [ai-agent-lens-strategy.pine](ai-agent-lens-strategy.pine) into the Pine Editor, **Save**, **Add to chart**. Open the **Strategy Tester** tab to see the backtest.
2. Pick your entry ideas in **Settings → Inputs → Signal modules** (score, structure break, EMA cross, RSI pullback) and how they vote (Any, All, At least N). Add filters (regime, volatility, higher timeframe, session).
3. Create one alert:
   - for an **AI agent**: condition `AI Agent Lens Strategy` → `alert() function calls only`, webhook URL of your agent, message unchanged;
   - for an **execution bot**: condition `Order fills only`, message exactly `{{strategy.order.alert_message}}`.

The same receiver handles both: packets go to `packets/latest.json`, order messages to `packets/orders.jsonl`. Schemas: [docs/PACKET_SCHEMA.md](docs/PACKET_SCHEMA.md#strategy-packet-ai-agent-lens-strategyv1).

---

## What a signal looks like

Example output from the agent prompt ([examples/sample_signal.json](examples/sample_signal.json)):

```json
{
  "decision": "LONG",
  "confidence": 74,
  "entry": 70.71,
  "stop": 69.882,
  "target_1": 71.952,
  "target_2": 73.194,
  "candle_read": "Three candles of steady higher closes, a bearish engulfing shakeout that held above the last swing low, then a bullish engulfing on 1.31x volume that closed in the top quarter of its range and above the last swing high.",
  "invalidation": "A 1h close back below 70.48 or a touch of the 69.882 stop",
  "why_this_could_fail": "This could be a relief rally inside a larger daily pullback."
}
```

The example files are illustrative, not live market data or a real trade.

---

## What you see on the chart

| Element | What it shows |
|---|---|
| **Agent Readout panel** | A clean signal card: LONG, SHORT or WAIT, regime, scores, confluence, the open trade with live R multiple, and market context |
| **Position boxes** | Every setup is drawn like TradingView's long/short tool: a red risk box (entry to stop) and a green reward box (entry to target 2) with a dashed target 1 line. Boxes extend while the trade is open and stop where it closed |
| **Price tags** | ENTRY, STOP, T1 and T2 tags on the right of the open trade |
| **Setup labels** | ▲ LONG 81 / ▼ SHORT 77. Hover a label to see the factor breakdown behind the score |
| **EMA ribbon** | EMA 20 and 50 with a green or red fill between them, and a glowing EMA 200 |
| **Structure** | Confirmed swing highs and lows as dots, and BOS markers when price breaks them |
| **Key levels** | Previous day high and low (PDH, PDL) and VWAP |
| **Optional** | Candles colored by score, background shaded by regime |

### The Agent Readout panel

A clean signal card in the corner of the chart:

| Row | Shows |
|---|---|
| Header | AI AGENT LENS, symbol and timeframe |
| Signal | **LONG**, **SHORT** or **WAIT** in large type, with the score |
| Status | Setup active, target 1 hit, long building (64 of 70), or no confluence yet |
| Regime | Trend up, trend down, range, high volatility |
| Long / Short | Both scores |
| Confluence | How many of the five factors are clearly aligned |
| Entry, Stop, Targets, Open P&L | The open trade and its live R multiple (shown only while a trade is open) |
| Context | Higher-timeframe bias, RSI, ADX |
| Candle, Structure | Current candle pattern and market structure |

Switch **Panel mode** to Compact to keep only the signal, regime, scores and confluence. The indicator keeps the chart's status line clean (no input values printed next to its name), and every value is also in TradingView's **Data Window**.

---

## How the scores work

Each score is out of 100: five factors, 20 points each.

| Factor | Long side gets points when |
|---|---|
| Trend | EMA 20 > 50 > 200 and close above EMA 20 |
| Momentum | RSI above 50 (not overbought), MACD histogram positive and rising |
| Strength | DI+ above DI- and ADX at or above 20 |
| Volume | Bullish candle on above-average volume |
| Higher timeframe | 4h close above its 50 EMA |

The short score mirrors it. A **setup** fires when a score crosses 70 on a closed candle and the regime does not point the other way. While a trade is open, repeat signals in the same direction are ignored, so one move gives one signal. Full rules: [docs/SPECIFICATION.md](docs/SPECIFICATION.md).

---

## Settings

| Setting | Default | What it changes |
|---|---|---|
| Setup score threshold | 70 | Higher = fewer, stronger setups |
| Higher timeframe | 240 (4h) | Use D on a 4h chart, W on a daily chart |
| Block setups in HIGH_VOLATILITY | On | Skips setups during volatility spikes |
| Stop distance | 1.5 x ATR | Wider or tighter stops |
| Target 1 / Target 2 | 1.5R / 3R | Reward multiples |
| Send JSON packet | Every bar close | Or only setups and trade updates, or off |
| Recent candles in packet | 5 | 1 to 10 |
| Show packet preview on chart | Off | Prints the live packet next to price, useful for checking your setup |
| Panel mode | Full | Full or Compact |
| Panel position, text size | Top right, Small | Where and how big the panel is |
| Show position boxes | On | Risk and reward boxes for every setup |
| Color candles by score | Off | Green or red candles when a side leads |

---

## FAQ

**Does it repaint?**
No. Setups, trade tracking and packets use closed candles only. Higher-timeframe and daily values use only bars that have already closed. Swing points appear 5 bars after the pivot and never move.

**Which markets and timeframes?**
Any symbol on TradingView. Crypto, stocks, forex, futures. Intraday timeframes (5m to 4h) get the most out of VWAP and previous-day levels. Symbols without volume data get `null` volume fields.

**Can I use it on the free TradingView plan?**
Yes. The indicator, panel and Data Window all work. Sending packets to an agent needs webhook alerts, which need a paid plan.

**How many packets will I get?**
One per closed candle per chart. A 1h chart sends 24 a day. Switch "Send JSON packet" to "Setups and trade updates" to receive only the important ones.

**Does it place trades?**
No. The indicator produces data and signals. The strategy places orders only inside TradingView's backtester; a real broker sees nothing unless you create an order-fill alert and connect it to your own bot.

**How do I add my own entry rule?**
Use the strategy and follow [docs/STRATEGY.md, section 6](docs/STRATEGY.md#6-add-your-own-module): one toggle input, one condition, one registry line. Then run `python3 -m unittest discover -s tests` and compile it in the Pine Editor.

---

## Repository

```
tradingview-indicator-for-ai-agents/
├── ai-agent-lens.pine           the indicator (Pine Script v6)
├── ai-agent-lens-strategy.pine  the strategy with alerts and signal modules
├── agent/AGENT_PROMPT.md        system prompt for your AI agent
├── docs/SPECIFICATION.md        every calculation and rule
├── docs/PACKET_SCHEMA.md        every field in the JSON packets
├── docs/STRATEGY.md             strategy rules, alerts, how to add modules and filters
├── examples/webhook_receiver.py receive packets locally (Python 3, no installs)
├── examples/sample_packet.json  example packet
├── examples/sample_signal.json  example agent signal
├── examples/sample_strategy_packet.json  example strategy packet
├── examples/sample_order.json   example order-fill message
├── tests/                       python3 -m unittest discover -s tests
└── LICENSE                      MIT
```

---

## Disclaimer

This project is for education and research. It is not financial advice. The indicator describes the chart using fixed rules; it does not predict the future. Signals from any AI agent can be wrong. Test on paper first, size small, and never risk money you can't afford to lose.

## License

MIT. Use it, fork it, build on it.
