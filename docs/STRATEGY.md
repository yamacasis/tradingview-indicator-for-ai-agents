# AI Agent Lens Strategy

Version 1.0 · Pine Script v6 · Packet schemas `ai-agent-lens-strategy/v1` and `ai-agent-lens-order/v1`

[`ai-agent-lens-strategy.pine`](../ai-agent-lens-strategy.pine) is the AI Agent Lens indicator rebuilt as a TradingView **strategy**. It keeps the candle breakdown, regime, scores and JSON packet, and adds:

- real orders (entry, ATR stop, two targets, breakeven, time exit), so the **Strategy Tester** backtests the rules with fees and slippage;
- a **signal module registry**: every entry idea is one small module, and you can add your own without touching the order, alert or panel code;
- a **filter registry** that can only block entries (direction, regime, volatility, higher timeframe, session, or your own);
- **two kinds of alerts**: a full JSON packet for AI agents, and a compact order message for execution bots.

The indicator ([`ai-agent-lens.pine`](../ai-agent-lens.pine)) is unchanged and still works on its own.

---

## 1. How it fits together

```
 every closed candle
 ┌─────────────────────────────────────────────────────────────────────────────┐
 │ core calculations (EMAs, RSI, MACD, ADX, ATR, volume, structure, scores)    │
 └───────────────┬─────────────────────────────────────────────────────────────┘
                 ▼
 ┌───────────────────────────┐   votes   ┌──────────────┐  edge   ┌───────────┐
 │ SIGNAL MODULES (registry) │ ────────► │ combiner     │ ──────► │ filters   │
 │ confluence_score          │           │ Any / All /  │ first   │ (registry)│
 │ structure_break           │           │ At least N   │ bar the │ can only  │
 │ ema_cross, rsi_pullback   │           └──────────────┘ vote    │ block     │
 │ + your modules            │                            passes  └─────┬─────┘
 └───────────────────────────┘                                          ▼
                                       ┌───────────────────────────────────────┐
                                       │ orders: entry, T1 (partial), T2, stop │
                                       │ breakeven after T1, optional time exit│
                                       └──────────────┬────────────────────────┘
                                                      ▼
                        ┌──────────────────────────────┴──────────────────────────┐
                        │ alert() JSON packet          order alert_message        │
                        │ ai-agent-lens-strategy/v1    ai-agent-lens-order/v1     │
                        │ → AI agent                   → execution bot            │
                        └─────────────────────────────────────────────────────────┘
```

### Modules report states, the combiner makes events

A module answers one question on every bar: "do I agree with a long right now? with a short?" Those are **states** that can stay true for many bars. The combiner counts the enabled modules that agree with each side:

| Combine mode | A side passes when |
|---|---|
| `Any` (default) | at least 1 enabled module agrees |
| `All` | every enabled module agrees |
| `At least N` | N enabled modules agree. N is capped at the number of enabled modules |

An entry signal fires only on the closed candle where a side **first** passes (it did not pass on the previous candle), and only if every enabled filter allows that side. If both sides fire on the same candle, neither is taken.

With only `confluence_score` enabled (the default), this reproduces the indicator's setups exactly: the score crossing the threshold, blocked against the regime and in high volatility.

---

## 2. Built-in signal modules

| Module | Long state | Short state | Default |
|---|---|---|---|
| `confluence_score` | long score >= threshold (70) | short score >= threshold | on |
| `structure_break` | a break above the last swing high within the last N bars (3) and close > slow EMA | a break below the last swing low within N bars and close < slow EMA | off |
| `ema_cross` | fast EMA > mid EMA | fast EMA < mid EMA | off |
| `rsi_pullback` | close > slow EMA, fast > mid EMA, RSI > 50 and RSI was below 40 in the previous 5 bars | mirror: RSI < 50 and was above 60 | off |

Examples of combinations:

- `confluence_score` + `structure_break` with `All`: a score breakout that also breaks structure.
- `ema_cross` + `rsi_pullback` + `structure_break` with `At least N` = 2: any two of the three.

## 3. Built-in filters

| Filter | Blocks longs when | Blocks shorts when | Default |
|---|---|---|---|
| `direction` | "Trade direction" is Short only | "Trade direction" is Long only | always on |
| `regime` | regime is `TREND_DOWN` | regime is `TREND_UP` | on |
| `high_volatility` | regime is `HIGH_VOLATILITY` | regime is `HIGH_VOLATILITY` | on |
| `htf_agreement` | higher-timeframe bias is not `UP` | higher-timeframe bias is not `DOWN` | off |
| `session` | the candle is outside the session | the candle is outside the session | off |

---

## 4. Orders and exits

On a long signal (shorts mirror it) at the close of candle N:

| Order | Id | Level | Size |
|---|---|---|---|
| Entry | `Long` | market, fills at the open of candle N+1 | from "Position sizing" |
| Target 1 + stop | `Long T1` | limit at close + 1.5R, stop at close - 1.5 ATR | "Close at target 1" (50%) |
| Target 2 + stop | `Long T2` | limit at close + 3R, same stop | the rest |

- **R** = 1.5 x ATR, the distance from the signal close to the stop.
- **Breakeven:** after target 1 fills, the stop of `Long T2` moves to the average entry price (input "Move stop to entry after target 1").
- **Time exit:** "Time exit after N bars" closes the whole position at the next open after N bars (0 = off).
- **Same direction:** a long signal while long is ignored. **Opposite direction:** a short signal while long reverses the position.

