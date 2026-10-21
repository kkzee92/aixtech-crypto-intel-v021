"""Asset-class strategy research rules (v0.21).

Transparent heuristics for paper research. Not forecasts and not a recommendation
to trade. Each class has an entry, an invalidation, and a multi-factor regime overlay.
"""

from __future__ import annotations

from statistics import fmean

from crypto_intel.models import AssetClass, Candle, Side, Signal
from crypto_intel.regime import Regime, classify

PLAYBOOK: dict[AssetClass, dict[str, str]] = {
    AssetClass.MAJOR: {
        "hypothesis": "Liquid majors trend, confirmed by EMA + Bollinger/MACD proxy, except when RSI is stretched or the book is in stress.",
        "entry": "Fast EMA above slow EMA with RSI 45-70 in trend or range, plus Bollinger proximity or MACD proxy. Washed-out RSI only in range.",
        "invalidation": "Stress regime, or RSI above 70 on a trend entry, or missing multi-factor confirmation.",
        "horizon": "8 bars mean-reversion, 20 bars trend",
    },
    AssetClass.LARGE_CAP_ALT: {
        "hypothesis": "Breakouts without volume or Bollinger confirmation are noise, and stress-regime breakouts are mostly gap risk.",
        "entry": "Close above the prior five-bar high, volume at least 1.2x, Bollinger proximity, outside stress.",
        "invalidation": "Stress regime or volume/Bollinger confirmation missing.",
        "horizon": "12 bars",
    },
    AssetClass.STABLECOIN: {
        "hypothesis": "The useful signal is a peg break, not direction.",
        "entry": "Deviation of 50 bps or more raises an alert. No order.",
        "invalidation": "Not applicable. Size stays zero.",
        "horizon": "1 bar monitor",
    },
    AssetClass.DEFI: {
        "hypothesis": "Trend only in a calm realised-vol regime with MACD proxy confirmation.",
        "entry": "Close above 8-bar EMA, mean absolute return at or below 6%, MACD proxy positive, not in stress.",
        "invalidation": "Stress regime, realised vol above 6%, or missing MACD proxy.",
        "horizon": "10 bars",
    },
    AssetClass.MEME: {
        "hypothesis": "Most bursts are untradeable. A qualified burst still gets a hard time stop and tighter chase filter.",
        "entry": "15% four-bar burst, rising volume, volume floor, and not already extended 35% over 8 bars.",
        "invalidation": "Thin liquidity proxy or chase extension.",
        "horizon": "3 bars",
    },
    AssetClass.L2: {
        "hypothesis": "L2 tokens are relative-strength bets versus a benchmark with momentum filter.",
        "entry": "Six-bar excess return above 3% versus benchmark, benchmark not in stress, positive momentum.",
        "invalidation": "Missing benchmark or benchmark stress.",
        "horizon": "12 bars",
    },
    AssetClass.RWA: {
        "hypothesis": "Tokenised real-world assets should be slow. Gaps above 6% are a halt.",
        "entry": "Close above 8-bar EMA and above the close five bars ago, gap inside 6%.",
        "invalidation": "Open gap above 6% or stress regime.",
        "horizon": "24 bars",
    },
    AssetClass.PERPETUAL: {
        "hypothesis": "Negative funding with contained drift is a carry observation, not a forecast.",
        "entry": "Funding at or below -5 bps and absolute six-bar drift under 4%.",
        "invalidation": "Funding at or above 10 bps, or drift no longer contained.",
        "horizon": "8 bars",
    },
}


def _returns(closes: list[float]) -> list[float]:
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]


def _ema(values: list[float], span: int) -> float:
    alpha = 2.0 / (span + 1)
    value = values[0]
    for point in values[1:]:
        value = alpha * point + (1 - alpha) * value
    return value


