"""
update_entities.py - CoinGecko API からエンティティを自動取得・更新するスクリプト

動作概要:
  1. CoinGecko から時価総額上位コイン・取引所を取得
  2. entities.py（静的）に未登録のものだけ entities_auto.json に追記
  3. 新規エンティティがあれば trend-detection サービスを再起動

実行タイミング:
  VPS の cron で毎日 1 回実行する（例: 毎朝 4:00 JST）
  crontab 設定例:
    0 4 * * * cd /root/trend_detection && /root/trend_detection/venv/bin/python update_entities.py >> logs/update_entities.log 2>&1

注意:
  CoinGecko Lite プランの API キーを .env の COINGECKO_API_KEY に設定すること。
"""

import os
import json
import time
import subprocess
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

COINGECKO_BASE    = "https://pro-api.coingecko.com/api/v3"
AUTO_FILE         = "entities_auto.json"
TOP_COINS         = 100
TOP_EXCHANGES     = 50
REQUEST_INTERVAL  = 2.0  # API 呼び出し間隔（秒）


# ------------------------------------------------------------------
# CoinGecko API
# ------------------------------------------------------------------

def _cg_headers() -> dict:
    key = os.getenv("COINGECKO_API_KEY")
    if not key:
        raise EnvironmentError("COINGECKO_API_KEY が .env に設定されていません。")
    return {"x-cg-pro-api-key": key}


def fetch_top_coins(n: int = TOP_COINS) -> list:
    resp = requests.get(
        f"{COINGECKO_BASE}/coins/markets",
        headers=_cg_headers(),
        params={
            "vs_currency": "usd",
            "order":        "market_cap_desc",
            "per_page":     n,
            "page":         1,
            "sparkline":    False,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_top_exchanges(n: int = TOP_EXCHANGES) -> list:
    resp = requests.get(
        f"{COINGECKO_BASE}/exchanges",
        headers=_cg_headers(),
        params={"per_page": n, "page": 1},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ------------------------------------------------------------------
# entities_auto.json の読み書き
# ------------------------------------------------------------------

def load_auto() -> dict:
    if os.path.exists(AUTO_FILE):
        with open(AUTO_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "CRYPTO": {}, "EXCHANGE": {}}


def save_auto(data: dict) -> None:
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(AUTO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------
# 静的エンティティの既登録シンボル・名前を収集
# ------------------------------------------------------------------

def _static_symbols() -> set:
    """entities.py の全グループキーを返す"""
    from entities import ENTITIES
    symbols = set()
    for groups in ENTITIES.values():
        symbols.update(k.upper() for k in groups.keys())
    return symbols


def _static_exchange_names() -> set:
    """entities.py の EXCHANGE カテゴリに登録済みの取引所名（小文字）を返す"""
    from entities import ENTITIES
    names = set()
    for terms in ENTITIES.get("EXCHANGE", {}).values():
        names.update(t.lower() for t in terms)
    return names


# ------------------------------------------------------------------
# メイン
# ------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Entity Auto-Updater（CoinGecko）")
    print(f"  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    os.makedirs("logs", exist_ok=True)

    auto           = load_auto()
    static_symbols = _static_symbols()
    static_ex_names = _static_exchange_names()
    new_count      = 0

    # ------------------------------------------------------------------
    # コイン
    # ------------------------------------------------------------------
    print("\n[1/2] トップコインを取得中...")
    try:
        coins = fetch_top_coins()
        for coin in coins:
            symbol = coin["symbol"].upper()
            name   = coin["name"]

            # 静的・自動どちらにも未登録ならば追加
            if symbol not in static_symbols and symbol not in auto["CRYPTO"]:
                auto["CRYPTO"][symbol] = [name, symbol]
                print(f"  + {symbol} ({name})")
                new_count += 1

        print(f"  取得完了: {len(coins)} 件 / 新規追加: {new_count} 件")
    except Exception as e:
        print(f"  ❌ コイン取得エラー: {e}")

    time.sleep(REQUEST_INTERVAL)

    # ------------------------------------------------------------------
    # 取引所
    # ------------------------------------------------------------------
    print("\n[2/2] トップ取引所を取得中...")
    ex_new = 0
    try:
        exchanges = fetch_top_exchanges()
        for ex in exchanges:
            name = ex.get("name", "")
            key  = name.upper().replace(" ", "_").replace(".", "_")

            if name.lower() not in static_ex_names and key not in auto["EXCHANGE"]:
                auto["EXCHANGE"][key] = [name]
                print(f"  + {name}")
                new_count += 1
                ex_new += 1

        print(f"  取得完了: {len(exchanges)} 件 / 新規追加: {ex_new} 件")
    except Exception as e:
        print(f"  ❌ 取引所取得エラー: {e}")

    # ------------------------------------------------------------------
    # 保存・サービス再起動
    # ------------------------------------------------------------------
    save_auto(auto)
    print(f"\n合計新規追加: {new_count} 件 → {AUTO_FILE} を更新しました")

    if new_count > 0:
        print("\ntrend-detection サービスを再起動します...")
        try:
            subprocess.run(["systemctl", "restart", "trend-detection"], check=True)
            print("再起動完了")
        except Exception as e:
            print(f"⚠️  再起動エラー（手動で実行してください）: {e}")
    else:
        print("新規追加なし。サービス再起動は不要です。")

    print("\n" + "=" * 60)
    print("  完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
