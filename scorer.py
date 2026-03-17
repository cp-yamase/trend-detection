"""
scorer.py - 異常検知（スコアリング）ロジック

スコアリング方式:
  growth_rate     = 現在カウント / ベースライン平均（過去7日同時間帯）
                    ※ ベースラインデータなし時は 1.0 を分母として使用
  diversity_ratio = ユニークユーザー数 / 総ツイート数
                    （同一ユーザーの連投スパムを抑制）
  anomaly_score   = growth_rate × diversity_ratio

アラート閾値（暫定）:
  growth_rate   >= 3.0  : ベースライン比3倍以上
  unique_users  >= 3    : 少なくとも3アカウントから発生
  anomaly_score >= 2.0  : 総合スコア

ベースラインデータが不足している間は:
  - スコアは算出・保存するが 🔍 SIGNAL として表示（🚨 ALERT とは区別）
  - 7日分のデータが蓄積されると自動的に精度が上がる
"""
from datetime import datetime, timezone, timedelta
from database import get_connection, save_anomaly_score

# ベースライン計算パラメータ
LOOKBACK_DAYS    = 7   # 過去何日分を参照するか
SLOT_MARGIN_MIN  = 15  # 同時間帯とみなす前後の分数（±15分）
MIN_BASELINE_DAYS = 3  # この日数以上あればベースライン「十分」とみなす

# アラート閾値
ALERT_GROWTH_RATE   = 3.0
ALERT_UNIQUE_USERS  = 3
ALERT_ANOMALY_SCORE = 2.0


def get_baseline(rule_tag, window_minutes, window_start_dt):
    """
    過去 LOOKBACK_DAYS 日間の同時間帯における tweet_count の平均を返す。

    同時間帯 = window_start_dt と同じ時刻 ± SLOT_MARGIN_MIN 分

    Returns:
        (baseline_avg: float, data_days: int)
        data_days == 0 のときはベースラインデータなし
    """
    margin = timedelta(minutes=SLOT_MARGIN_MIN)
    daily_counts = []

    with get_connection() as conn:
        for delta in range(1, LOOKBACK_DAYS + 1):
            past_dt    = window_start_dt - timedelta(days=delta)
            day_start  = past_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end    = day_start + timedelta(days=1)
            slot_start = (past_dt - margin).isoformat()
            slot_end   = (past_dt + margin).isoformat()

            coverage_row = conn.execute(
                """
                SELECT 1
                FROM tweet_counts
                WHERE window_minutes = ?
                  AND window_start  >= ?
                  AND window_start  <  ?
                LIMIT 1
                """,
                (window_minutes, day_start.isoformat(), day_end.isoformat()),
            ).fetchone()

            if not coverage_row:
                continue

            row = conn.execute(
                """
                SELECT AVG(tweet_count) AS avg_count
                FROM tweet_counts
                WHERE rule_tag       = ?
                  AND window_minutes = ?
                  AND window_start  BETWEEN ? AND ?
                """,
                (rule_tag, window_minutes, slot_start, slot_end),
            ).fetchone()

            if row and row["avg_count"] is not None:
                daily_counts.append(row["avg_count"])
            else:
                daily_counts.append(0.0)

    if daily_counts:
        return sum(daily_counts) / len(daily_counts), len(daily_counts)
    return 0.0, 0


def compute_score(current_count, unique_users, baseline_avg):
    """
    growth_rate / diversity_ratio / anomaly_score を計算して返す。

    Args:
        current_count : 現在ウィンドウのツイート件数
        unique_users  : 現在ウィンドウのユニークユーザー数
        baseline_avg  : 過去同時間帯の平均ツイート件数（0 の場合はデータなし）

    Returns:
        dict with growth_rate, diversity_ratio, anomaly_score
    """
    growth_rate     = current_count / max(baseline_avg, 1.0)
    diversity_ratio = unique_users  / max(current_count, 1)
    anomaly_score   = growth_rate * diversity_ratio

    return {
        "growth_rate":     round(growth_rate,     3),
        "diversity_ratio": round(diversity_ratio, 3),
        "anomaly_score":   round(anomaly_score,   3),
    }


def run_scoring(window_minutes=5, lookback_minutes=30):
    """
    直近 lookback_minutes 分の tweet_counts をスコアリングして anomaly_scores に保存する。

    Returns:
        list[dict] - スコアリング結果（anomaly_score 降順）
    """
    since = (datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)).isoformat()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT window_start, window_minutes, rule_tag, tweet_count, unique_users
            FROM tweet_counts
            WHERE window_start   >= ?
              AND window_minutes  = ?
            ORDER BY window_start DESC
            """,
            (since, window_minutes),
        ).fetchall()

    results = []
    for row in rows:
        window_start_dt = datetime.fromisoformat(row["window_start"])

        baseline_avg, data_days = get_baseline(
            row["rule_tag"], row["window_minutes"], window_start_dt
        )

        scores = compute_score(row["tweet_count"], row["unique_users"], baseline_avg)

        result = {
            "window_start":   row["window_start"],
            "window_minutes": row["window_minutes"],
            "rule_tag":       row["rule_tag"],
            "current_count":  row["tweet_count"],
            "unique_users":   row["unique_users"],
            "baseline_avg":   round(baseline_avg, 2),
            "baseline_days":  data_days,
            **scores,
        }

        save_anomaly_score(result)
        results.append(result)

    return sorted(results, key=lambda x: -x["anomaly_score"])


def classify(result):
    """
    スコアリング結果を分類する。

    Returns:
        "ALERT"  : 閾値を超えており、かつベースラインが十分（信頼度高）
        "SIGNAL" : 閾値を超えているがベースラインが不十分（要注視）
        "NORMAL" : 閾値未満（通常範囲内）
    """
    over_threshold = (
        result["growth_rate"]   >= ALERT_GROWTH_RATE
        and result["unique_users"]  >= ALERT_UNIQUE_USERS
        and result["anomaly_score"] >= ALERT_ANOMALY_SCORE
    )
    if not over_threshold:
        return "NORMAL"
    if result["baseline_days"] >= MIN_BASELINE_DAYS:
        return "ALERT"
    return "SIGNAL"


def format_score_line(result):
    """スコア1件をターミナル表示用の文字列に整形する。"""
    label = classify(result)

    if label == "ALERT":
        prefix = "🚨 ALERT "
    elif label == "SIGNAL":
        prefix = "🔍 SIGNAL"
    else:
        prefix = "   ------"

    baseline_note = (
        f"baseline={result['baseline_avg']} ({result['baseline_days']}日分)"
        if result["baseline_days"] > 0
        else "ベースラインデータなし"
    )

    window_dt = datetime.fromisoformat(result["window_start"])
    return (
        f"{prefix} | [{result['rule_tag']}] "
        f"count={result['current_count']} users={result['unique_users']} "
        f"growth={result['growth_rate']}x score={result['anomaly_score']} "
        f"| {baseline_note} | {window_dt.strftime('%H:%M')}窓"
    )
