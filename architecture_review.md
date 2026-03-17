# Trend Detection System - 要件整理・アーキテクチャ検討（最新情報版）

> 最終更新: 2026-03-09

---

## 何を作るか（一言）

暗号資産関連の「エンティティ × イベントキーワード」の組み合わせ（例：Binance + hack）がXで急増した瞬間を検知し、APIまたは通知で知らせるシステム。

---

## コア要件

| 項目 | 内容 |
|---|---|
| 検知遅延 | 10分以内（理想は数分〜15分以内） |
| 更新頻度 | 1分間隔 |
| 出力 | JSON API + Webhook通知 |
| 異常スコアの基準 | 絶対数ではなく「過去1週間同時間帯比の増加倍率」 |
| ノイズ除去 | 同一ユーザーの連投・自己宣伝を低減 |
| 表記ゆれ対応 | BTC / Bitcoin / ビットコイン を同一視 |

---

## エンジニアコメントの評価（最新情報に基づく再評価）

### X API の現状（2026年2月〜）

X APIは2026年2月に**完全従量課金制（Pay-per-use）に移行**。固定月額プランは廃止。

| 操作 | 単価 |
|---|---|
| 投稿の読み取り | $0.005 / 件 |
| ユーザープロフィール取得 | $0.010 / 件 |
| 投稿の作成 | $0.010 / リクエスト |

- 月間上限：200万投稿まで（それ以上はエンタープライズ）
- 同じ投稿は24時間以内に再取得しても二重課金なし
- 自動チャージ・月次上限設定が可能

**Filtered Stream（リアルタイムストリーム）**

Pay-per-use プランで **Filtered Stream は利用可能**。エンジニアの提案（`POST /2/tweets/search/stream/rules`）は現プランで実行できる。

公式レートリミット（アプリ単位）：
- 同時接続数：**1接続**
- ルール上限：**1,000ルール**（Entity × EventKeyword の組み合わせを事前登録）
- スループット：**250投稿/秒**
- コスト：受信した投稿に対して $0.005/件

**Filtered Stream の優位点**
- ルールにマッチした投稿だけをリアルタイムで受信 → 無関係な投稿への課金なし
- 投稿の瞬間に受信するため検知遅延が最小（秒単位）
- ポーリングより**コスト効率が高い**

---

### OpenClaw について（廃止）

当初 OpenClaw をデータ処理パイプラインとして採用する案があったが、**Coinpost Terminal への接続を前提とした構成に変更**したため不要と判断。

理由：
- エンティティ抽出・表記ゆれ解決等の高度な処理は Coinpost Terminal 側の既存の自動実行の仕組みで対応可能
- 本システムはスコア・シグナルの生成に専念し、結果を JSON API で提供する役割に絞る
- AIエージェント基盤を別途導入するコスト・複雑さを回避できる

---

### 推奨アーキテクチャ

```
【データ取得】
[X API Filtered Stream]
  事前登録ルール：Entity × EventKeyword の全組み合わせ（最大1,000）
        ↓ マッチした投稿をリアルタイム受信

【収集・蓄積】
[KAGOYA Cloud VPS（Python・常時稼働）]
        ↓
[SQLite] ← ツイートデータ・ベースライン（過去7日分）蓄積

【データ処理（ルールベース）】
[scorer.py]
  - Entity × EventKeyword の 1分/5分 カウント集計
  - 過去7日間同時間帯比の増加倍率算出
  - ユニークユーザー数フィルタリング（ノイズ除去）
        ↓ 閾値超過時

【通知・外部連携】
[通知モジュール / JSON API]
  - Slack Webhook 通知
  - JSON API → Coinpost Terminal へ連携
```

**コンポーネントの役割**

| コンポーネント | 役割 |
|---|---|
| X API Filtered Stream | データ取得（公式・唯一の選択肢） |
| KAGOYA Cloud VPS | 常時稼働サーバー・SQLite 管理 |
| scorer.py | ルールベースのデータ処理・スコアリング |
| Grok | 補助的なサマリー生成・xAI クレジット還元も活用 |
| JSON API | Coinpost Terminal への検知結果の提供 |

**LLM の活用箇所**