def _rsi(closes: list[float], period: int = 14) -> float:
    changes = _returns(closes[-(period + 1) :])
    gains = [max(change, 0.0) for change in changes]
    losses = [abs(min(change, 0.0)) for change in changes]
    average_loss = fmean(losses) if losses else 0.0
    if average_loss == 0:
        return 100.0
    rs = fmean(gains) / average_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _bollinger_proximity(closes: list[float], period: int = 20) -> float:
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mean = fmean(window)
    std = (sum((x - mean) ** 2 for x in window) / period) ** 0.5
    if std == 0:
        return 0.0
    return (closes[-1] - mean) / std


def _macd_proxy(closes: list[float]) -> float:
    if len(closes) < 26:
        return 0.0
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    return ema12 - ema26


def _atr_pct(candles: list[Candle]) -> float:
    ranges = [(c.high - c.low) / c.close for c in candles[-14:] if c.close]
    return fmean(ranges) if ranges else 0.0


def _base(candles: list[Candle], side: Side, confidence: float, reason: str, size: float, bars: int) -> Signal:
    last = candles[-1]
    regime = classify(candles)
    return Signal(
        symbol=last.symbol,
        asset_class=last.asset_class,
        side=side,
        confidence=round(max(0.0, min(confidence, 1.0)), 4),
        reason=f"{reason}; regime={regime.value}",
        stop_distance_pct=round(max(_atr_pct(candles) * 1.5, 0.01), 4),
        size_fraction=size,
        horizon_bars=bars,
    )


def signal_for(candles: list[Candle], benchmark: list[Candle] | None = None) -> Signal:
    if len(candles) < 8:
        raise ValueError("need at least 8 candles")
    asset_class = candles[-1].asset_class
    closes = [c.close for c in candles]
    regime = classify(candles)
    if asset_class is AssetClass.MAJOR:
        return _major(candles, closes, regime)
    if asset_class is AssetClass.LARGE_CAP_ALT:
        return _breakout(candles, closes, size=0.04, bars=12, regime=regime)
    if asset_class is AssetClass.STABLECOIN:
        return _stable(candles)
    if asset_class is AssetClass.DEFI:
        return _defi(candles, closes, regime)
    if asset_class is AssetClass.MEME:
        return _meme(candles, closes)
    if asset_class is AssetClass.L2:
        return _l2(candles, closes, benchmark)
    if asset_class is AssetClass.RWA:
        return _rwa(candles, closes, regime)
    return _perpetual(candles, closes)


def _major(candles: list[Candle], closes: list[float], regime: Regime) -> Signal:
    fast, slow = _ema(closes, 5), _ema(closes, 13)
    rsi = _rsi(closes)
    bb = _bollinger_proximity(closes)
    macd = _macd_proxy(closes)
    if regime is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.45, "major stress: stand aside", 0.0, 1)
    multi_factor = bb > -0.5 or macd > 0
    if fast > slow and 45 <= rsi <= 70 and multi_factor:
        return _base(candles, Side.LONG, 0.76, "major trend: fast EMA above slow, RSI not stretched, multi-factor confirm", 0.06, 20)
    if regime is Regime.RANGE and rsi < 30 and closes[-1] > closes[-3]:
        return _base(candles, Side.LONG, 0.62, "major mean-reversion: washed-out RSI in range", 0.03, 8)
    return _base(candles, Side.FLAT, 0.4, "major: no trend or reversion edge", 0.0, 1)


def _breakout(candles: list[Candle], closes: list[float], size: float, bars: int, regime: Regime) -> Signal:
    if regime is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.4, "breakout suppressed in stress", 0.0, 1)
    window = closes[-6:-1]
    volume_now = candles[-1].volume
    volume_base = fmean(c.volume for c in candles[-6:-1])
    bb = _bollinger_proximity(closes)
    if closes[-1] > max(window) and volume_now > volume_base * 1.2 and bb > 0:
        return _base(candles, Side.LONG, 0.73, "breakout with volume and Bollinger confirmation", size, bars)
    return _base(candles, Side.FLAT, 0.35, "no confirmed breakout", 0.0, 1)


