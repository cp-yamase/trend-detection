"""
database.py - SQLiteの初期化と基本操作
"""
import sqlite3
import os
import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# data/ ディレクトリにDBファイルを配置（自動生成）
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tweets.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """テーブルとインデックスを作成する。既存の場合はスキップ。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    with get_connection() as conn:
        # -------------------------------------------------------
        # テーブル1: raw_tweets
        # Filtered Stream から受信した生ツイートをそのまま保存する
        # -------------------------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS raw_tweets (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id     TEXT    UNIQUE NOT NULL,
                text         TEXT    NOT NULL,
                author_id    TEXT    NOT NULL,
                created_at   TEXT    NOT NULL,  -- X側のタイムスタンプ (ISO8601)
                received_at  TEXT    NOT NULL,  -- こちらが受信した時刻 (ISO8601)
                matched_rules TEXT   NOT NULL   -- マッチしたルールのtagリスト (JSON配列)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_created
            ON raw_tweets(created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_raw_received
            ON raw_tweets(received_at)
        """)

        # -------------------------------------------------------
        # テーブル2: tweet_counts
        # 1分・5分・15分ウィンドウ単位の集計値を保存する
        # 将来のベースライン（過去7日間同時間帯比）算出に使用
        # -------------------------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweet_counts (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start   TEXT    NOT NULL,  -- ウィンドウ開始時刻 (ISO8601)
                window_minutes INTEGER NOT NULL,  -- ウィンドウ幅: 1 / 5 / 15
                rule_tag       TEXT    NOT NULL,  -- どのルール（entity×event）か
                tweet_count    INTEGER NOT NULL DEFAULT 0,
                unique_users   INTEGER NOT NULL DEFAULT 0,
                created_at     TEXT    NOT NULL,  -- この集計レコードの作成時刻
                UNIQUE(window_start, window_minutes, rule_tag)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_counts_window
            ON tweet_counts(window_start, window_minutes, rule_tag)
        """)

        # -------------------------------------------------------
        # テーブル3: anomaly_scores
        # スコアリングエンジンが算出した異常スコアを保存する
        # -------------------------------------------------------
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomaly_scores (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                window_start     TEXT    NOT NULL,
                window_minutes   INTEGER NOT NULL,
                rule_tag         TEXT    NOT NULL,
                current_count    INTEGER NOT NULL,
                unique_users     INTEGER NOT NULL,
                baseline_avg     REAL    NOT NULL,  -- 過去N日同時間帯の平均カウント
                baseline_days    INTEGER NOT NULL,  -- ベースライン算出に使った日数
                growth_rate      REAL    NOT NULL,  -- current_count / max(baseline_avg, 1)
                diversity_ratio  REAL    NOT NULL,  -- unique_users / current_count
                anomaly_score    REAL    NOT NULL,  -- growth_rate × diversity_ratio
                scored_at        TEXT    NOT NULL,
                UNIQUE(window_start, window_minutes, rule_tag)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_scores_tag
            ON anomaly_scores(rule_tag, window_start)
        """)

        conn.commit()

    print(f"[DB] Initialized: {DB_PATH}")


def save_tweet(
    tweet_id: str,
    text: str,
    author_id: str,
    created_at: str,
    matched_rule_tags: list[str],
) -> bool:
    """
    ツイートを raw_tweets に保存する。
    tweet_id が重複する場合は INSERT IGNORE でスキップ。
    戻り値: 新規保存なら True、重複スキップなら False
    """
    received_at = datetime.now(timezone.utc).isoformat()
    matched_rules_json = json.dumps(matched_rule_tags, ensure_ascii=False)

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO raw_tweets
                (tweet_id, text, author_id, created_at, received_at, matched_rules)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tweet_id, text, author_id, created_at, received_at, matched_rules_json),
        )
        conn.commit()
        return cursor.rowcount > 0


