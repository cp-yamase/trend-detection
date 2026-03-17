"""
test_slack.py - Slack Webhook 疎通確認スクリプト

実行前に .env の SLACK_WEBHOOK_URL を設定しておくこと。

使い方:
    python test_slack.py
"""
import os
from dotenv import load_dotenv
from notifier import _notify_terminal, _notify_slack

load_dotenv()

# ダミーのスコアリング結果（実際のイベントに近い値）
DUMMY_RESULT = {
    "window_start":   "2026-03-10T05:00:00+00:00",
    "window_minutes": 5,
    "rule_tag":       "EXCHANGE_LISTING",
    "current_count":  8,
    "unique_users":   7,
    "baseline_avg":   0.0,
    "baseline_days":  0,
    "growth_rate":    8.0,
    "diversity_ratio": 0.875,
    "anomaly_score":  7.0,
}


def main():
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")

    print("=== Slack Webhook 疎通確認 ===\n")

    if not webhook_url:
        print("⚠️  SLACK_WEBHOOK_URL が .env に設定されていません。")
        print("   ターミナル通知のテストを実行します。\n")
        _notify_terminal(DUMMY_RESULT, "SIGNAL")
        print("✅ ターミナル通知の表示確認完了。")
        print("   .env に SLACK_WEBHOOK_URL を設定してから再実行してください。")
        return

    print(f"Webhook URL: {webhook_url[:40]}...")
    print("Slack にテスト通知を送信中...\n")

    _notify_slack(DUMMY_RESULT, "SIGNAL")

    print("\n上記のメッセージが Slack に届いていれば設定完了です。")


if __name__ == "__main__":
    main()