| Position sizing | Units |
|---|---|
| Risk % of equity (default 1%) | equity x risk % / (stop distance x point value). A stop-out loses about that % before fees and slippage |
| % of equity | equity x % / (price x point value) |
| Fixed quantity | the number you enter |

Defaults in the strategy properties: initial capital 10,000, commission 0.05% per order, slippage 1 tick, no pyramiding. Change them in **Settings → Properties** to match your broker.

---

## 5. Alerts

The strategy needs only one alert per chart. Pick the kind that matches what is on the other end.

### For an AI agent: the full JSON packet

1. Add the strategy to the chart, open the alert dialog (`Alt + A`).
2. **Condition:** `AI Agent Lens Strategy` → **`alert() function calls only`**.
3. **Webhook URL:** your agent's URL (see the README, Step 3).
4. Leave the message as it is. Create.

"Send JSON packet" decides how often:

| Setting | Packets |
|---|---|
| Every bar close | one per closed candle, `event` tells what happened |
| Trade events only | only `LONG_ENTRY`, `SHORT_ENTRY`, `ENTRY_FILLED`, `PARTIAL_EXIT`, `EXIT` |
| Off | none |

### For an execution bot: order messages

1. Same dialog, **Condition:** `AI Agent Lens Strategy` → **`Order fills only`**.
2. **Message:** delete everything and type exactly `{{strategy.order.alert_message}}`.
3. Webhook URL: your bot. Create.

Each fill sends one `ai-agent-lens-order/v1` message (`OPEN_LONG`, `CLOSE_LONG` with reason `T1`, `T2`, `SL`, `BE` or `TIME`, and so on). Set "Bot / account tag" to route several strategies through one webhook.

Both kinds are received by [`examples/webhook_receiver.py`](../examples/webhook_receiver.py): packets go to `packets/latest.json`, `packets/latest/` and `packets/history.jsonl`, order messages to `packets/orders.jsonl`. Field lists: [PACKET_SCHEMA.md](PACKET_SCHEMA.md#strategy-packet-ai-agent-lens-strategyv1).

> Strategy alerts run on the settings at the moment you create the alert. After you change an input, delete the alert and create it again.

---

## 6. Add your own module

Every module is three edits in [`ai-agent-lens-strategy.pine`](../ai-agent-lens-strategy.pine), each at a marked spot. Example: a **VWAP reclaim** module.

**1. A toggle (and its settings)** under `// ADD NEW MODULE INPUTS HERE`:

```pine
bool   useVwap        = input.bool(false, "5. VWAP reclaim", group = G_MOD, display = display.none)
```

**2. The condition** under `// ADD NEW MODULE CONDITIONS HERE`. Return a state (true while the idea holds), not a one-bar event; the combiner turns it into one entry:

```pine
bool vwapLong  = close > vwapV and low <= vwapV and close > emaM
bool vwapShort = close < vwapV and high >= vwapV and close < emaM
```

**3. Register it** under `// ADD NEW MODULES HERE`:

```pine
modules.push(SignalModule.new("vwap_reclaim", useVwap, vwapLong, vwapShort))
```

That is all. The new module now votes, shows in the label tooltip and in `signals.modules` of every packet, and is counted on the panel. Finally add a row for it to the table in section 2 of this file (the tests check that every module is documented).

Rules for modules:

- Use only closed-bar values: `close`, `high[1]`, `ta.*` on the chart series, or `request.security(..., expr[1], lookahead = barmerge.lookahead_on)`. Never `lookahead_on` without `[1]`.
- Call `ta.*` functions at global scope (not inside `if`), so they update on every bar.
- Name modules in `snake_case`. Names are part of the packet, so agents can rely on them.

## 7. Add your own filter

Two edits. A toggle under `// ADD NEW FILTER INPUTS HERE`, then one line under `// ADD NEW FILTERS HERE`. Example: skip entries when volume is low.

```pine
bool   fltVolume      = input.bool(false, "Require relative volume >= 1", group = G_FLT, display = display.none)
```

```pine
filters.push(FilterModule.new("min_volume", fltVolume, relVol >= 1, relVol >= 1))
```

Add the filter to the table in section 3.

---

## 8. Tests

```bash
python3 -m unittest discover -s tests -v
```

Standard library only. The tests cover:

| File | What it checks |
|---|---|
| `tests/test_receiver.py` | Validation of all three schemas, where each kind of message is stored, token check, bad JSON, oversized bodies, a real HTTP round trip |
| `tests/test_pine_strategy.py` | Both Pine files: brackets and quotes balanced, 4-space indentation, no lookahead leak, every packet key documented. Strategy only: every module and filter has an `input.bool` toggle, unique `snake_case` names, documented here, registered at global scope; order ids and exit comments are consistent; packet and order keys match the examples; schemas and actions match the receiver |
| `tests/test_examples.py` | Example files are valid JSON with the documented enums and consistent prices |

These are static checks. TradingView's Pine Editor is the only Pine compiler, so after editing the script, paste it into the Pine Editor, save, and open the Strategy Tester before you trust it. The GitHub workflow in `.github/workflows/tests.yml` runs the tests on every push and pull request.

---

## 9. Limitations

- Orders fill at the next candle's open. Stops and targets are from the signal candle's close, so the real R can be slightly different.
- When one candle touches both a stop and a target, TradingView's broker emulator decides the order using its intrabar assumptions. Enable "Bar magnifier" (Premium plans) for a more realistic fill order.
- `performance.closed_trades` counts a partial exit as a trade, the same way the Strategy Tester does.
- Backtest results depend on fees, slippage and the symbol's history. They are not a promise of future results.
- The script never connects to a broker. An order message only reaches a bot if you create that alert.
