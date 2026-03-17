"""
notifier.py - 通知モジュール

通知優先順:
  1. Slack Webhook  (.env に SLACK_WEBHOOK_URL が設定されている場合)
  2. ターミナル出力 (フォールバック)

連続通知の抑制:
  同じ rule_tag に対して COOLDOWN_MINUTES 分以内は再通知しない。
  これにより、同一イベントの連投でアラートが連発するのを防ぐ。
"""
import os
import json
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from scorer import classify

load_dotenv()

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
COOLDOWN_MINUTES  = 10  # 同じ rule_tag への通知クールダウン（分）

# メモリ内クールダウン管理 {rule_tag: last_notified_at}
_last_notified: dict = {}


# ------------------------------------------------------------------
# 公開インターフェース
# ------------------------------------------------------------------

def notify(result: dict) -> bool:
    """
    スコアリング結果を受け取り、通知対象なら通知を送る。

    通知条件:
      - classify() が "ALERT" または "SIGNAL" を返す
      - 同じ rule_tag のクールダウンが切れている

    Returns:
        True: 通知を送信した
        False: 通知しなかった（NORMAL / クールダウン中）
    """
    label = classify(result)
    if label == "NORMAL":
        return False

    if not _is_cooled_down(result["rule_tag"]):
        return False

    _mark_notified(result["rule_tag"])

    if SLACK_WEBHOOK_URL:
        _notify_slack(result, label)
    else:
        _notify_terminal(result, label)

    return True


# ------------------------------------------------------------------
# クールダウン管理
# ------------------------------------------------------------------

def _is_cooled_down(rule_tag: str) -> bool:
    last = _last_notified.get(rule_tag)
    if last is None:
        return True
    return datetime.now(timezone.utc) - last >= timedelta(minutes=COOLDOWN_MINUTES)


def _mark_notified(rule_tag: str):
    _last_notified[rule_tag] = datetime.now(timezone.utc)


# ------------------------------------------------------------------
# Slack 通知
# ------------------------------------------------------------------

def _build_slack_payload(result: dict, label: str) -> dict:
    emoji = "🚨" if label == "ALERT" else "🔍"
    color = "#ff0000" if label == "ALERT" else "#ff9900"
    window_dt = datetime.fromisoformat(result["window_start"])

    baseline_text = (
        f"{result['baseline_avg']} tweets / {result['window_minutes']}分 "
        f"（過去 {result['baseline_days']} 日平均）"
        if result["baseline_days"] > 0
        else "データなし（蓄積中）"
    )

    return {
        "attachments": [
            {
                "color": color,
                "title": f"{emoji} {label}: {result['rule_tag']}",
                "fields": [
                    {
                        "title": "ツイート数",
                        "value": f"{result['current_count']} 件",
                        "short": True,
                    },
                    {
                        "title": "ユニークユーザー",
                        "value": f"{result['unique_users']} アカウント",
                        "short": True,
                    },
                    {
                        "title": "増加倍率 (growth_rate)",
                        "value": f"{result['growth_rate']}x",
                        "short": True,
                    },
                    {
                        "title": "異常スコア",
                        "value": str(result["anomaly_score"]),
                        "short": True,
                    },
                    {
                        "title": "ベースライン",
                        "value": baseline_text,
                        "short": False,
                    },
                    {
                        "title": "検知ウィンドウ",
                        "value": (
                            f"{window_dt.strftime('%Y-%m-%d %H:%M')} UTC "
                            f"（{result['window_minutes']}分窓）"
                        ),
                        "short": False,
                    },
                ],
                "footer": "Trend Detection System",
                "ts": int(datetime.now(timezone.utc).timestamp()),
            }
        ]
    }


def _notify_slack(result: dict, label: str):
    """Slack Webhook に通知を送る。失敗時はターミナルにフォールバック。"""
    payload = _build_slack_payload(result, label)
    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"[NOTIFY] ✅ Slack 送信完了: [{result['rule_tag']}] ({label})")
        else:
            print(f"[NOTIFY] ❌ Slack 送信失敗 (HTTP {resp.status_code}): {resp.text}")
            _notify_terminal(result, label)
    except Exception as e:
        print(f"[NOTIFY] ❌ Slack 送信エラー: {e}")
        _notify_terminal(result, label)


# ------------------------------------------------------------------
# ターミナル通知（フォールバック）
# ------------------------------------------------------------------

def _notify_terminal(result: dict, label: str):
    """ターミナルに通知ブロックを表示する。"""
    emoji = "🚨" if label == "ALERT" else "🔍"
    window_dt = datetime.fromisoformat(result["window_start"])

    print()
    print("=" * 62)
    print(f"  {emoji}  {label}: {result['rule_tag']}")
    print("=" * 62)
    print(f"  ツイート数      : {result['current_count']} 件")
    print(f"  ユニークユーザー: {result['unique_users']} アカウント")
    print(f"  増加倍率        : {result['growth_rate']}x")
    print(f"  異常スコア      : {result['anomaly_score']}")
    if result["baseline_days"] > 0:
        print(
            f"  ベースライン    : {result['baseline_avg']} tweets/min "
            f"（過去 {result['baseline_days']} 日平均）"
        )
    else:
        print("  ベースライン    : データなし（蓄積中）")
    print(f"  検知ウィンドウ  : {window_dt.strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 62)
    print()
