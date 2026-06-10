# 生成AIガバナンスの実践 ハンズオン

Databricks上で**AIガードレール**と**プロンプト管理**を実装するワークショップのハンズオンノートブックです。

## 概要

| # | セクション | 内容 | 時間 |
|---|-----------|------|------|
| 1 | AIゲートウェイとガードレール | エンドポイント作成、ビルトイン+カスタムガードレール設定・検証 | 25分 |
| 2 | 簡易エージェントの構築 | ガードレール付きエンドポイントで商品検索エージェントを構築 | 15分 |
| 3 | トレースによる可観測性 | エージェントの動作をMLflowトレースで可視化、トークン使用量の確認 | 10分 |
| 4 | プロンプトの登録・バージョン管理 | エージェントのプロンプトをPrompt Registryで管理・デプロイ制御 | 15分 |
| 5 | まとめ・次のステップ | 推論テーブル・Usage Trackingの紹介、振り返り | 5分 |

## 構成図

```
┌─────────────────────────────────────────────────┐
│              AIゲートウェイ                       │
│  ┌───────────┐  ┌──────────────────────────┐   │
│  │PIIマスキング│  │安全でないコンテンツ        │   │
│  │(サニタイズ) │  │(ブロック)                 │   │
│  └───────────┘  └──────────────────────────┘   │
│  ┌──────────────────┐ ┌─────────────────────┐  │
│  │カスタム:機密情報   │ │カスタム:競合他社ブロック│  │
│  │(ブロック)         │ │(ブロック)             │  │
│  └──────────────────┘ └─────────────────────┘  │
│                    ↓                             │
│          ┌─────────────────┐                    │
│          │  LLM (Llama 3.3) │                    │
│          └─────────────────┘                    │
└─────────────────────────────────────────────────┘
                    ↑
         ┌──────────────────────┐
         │    エージェント        │
         │  ┌────────────────┐  │
         │  │Prompt Registry │  │
         │  │ @production    │  │
         │  └────────────────┘  │
         │  ┌────────────────┐  │
         │  │search_products │  │
         │  │(ツール)         │  │
         │  └────────────────┘  │
         └──────────────────────┘
                    ↓
         ┌──────────────────────┐
         │  MLflow トレース      │
         │  推論テーブル          │
         │  Usage Tracking      │
         └──────────────────────┘
```

## 前提条件

- Databricksワークスペースへのアクセス権限
- Unity AIゲートウェイ（Beta）が Account Console Previews で有効化済み
- MLflow Prompt Registry（Beta）が Workspace Previews で有効化済み

## カスタマイズ

ノートブック冒頭の設定変数を変更することで、任意の企業・業種向けにカスタマイズできます。

```python
# 自社名
COMPANY_NAME = "サンプル株式会社"

# 競合他社リスト（カスタムガードレールで使用）
COMPETITORS = ["A社", "B社", "C社"]

# ダミーの商品/サービスデータ（エージェントのツールで使用）
PRODUCT_DATA = {
    "プレミアムプラン": {"月額": "9,800円", "内容": "全機能利用可能", "特徴": "フルサポート付き"},
    "スタンダードプラン": {"月額": "4,980円", "内容": "主要機能利用可能", "特徴": "コストパフォーマンス重視"},
    "ライトプラン": {"月額": "1,980円", "内容": "基本機能のみ", "特徴": "ライトユーザー向け"},
}

# カスタムガードレールで検出する機密情報の種類
SENSITIVE_INFO_NAME = "マイナンバー"
SENSITIVE_INFO_GUARDRAIL_NAME = "block_my_number"
```

## 参考ドキュメント

| トピック | リンク |
|---------|--------|
| Unity AIゲートウェイ | [概要](https://docs.databricks.com/ja/ai-gateway/) / [エンドポイント設定](https://docs.databricks.com/ja/ai-gateway/configure-endpoints-beta) |
| ガードレール | [設定ガイド](https://docs.databricks.com/ja/ai-gateway/guardrails) |
| 推論テーブル | [設定ガイド](https://docs.databricks.com/ja/ai-gateway/inference-tables) |
| MLflow Prompt Registry | [概要](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/) / [プロンプトの作成](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/create-and-edit-prompts) |
| MLflowトレーシング | [概要](https://docs.databricks.com/ja/mlflow3/genai/tracing/index) |
| Agent Framework | [エージェント構築](https://docs.databricks.com/ja/generative-ai/agent-framework/build-genai-apps.html) |
