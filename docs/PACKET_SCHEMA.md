# Packet schema: `ai-agent-lens/v1`

One packet is sent per closed candle (or only on setups and trade updates, depending on the "Send JSON packet" input). Missing values are sent as `null`. Prices are rounded to the symbol's tick size.

Full example: [`examples/sample_packet.json`](../examples/sample_packet.json)

## Top level

| Field | Type | Description |
|---|---|---|
| `schema` | string | Always `"ai-agent-lens/v1"` |
| `event` | enum | `BAR_CLOSE`, `LONG_SETUP`, `SHORT_SETUP`, `TRADE_UPDATE` |
| `symbol` | string | Exchange prefix and ticker, e.g. `BINANCE:BTCUSDT` |
| `timeframe` | string | TradingView timeframe code: `1`, `15`, `60`, `240`, `D`, `W` |
| `time` | string | Candle close time, ISO 8601 UTC |
| `state_code` | string | One-line summary: `LENS\|TICKER\|TF\|REGIME\|L<long>\|S<short>\|SIDE:STATUS` |
| `candle` | object | The candle that just closed |
| `recent_candles` | array | The last N candles (default 5), oldest first, the last one is the current candle |
| `regime` | enum | `TREND_UP`, `TREND_DOWN`, `RANGE`, `HIGH_VOLATILITY` |
| `trend` | object | EMAs and higher-timeframe bias |
| `momentum` | object | RSI and MACD |
| `strength` | object | ADX and DI |
| `volatility` | object | ATR and its percentile |
| `volume` | object | Relative volume |
| `structure` | object | Swing structure |
| `levels` | object | Key price levels |
| `scores` | object | Long and short confluence scores and their factors |
| `trade` | object | The indicator's tracked trade |
| `last_setup` | object | Most recent setup |

## `candle`