def aggregate_counts(window_minutes):
    """
    直近 window_minutes 分間の raw_tweets を集計し tweet_counts に UPSERT する。

    ウィンドウはクロック境界に揃える:
      1分: 14:37:45 → window_start = 14:37:00
      5分: 14:37:45 → window_start = 14:35:00

    同じ window_start × window_minutes × rule_tag が既にあれば上書き更新する。
    """
    now = datetime.now(timezone.utc)

    # ウィンドウ開始時刻をクロック境界に切り捨て
    floored_minute = (now.minute // window_minutes) * window_minutes
    window_start = now.replace(minute=floored_minute, second=0, microsecond=0)
    window_start_iso = window_start.isoformat()

    # ウィンドウ開始以降に受信したツイートを取得
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT author_id, matched_rules
            FROM raw_tweets
            WHERE received_at >= ?
            """,
            (window_start_iso,),
        ).fetchall()

    if not rows:
        return

    # rule_tag ごとに tweet 数・ユニークユーザー数を集計
    counts = defaultdict(int)
    users = defaultdict(set)

    for row in rows:
        try:
            tags = json.loads(row["matched_rules"])
        except (json.JSONDecodeError, TypeError):
            tags = []
        for tag in tags:
            counts[tag] += 1
            users[tag].add(row["author_id"])

    # tweet_counts に UPSERT
    aggregated_at = now.isoformat()
    with get_connection() as conn:
        for tag, count in counts.items():
            conn.execute(
                """
                INSERT INTO tweet_counts
                    (window_start, window_minutes, rule_tag,
                     tweet_count, unique_users, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(window_start, window_minutes, rule_tag)
                DO UPDATE SET
                    tweet_count  = excluded.tweet_count,
                    unique_users = excluded.unique_users,
                    created_at   = excluded.created_at
                """,
                (window_start_iso, window_minutes, tag,
                 count, len(users[tag]), aggregated_at),
            )
        conn.commit()

    print(
        f"[DB] 集計完了 ({window_minutes}分窓 / 開始:{window_start.strftime('%H:%M')}) "
        + " | ".join(f"{tag}={cnt}" for tag, cnt in counts.items())
    )


def get_counts_summary(since_minutes=10):
    """
    直近 since_minutes 分間の raw_tweets を直接集計して返す。
    tweet_counts の集計タイミングに依存しないため、短時間セッションでも正確。

    戻り値: [{"rule_tag": str, "tweet_count": int, "unique_users": int}, ...]
    """
    since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT author_id, matched_rules
            FROM raw_tweets
            WHERE received_at >= ?
            """,
            (since,),
        ).fetchall()

    counts = defaultdict(int)
    users  = defaultdict(set)
    for row in rows:
        try:
            tags = json.loads(row["matched_rules"])
        except (json.JSONDecodeError, TypeError):
            tags = []
        for tag in tags:
            counts[tag] += 1
            users[tag].add(row["author_id"])

    return [
        {"rule_tag": tag, "tweet_count": cnt, "unique_users": len(users[tag])}
        for tag, cnt in sorted(counts.items(), key=lambda x: -x[1])
    ]


def save_anomaly_score(result):
    """
    スコアリング結果を anomaly_scores に UPSERT する。
    result は scorer.run_scoring() が返す dict 形式。
    """
    scored_at = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO anomaly_scores
                (window_start, window_minutes, rule_tag,
                 current_count, unique_users, baseline_avg, baseline_days,
                 growth_rate, diversity_ratio, anomaly_score, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(window_start, window_minutes, rule_tag)
            DO UPDATE SET
                current_count   = excluded.current_count,
                unique_users    = excluded.unique_users,
                baseline_avg    = excluded.baseline_avg,
                baseline_days   = excluded.baseline_days,
                growth_rate     = excluded.growth_rate,
                diversity_ratio = excluded.diversity_ratio,
                anomaly_score   = excluded.anomaly_score,
                scored_at       = excluded.scored_at
            """,
            (
                result["window_start"], result["window_minutes"], result["rule_tag"],
                result["current_count"], result["unique_users"],
                result["baseline_avg"], result["baseline_days"],
                result["growth_rate"], result["diversity_ratio"],
                result["anomaly_score"], scored_at,
            ),
        )
        conn.commit()


def get_recent_anomaly_scores(since_minutes=30, window_minutes=5):
    """直近 since_minutes 分の anomaly_scores を anomaly_score 降順で返す。"""
    since = (datetime.now(timezone.utc) - timedelta(minutes=since_minutes)).isoformat()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM anomaly_scores
            WHERE window_start   >= ?
              AND window_minutes  = ?
            ORDER BY anomaly_score DESC
            """,
            (since, window_minutes),
        ).fetchall()
    return [dict(row) for row in rows]
