# Trend Detection System - 開発ロードマップ

## フェーズ一覧

### ✅ フェーズ1: 基盤構築と安全なストリーム開通（完了）

**目的**: プロジェクト骨格の構築と X API Filtered Stream の疎通確認

- [x] プロジェクト構成設計（`requirements.txt`, `database.py`, `x_stream.py`）
- [x] SQLite テーブル設計（`raw_tweets`, `tweet_counts`）
- [x] Filtered Stream への接続・受信・DB保存の実装
- [x] テスト用キーワードによる安全な動作確認（`main.py`）

---

### ✅ フェーズ2: 本番キーワード適用・集計処理の実装（完了）

**目的**: PoC用の実キーワードで受信し、1分/5分の集計レコードを生成する

- [x] PoC用ルール定義（3件・マイナス検索によるノイズ除外）（`rules_config.py`）
- [x] 集計ロジックの実装（`aggregate_counts` を `database.py` に追加）
- [x] `connect_stream` に `max_tweets` 上限引数を追加（`x_stream.py`）
- [x] 安全装置付き PoC 実行スクリプト（`main_poc.py`）
  - **安全装置**: 5分経過 または 50件受信 で自動切断

---

### ✅ フェーズ3: 異常検知（スコアリング）ロジックの実装（完了）

**目的**: 過去データとのベースライン比較で「増加倍率」を算出する

- [x] ベースライン取得関数（同時間帯・過去7日間の平均カウント）（`scorer.py`）
- [x] 異常スコア算出（growth_rate × diversity_ratio）（`scorer.py`）
- [x] スコアリング結果のDB保存（`anomaly_scores` テーブル追加）（`database.py`）
- [x] 60秒ごとのリアルタイムスコア表示（`main_poc.py` 統合）

---

### ✅ フェーズ2.5: ベースラインシード（完了）

**目的**: Recent Search Counts API で過去7日分のカウントデータを一括投入し、即日ベースライン比較を可能にする

- [x] `GET /2/tweets/counts/recent` によるカウント一括取得（`seed_baseline.py`）
- [x] per-minute → 5分窓への集計・DB投入
- [x] 実データ優先（既存レコードは上書きしない）

---

### ✅ フェーズ4: 通知モジュールの実装（完了）

**目的**: 閾値を超えた異常をリアルタイムで通知する

- [x] ターミナル通知（フォールバック）（`notifier.py`）
- [x] Slack Webhook 通知（`notifier.py`・`SLACK_WEBHOOK_URL` を `.env` に設定）
- [x] クールダウン制御（同一ルールへの連続通知を 10 分間抑制）
- [x] `main_poc.py` へのスコアリング後自動通知を統合
- [ ] JSON API エンドポイント（将来の外部連携用・未着手）

---

### ✅ フェーズ5: 本番サーバーへのデプロイ（完了）

**目的**: 24時間365日稼働する本番環境を構築する

- [x] 本番用エントリーポイント作成（`main_prod.py`）
  - 安全装置なし・無制限稼働
  - ストリーム切断時の指数バックオフ自動再接続（5秒〜最大300秒）
  - ログファイル出力（`logs/trend_detection.log`）
- [x] VPS契約・インスタンス作成（KAGOYA Cloud VPS・Ubuntu 22.04）
- [x] SSH接続確認
- [x] Python環境セットアップ（`python3-venv`）
- [x] プロジェクトファイルの転送（`rsync`）
- [x] `.env` ファイルの設置
- [x] ベースラインデータの移行（`tweets.db`）
- [x] systemd サービス設定・常時起動化

---

### 🔄 フェーズ6: ルール拡張・スケールアップ（進行中）

**目的**: PoC用の3ルールから、実運用規模（数十〜数百ルール）へ拡張する

- [x] エンティティ辞書の設計（`entities.py`）— BTC / Bitcoin / ビットコイン 等の表記ゆれ統一
- [x] イベントキーワード辞書の設計（`event_keywords.py`）— hack / exploit / breach 等のカテゴリ分類
- [x] Entity × EventKeyword のルール組み合わせ自動生成（`rules_config.py`）— 現在 930ルール
- [x] CoinGecko API によるエンティティ自動更新（`update_entities.py`, `entities_auto.json`）
  - 毎日上位100コイン・上位50取引所を取得し新規エンティティを自動追加
  - 新規追加があればサービスを自動再起動
- [x] VPS での cron 設定（毎日4時に `update_entities.py` を自動実行）
  - 推奨設定: `0 4 * * * cd /root/trend_detection && /root/trend_detection/venv/bin/python update_entities.py >> logs/update_entities.log 2>&1`
- [x] Filtered Stream の1,000ルール上限に対するルール優先度設計
  - `rules_config.py` でカテゴリ優先度を導入し、上限超過時は上位ルールを残す
- [x] ルール追加時の `seed_baseline.py` 再実行フロー整備
  - `python seed_baseline.py --missing-only` で未投入ルールのみ7日分を取得
- [x] スコアリング閾値のチューニング（ゼロウィンドウバイアスの解消）
  - 現状：ツイート0件の時間帯がベースラインに含まれず平均が高くなる問題
  - 対応: `seed_baseline.py` でゼロ件窓も保持し、`scorer.py` でもカバレッジがある日は 0 件として平均に反映

---

### ~~フェーズ7: OpenClaw統合~~（廃止）

**廃止理由**: Coinpost Terminal への接続を前提とする構成に変更。エンティティ抽出・表記ゆれ解決等のデータ処理は Coinpost Terminal 側の既存の自動実行の仕組みで対応する。本システムはスコア・シグナルの生成に専念し、AIエージェント基盤の導入は不要と判断。

---

### フェーズ7: Grok統合（検知後サマリー生成）（未着手）

**目的**: 異常検知後の通知品質を高め、担当者が即座に状況判断できるようにする

- [ ] Grok API（`x_search`）連携モジュール実装
- [ ] 異常検知トリガー時に Grok でXの文脈サマリーを自動生成
- [ ] Slack 通知へのサマリー文添付
- [ ] xAI クレジット還元の活用確認（X API月次支出 $200以上から適用）

---

### フェーズ8: JSON API + Coinpost Terminal連携（未着手）

**目的**: 検知結果を Coinpost Terminal から参照・利用できるAPIを提供する

- [ ] FastAPI による JSON API エンドポイント実装
  - `GET /scores` — 直近の異常スコア一覧
  - `GET /scores/{rule_tag}` — ルール別スコア履歴
- [ ] 認証（APIキー方式）
- [ ] VPS への API サーバーデプロイ（systemd サービス追加）
- [ ] Coinpost Terminal との接続設計・実装

---

## 採用スタック（確定）

| レイヤー | 技術 |
|---|---|
| データ取得 | X API Filtered Stream（Pay-per-use・$0.005/件） |
| サーバー | KAGOYA Cloud VPS（Ubuntu 22.04・常時稼働） |
| データ蓄積 | SQLite |
| データ処理 | ルールベース（scorer.py）|
| 補助 LLM | Grok（サマリー生成・xAI クレジット還元） |
| 通知・連携 | Slack Webhook / JSON API / Coinpost Terminal |
