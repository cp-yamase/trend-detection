"""
main_poc.py - フェーズ2+3: PoC 実行スクリプト（スコアリング統合済み）

【安全装置（二重）】
  - MAX_SECONDS : 300秒（5分）経過で自動切断
  - MAX_TWEETS  : 50件受信で自動切断
  どちらか早い方が発動する。課金爆発を防ぐため絶対に変更しないこと。

【本番移行時の注意】
  フェーズ4以降では、この安全装置を緩和する専用スクリプトを別途作成する。
  このファイルの定数は変更しない。
"""
import signal
import sys
import threading

from database import init_db, aggregate_counts, get_counts_summary, get_recent_anomaly_scores
from x_stream import get_rules, add_rules, delete_all_rules, connect_stream
from rules_config import POC_RULES
from scorer import run_scoring, format_score_line, classify
from notifier import notify

# ------------------------------------------------------------------
# ⚠️  安全装置（変更禁止）
# ------------------------------------------------------------------
MAX_SECONDS = 300   # 5分
MAX_TWEETS  = 50    # 50件


def _aggregation_loop(stop_event):
    """
    60秒ごとに集計 → スコアリングを実行するバックグラウンドスレッド。
    stop_event がセットされると終了する。
    """
    while not stop_event.wait(timeout=60):
        aggregate_counts(1)
        aggregate_counts(5)
        _run_and_print_scores()


def _run_and_print_scores():
    """スコアリングを実行し、結果を表示・通知する。"""
    results = run_scoring(window_minutes=5, lookback_minutes=30)
    if not results:
        return

    print("\n[SCORE] ========== 異常スコア ==========")
    for r in results:
        print("  " + format_score_line(r))
        notify(r)  # ALERT / SIGNAL なら Slack またはターミナルに通知
    print("[SCORE] ====================================\n")


def _print_summary():
    """セッション終了時のサマリーを表示する。"""
    print("\n" + "=" * 60)
    print("  PoC セッション サマリー（直近10分の集計）")
    print("=" * 60)
    rows = get_counts_summary(since_minutes=10)
    if not rows:
        print("  集計データなし（受信件数ゼロ、または集計未実施）")
    else:
        print(f"  {'ルールタグ':<25} {'ツイート数':>10} {'ユニークユーザー':>16}")
        print(f"  {'-'*25} {'-'*10} {'-'*16}")
        for row in rows:
            print(
                f"  {row['rule_tag']:<25} "
                f"{row['tweet_count']:>10} "
                f"{row['unique_users']:>16}"
            )
    print("=" * 60 + "\n")


def cleanup(stop_event, sig=None, frame=None):
    """終了処理: 集計 → スコアリング → サマリー → ルール削除。"""
    print("\n[MAIN] クリーンアップ中...")
    stop_event.set()

    # 最終集計・スコアリングを実行
    aggregate_counts(1)
    aggregate_counts(5)
    _run_and_print_scores()
    _print_summary()

    print("[MAIN] PoC ルールを削除します...")
    try:
        delete_all_rules()
    except Exception as e:
        print(f"[MAIN] ルール削除エラー: {e}")

    print("[MAIN] 完了。")
    sys.exit(0)


def main():
    print("=" * 60)
    print("  Trend Detection System - Phase 2: PoC テスト")
    print(f"  安全装置: {MAX_SECONDS}秒 または {MAX_TWEETS}件 で自動切断")
    print("=" * 60)

    # 集計スレッド停止用イベント
    stop_event = threading.Event()

    # Ctrl+C / SIGTERM でクリーンアップ
    signal.signal(signal.SIGINT,  lambda s, f: cleanup(stop_event, s, f))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup(stop_event, s, f))

    # 1. DB 初期化
    print("\n[STEP 1] データベース初期化")
    init_db()

    # 2. 既存ルールをクリア
    print("\n[STEP 2] 既存ストリームルールをクリア")
    delete_all_rules()

    # 3. PoC ルールを登録して確認
    print("\n[STEP 3] PoC ルールを登録")
    add_rules(POC_RULES)

    print("\n[STEP 4] 登録済みルールを確認")
    for r in get_rules():
        print(f"  - [{r.get('tag')}] {r.get('value')}")

    # 4. 集計スレッドを起動（1分ごとに集計）
    agg_thread = threading.Thread(target=_aggregation_loop, args=(stop_event,), daemon=True)
    agg_thread.start()
    print("\n[MAIN] 集計スレッド起動（60秒ごとに自動集計）")

    # 5. ストリーム接続（安全装置付き）
    print(f"\n[STEP 5] ストリーム接続開始")
    print(f"  ルール数: {len(POC_RULES)} 件")
    print(f"  自動切断条件: {MAX_SECONDS}秒経過 または {MAX_TWEETS}件受信\n")

    try:
        saved = connect_stream(
            timeout_seconds=MAX_SECONDS,
            max_tweets=MAX_TWEETS,
        )
        print(f"\n[MAIN] ストリーム終了。新規保存: {saved}件")
    except Exception as e:
        print(f"\n[MAIN] ストリームエラー: {e}")
    finally:
        cleanup(stop_event)


if __name__ == "__main__":
    main()