def _stable(candles: list[Candle]) -> Signal:
    deviation = abs(candles[-1].close - 1.0)
    if deviation >= 0.005:
        return _base(candles, Side.ALERT, 0.92, f"stablecoin depeg monitor: deviation {deviation:.4f}", 0.0, 1)
    if deviation >= 0.002:
        return _base(candles, Side.ALERT, 0.7, f"stablecoin watch band: deviation {deviation:.4f}", 0.0, 1)
    return _base(candles, Side.FLAT, 0.8, "stablecoin inside peg band", 0.0, 1)


def _defi(candles: list[Candle], closes: list[float], regime: Regime) -> Signal:
    realised = fmean(abs(v) for v in _returns(closes[-8:]))
    macd = _macd_proxy(closes)
    if regime is Regime.STRESS or realised > 0.06:
        return _base(candles, Side.FLAT, 0.48, "defi volatility regime: stand aside", 0.0, 1)
    if closes[-1] > _ema(closes, 8) and macd > 0:
        return _base(candles, Side.LONG, 0.71, "defi trend in calm regime with MACD proxy", 0.02, 10)
    return _base(candles, Side.FLAT, 0.4, "defi: no calm trend", 0.0, 1)


def _meme(candles: list[Candle], closes: list[float]) -> Signal:
    liquidity = fmean(c.volume for c in candles[-5:])
    burst = closes[-1] / closes[-4] - 1.0
    extension = closes[-1] / closes[-8] - 1.0
    if liquidity < 1000:
        return _base(candles, Side.FLAT, 0.2, "meme liquidity proxy too thin", 0.0, 1)
    if extension > 0.35:
        return _base(candles, Side.FLAT, 0.35, "meme chase filter: 8-bar extension too large", 0.0, 1)
    if burst > 0.15 and candles[-1].volume > candles[-2].volume:
        return _base(candles, Side.LONG, 0.78, "meme momentum burst; hard time stop applies", 0.005, 3)
    return _base(candles, Side.FLAT, 0.3, "meme: no qualified burst", 0.0, 1)


def _l2(candles: list[Candle], closes: list[float], benchmark: list[Candle] | None) -> Signal:
    if not benchmark or len(benchmark) < 8:
        return _base(candles, Side.FLAT, 0.3, "l2 requires a benchmark series", 0.0, 1)
    if classify(benchmark) is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.42, "l2 benchmark in stress", 0.0, 1)
    own = closes[-1] / closes[-6] - 1.0
    bench_closes = [c.close for c in benchmark]
    bench = bench_closes[-1] / bench_closes[-6] - 1.0
    if own - bench > 0.03 and own > 0:
        return _base(candles, Side.LONG, 0.7, "l2 relative strength versus benchmark with momentum", 0.03, 12)
    return _base(candles, Side.FLAT, 0.4, "l2 not leading benchmark", 0.0, 1)


def _rwa(candles: list[Candle], closes: list[float], regime: Regime) -> Signal:
    gap = candles[-1].open / candles[-2].close - 1.0
    if abs(gap) > 0.06 or regime is Regime.STRESS:
        return _base(candles, Side.FLAT, 0.5, "rwa gap or stress halt", 0.0, 1)
    if closes[-1] > _ema(closes, 8) and closes[-1] > closes[-5]:
        return _base(candles, Side.LONG, 0.67, "rwa slow trend", 0.02, 24)
    return _base(candles, Side.FLAT, 0.4, "rwa: no slow trend", 0.0, 1)


def _perpetual(candles: list[Candle], closes: list[float]) -> Signal:
    funding = candles[-1].funding_rate
    drift = closes[-1] / closes[-6] - 1.0
    if funding >= 0.001:
        return _base(candles, Side.ALERT, 0.7, "perp funding crowded: monitor, no carry", 0.0, 1)
    if funding <= -0.0005 and abs(drift) < 0.04:
        return _base(candles, Side.LONG, 0.75, "perp funding carry: negative funding, basis contained", 0.02, 8)
    if funding <= -0.0005:
        return _base(candles, Side.FLAT, 0.5, "perp funding attractive but drift not contained", 0.0, 1)
    return _base(candles, Side.FLAT, 0.4, "perp: no carry edge", 0.0, 1)
