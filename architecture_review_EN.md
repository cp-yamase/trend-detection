# Trend Detection System - Architecture Review (Latest)

> Last updated: 2026-03-17

---

## What This System Does (In One Line)

Detects the moment when a combination of a crypto entity and an event keyword (e.g., Binance + hack) spikes on X, and delivers alerts via API or notification.

---

## Core Requirements

| Item | Spec |
|---|---|
| Detection latency | Within 10 minutes (ideally 2–15 minutes) |
| Update frequency | Every 1 minute |
| Output | JSON API + Webhook notifications |
| Anomaly score basis | Growth multiplier vs. same time window over the past 7 days (not absolute count) |
| Noise filtering | Reduce repeated posts and self-promotion from the same user |
| Entity normalization | BTC / Bitcoin treated as the same entity |

---

## X API Status (as of February 2026)

X API migrated to **full Pay-per-use pricing in February 2026**. Fixed monthly plans have been discontinued.

| Action | Unit Price |
|---|---|
| Read tweets | $0.005 / tweet |
| Get user profile | $0.010 / request |
| Create tweet | $0.010 / request |

- Monthly cap: 2 million tweets (Enterprise for more)
- No double-billing if the same tweet is re-fetched within 24 hours
- Auto-charge and monthly spend limits available

**Filtered Stream (Real-time Stream)**

Filtered Stream is available on the Pay-per-use plan.

Official rate limits (per app):
- Concurrent connections: **1**
- Rule limit: **1,000 rules** (Entity × EventKeyword combinations registered in advance)
- Throughput: **250 tweets/second**
- Cost: $0.005 per received tweet

**Advantages of Filtered Stream**
- Only receives tweets matching registered rules → no charges for irrelevant content
- Received at the moment of posting → minimal detection latency (seconds)
- More cost-efficient than polling

---

## OpenClaw (Cancelled)

OpenClaw was initially considered as a data processing pipeline, but has been **dropped in favor of direct Coinpost Terminal integration**.

Reasons:
- Advanced processing such as entity extraction and normalization will be handled by Coinpost Terminal's existing automation infrastructure
- This system focuses solely on signal generation and exposes results via JSON API
- Avoids the cost and complexity of introducing a separate AI agent framework

---

## Recommended Architecture

```
[Data Ingestion]
[X API Filtered Stream]
  Pre-registered rules: all Entity × EventKeyword combinations (up to 1,000)
        ↓ Receive matching tweets in real time

[Collection & Storage]
[KAGOYA Cloud VPS (Python, always-on)]
        ↓
[SQLite] ← tweet data + baseline (past 7 days)

[Data Processing (Rule-based)]
[scorer.py]
  - 1-min / 5-min count aggregation per Entity × EventKeyword
  - Calculate growth multiplier vs. same time window over past 7 days
  - Unique user count filtering (noise reduction)
        ↓ When threshold exceeded

[Notification & External Integration]
[Notifier / JSON API]
  - Slack Webhook notification
  - JSON API → feed results to Coinpost Terminal
```

**Component Roles**

| Component | Role |
|---|---|
| X API Filtered Stream | Data ingestion (official, only option) |
| KAGOYA Cloud VPS | Always-on server, SQLite management |
| scorer.py | Rule-based data processing and scoring |
| Grok | Supplemental summary generation + xAI credit rewards |
| JSON API | Expose detection results to Coinpost Terminal |

**Where LLMs Are Used**

| Use Case | Appropriate? | Recommended Model |
|---|---|---|
| Anomaly score calculation | ❌ Rule-based is sufficient | — |
| Entity extraction / normalization | ✅ Useful for edge cases dictionaries can't handle | GPT-4o-mini / Grok |
| Event keyword classification | ✅ Useful when context understanding is needed | GPT-4o-mini / Grok |
| Initial dictionary generation | ✅ Build once, rarely needs updating | Claude / Grok |
| Post-detection context summary | ✅ Improves notification quality | Grok (strong X context awareness) |

---

## Grok API Role

**Cannot be used for data ingestion, but a reasonable choice as a supplemental layer.**

Grok API's `x_search` tool can search X in real time, but it returns **LLM-summarized natural language results** — not raw tweet data (counts, user IDs, timestamps). It cannot be used for anomaly score calculation.

| Use Case | Grok API x_search | X API Filtered Stream |
|---|---|---|
| Real-time tweet retrieval | ❌ LLM summary only, counts unreliable | ✅ Raw data |
| Count data for anomaly scoring | ❌ Statistically unreliable | ✅ Accurate |
| Post-detection context summary | ✅ Excels (strong X context) | — |

**Biggest benefit of using Grok: xAI credit rewards**

xAI credits are earned based on X API Pay-per-use spending, effectively reducing the cost of supplemental Grok API usage.

| X API Monthly Spend | xAI Credit Reward Rate |
|---|---|
| Under $200 | 0% |
| $200–$499 | 10% |
| $500–$999 | 15% |
| $1,000+ | 20% |

---

## Confirmed Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Data Ingestion | X API Filtered Stream | Official, Pay-per-use, $0.005/tweet |
| Server | KAGOYA Cloud VPS | Ubuntu 22.04, always-on |
| Data Storage | SQLite | Retains 7-day baseline |
| Data Processing | Rule-based (scorer.py) | OpenClaw not adopted |
| Supplemental LLM | Grok | Summary generation + xAI credit rewards |
| Notification & Integration | Slack Webhook / JSON API | Feeds into Coinpost Terminal |

---

## Conclusion

- **Data ingestion**: X API Filtered Stream (official, Pay-per-use) — only viable option
- **Data processing**: Rule-based (scorer.py) — self-contained, no OpenClaw
- **External integration**: Detection results provided to Coinpost Terminal via JSON API. Automation logic implemented on the Coinpost Terminal side
- **Supplemental**: Grok used for post-detection summary generation (xAI credit rewards are an added benefit)

---

## References

- [X API Pricing (Official)](https://docs.x.com/x-api/getting-started/pricing)
- [X Pay-Per-Use Announcement (2026/02)](https://www.medianama.com/2026/02/223-x-developer-api-pricing-pay-per-use-model/)
- [X API Pay-Per-Use Developer Forum](https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476)
- [xAI Live Search Documentation](https://docs.x.ai/docs/guides/live-search)
- [xAI Models & Pricing](https://docs.x.ai/developers/models)
