# Security architecture (v0.21)

Version 0.21 extends the control plane with zero-trust principles, expanded redaction, series integrity, and anomaly scoring. It is still a research design, not a certified security product and not legal advice.

## Trust boundaries

```mermaid
flowchart LR
    F["Synthetic fixture or injected public ticker"] --> AT["Source attestation + series integrity"]
    AT --> S["Strategy research rules plus multi-factor regime overlay"]
    S --> R["Risk gate: class caps, kill switch, drawdown, anomaly score"]
    R --> P["Paper fill only"]
    P --> A["Hash-chained audit log"]
    K["Trade or withdrawal keys"] -.-> X["Refused. Never loaded"]
    RBAC["Researcher, auditor, operator (zero-trust)"] --> R
```

The system has no order router. `assert_paper_only` refuses any mode other than `PAPER`. `refuse_trade_secret` rejects names that look like trade, withdraw, transfer, or order credentials. Roles cannot enable live trading. Zero-trust: every action re-checks role and mode.

## Roles

| Role | Allowed | Denied |
|---|---|---|
| Researcher | scan, backtest, read audit | place order, withdraw, enable live |
| Auditor | read audit, verify chain, scan | place order, withdraw, enable live |
| Operator | scan, kill switch, read audit | place order, withdraw, enable live |

There is no trader role. Promoting a signal to a broker is a separate system.

## Data classes

| Field | Class | Handling |
|---|---|---|
| Symbol, OHLCV | Public market | Synthetic in this repo |
| Funding rate | Public market | Research feature only |
| Source label | Integrity | Must be SYNTHETIC or PUBLIC_READ |
| Read-only market key | Secret, optional | Name must say read, market, or public. Never logged |
| Trade or withdrawal key | Secret | Refused |
| Wallet address | Sensitive identifier | Redacted, banned from fixtures |
| Email, NRIC, phone | Personal | Tripwire in `scripts/check_pdpa.py` |
| JWT, base64, mnemonic, private key | Secret | Expanded redaction |

PDPA note: the tripwire is not a data-loss-prevention product. A production deployment still needs access control, vendor review, and a human DPO decision. Wallet addresses can be personal data depending on context; this repo does not store them.

## Feed integrity

`feed_status` flags a non-positive price, a print older than 15 minutes, or a jump above 25% versus the prior print. Tests inject the payload. The default path does not open a socket. Added series_integrity_digest for candle series tamper detection.

`attest_source` hashes the label plus body so a fixture swap changes the digest. The loader still rejects anything that is not labelled SYNTHETIC.

## Threats and controls

| Threat | Control |
|---|---|
| Secret committed | gitleaks CI, expanded redaction, no key loader |
| Trade key pasted into config | `refuse_trade_secret` |
| Strategy injection via fixture | SYNTHETIC label required, source attestation, series integrity |
| Stale or jumped public ticker | feed status watch or high + anomaly score |
| Oversized risk on thin assets | Per-class cap, confidence floor, class cost |
| Runaway loss | Drawdown halt and kill switch |
| Audit tamper | SHA-256 chain over sequence, action, detail |
| Live-order mistake | No live client; mode guard; RBAC deny; zero-trust checks |
| Personal data in agent context | AGENTS.md ban plus CI tripwire |
| Privilege creep | No role can place an order |
| Supply-chain or input anomaly | Expanded patterns + integrity digests |

## Incident handling

1. Engage the kill switch. New paper size goes to zero.
2. Freeze the audit chain and record the source attestation and series integrity digests.
3. If a secret was pasted, rotate it outside this repo and purge it from history.
4. Do not open a public issue that contains a secret or a wallet address.
5. A human reviews before the kill switch is cleared.

## Operating rules

- Market-data credentials, if ever added, stay read-only and separate from any future trade credential.
- Logs pass through `redact` before they are stored.
- Default deployment is research. Promoting a signal to a broker is a separate, human-approved system.
- Zero-trust: re-validate mode, role, and source integrity on every decision.
