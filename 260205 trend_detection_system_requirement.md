# **X (Twitter) Trend Detection System \- Requirements Specification**

## **1\. Background & Objectives**

We aim to detect topics and events emerging on X in real-time within the cryptocurrency market (and related financial markets) to support investment decisions and information dissemination. While in-house development is under consideration, we are first exploring the feasibility of utilizing external services.

---

## **2\. Objectives (Requirements)**

### **2.1 Core Functions**

* **Real-time Anomaly Detection**: Capture the moment cryptocurrency-related topics surge  
* **Low Latency**: Minimize the time from topic emergence to detection

### **2.2 Specific Detection Examples**

| Category | Detection Target Example |
| ----- | ----- |
| Exchange Issues | Sharp increase in posts mentioning "Bitcoin" \+ "withdrawal suspended" within a short timeframe |
| Listing-Related | Surge in mentions of "Binance" \+ "listing/delisting" |
| Security | Increase in posts about "Uniswap" \+ "hack/exploit" |

---

## **3\. Technical Requirements**

### **3.1 Required Feature Extraction Functions**

**(1) Entity Dictionary Matching**

Identify what each post is referring to across the following categories:

* Ticker symbols (BTC, ETH, SOL, etc.)  
* Exchange names (Binance, Coinbase, etc.)  
* Project names  
* Regulatory authorities and notable figures

**(2) Event Keyword Dictionary Matching**

Determine what type of event may have occurred:

* listing / delist  
* hack / exploit / breach  
* halt / suspend / withdraw  
* SEC / lawsuit / regulatory  
* airdrop / unlock / vesting

→ Structure topics as combinations of "Entity × Event Keyword" → Additionally extract frequently co-occurring related words within the topic (e.g., "bug," "maintenance" in a "Binance \+ withdrawal suspended" topic)

**(3) Image Normalization (if possible)**

* Detect the spread of identical images (screenshots)  
* Capture the dissemination of official announcements or internal documents even without accompanying text

### **3.2 Anomaly Detection Logic**

**Detection Window**

* Time window: Several minutes to \~15 minutes (target time from topic emergence to detection)  
* Target: Each "Entity × Event Keyword" combination

**Evaluation Metrics**

1. **Growth Rate**: Multiplier compared to baseline (e.g., same time period over the past week)  
2. **Unique User Count**: Number of distinct accounts mentioning the topic  
3. **Noise Filtering**: Downweight consecutive posts from the same user or self-promotion patterns

→ **Prioritize relative anomaly score over absolute post count**

---

## **4\. Required Specific Functions**

### **4.1 Essential Functions**

| Feature | Requirement |
| ----- | ----- |
| Trending Keyword Detection | Automatically detect the moment cryptocurrency-related topics surge in real-time |
| Ranking Function | Rank topics by surge intensity (e.g., Top 1-100) |
| Real-time Performance | Ranking update frequency: 1-minute intervals (ideal) \*For tracking rank changes of already-detected topics |
| API Access | Machine-readable data retrieval via API, not just web dashboard |
| Notation Variation Support | Treat variations as identical (e.g., "BTC," "ビットコイン," "Bitcoin") |
| Multi-condition Search | Support combinations like "Binance" AND "hacking" |

### **4.2 Data Retrieval & Integration**

**Input (Desirable)**

* Ability to pre-register lists of monitored entities and event keywords  
* Support for uploading custom dictionaries

**Output (Required)**

* Data retrieval via API in JSON format  
* For each topic, include the following:  
  * Detection timestamp  
  * Entity (what it's about)  
  * Event keyword (what happened)  
  * Related keywords for the topic  
  * Anomaly score / ranking position  
  * Post count, unique user count  
  * Representative post URLs (samples)

---

## **5\. Evaluation Criteria**

| Priority | Item | Criteria |
| ----- | ----- | ----- |
| High | Real-time Performance | Detection delay within 10 minutes (ideal) |
| High | API Support | REST API \+ Webhook support |
| High | Customizability | Ability to register custom dictionaries |
| Medium | Cost | (Negotiable based on budget) |
| Medium | Multi-condition Search | Support for Entity × Event combinations |
| Low | Tweet Text Retrieval | Ability to retrieve representative post text via API |
| Low | Image Normalization | Preferable if available |

