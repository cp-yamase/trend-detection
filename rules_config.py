"""
rules_config.py - ストリームルール定義

設計方針:
  - -is:retweet : RT を除外（同一情報の重複カウントを防ぐ）
  - 多言語対応のため lang:en は付与しない
  - エンティティ・イベントキーワードは entities.py / event_keywords.py で管理
  - generate_rules() で Entity グループ × イベントカテゴリ の全組み合わせを自動生成
  - タグ形式: {ENTITY_CATEGORY}_{GROUP_ID}_{EVENT_TAG}
              例: CRYPTO_BTC_SECURITY, EXCHANGE_TIER1_REGULATORY

X API 制約:
  - ルール上限: 1,000ルール
  - 1ルールあたりのクエリ長上限: 1,024文字
  - generate_rules() は上限超過ルールを自動スキップし警告を出す
"""

import json
import os
import copy

from entities import ENTITIES as _STATIC_ENTITIES
from event_keywords import EVENT_KEYWORDS

_AUTO_FILE = os.path.join(os.path.dirname(__file__), "entities_auto.json")


def _load_merged_entities() -> dict:
    """
    静的エンティティ（entities.py）と自動更新エンティティ（entities_auto.json）をマージして返す。
    auto の各エントリは CRYPTO → CRYPTO_AUTO_xxx、EXCHANGE → EXCHANGE_AUTO_xxx として追加。
    """
    merged = copy.deepcopy(_STATIC_ENTITIES)

    if not os.path.exists(_AUTO_FILE):
        return merged

    try:
        with open(_AUTO_FILE, encoding="utf-8") as f:
            auto = json.load(f)
    except Exception:
        return merged

    # コイン: 静的に未登録のものだけ追加
    static_crypto_keys = set(merged.get("CRYPTO", {}).keys())
    for symbol, terms in auto.get("CRYPTO", {}).items():
        if symbol not in static_crypto_keys:
            merged.setdefault("CRYPTO", {})[symbol] = terms

    # 取引所: 静的に未登録のものだけ EXCHANGE カテゴリに追加
    static_exchange_names = set()
    for terms in merged.get("EXCHANGE", {}).values():
        static_exchange_names.update(t.lower() for t in terms)

    for key, terms in auto.get("EXCHANGE", {}).items():
        if not any(t.lower() in static_exchange_names for t in terms):
            merged.setdefault("EXCHANGE", {})[key] = terms

    return merged


ENTITIES = _load_merged_entities()

# フェーズ6移行前の旧PoC用ルール（参照用・本番では使用しない）
_LEGACY_POC_RULES = [
    {
        "value": (
            "(Bitcoin OR BTC OR Ethereum OR ETH) "
            "(hack OR hacked OR exploit OR exploited OR breach OR breached) "
            "-is:retweet -is:reply lang:en"
        ),
        "tag": "CRYPTO_SECURITY",
    },
    {
        "value": (
            "(Binance OR Coinbase OR Kraken OR OKX OR Bybit) "
            "(listing OR listed OR delist OR delisted OR delisting) "
            "-is:retweet -is:reply lang:en"
        ),
        "tag": "EXCHANGE_LISTING",
    },
    {
        "value": (
            "(Binance OR Coinbase OR Kraken OR OKX OR Bybit) "
            "(withdraw OR withdrawal OR suspend OR suspended OR halt OR halted OR outage) "
            "-is:retweet -is:reply lang:en"
        ),
        "tag": "EXCHANGE_ISSUE",
    },
]

# テスト用（フェーズ1 / 動作確認専用。本番では使用しない）
TEST_RULES = [
    {
        "value": "test_crypto_trend_system_999",
        "tag": "TEST_SAFETY_RULE",
    }
]

MAX_RULES = 1000
MAX_QUERY_LENGTH = 1024


def _to_query_term(term: str) -> str:
    """スペースを含む語句をクォートで囲む"""
    return f'"{term}"' if " " in term else term


def _build_or_clause(terms: list[str]) -> str:
    return " OR ".join(_to_query_term(t) for t in terms)


def generate_rules() -> list[dict]:
    """
    entities.py × event_keywords.py の全組み合わせからルールを生成する。
    1,024文字を超えるルールはスキップして警告を出す。
    1,000ルール上限を超えた場合も警告を出す。
    """
    rules = []
    skipped = []

    for entity_cat, groups in ENTITIES.items():
        for group_id, entity_terms in groups.items():
            entity_clause = _build_or_clause(entity_terms)

            for event_cat, event_def in EVENT_KEYWORDS.items():
                keyword_clause = _build_or_clause(event_def["keywords"])
                tag = f"{entity_cat}_{group_id}_{event_def['tag']}"
                value = f"({entity_clause}) ({keyword_clause}) -is:retweet"

                if len(value) > MAX_QUERY_LENGTH:
                    skipped.append((tag, len(value)))
                    continue

                rules.append({"value": value, "tag": tag})

    if skipped:
        print(f"[RULES] ⚠️  クエリ長超過のためスキップしたルール ({len(skipped)}件):")
        for tag, length in skipped:
            print(f"  - {tag}: {length}文字")

    if len(rules) > MAX_RULES:
        print(f"[RULES] ⚠️  ルール数が上限({MAX_RULES})を超えています: {len(rules)}件")
        print("[RULES]    先頭1,000件を使用します。優先度設計を検討してください。")
        rules = rules[:MAX_RULES]

    print(f"[RULES] 生成ルール数: {len(rules)}")
    return rules


# 本番用ルール
STREAM_RULES = generate_rules()
