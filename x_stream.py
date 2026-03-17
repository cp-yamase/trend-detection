"""
x_stream.py - X API Filtered Stream の操作モジュール

担当する処理:
  - ストリームルールの追加・削除
  - Filtered Stream への接続とツイートの受信・保存
"""
import os
import json
import time
import requests
from dotenv import load_dotenv
from database import save_tweet

load_dotenv()

RULES_URL = "https://api.x.com/2/tweets/search/stream/rules"
STREAM_URL = "https://api.x.com/2/tweets/search/stream"


def _headers() -> dict:
    token = os.getenv("BEARER_TOKEN")
    if not token:
        raise EnvironmentError(
            "BEARER_TOKEN が .env に設定されていません。"
            ".env.example を参考に .env を作成してください。"
        )
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------
# ルール管理
# ------------------------------------------------------------------

def get_rules() -> list[dict]:
    """現在登録されているストリームルールを取得する。"""
    resp = requests.get(RULES_URL, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json().get("data") or []


def add_rules(rules: list[dict]) -> dict:
    """
    ストリームルールを追加する。

    rules の形式:
        [{"value": "Bitcoin lang:ja", "tag": "BTC_GENERAL"}, ...]

    tag はデータ処理側でどのルールにマッチしたかを識別するためのラベル。
    """
    payload = {"add": rules}
    resp = requests.post(RULES_URL, headers=_headers(), json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()

    errors = result.get("errors")
    if errors:
        print(f"[STREAM] ルール追加エラー: {errors}")

    meta = result.get("meta", {})
    print(
        f"[STREAM] ルール追加完了 - "
        f"作成: {meta.get('summary', {}).get('created', 0)}件 / "
        f"無効: {meta.get('summary', {}).get('invalid', 0)}件"
    )
    return result


def delete_all_rules():
    """登録済みのストリームルールをすべて削除する。"""
    existing = get_rules()
    if not existing:
        print("[STREAM] 削除対象のルールなし。")
        return

    ids = [r["id"] for r in existing]
    payload = {"delete": {"ids": ids}}
    resp = requests.post(RULES_URL, headers=_headers(), json=payload, timeout=10)
    resp.raise_for_status()
    print(f"[STREAM] {len(ids)} 件のルールを削除しました。")


# ------------------------------------------------------------------
# ストリーム接続
# ------------------------------------------------------------------

def connect_stream(timeout_seconds=None, max_tweets=None, on_tweet=None):
    """
    Filtered Stream に接続し、受信したツイートを SQLite に保存する。

    Args:
        timeout_seconds : 指定秒数後に自動切断（安全装置）。None で無制限。
        max_tweets      : 指定件数受信後に自動切断（安全装置）。None で無制限。
        on_tweet        : ツイート受信のたびに呼ばれるコールバック関数(省略可)。
                          引数: (tweet_id, text, matched_rule_tags)

    Returns:
        int: セッション中に新規保存したツイート数
    """
    params = {
        # デフォルト返却値 (id, text) に加えて author_id と created_at を追加
        "tweet.fields": "author_id,created_at",
    }

    CONNECT_TIMEOUT = 10
    READ_TIMEOUT = 30  # X はハートビートを約20秒ごとに送信するため30秒で十分

    print(f"[STREAM] 接続中... {STREAM_URL}")
    if timeout_seconds:
        print(f"[STREAM] 安全装置: {timeout_seconds}秒 または {max_tweets}件 で自動切断")

    start_time = time.monotonic()
    saved_count = 0

    try:
        with requests.get(
            STREAM_URL,
            headers=_headers(),
            params=params,
            stream=True,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            print("[STREAM] 接続完了。ツイート待機中...\n")

            for line in resp.iter_lines():

                # --- 安全装置: 時間チェック ---
                elapsed = time.monotonic() - start_time
                if timeout_seconds and elapsed >= timeout_seconds:
                    print(f"\n[STREAM] ⏱  {timeout_seconds}秒経過。自動切断します。")
                    break

                # --- 安全装置: 件数チェック ---
                if max_tweets and saved_count >= max_tweets:
                    print(f"\n[STREAM] 🛑  受信上限 {max_tweets}件 に達しました。自動切断します。")
                    break

                if not line:
                    continue

                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[STREAM] JSONパースエラー: {line[:100]}")
                    continue

                # ストリームエラーレスポンス（例: 接続数超過）
                if "errors" in payload and "data" not in payload:
                    print(f"[STREAM] エラーレスポンス: {payload['errors']}")
                    continue

                tweet_id, text, tags = _process_tweet(payload)
                if tweet_id:  # 新規保存された場合のみカウント
                    saved_count += 1
                    if on_tweet:
                        on_tweet(tweet_id, text, tags)

    except requests.exceptions.ConnectionError:
        print("[STREAM] 接続エラー。ネットワークまたはAPIを確認してください。")
        raise
    except requests.exceptions.ReadTimeout:
        print("[STREAM] 読み取りタイムアウト（ハートビートが途絶えた可能性）。")
        raise
    except requests.exceptions.HTTPError as e:
        print(f"[STREAM] HTTPエラー: {e.response.status_code} - {e.response.text}")
        raise

    return saved_count


def _process_tweet(payload: dict):
    """
    受信したペイロードからツイートを取り出してDBに保存する。

    Returns:
        (tweet_id, text, matched_rule_tags) - 新規保存時
        ("", "", [])                         - 重複スキップ時
    """
    tweet = payload.get("data", {})
    tweet_id   = tweet.get("id", "")
    text       = tweet.get("text", "")
    author_id  = tweet.get("author_id", "")
    created_at = tweet.get("created_at", "")

    matched_rule_tags = [
        r.get("tag", r.get("id", "unknown"))
        for r in payload.get("matching_rules", [])
    ]

    saved = save_tweet(tweet_id, text, author_id, created_at, matched_rule_tags)

    if saved:
        print(f"[SAVED] {matched_rule_tags} | {text[:70]!r}")
        return tweet_id, text, matched_rule_tags
    else:
        return "", "", []
