"""
main.py - フェーズ1 動作確認用エントリーポイント

【重要: API課金爆発防止】
本番キーワード（"Bitcoin", "BTC" 等）は絶対に登録しないこと。
以下のテスト用キーワードは実際には誰もつぶやかないため、
ストリームが起動しても受信件数はゼロのまま課金は発生しない。

本番キーワードへの切り替えは フェーズ2 以降で行う。
"""
import signal
import sys
from database import init_db
from x_stream import get_rules, add_rules, delete_all_rules, connect_stream

# ------------------------------------------------------------------
# ⚠️  テスト用ルール定義
#
# value : ストリームのフィルタ条件（X の検索構文に準拠）
# tag   : データ処理側でどのルールにマッチしたかを識別するラベル
#
# 変更禁止: フェーズ2 に進むまでここを書き換えないこと
# ------------------------------------------------------------------
TEST_RULES = [
    {
        "value": "test_crypto_trend_system_999",
        "tag": "TEST_SAFETY_RULE",
    }
]

# テスト用ストリーム接続時間（秒）。0 にすると手動 Ctrl+C まで動き続ける
TEST_TIMEOUT_SECONDS = 60


def cleanup(sig=None, frame=None):
    """終了時にテストルールを必ず削除してから終了する。"""
    print("\n[MAIN] クリーンアップ中: テストルールを削除します...")
    try:
        delete_all_rules()
    except Exception as e:
        print(f"[MAIN] ルール削除中にエラー: {e}")
    print("[MAIN] 完了。終了します。")
    sys.exit(0)


def main():
    print("=" * 60)
    print("  Trend Detection System - Phase 1: 基盤構築テスト")
    print("  [SAFE MODE] テスト用キーワードのみ使用")
    print("=" * 60)

    # Ctrl+C で cleanup が呼ばれるよう登録
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # 1. DB 初期化
    print("\n[STEP 1] データベース初期化")
    init_db()

    # 2. 既存ルールをすべて削除（前回の実行ゴミを消す）
    print("\n[STEP 2] 既存ストリームルールをクリア")
    delete_all_rules()

    # 3. テスト用ルールを登録
    print("\n[STEP 3] テスト用ルールを登録")
    add_rules(TEST_RULES)

    # 4. 登録内容を確認
    print("\n[STEP 4] 登録済みルールを確認")
    rules = get_rules()
    for r in rules:
        print(f"  - id={r['id']} tag={r.get('tag')} value={r.get('value')}")

    # 5. ストリーム接続（テスト用タイムアウト付き）
    print(f"\n[STEP 5] ストリーム接続 ({TEST_TIMEOUT_SECONDS}秒間テスト受信)")
    print("  ※ テストキーワードは誰もつぶやかないため、受信件数はゼロが正常です")
    print("  ※ Ctrl+C で随時終了できます\n")

    try:
        connect_stream(timeout_seconds=TEST_TIMEOUT_SECONDS)
    except Exception as e:
        print(f"\n[MAIN] ストリームエラー: {e}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
