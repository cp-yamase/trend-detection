"""
main_prod.py - 本番用エントリーポイント（EC2常時稼働版）

main_poc.py との違い:
  - 安全装置（300秒/50件）なし → 無制限で動き続ける
  - ストリーム切断時は指数バックオフで自動再接続
  - ログをファイルにも出力（logs/trend_detection.log）
  - systemd から管理されることを前提とする
"""
import os
import sys
import signal
import time
import logging
import threading

from database import init_db, aggregate_counts
from x_stream import add_rules, delete_all_rules, connect_stream
from rules_config import STREAM_RULES
from scorer import run_scoring, format_score_line
from notifier import notify

# ------------------------------------------------------------------
# ログ設定（ターミナル + ファイルに同時出力）
# ------------------------------------------------------------------
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/trend_detection.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 再接続バックオフ設定
# ------------------------------------------------------------------
INITIAL_BACKOFF = 5    # 秒（初回の待機時間）
MAX_BACKOFF     = 300  # 秒（最大5分まで延ばす）


# ------------------------------------------------------------------
# 集計・スコアリングスレッド
# ------------------------------------------------------------------

def _aggregation_loop(stop_event):
    """60秒ごとに集計 → スコアリング → 必要なら通知。"""
    while not stop_event.wait(timeout=60):
        try:
            aggregate_counts(1)
            aggregate_counts(5)
            results = run_scoring(window_minutes=5, lookback_minutes=30)
            for r in results:
                log.info(format_score_line(r))
                notify(r)
        except Exception as e:
            log.error(f"集計/スコアリングエラー: {e}")


# ------------------------------------------------------------------
# 終了処理
# ------------------------------------------------------------------

def cleanup(stop_event, sig=None, frame=None):
    """SIGTERM / SIGINT 受信時にルールを削除してから終了する。"""
    log.info("シャットダウン中... ストリームルールを削除します")
    stop_event.set()
    try:
        delete_all_rules()
    except Exception as e:
        log.error(f"ルール削除エラー: {e}")
    log.info("終了しました。")
    sys.exit(0)


# ------------------------------------------------------------------
# メイン
# ------------------------------------------------------------------

def main():
    log.info("=" * 50)
    log.info("  Trend Detection System 起動")
    log.info("=" * 50)

    stop_event = threading.Event()

    signal.signal(signal.SIGINT,  lambda s, f: cleanup(stop_event, s, f))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup(stop_event, s, f))

    # DB 初期化
    init_db()

    # ストリームルール登録
    log.info("ストリームルールを登録中...")
    delete_all_rules()
    add_rules(STREAM_RULES)
    log.info(f"登録完了: {len(STREAM_RULES)}ルール")

    # 集計スレッド起動
    agg_thread = threading.Thread(
        target=_aggregation_loop, args=(stop_event,), daemon=True
    )
    agg_thread.start()
    log.info("集計スレッド起動（60秒ごとに自動集計）")

    # ストリーム接続ループ（切断時は自動再接続）
    backoff = INITIAL_BACKOFF
    while not stop_event.is_set():
        try:
            log.info("Filtered Stream に接続中...")
            connect_stream()
            # 正常終了（通常はここに来ない）
            backoff = INITIAL_BACKOFF
        except Exception as e:
            if stop_event.is_set():
                break
            log.error(f"ストリームエラー: {e}")
            log.info(f"{backoff} 秒後に再接続します...")
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)


if __name__ == "__main__":
    main()
