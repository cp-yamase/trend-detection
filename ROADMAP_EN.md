# Trend Detection System - Development Roadmap

## Phases

### ✅ Phase 1: Foundation & Stream Connection (Complete)

**Goal**: Set up project skeleton and verify X API Filtered Stream connectivity

- [x] Project structure design (`requirements.txt`, `database.py`, `x_stream.py`)
- [x] SQLite table design (`raw_tweets`, `tweet_counts`)
- [x] Filtered Stream connection, reception, and DB storage
- [x] Safe operation verification with test keywords (`main.py`)

---

### ✅ Phase 2: Production Keywords & Aggregation (Complete)

**Goal**: Receive tweets with real keywords and generate 1-min/5-min aggregation records

- [x] PoC rule definitions (3 rules, noise exclusion via negative search) (`rules_config.py`)
- [x] Aggregation logic implementation (`aggregate_counts` added to `database.py`)
- [x] Added `max_tweets` limit argument to `connect_stream` (`x_stream.py`)
- [x] PoC execution script with safety guard (`main_poc.py`)
  - **Safety guard**: Auto-disconnect after 5 minutes or 50 tweets received

---

### ✅ Phase 3: Anomaly Detection (Scoring) Logic (Complete)

**Goal**: Calculate growth multiplier by comparing against baseline data

- [x] Baseline retrieval function (same time window, past 7-day average) (`scorer.py`)
- [x] Anomaly score calculation (growth_rate × diversity_ratio) (`scorer.py`)
- [x] Scoring results saved to DB (`anomaly_scores` table added to `database.py`)
- [x] Real-time score display every 60 seconds (integrated into `main_poc.py`)

---

### ✅ Phase 2.5: Baseline Seeding (Complete)

**Goal**: Bulk-insert 7 days of historical count data via Recent Search Counts API for immediate baseline comparison

- [x] Bulk count retrieval via `GET /2/tweets/counts/recent` (`seed_baseline.py`)
- [x] Aggregation from per-minute to 5-minute windows and DB insertion
- [x] Real data takes priority (existing records are not overwritten)

---

### ✅ Phase 4: Notification Module (Complete)

**Goal**: Send real-time alerts when anomaly scores exceed threshold

- [x] Terminal notification (fallback) (`notifier.py`)
- [x] Slack Webhook notification (`notifier.py`, `SLACK_WEBHOOK_URL` set in `.env`)
- [x] Cooldown control (suppress repeated notifications for same rule for 10 minutes)
- [x] Auto-notification after scoring integrated into `main_poc.py`
- [ ] JSON API endpoint (for future external integration — not yet implemented)

---

### ✅ Phase 5: Production Server Deployment (Complete)

**Goal**: Build a production environment running 24/7

- [x] Production entry point created (`main_prod.py`)
  - No safety guard — runs indefinitely
  - Exponential backoff auto-reconnect on stream disconnection (5s up to 300s max)
  - Log file output (`logs/trend_detection.log`)
- [x] VPS provisioned (KAGOYA Cloud VPS, Ubuntu 22.04)
- [x] SSH connection verified
- [x] Python environment set up (`python3-venv`)
- [x] Project files transferred (`rsync`)
- [x] `.env` file placed on server
- [x] Baseline data migrated (`tweets.db`)
- [x] systemd service configured for always-on operation

---

### 🔄 Phase 6: Rule Expansion & Scale-Up (In Progress)

**Goal**: Expand from 3 PoC rules to production scale (hundreds of rules)

- [x] Entity dictionary design (`entities.py`) — BTC / Bitcoin / ビットコイン etc.
- [x] Event keyword dictionary design (`event_keywords.py`) — hack / exploit / breach etc.
- [x] Auto-generation of Entity × EventKeyword rule combinations (`rules_config.py`) — currently 930 rules
- [x] Auto-update entity dictionary from CoinGecko API (`update_entities.py`, `entities_auto.json`)
  - Fetches top 100 coins and top 50 exchanges daily; automatically adds new entities
  - Restarts the service automatically when new entities are detected
- [ ] Set up cron job on VPS (run `update_entities.py` daily at 4:00 AM)
- [ ] Rule priority design within the 1,000-rule limit of Filtered Stream
- [ ] Re-run flow for `seed_baseline.py` when new rules are added
- [ ] Scoring threshold tuning (fix zero-window bias)
  - Current issue: time windows with 0 tweets are excluded from baseline, inflating the average

---

### ~~Phase 7: OpenClaw Integration~~ (Cancelled)

**Reason for cancellation**: Architecture changed to connect directly to Coinpost Terminal. Entity extraction, normalization, and other data processing will be handled by Coinpost Terminal's existing automation infrastructure. This system focuses solely on signal generation; an AI agent framework is not needed.

---

### Phase 7: Grok Integration (Post-Detection Summarization) (Not Started)

**Goal**: Improve notification quality so operators can assess the situation immediately

- [ ] Grok API (`x_search`) integration module
- [ ] Auto-generate X context summary via Grok when anomaly is detected
- [ ] Attach summary text to Slack notifications
- [ ] Confirm xAI credit rewards (applies when X API monthly spend exceeds $200)

---

### Phase 8: JSON API + Coinpost Terminal Integration (Not Started)

**Goal**: Provide an API for Coinpost Terminal to query detection results

- [ ] JSON API endpoint implementation via FastAPI
  - `GET /scores` — latest anomaly scores
  - `GET /scores/{rule_tag}` — score history by rule
- [ ] Authentication (API key method)
- [ ] Deploy API server to VPS (add systemd service)
- [ ] Integration design and implementation with Coinpost Terminal

---

## Confirmed Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Data Ingestion | X API Filtered Stream | Official, Pay-per-use, $0.005/tweet |
| Server | KAGOYA Cloud VPS (Ubuntu 22.04) | Always-on |
| Data Storage | SQLite | Retains 7-day baseline |
| Data Processing | Rule-based (scorer.py) | OpenClaw not adopted |
| Supplemental LLM | Grok | Summary generation + xAI credit rewards |
| Notification & Integration | Slack Webhook / JSON API / Coinpost Terminal | — |
