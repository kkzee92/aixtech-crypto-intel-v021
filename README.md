# AIxTech crypto intel v0.21: enhanced paper-only trading information system

Research harness for automated cryptocurrency **information** and paper strategy
evaluation. It does not place live orders, does not store exchange secrets, and
is not financial advice.

Reference style: [zeekiankok92/aixtech-agent-harness-demo](https://github.com/zeekiankok92/aixtech-agent-harness-demo)
and [zeekiankok92/aixtech-crypto-intel](https://github.com/zeekiankok92/aixtech-crypto-intel).
This repository is published from the connected account `kkzee92` because that connector cannot
push to `zeekiankok92`.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![version](https://img.shields.io/badge/version-0.21.0-blue)
![mode](https://img.shields.io/badge/execution-paper%20only-orange)
![Licence](https://img.shields.io/badge/licence-MIT-green)

## v0.21 Enhancements

- Multi-factor strategies: added Bollinger Band proximity and MACD-histogram proxy confirmation for Major, Large-cap alt, and DeFi.
- Adaptive regime filters with volume-weighted momentum and tighter chase filters for Meme and RWA.
- Strengthened cyber/data security: expanded redaction (JWTs, base64 secrets, mnemonics, private keys, session tokens), series integrity digest, zero-trust role checks, and anomaly scoring on feeds.
- Still strictly paper-only. No live execution path. Research, not live trading.

## What it does

- Classifies markets into eight asset classes and applies a different research rule to each.
- Labels each series trend, range, or stress, and stands aside in stress.
- Scores a signal, then a risk gate that can shrink or refuse it.
- Applies a declared round-trip cost by asset class in the paper backtest.
- Writes a hash-chained audit log, attests fixture sources, and redacts secret-like strings.
- Backtests on **synthetic** candles only. Network access is injectable and unused by default.

| Asset class | Research rule | Risk cap | Cost |
|---|---|---|---|
| Major (BTC, ETH) | EMA trend + Bollinger/MACD proxy outside stress; range-only RSI reversion | 8% | 8 bps |
| Large-cap alt | Volume-confirmed breakout with Bollinger confirmation, suppressed in stress | 4% | 14 bps |
| Stablecoin | 20 bp watch, 50 bp depeg alert. No order | 0% | n/a |
| DeFi | Calm-regime trend with MACD proxy and vol filter | 2% | 22 bps |
| Meme | Qualified burst with tighter chase + volume floor, 3-bar horizon | 0.5% | 45 bps |
| L2 | Relative strength versus non-stress benchmark + momentum filter | 3% | 16 bps |
| RWA | Slow trend; halt on gap >6% or stress; adaptive horizon | 2% | 12 bps |
| Perpetual | Negative-funding carry if drift contained; crowded funding alert | 2% | 10 bps |

Full notes: [docs/asset-class-strategies.md](docs/asset-class-strategies.md).
Security design: [docs/security-architecture.md](docs/security-architecture.md).

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python scripts/make_fixtures.py
PYTHONPATH=src python -m crypto_intel scan fixtures/candles_synthetic.json
PYTHONPATH=src python -m crypto_intel brief fixtures/candles_synthetic.json
PYTHONPATH=src python -m crypto_intel posture fixtures/candles_synthetic.json
PYTHONPATH=src python -m crypto_intel demo fixtures/candles_synthetic.json
```

The fixture is labelled `SYNTHETIC` and is not a market history.

## Controls

1. Paper-only execution. `HALTED` and any live mode raise `PermissionError`.
2. Trade and withdrawal credential names are refused. No role can place an order.
3. Class size caps, confidence floors, kill switch, drawdown halt, RWA gap halt, stress overlay.
4. Hash-chained audit log, source attestation, feed jump and staleness checks, series integrity digest.
5. PDPA-style tripwire over fixtures and docs.
6. Ruff lint (including bandit-style `S` rules), format, pytest coverage floor, gitleaks in CI.

## Honesty

- No live exchange connector is included. Do not add trade keys to this tree.
- Strategy scores describe the synthetic fixture, not future returns.
- This is not legal, compliance, or investment advice.