| 用途 | 適切か | 推奨モデル |
|---|---|---|
| 異常スコア計算 | ❌ ルールベースで十分・LLMは不要 | — |
| エンティティ抽出・表記ゆれ解決 | ✅ 辞書で難しいケースに有効 | GPT-4o-mini / Grok |
| イベントキーワード分類 | ✅ 文脈理解が必要な場合に有効 | GPT-4o-mini / Grok |
| 辞書の初期生成 | ✅ 一度作れば更新は少ない | Claude / Grok |
| 検知済み異常の文脈サマリー | ✅ 通知文の品質向上に有効 | Grok（X文脈に強い） |

> 「Codexの方がUsage Limitがゆるい」は正しい。大量ツイートの一括分類なら OpenAI API（GPT-4o-mini 等）がコスト・速度面で有利。

---

### Grok API の位置付け

**データ取得には使えないが、補助レイヤーとして合理的な選択肢。**

Grok API の `x_search` ツールは「Xをリアルタイム検索して回答する」機能を持つが、返却されるのは **LLMが要約した自然言語の結果**。生のツイートデータ（件数・ユーザーID・タイムスタンプ）は取得できず、異常スコア計算には使えない。

| 用途 | Grok API x_search | X API Filtered Stream |
|---|---|---|
| リアルタイム投稿取得 | ❌ LLM要約のみ・件数は不正確 | ✅ 生データ取得 |
| 異常スコア計算用カウント | ❌ 統計的信頼性なし | ✅ 正確 |
| 検知後の文脈サマリー | ✅ 得意（X文脈に強い） | — |

**Grok を使う最大のメリット：xAI クレジット還元**

X API Pay-per-use の支出に応じて xAI クレジットが還元されるため、Grok API を補助利用するコストが実質的に下がる。

| X API 月次支出 | xAI クレジット還元率 |
|---|---|
| $200 未満 | 0% |
| $200〜$499 | 10% |
| $500〜$999 | 15% |
| $1,000 以上 | 20% |

---

## 採用構成

| レイヤー | 採用技術 | 備考 |
|---|---|---|
| データ取得 | X API Filtered Stream | 公式・Pay-per-use・$0.005/件 |
| サーバー | KAGOYA Cloud VPS | Ubuntu 22.04・常時稼働 |
| データ蓄積 | SQLite | ベースライン7日分を保持 |
| データ処理 | ルールベース（scorer.py） | OpenClaw は不採用 |
| 補助 LLM | Grok | サマリー生成・xAI クレジット還元を活用 |
| 通知・連携 | Slack Webhook / JSON API | Coinpost Terminal へ連携 |

---

## 優先度付き TODO

| 優先度 | 確認・作業 |
|---|---|
| 🔴 最優先 | エンティティ辞書・イベントキーワード辞書の設計（BTC/Bitcoin/ビットコイン等） |
| 🔴 最優先 | Filtered Stream のルール設計とコスト試算（何ルール・どの組み合わせを登録するか） |
| 🟠 高 | ベースライン計算ロジック設計（何日分保持するか・増加倍率の閾値設定） |
| 🟠 高 | OpenClaw + EC2 の構成検証（PoC） |
| 🟡 中 | 通知先・フォーマット決定（Slack / API） |
| 🟢 低 | 画像ノーマライゼーション（要件では「あれば望ましい」レベル） |

---

## 結論

- **データ取得**: X API Filtered Stream（公式・Pay-per-use）一択
- **データ処理**: ルールベース（scorer.py）で完結。OpenClaw は不採用
- **外部連携**: JSON API 経由で Coinpost Terminal へ検知結果を提供。処理の自動化は Coinpost Terminal 側で実装
- **補助**: Grok を検知後のサマリー生成に活用（xAI クレジット還元も利点）

---

## 参考リンク

- [X API Pricing (公式)](https://docs.x.com/x-api/getting-started/pricing)
- [X Pay-Per-Use 発表 (2026/02)](https://www.medianama.com/2026/02/223-x-developer-api-pricing-pay-per-use-model/)
- [OpenClaw スキルマーケットプレイス](https://github.com/VoltAgent/awesome-openclaw-skills)
- [X API Pay-Per-Use 開発者フォーラム](https://devcommunity.x.com/t/announcing-the-launch-of-x-api-pay-per-use-pricing/256476)
- [xAI Live Search 公式ドキュメント](https://docs.x.ai/docs/guides/live-search)
- [xAI Models & Pricing](https://docs.x.ai/developers/models)
