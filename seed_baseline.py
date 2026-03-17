"""
seed_baseline.py - 過去7日分のベースラインデータを一括投入するスクリプト

使用エンドポイント:
  GET /2/tweets/counts/recent
  → 実際のツイート本文を取得しないカウント専用エンドポイント。
    ツイート件数ではなく「リクエスト単位」での課金となるため、
    search/recent より大幅にコストが低い。
    ※ 正確な単価は Developer Console で確認してください。

動作概要:
  1. STREAM_RULES の各クエリで過去7日分の per-minute カウントを取得
  2. 5分窓に集計して tweet_counts テーブルに INSERT
  3. 既存レコードは上書きしない（実データ優先）

実行タイミング:
  初回のみ実行すれば OK。以後は Filtered Stream が自動蓄積する。
"""
import os
import time
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from database import init_db, get_connection
from rules_config import STREAM_RULES

load_dotenv()

COUNTS_URL = "https://api.x.com/2/tweets/counts/recent"
WINDOW_MINUTES = 5
REQUEST_INTERVAL = 1.5  # API 連続呼び出しの間隔（秒）


def _headers() -> dict:
    token = os.getenv("BEARER_TOKEN")
    if not token:
        raise EnvironmentError("BEARER_TOKEN が .env に設定されていません。")
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------
# API 呼び出し
# ------------------------------------------------------------------

def fetch_minute_counts(query: str, start_iso: str, end_iso: str) -> list:
    """
    granularity=minute で per-minute カウントを取得する。
    ページネーション (next_token) にも対応。

    Returns:
        [{"start": "...", "end": "...", "tweet_count": int}, ...]
    """
    params = {
        "query":       query,
        "granularity": "minute",
        "start_time":  start_iso,
        "end_time":    end_iso,
    }

    all_data = []
    next_token = None

    while True:
        if next_token:
            params["next_token"] = next_token

        resp = requests.get(COUNTS_URL, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        all_data.extend(body.get("data", []))

        next_token = body.get("meta", {}).get("next_token")
        if not next_token:
            break

        time.sleep(REQUEST_INTERVAL)

    return all_data


# ------------------------------------------------------------------
# 5分窓への集計
# ------------------------------------------------------------------

def aggregate_to_5min(minute_data: list) -> dict:
    """
    per-minute データを WINDOW_MINUTES 分窓に集計する。

    Returns:
        {window_start_iso: tweet_count}
    """
    windows: dict = {}

    for item in minute_data:
        if item["tweet_count"] == 0:
            continue

        # "2026-03-03T05:00:00.000Z" → datetime
        raw = item["start"].replace("Z", "+00:00")
        dt  = datetime.fromisoformat(raw)

        floored      = (dt.minute // WINDOW_MINUTES) * WINDOW_MINUTES
        window_start = dt.replace(minute=floored, second=0, microsecond=0)
        key          = window_start.isoformat()

        windows[key] = windows.get(key, 0) + item["tweet_count"]

    return windows


# ------------------------------------------------------------------
# DB への投入
# ------------------------------------------------------------------

def insert_baseline(rule_tag: str, windows: dict) -> int:
    """
    5分窓データを tweet_counts に INSERT OR IGNORE で投入する。
    既存レコート（実データ）は上書きしない。

    Returns:
        挿入に成功したレコード数
    """
    created_at = datetime.now(timezone.utc).isoformat()
    inserted   = 0

    with get_connection() as conn:
        for window_start, count in windows.items():
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO tweet_counts
                    (window_start, window_minutes, rule_tag,
                     tweet_count, unique_users, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (window_start, WINDOW_MINUTES, rule_tag, count, 0, created_at),
            )
            inserted += cursor.rowcount
        conn.commit()

    return inserted


# ------------------------------------------------------------------
# メイン
# ------------------------------------------------------------------

def main():
    print("=" * 62)
    print("  Baseline Seeder - 過去7日分のベースラインデータ投入")
    print("=" * 62)

    # 取得範囲:
    #   end_time   = 直近5分前（ストリームとの重複を避ける）
    #   start_time = 6日23時間前（X APIは「ちょうど7日前」を拒否するため10分のバッファを確保）
    end_time   = datetime.now(timezone.utc) - timedelta(minutes=5)
    start_time = datetime.now(timezone.utc) - timedelta(days=6, hours=23, minutes=50)

    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_iso   = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\n  取得範囲  : {start_iso}")
    print(f"            〜 {end_iso}")
    print(f"  対象ルール: {len(STREAM_RULES)} 件")
    print(f"  窓サイズ  : {WINDOW_MINUTES} 分\n")

    init_db()

    total_inserted    = 0
    total_raw_tweets  = 0

    for i, rule in enumerate(STREAM_RULES, 1):
        tag   = rule["tag"]
        query = rule["value"]

        print(f"[{i}/{len(STREAM_RULES)}] {tag}")
        print(f"  クエリ: {query[:70]}...")

        try:
            minute_data = fetch_minute_counts(query, start_iso, end_iso)

            if not minute_data:
                print("  → データなし（過去7日間にマッチするツイートがゼロ）\n")
                continue

            raw_total = sum(d["tweet_count"] for d in minute_data)
            total_raw_tweets += raw_total
            print(f"  → {len(minute_data):,} 分分のカウント取得 / 合計 {raw_total:,} tweets")

            windows   = aggregate_to_5min(minute_data)
            non_zero  = len(windows)
            inserted  = insert_baseline(tag, windows)
            total_inserted += inserted

            print(f"  → {non_zero:,} 窓（{WINDOW_MINUTES}分窓）を生成 / {inserted:,} 件を DB に投入")

        except requests.exceptions.HTTPError as e:
            print(f"  ❌ HTTPエラー: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"  ❌ エラー: {e}")

        print()
        if i < len(STREAM_RULES):
            time.sleep(REQUEST_INTERVAL)

    print("=" * 62)
    print(f"  完了")
    print(f"  取得ツイート総数 : {total_raw_tweets:,} 件（カウントのみ・本文取得なし）")
    print(f"  DB 投入レコード  : {total_inserted:,} 件")
    print()
    print("  次回から main_poc.py を実行すると")
    print("  ベースライン比較の精度の高いスコアが出力されます。")
    print("=" * 62)


if __name__ == "__main__":
    main()