| Field | Type | Description |
|---|---|---|
| `open`, `high`, `low`, `close` | number | Prices |
| `volume` | number or null | Volume |
| `direction` | enum | `bull`, `bear`, `flat` |
| `body_pct` | number | Body as % of range |
| `upper_wick_pct` | number | Upper wick as % of range |
| `lower_wick_pct` | number | Lower wick as % of range |
| `range_atr` | number or null | Range divided by ATR |
| `close_position_pct` | number | Where the close sits in the range: 0 = low, 100 = high |
| `gap_pct` | number or null | Open versus previous close, % |
| `closed_above_prev_high` | bool | Close > previous high |
| `closed_below_prev_low` | bool | Close < previous low |
| `pattern` | enum | See [SPECIFICATION.md](SPECIFICATION.md#patterns) |

## `recent_candles[]`

| Field | Type | Description |
|---|---|---|
| `bars_ago` | int | 0 = current candle |
| `o`, `h`, `l`, `c` | number | Prices |
| `v` | number or null | Volume |
| `dir` | enum | `bull`, `bear`, `flat` |
| `body_pct` | number | Body as % of range |
| `range_atr` | number or null | Range divided by ATR at that bar |
| `pattern` | enum | Pattern of that candle |

## `trend`

| Field | Type | Description |
|---|---|---|
| `ema_fast`, `ema_mid`, `ema_slow` | number | EMA 20, 50, 200 by default |
| `stack` | enum | `BULLISH` (fast > mid > slow), `BEARISH`, `MIXED` |
| `slow_slope` | enum | `RISING`, `FALLING`, `FLAT` |
| `htf` | string | Higher timeframe used |
| `htf_bias` | enum | `UP`, `DOWN`, `FLAT`, `N/A` |

## `momentum`, `strength`, `volatility`, `volume`

| Field | Type | Description |
|---|---|---|
| `momentum.rsi` | number | RSI 14 |
| `momentum.macd_hist` | number | MACD histogram |
| `momentum.macd_hist_rising` | bool | Histogram higher than previous bar |
| `strength.adx` | number | ADX 14 |
| `strength.di_plus`, `strength.di_minus` | number | Directional indicators |
| `volatility.atr` | number | ATR 14 |
| `volatility.atr_percentile` | number | ATR rank over the last 100 bars, 0 to 100 |
| `volume.relative` | number or null | Volume / 20-bar average |

## `structure` and `levels`

| Field | Type | Description |
|---|---|---|
| `structure.bias` | enum | `BULLISH`, `BEARISH`, `MIXED` |
| `structure.event` | enum | `BREAK_UP`, `BREAK_DOWN`, `NONE` |
| `structure.last_swing_high` | number or null | Last confirmed swing high |
| `structure.last_swing_low` | number or null | Last confirmed swing low |
| `levels.prev_day_high` | number or null | Previous day high |
| `levels.prev_day_low` | number or null | Previous day low |
| `levels.vwap` | number or null | Session VWAP |

## `scores`

| Field | Type | Description |
|---|---|---|
| `long`, `short` | int | 0 to 100 |
| `threshold` | int | Setup threshold in use |
| `long_factors`, `short_factors` | object | `trend`, `momentum`, `strength`, `volume`, `htf`, each 0 to 20 |

## `trade` and `last_setup`

| Field | Type | Description |
|---|---|---|
| `trade.side` | enum | `LONG`, `SHORT`, `NONE` (side of the most recent tracked trade) |
| `trade.status` | enum | `ACTIVE`, `TARGET_1_HIT`, `TARGET_2_HIT`, `STOPPED`, `STOPPED_AFTER_T1`, `NONE` |
| `trade.entry`, `trade.stop`, `trade.target_1`, `trade.target_2` | number or null | Levels of the tracked trade |
| `trade.bars_since_entry` | int or null | Bars since the trade opened |
| `last_setup.side` | enum | `LONG`, `SHORT`, `NONE` |
| `last_setup.bars_ago` | int or null | Bars since the last setup |

## Versioning

Breaking changes will use a new schema name (`ai-agent-lens/v2`). Agents should check `schema` before reading a packet.

---

# Strategy packet: `ai-agent-lens-strategy/v1`

Sent by [`ai-agent-lens-strategy.pine`](../ai-agent-lens-strategy.pine) through `alert()` once per closed candle, or only on trade events (input "Send JSON packet"). Example: [`examples/sample_strategy_packet.json`](../examples/sample_strategy_packet.json)

It contains every field of `ai-agent-lens/v1` above (`candle`, `recent_candles`, `regime`, `trend`, `momentum`, `strength`, `volatility`, `volume`, `structure`, `levels`, `scores`, `last_setup`), with these differences and additions.

## Top level

| Field | Type | Description |
|---|---|---|
| `schema` | string | Always `"ai-agent-lens-strategy/v1"` |
| `tag` | string | Optional. The "Bot / account tag" input, only present when it is set |
| `event` | enum | `BAR_CLOSE`, `LONG_ENTRY`, `SHORT_ENTRY` (signal on this candle, order goes out at the next open), `ENTRY_FILLED`, `PARTIAL_EXIT` (target 1), `EXIT` (position closed) |
| `state_code` | string | `LENS-S\|TICKER\|TF\|REGIME\|L<long>\|S<short>\|V<long votes>/<short votes>\|SIDE:STATUS` |
| `signals` | object | Votes of the signal modules |
| `filters` | object | Which sides the filters allow |
| `trade` | object | The strategy's real position |
| `fills` | array | Fills that happened on this candle (empty on most candles) |
| `performance` | object | Strategy Tester numbers at this candle |

## `signals`

| Field | Type | Description |
|---|---|---|
| `signals.combine` | enum | `Any`, `All`, `At least N` |
| `signals.enabled` | int | Number of enabled modules |
| `signals.votes_needed` | int | Votes a side needs |
| `signals.long_votes`, `signals.short_votes` | int | Enabled modules agreeing with each side |
| `signals.modules[]` | array | One item per registered module: `name`, `enabled` (bool), `long` (bool), `short` (bool). Disabled modules are listed too, with their raw state, so an agent can see what they would say |

## `filters`

| Field | Type | Description |
|---|---|---|
| `filters.long_ok`, `filters.short_ok` | bool | All enabled filters allow that side |
| `filters.items[]` | array | One item per filter: `name`, `enabled`, `allow_long`, `allow_short` |

## `trade` (strategy version)

| Field | Type | Description |
|---|---|---|
| `trade.side` | enum | `LONG`, `SHORT`, `FLAT` (the live position) |
| `trade.status` | enum | `NONE`, `PENDING` (signal sent, not filled yet), `ACTIVE`, `TARGET_1_HIT`, `TARGET_2_HIT`, `STOPPED`, `STOPPED_AFTER_T1`, `BREAKEVEN_AFTER_T1`, `TIME_EXIT`, `REVERSED` |
| `trade.entry` | number or null | Average fill price while open, otherwise the reference price of the last signal |
| `trade.stop` | number or null | Current stop (moves to entry after target 1 when breakeven is on) |
| `trade.target_1`, `trade.target_2` | number or null | Targets of the last signal |
| `trade.qty` | number | Open position size in units, 0 when flat |
| `trade.bars_since_entry` | int or null | Bars since the fill |

## `fills[]`

| Field | Type | Description |
|---|---|---|
| `type` | enum | `ENTRY`, `PARTIAL_EXIT`, `EXIT` |
| `side` | enum | `LONG`, `SHORT` |
| `price` | number | `ENTRY` only: average fill price |
| `reason` | enum | Exits only: `T1`, `T2`, `SL`, `BE`, `TIME`, `REVERSE` |
| `entry_price`, `exit_price` | number | Exits only |
| `qty` | number | Units filled |
| `profit` | number | Exits only: profit of that piece in account currency |

## `performance`

| Field | Type | Description |
|---|---|---|
| `performance.equity` | number | Strategy equity |
| `performance.net_profit` | number | Closed profit |
| `performance.open_profit` | number | Unrealized profit |
| `performance.closed_trades` | int | Closed trades. A partial exit counts as one |
| `performance.win_rate_pct` | number or null | Winning closed trades, % |
| `performance.max_drawdown` | number | Maximum drawdown so far |

---

# Order message: `ai-agent-lens-order/v1`

A compact message attached to every strategy order. TradingView sends it when the order **fills**, if the alert's message is exactly `{{strategy.order.alert_message}}`. Use it for execution bots. Example: [`examples/sample_order.json`](../examples/sample_order.json)

| Field | Type | Description |
|---|---|---|
| `schema` | string | Always `"ai-agent-lens-order/v1"` |
| `tag` | string | Optional, same as above |
| `action` | enum | `OPEN_LONG`, `OPEN_SHORT`, `CLOSE_LONG`, `CLOSE_SHORT` |
| `reason` | enum | `SIGNAL` for entries; `T1`, `T2`, `SL`, `BE`, `TIME` for exits |
| `order_id` | string | `Long`, `Short`, `Long T1`, `Long T2`, `Short T1`, `Short T2`, `ALL` |
| `symbol`, `timeframe` | string | As above |
| `time` | string | Close time of the candle that created the order, ISO 8601 UTC |
| `price_ref` | number | Close of that candle. The real fill price can differ |
| `qty` | number | Units this order is meant to fill |
| `stop`, `target_1`, `target_2` | number | Levels of the trade |
