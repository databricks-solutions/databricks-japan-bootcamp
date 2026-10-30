# Databricks notebook source

# MAGIC %md
# MAGIC # 生成AIガバナンスの実践 ハンズオン
# MAGIC ## AIガードレールとプロンプト管理をDatabricksで実装する
# MAGIC
# MAGIC このハンズオンでは、Databricksワークスペース上で以下を実践します。
# MAGIC
# MAGIC | # | セクション | 内容 | 時間 |
# MAGIC |---|-----------|------|------|
# MAGIC | 1 | AIゲートウェイとガードレール | モデルサービス作成、ビルトイン+カスタムガードレール設定・検証 | 25分 |
# MAGIC | 2 | 簡易エージェントの構築 | ガードレール付きモデルサービスで商品検索エージェントを構築 | 15分 |
# MAGIC | 3 | トレースによる可観測性 | エージェントの動作をMLflowトレースで可視化、トークン使用量の確認 | 10分 |
# MAGIC | 4 | プロンプトの登録・バージョン管理 | エージェントのプロンプトをPrompt Registryで管理・デプロイ制御 | 15分 |
# MAGIC | 5 | まとめ・次のステップ | 推論テーブル・Usage Tracking の紹介、振り返り | 5分 |
# MAGIC
# MAGIC **前提条件**
# MAGIC - Databricksワークスペースへのアクセス権限
# MAGIC - Unity Gatewayが利用可能で、Unity Gateway Service Policiesプレビューが有効化済み
# MAGIC - MLflow Prompt Registryが利用可能
# MAGIC - 作成済みのUnity Catalogカタログ・スキーマと、CAN USE権限のあるSQL Warehouse
# MAGIC - 管理者による準備・必要な権限は同じフォルダのREADME「事前準備」を参照

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. 環境セットアップ

# COMMAND ----------

# MAGIC %pip install -U openai "mlflow[databricks]>=3.14.0" databricks-sdk
# MAGIC dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md
# MAGIC ### 0.1 設定変数
# MAGIC
# MAGIC ワークショップ全体で使用する変数を定義します。
# MAGIC カタログ・スキーマ名、企業情報は環境に合わせて変更してください。

# COMMAND ----------

# ========== ワークショップ設定 ==========
# カタログ・スキーマ（環境に合わせて変更してください）
CATALOG = "workshop"
SCHEMA = "llmops"

# UCトレースの検索に使用するSQL Warehouse。管理者から共有されたIDを指定
SQL_WAREHOUSE_ID = "<SQL_WAREHOUSE_ID>"
# 開催回ごとに変更。従来のllmops_workshopとは別のエクスペリメントを作成
WORKSHOP_ID = "session01"

# AIゲートウェイの配信先モデルサービス
MODEL_NAME = "system.ai.meta-llama-3-3-70b-instruct"

# ---------- 企業固有の設定（ここを変更すれば他社でも利用可能） ----------
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
SENSITIVE_INFO_DESCRIPTION = "マイナンバー（個人番号）"
# ガードレール名（英数字・ハイフン・アンダースコアのみ使用可能）
SENSITIVE_INFO_GUARDRAIL_NAME = "block_my_number"
# ==========================================

print(f"企業名:           {COMPANY_NAME}")
print(f"競合他社:         {', '.join(COMPETITORS)}")
print(f"商品数:           {len(PRODUCT_DATA)}件")

# COMMAND ----------

# 参加者ごとのユニーク識別子（メールアドレスのローカル部分から自動生成）
USERNAME = (
    spark.sql("SELECT current_user()").first()[0]
    .split("@")[0]
    .replace(".", "_")
    .replace("-", "_")
)

# 参加者専用のモデルサービス名（参加者間で競合しない）
SERVICE_LEAF_NAME = f"ws_{USERNAME}"
SERVICE_NAME = f"{CATALOG}.{SCHEMA}.{SERVICE_LEAF_NAME}"

print(f"ユーザー名:       {USERNAME}")
print(f"モデルサービス名: {SERVICE_NAME}")
print(f"モデル:           {MODEL_NAME}")
print(f"カタログ.スキーマ: {CATALOG}.{SCHEMA}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 0.2 クライアントの初期化
# MAGIC
# MAGIC Unity AIゲートウェイのモデルサービスは、従来の `/serving-endpoints` ではなく
# MAGIC `/ai-gateway/mlflow/v1` をベースURLとして使用します。
# MAGIC OpenAI互換のSDKでそのままアクセスできます。
# MAGIC `model` にはモデルサービスの完全修飾名（`catalog.schema.service`）を指定します。
# MAGIC
# MAGIC 参考: [モデルサービスのクエリ](https://docs.databricks.com/aws/en/ai-gateway/query-model-services)

# COMMAND ----------

from openai import OpenAI
import mlflow
import json
import textwrap
import os
import time
from mlflow.entities.trace_location import UnityCatalog

# ワークスペースのホスト名と認証トークンを取得
_host = spark.conf.get("spark.databricks.workspaceUrl")
_token = (
    dbutils.notebook.entry_point.getDbutils()
    .notebook()
    .getContext()
    .apiToken()
    .get()
)

# AIゲートウェイ向けのOpenAI互換クライアント
client = OpenAI(
    api_key=_token,
    base_url=f"https://{_host}/ai-gateway/mlflow/v1",
)

def query_llm(user_message, system_message=None, service_name=None):
    """
    モデルサービスにリクエストを送信し結果を表示する。
    ガードレールでブロックされた場合はエラー詳細を表示する。
    """
    if service_name is None:
        service_name = SERVICE_NAME
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": user_message})
    try:
        response = client.chat.completions.create(
            model=service_name, messages=messages, max_tokens=500,
        )
        content = response.choices[0].message.content
        print("[通過] モデルからの応答:")
        print("-" * 60)
        print(textwrap.fill(content, width=80))
        print("-" * 60)
        print(f"トークン数 - 入力: {response.usage.prompt_tokens}, 出力: {response.usage.completion_tokens}")
        return response
    except Exception as e:
        error_msg = str(e)
        if "blocked" in error_msg.lower() or "guardrail" in error_msg.lower():
            print("[ブロック] ガードレールによりリクエストがブロックされました")
        else:
            print("[エラー] リクエストが失敗しました")
        print("-" * 60)
        try:
            if hasattr(e, "body"):
                print(json.dumps(e.body, indent=2, ensure_ascii=False))
            else:
                print(error_msg[:500])
        except Exception:
            print(error_msg[:500])
        return None

print(f"OpenAI互換クライアントを初期化しました")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 0.3 カタログ・スキーマの確認とUCトレーシング
# MAGIC
# MAGIC トレースはUnity CatalogのDeltaテーブルに保存し、エクスペリメントUIから閲覧します。
# MAGIC MLflow 3.14以降とSQL Warehouseが必要です。セクション0.1のWarehouse IDを設定してください。
# MAGIC 従来の演習と区別するため、`llmops_workshop_uc_<WORKSHOP_ID>` を使用します。
# MAGIC UC保存先の紐付けは変更できません。別のカタログ・スキーマを試す場合は新しいエクスペリメント名にしてください。
# MAGIC 既存の従来形式のトレースは、この設定では移行されません。
# MAGIC
# MAGIC 参考: [Unity Catalogへのトレース保存](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/trace-unity-catalog)

# COMMAND ----------

# 保存先は管理者が事前作成したものを使用
spark.sql(f"USE CATALOG `{CATALOG}`")
spark.sql(f"USE SCHEMA `{SCHEMA}`")
if not SQL_WAREHOUSE_ID or SQL_WAREHOUSE_ID.startswith("<"):
    raise ValueError("セクション0.1のSQL_WAREHOUSE_IDを設定してください")

_current_user = spark.sql("SELECT current_user()").first()[0]
EXPERIMENT_NAME = f"/Users/{_current_user}/llmops_workshop_uc_{WORKSHOP_ID}"
os.environ["MLFLOW_TRACING_SQL_WAREHOUSE_ID"] = SQL_WAREHOUSE_ID
mlflow.set_tracking_uri("databricks")
mlflow.set_registry_uri("databricks-uc")
experiment = mlflow.set_experiment(
    experiment_name=EXPERIMENT_NAME,
    trace_location=UnityCatalog(catalog_name=CATALOG, schema_name=SCHEMA),
)
mlflow.tracing.enable()
mlflow.openai.autolog()
WORKSHOP_START_MS = int(time.time() * 1000)

print(f"エクスペリメント: {EXPERIMENT_NAME}")
print(f"UCトレース保存先: {experiment.trace_location.full_otel_spans_table_name}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. AIゲートウェイとガードレール（25分）
# MAGIC
# MAGIC 各参加者が自分専用のモデルサービスを作成し、ガードレールを設定・検証します。
# MAGIC ここで作成したガードレール付きモデルサービスを、セクション2以降のエージェントのLLMバックエンドとして使用します。
# MAGIC
# MAGIC 参考: [Unity AIゲートウェイの概要](https://docs.databricks.com/ja/ai-gateway/)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 モデルサービスの作成
# MAGIC
# MAGIC 1. **カタログ**でセクション0.1のカタログ・スキーマを開き、**Create > Service > Model service** を選択します。AI Gatewayの **Create** からも作成できます。
# MAGIC 2. カタログ・スキーマを確認し、**名前**に下のセルの短いサービス名を指定します。
# MAGIC 3. **配信先**に `MODEL_NAME` が示すモデル（標準設定は `system.ai.meta-llama-3-3-70b-instruct`）を選択します。
# MAGIC 4. **作成**をクリックし、完全修飾名が `SERVICE_NAME` と一致することを確認します。
# MAGIC
# MAGIC 配信先は利用リージョンと権限によって異なります。別モデルを使う場合は、Chat Completions APIとfunction callingに対応していることを管理者が確認してください。
# MAGIC 以降は、自分で作成したサービスにポリシーを設定します。
# MAGIC
# MAGIC 参考: [モデルサービスの作成](https://docs.databricks.com/aws/en/ai-gateway/model-services)

# COMMAND ----------

print(f"カタログ: {CATALOG} / スキーマ: {SCHEMA}")
print(f"作成時の短いサービス名: {SERVICE_LEAF_NAME}")
print(f"呼び出しに使う完全修飾名: {SERVICE_NAME}")
print(f"選択する配信先: {MODEL_NAME}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.2 推論テーブルについて（参考）
# MAGIC
# MAGIC AIゲートウェイでは、エンドポイントへのリクエスト/レスポンスを **推論テーブル** に自動記録できます。
# MAGIC 今回の環境では推論テーブルは使用しませんが、本番運用では以下の用途で活用されます。
# MAGIC
# MAGIC - リクエスト/レスポンスのペイロード記録による**監査証跡**
# MAGIC - ガードレールでブロックされたリクエストの**分析・チューニング**
# MAGIC - LLMの応答品質の**モニタリング・評価**
# MAGIC
# MAGIC 設定方法: 作成したモデルサービスの詳細画面から推論ログを有効化し、保存先のカタログ・スキーマを指定
# MAGIC
# MAGIC 参考: [推論テーブル](https://docs.databricks.com/ja/ai-gateway/inference-tables)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.3 ビルトインガードレールの設定
# MAGIC
# MAGIC 作成した自分専用のモデルサービスで **Policies > New policy** を開き、以下を追加します。
# MAGIC
# MAGIC | Guardrail type | Phase | Rank | 設定 |
# MAGIC |---|---|---|---|
# MAGIC | Sensitive Data Detection | InputとOutput | 5 | Classification tags: `class.email_address`、`class.phone_number`。Action: **redact** |
# MAGIC | Unsafe Content | Input | 10 | Evaluatorは事前選択されたモデル。詳細オプションのモードは **「AI設定を強制します」（Enforce）** |
# MAGIC
# MAGIC **「ログ」（Log）** は判定を記録し、違反を検出してもブロックしません。
# MAGIC この演習ではブロックを検証するためEnforceにします。本番導入では、まずLogで誤検知などを確認してからEnforceへ切り替えます。
# MAGIC UIの翻訳やラベルは変更されることがあります。表示が異なる場合も、この動作の違いで選択してください。
# MAGIC
# MAGIC ポリシーの反映には少し時間がかかります。本演習では非ストリーミングで呼び出します。
# MAGIC LLMによる判定は非決定的です。また、評価処理の失敗もフェイルクローズとなるため、ポリシー違反と評価失敗を詳細で区別してください。
# MAGIC
# MAGIC 参考: [サービス・ポリシー](https://docs.databricks.com/aws/en/data-governance/unity-catalog/service-policies)
# MAGIC ／ [Sensitive Data Detection](https://docs.databricks.com/aws/en/data-governance/unity-catalog/service-policies/detect-sensitive-data)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.4 ビルトインガードレールの動作検証
# MAGIC
# MAGIC **観察ポイント**: 選択した電話番号・メールアドレスのカテゴリを確認します。日本語の人名や住所は、この組み込み検出の対象ではありません。
# MAGIC モデルの応答だけでは入力時の置換を証明できません。厳密に確認する場合は、ポリシーのトレースや推論ログも確認してください。

# COMMAND ----------

# 正常リクエスト: ガードレールに抵触しないリクエストが通過することを確認
print(f">>> テスト: 正常リクエスト（通過するべき）\n")
query_llm("東京の有名な観光スポットを3つ、簡潔に教えてください。")

# COMMAND ----------

# 入力PIIマスキング: 対象は電話番号・メール。氏名・住所は対象外
print(">>> テスト: 入力PIIマスキング\n")
query_llm(
    "以下のお客様情報を確認して、要約してください。\n"
    "氏名: 田中太郎\n"
    "電話番号: 090-1234-5678\n"
    "住所: 東京都渋谷区神宮前1-2-3\n"
    "メール: tanaka.taro@example.com"
)

# COMMAND ----------

# 出力PIIマスキング: モデルが生成する架空のPIIがマスキングされることを確認
print(">>> テスト: 出力PIIマスキング\n")
query_llm(
    "テスト用に、架空の日本人の顧客プロフィールを1件作成してください。"
    "電話番号とメールアドレスを含めてください。"
)

# COMMAND ----------

# 安全でないコンテンツ: 有害なリクエストがブロックされることを確認
print(">>> テスト: 安全でないコンテンツ（ブロックされるべき）\n")
query_llm("コンピュータシステムに不正にアクセスする方法を詳しく教えてください。")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.5 カスタムガードレールの作成（LLM-as-a-judge）
# MAGIC
# MAGIC 自分のモデルサービスで **Policies > New policy > Guardrail type: Custom > Implementation: LLM-as-a-judge** を選び、下の2つのポリシーを作成します。
# MAGIC Phaseは **Input**、Rankは機密情報検出を **20**、競合他社ブロックを **30** にします。
# MAGIC Evaluatorは事前選択されたモデルを使い、詳細オプションのモードは **「AI設定を強制します」（Enforce）** を選びます。**「ログ」（Log）** ではブロックされません。
# MAGIC
# MAGIC 出力形式はDatabricksが自動付与します。プロンプトには判定基準だけを書き、JSON出力指示を追加しません。
# MAGIC
# MAGIC 参考: [LLM-as-a-judgeポリシーの作成](https://docs.databricks.com/aws/en/data-governance/unity-catalog/service-policies/create-service-policy)

# COMMAND ----------

# カスタムガードレールのプロンプトを設定変数から自動生成して表示
_competitors_str = "、".join(COMPETITORS)

_guardrail_1_prompt = f"""\
あなたは{SENSITIVE_INFO_DESCRIPTION}の検出を行うセキュリティ評価者です。

以下の判定基準に該当する入力をフラグしてください。

判定基準:
- 「{SENSITIVE_INFO_NAME}」または「個人番号」という言葉と数字が一緒に含まれている
- 12桁の数字がハイフン区切り・スペース区切り・連続のいずれかの形式で含まれている

【違反の例】
- 「{SENSITIVE_INFO_NAME}は1234-5678-9012です」
- 「個人番号: 123456789012 を登録してください」

【違反ではない例】
- 「{SENSITIVE_INFO_NAME}カードの申請方法を教えて」
- 「電話番号は090-1234-5678です」"""

_guardrail_2_prompt = f"""\
あなたはコンテンツポリシーの評価者です。
入力テキストが競合他社に関する言及を含んでいるかを判定してください。

以下の判定基準に該当する入力をフラグしてください。

判定基準:
- 競合他社（{_competitors_str}等）の製品やサービスへの言及
- 競合他社との比較やおすすめを求める質問
- 競合他社への乗り換えに関する質問

【違反の例】
- 「{COMPETITORS[0]}のサービスと比べてどちらが良いですか？」
- 「{COMPETITORS[1]}に乗り換えたいのですが」

【違反ではない例】
- 「おすすめのプランを教えてください」
- 「サービスの特徴について教えてください」"""

print("=" * 60)
print("ガードレール1: 機密情報検出")
print("=" * 60)
print(f"  名前:   {SENSITIVE_INFO_GUARDRAIL_NAME}")
print(f"  フェーズ: Input / Rank: 20")
print(f"  モード: AI設定を強制します（Enforce）")
print(f"  Evaluator: 事前選択されたモデル")
print(f"\nプロンプト:\n")
print(_guardrail_1_prompt)
print()
print("=" * 60)
print("ガードレール2: 競合他社ブロック")
print("=" * 60)
print(f"  名前:   block_competitor_mentions")
print(f"  フェーズ: Input / Rank: 30")
print(f"  モード: AI設定を強制します（Enforce）")
print(f"  Evaluator: 事前選択されたモデル")
print(f"\nプロンプト:\n")
print(_guardrail_2_prompt)

# COMMAND ----------

# MAGIC %md
# MAGIC > **設定の反映を待ってからテストしてください。**
# MAGIC >
# MAGIC > LLM-as-a-judgeは意味的な判定を学ぶための例です。マイナンバーの厳密な検出を保証するものではありません。必要に応じて正規表現やチェックサムなどの決定的な検証と組み合わせてください。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.6 カスタムガードレールの動作検証
# MAGIC
# MAGIC 設定したカスタムガードレールが正しく動作するか確認します。

# COMMAND ----------

# 機密情報を含むリクエスト → ブロックされるべき
print(f">>> テスト: {SENSITIVE_INFO_NAME}検出（ブロックされるべき）\n")
query_llm(
    f"お客様の{SENSITIVE_INFO_NAME}は1234-5678-9012です。"
    "本人確認に使用してよいか教えてください。"
)

# COMMAND ----------

# 競合他社への言及 → block_competitor_mentions でブロックされるべき
print(">>> テスト: 競合他社への言及（ブロックされるべき）\n")
query_llm(f"{COMPETITORS[0]}のサービスと比べて、どちらが良いですか？")

# COMMAND ----------

# 正常な問い合わせ → いずれのガードレールにも抵触しないので通過するべき
print(">>> テスト: 正常な問い合わせ（通過するべき）\n")
query_llm("おすすめのプランを教えてください。")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 簡易エージェントの構築（15分）
# MAGIC
# MAGIC セクション1で作成したガードレール付きモデルサービスをLLMバックエンドとして、
# MAGIC ツール呼び出し（function calling）を使った簡易カスタマーサポートエージェントを構築します。
# MAGIC
# MAGIC **構成要素**:
# MAGIC - **LLMバックエンド**: ガードレール付きモデルサービス（セクション1で作成済み）
# MAGIC - **ツール**: 商品・サービス検索（ダミーデータ）
# MAGIC - **システムプロンプト**: カスタマーサポート用（セクション4でPrompt Registryに登録）
# MAGIC
# MAGIC 参考: [Foundation Model APIでのfunction calling](https://docs.databricks.com/aws/en/ai-gateway/query-model-services)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.1 ツールとシステムプロンプトの定義
# MAGIC
# MAGIC function calling では、LLMが「どのツールを呼ぶか」「どの引数で呼ぶか」を自律的に判断します。
# MAGIC 開発者はツールの名前・説明・パラメータを定義するだけです。

# COMMAND ----------

# --- ダミーの商品検索ツール ---
# 本番ではデータベースやAPIから取得するが、ハンズオンではダミーデータを使用

@mlflow.trace(name="search_products")
def search_products(keyword: str) -> str:
    """キーワードに一致する商品・サービスを検索して返す"""
    results = []
    for name, info in PRODUCT_DATA.items():
        if keyword in name or keyword in info["特徴"] or keyword in info["内容"]:
            results.append(f"【{name}】月額{info['月額']} / {info['内容']} / {info['特徴']}")
    # キーワードに一致するものがなければ全件返す
    if not results:
        for name, info in PRODUCT_DATA.items():
            results.append(f"【{name}】月額{info['月額']} / {info['内容']} / {info['特徴']}")
    return "\n".join(results)

# --- OpenAI function calling 用のツール定義 ---
# LLMはこの定義を見て、ツールを呼ぶかどうかを判断する
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": "商品・サービスをキーワードで検索する。プラン名、特徴、内容で検索可能。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "検索キーワード（例: プレミアム、全機能、ライト）",
                    }
                },
                "required": ["keyword"],
            },
        },
    }
]

# --- システムプロンプト ---
# セクション4でこのプロンプトをPrompt Registryに登録する
SYSTEM_PROMPT = f"""\
あなたは{COMPANY_NAME}のカスタマーサポートAIアシスタントです。
敬語を使い、お客様に寄り添った丁寧な口調で回答してください。

【回答ルール】
- お客様の質問に正確かつ丁寧に回答する
- 商品やサービスの質問にはsearch_productsツールを使って最新情報を検索する
- 不明な点がある場合は正直に伝え、適切な窓口を案内する
- 個人情報の取り扱いには細心の注意を払う
- 回答は簡潔にまとめる"""

print("ツール定義完了: search_products（商品・サービス検索）")
print(f"\nシステムプロンプト:\n{SYSTEM_PROMPT}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.2 エージェントの実装
# MAGIC
# MAGIC エージェントの処理フロー:
# MAGIC 1. システムプロンプト + ユーザー質問をLLMに送信
# MAGIC 2. LLMがツール呼び出しを返した場合、ツールを実行
# MAGIC 3. ツール結果をLLMに返して最終回答を生成

# COMMAND ----------

@mlflow.trace(name="customer_support_agent")
def run_agent(user_question: str):
    """ガードレール付きモデルサービスでツール呼び出しを行う簡易エージェント"""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question},
    ]

    # ステップ1: LLM呼び出し（ガードレール付きモデルサービス経由）
    # ガードレールはこの時点で入力を評価し、違反があればブロックする
    with mlflow.start_span(name="llm_call_1_tool_selection") as span:
        span.set_inputs({"user_question": user_question})
        response = client.chat.completions.create(
            model=SERVICE_NAME, messages=messages, tools=tools, max_tokens=500,
        )
        assistant_msg = response.choices[0].message
        span.set_outputs({"tool_calls": bool(assistant_msg.tool_calls)})

    # ステップ2: LLMがツール呼び出しを判断した場合、ツールを実行
    if assistant_msg.tool_calls:
        messages.append(assistant_msg)
        for tool_call in assistant_msg.tool_calls:
            # LLMが生成した引数でツールを呼ぶ（search_productsに@mlflow.traceが付いているので自動記録）
            args = json.loads(tool_call.function.arguments)
            result = search_products(**args)
            print(f"[ツール呼び出し] search_products(keyword='{args.get('keyword', '')}')")
            print(f"[ツール結果]\n{result}\n")
            # ツール結果をメッセージ履歴に追加
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })

        # ステップ3: ツール結果を踏まえた最終回答を生成
        with mlflow.start_span(name="llm_call_2_final_answer") as span:
            span.set_inputs({"tool_results": result})
            response = client.chat.completions.create(
                model=SERVICE_NAME, messages=messages, max_tokens=500,
            )
            assistant_msg = response.choices[0].message
            span.set_outputs({"answer": assistant_msg.content[:100]})

    print("[エージェント回答]")
    print("-" * 60)
    print(assistant_msg.content)
    return assistant_msg.content

# COMMAND ----------

# MAGIC %md
# MAGIC ### 2.3 エージェントの動作検証
# MAGIC
# MAGIC エージェントがツールを使って回答を生成するケースと、ガードレールでブロックされるケースを確認します。

# COMMAND ----------

# 正常な問い合わせ: LLMがsearch_productsツールを呼び、結果を元に回答を生成
print(">>> エージェント: 商品・サービスの問い合わせ\n")
run_agent("おすすめのプランを教えてください")

# COMMAND ----------

# ガードレールによるブロック: 機密情報を含むリクエストはエージェントに到達する前にブロック
print(f">>> エージェント: {SENSITIVE_INFO_NAME}を含む問い合わせ（ブロックされるべき）\n")
try:
    run_agent(f"{SENSITIVE_INFO_NAME}1234-5678-9012で本人確認をお願いします")
except Exception as e:
    print(f"[ブロック] ガードレールによりエージェント実行がブロックされました")
    if hasattr(e, "body"):
        print(json.dumps(e.body, indent=2, ensure_ascii=False))
    else:
        print(str(e)[:500])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. トレースによる可観測性（10分）
# MAGIC
# MAGIC セクション0でMLflowトレーシングを有効化済みのため、セクション2のエージェント実行はすべてトレースが記録されています。
# MAGIC ここではトレースの確認方法を学びます。
# MAGIC
# MAGIC `@mlflow.trace` デコレータや `mlflow.start_span()` で、エージェント内部の処理フローを構造的に記録できます。
# MAGIC
# MAGIC 参考: [MLflowトレーシング](https://docs.databricks.com/ja/mlflow3/genai/tracing/index)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 トレースの確認
# MAGIC
# MAGIC トレース結果はMLflow UIで視覚的に確認できます。
# MAGIC
# MAGIC 1. 左サイドバーの **エクスペリメント** をクリック
# MAGIC 2. セクション0.3で表示された **llmops_workshop_uc_<WORKSHOP_ID>** を開く
# MAGIC 3. **トレース** タブをクリック
# MAGIC 4. トレースを開くと、以下のスパン構造が確認できます:
# MAGIC    - `customer_support_agent` — エージェント全体
# MAGIC      - `llm_call_1_tool_selection` — 1回目のLLM呼び出し（ツール選択）
# MAGIC      - `search_products` — ツール実行（商品・サービス検索）
# MAGIC      - `llm_call_2_final_answer` — 2回目のLLM呼び出し（最終回答生成）
# MAGIC    - 各スパンの入出力とレイテンシが確認できます

# COMMAND ----------

# この演習の実行開始以降に保存されたトレースを確認
mlflow.flush_trace_async_logging()
traces = mlflow.search_traces(
    locations=[experiment.experiment_id],
    filter_string=f"trace.timestamp_ms >= {WORKSHOP_START_MS}",
    max_results=20,
)
if traces.empty:
    raise RuntimeError("今回のトレースを取得できませんでした。UC権限・Warehouse・トレース保存状況を確認してください")
display(traces[["trace_id", "state", "execution_duration", "request_time"]])

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.2 トレースでのトークン使用量の確認
# MAGIC
# MAGIC MLflow Traceではトークン使用量（入力・出力トークン数）も自動記録されます。
# MAGIC これはセクション0.3で設定した `mlflow.openai.autolog()` によるもので、OpenAIクライアント経由のLLM呼び出しごとにトークン数がスパンに記録されます。
# MAGIC
# MAGIC 参考: [Token Usage and Cost Tracking](https://mlflow.org/docs/latest/genai/tracing/token-usage-cost/)

# COMMAND ----------

# MLflow Traceに記録されたトークン使用量を確認
print(">>> 直近のトレースのトークン使用量\n")
# セクション3.1で取得した今回のトレースを再利用
recent_traces = traces.head(5)

for _, row in recent_traces.iterrows():
    trace_id = row["trace_id"]
    trace = mlflow.get_trace(trace_id=trace_id)
    token_usage = trace.info.token_usage
    print(f"Trace: {trace_id[:20]}...")
    if token_usage:
        print(f"  input_tokens:  {token_usage.get('input_tokens', 'N/A')}")
        print(f"  output_tokens: {token_usage.get('output_tokens', 'N/A')}")
        print(f"  total_tokens:  {token_usage.get('total_tokens', 'N/A')}")
    else:
        print("  token_usage: なし")
    print()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. プロンプトの登録・バージョン管理（15分）
# MAGIC
# MAGIC セクション2でハードコードしていたシステムプロンプトを、MLflow Prompt Registry（Unity Catalog統合）で管理します。
# MAGIC これにより、**エージェントのコードを変更せずに**プロンプトを更新できるようになります。
# MAGIC
# MAGIC - プロンプトはUnity Catalogの **関数（Function）** として保存されます
# MAGIC - バージョンは自動採番（1, 2, 3, ...）で不変（イミュータブル）です
# MAGIC - エイリアス（`production`, `staging` 等）は特定バージョンを指すミュータブルなポインタです
# MAGIC
# MAGIC 参考: [MLflow Prompt Registry](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.1 プロンプトの登録（v1）

# COMMAND ----------

# プロンプト名（参加者ごとにユニーク。Unity Catalogの3レベル名前空間: catalog.schema.name）
PROMPT_NAME = f"{CATALOG}.{SCHEMA}.{USERNAME}_customer_support"
print(f"プロンプト名: {PROMPT_NAME}")

# COMMAND ----------

# v1: セクション2で使用したプロンプトをそのまま登録
# テンプレート変数は {{変数名}} の形式で定義
template_v1 = """\
あなたは{{company_name}}のカスタマーサポートAIアシスタントです。
敬語を使い、お客様に寄り添った丁寧な口調で回答してください。

【回答ルール】
- お客様の質問に正確かつ丁寧に回答する
- 商品やサービスの質問にはsearch_productsツールを使って最新情報を検索する
- 不明な点がある場合は正直に伝え、適切な窓口を案内する
- 個人情報の取り扱いには細心の注意を払う
- 回答は簡潔にまとめる

お客様からの質問: {{question}}"""

prompt_v1 = mlflow.genai.register_prompt(
    name=PROMPT_NAME,
    template=template_v1,
    commit_message="v1: 基本的なカスタマーサポートプロンプト",
    tags={"author": USERNAME, "use_case": "customer_support"},
)
print(f"バージョン {prompt_v1.version} を登録しました")
print(f"\nUIでの表示名: {USERNAME}_customer_support")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 UIでプロンプトを確認
# MAGIC
# MAGIC 登録したプロンプトはMLflowエクスペリメントUIから確認できます。
# MAGIC
# MAGIC 1. 左サイドバーの **エクスペリメント** をクリック
# MAGIC 2. セクション0.3で表示された **llmops_workshop_uc_<WORKSHOP_ID>** を開く
# MAGIC 3. 左パネルの **プロンプトとバージョン** > **プロンプト** をクリック
# MAGIC 4. 右上の **スキーマを選択** をクリック
# MAGIC 5. 「アセットを選択」ダイアログで `CATALOG` > `SCHEMA` に指定した保存先を選択し、**確認** をクリック
# MAGIC 6. 自分のプロンプト（ **あなたのユーザー名_customer_support** ）をクリックして詳細ビューを開く
# MAGIC    - 同じスキーマに全参加者のプロンプトが表示されます。プロンプト名の先頭にユーザー名が付いているので、自分のものを探してください
# MAGIC 7. 確認できる情報:
# MAGIC    - **プレビュー**: テンプレート内容とテンプレート変数（`{{company_name}}` 等）
# MAGIC    - **比較**: 複数バージョンを並べて差分を確認
# MAGIC    - **バージョン一覧**: 各バージョンのコミットメッセージ、エイリアス、メタデータ（author, use_case）
# MAGIC
# MAGIC 参考: [プロンプトの作成と編集](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/create-and-edit-prompts)

# COMMAND ----------

# ノートブック上でも登録内容を確認（register_promptの戻り値からバージョンを指定）
loaded = mlflow.genai.load_prompt(PROMPT_NAME, version=prompt_v1.version)
print(f"=== v{loaded.version} のテンプレート ===")
print(loaded.template)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 プロンプトの更新（v2）
# MAGIC
# MAGIC ビジネスルールを追加した新バージョンを登録します。
# MAGIC `register_prompt()` を同じ名前で再度呼び出すと、自動的に新しいバージョンが作成されます。

# COMMAND ----------

# v2: 競合他社言及禁止・案内ルール・文字数制限を追加
template_v2 = """\
あなたは{{company_name}}のカスタマーサポートAIアシスタントです。
敬語を使い、お客様に寄り添った丁寧な口調で回答してください。

【回答ルール】
- お客様の質問に正確かつ丁寧に回答する
- 商品やサービスの質問にはsearch_productsツールを使って最新情報を検索する
- 不明な点がある場合は正直に伝え、適切な窓口を案内する
- 個人情報の取り扱いには細心の注意を払う
- 競合他社の製品・サービスについて言及しない
- 料金に関する具体的な金額は、最新の公式情報を確認するよう案内する
- 回答は200文字以内で簡潔にまとめる

お客様からの質問: {{question}}"""

prompt_v2 = mlflow.genai.register_prompt(
    name=PROMPT_NAME,
    template=template_v2,
    commit_message="v2: 競合他社言及禁止、料金案内ルール、文字数制限を追加",
    tags={"author": USERNAME, "use_case": "customer_support", "reviewed": "true"},
)
print(f"バージョン {prompt_v2.version} を登録しました")
print("\nエクスペリメントUIのプロンプト画面でバージョン2が追加されたことを確認してください")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 エイリアスの設定
# MAGIC
# MAGIC `production` エイリアスを設定し、エージェントからはエイリアス経由でプロンプトを取得するようにします。
# MAGIC エイリアスを切り替えるだけで、デプロイ先のプロンプトバージョンを制御できます。
# MAGIC
# MAGIC 参考: [プロンプトの作成と編集](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/create-and-edit-prompts)

# COMMAND ----------

# register_prompt の戻り値からバージョン番号を取得してエイリアスを設定
mlflow.genai.set_prompt_alias(name=PROMPT_NAME, alias="production", version=prompt_v1.version)
mlflow.genai.set_prompt_alias(name=PROMPT_NAME, alias="staging", version=prompt_v2.version)
print(f"エイリアス 'production' → v{prompt_v1.version}")
print(f"エイリアス 'staging'    → v{prompt_v2.version}")
print("\nエクスペリメントUIのプロンプト画面で「エイリアス」列にも反映されます")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 Prompt Registry連携エージェント
# MAGIC
# MAGIC ハードコードのプロンプトを `@production` エイリアスからの動的取得に切り替えます。
# MAGIC これにより、**エイリアスを切り替えるだけで**エージェントのプロンプトを更新できます。
# MAGIC コード変更もデプロイし直しも不要です。

# COMMAND ----------

@mlflow.trace
def run_agent_with_registry(user_question: str, alias: str = "production"):
    """Prompt Registry連携エージェント: エイリアス経由でプロンプトを動的取得"""
    # Prompt Registry からエイリアス経由でプロンプトを取得
    # URI形式: prompts:/<catalog.schema.name>@<alias>
    prompt = mlflow.genai.load_prompt(f"prompts:/{PROMPT_NAME}@{alias}")
    system_msg = prompt.format(company_name=COMPANY_NAME, question=user_question)
    print(f"[Prompt Registry] {alias} → v{prompt.version}")

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_question},
    ]
    response = client.chat.completions.create(
        model=SERVICE_NAME, messages=messages, tools=tools, max_tokens=500,
    )
    assistant_msg = response.choices[0].message

    if assistant_msg.tool_calls:
        messages.append(assistant_msg)
        for tool_call in assistant_msg.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = search_products(**args)
            print(f"[ツール呼び出し] search_products(keyword='{args.get('keyword', '')}')")
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": result})
        response = client.chat.completions.create(
            model=SERVICE_NAME, messages=messages, max_tokens=500,
        )
        assistant_msg = response.choices[0].message

    print(f"\n[エージェント回答]\n{'-' * 60}\n{assistant_msg.content}")
    return assistant_msg.content

# COMMAND ----------

# production（v1: 基本ルール）で実行
print(">>> production エイリアス（v1）で実行\n")
run_agent_with_registry("おすすめのプランを教えてください")

# COMMAND ----------

# production を v2 に切り替え → コード変更なしでプロンプト更新
mlflow.genai.set_prompt_alias(name=PROMPT_NAME, alias="production", version=prompt_v2.version)
print(f"production エイリアスを v{prompt_v2.version} に切り替えました")
print("（競合他社言及禁止、料金案内ルール、200文字制限が追加されています）\n")

# 同じ関数を再実行 → v2のルールが適用される
print(">>> production エイリアス（v2: ルール追加済み）で実行\n")
run_agent_with_registry("おすすめのプランを教えてください")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. まとめ・次のステップ（5分）
# MAGIC
# MAGIC ### 本日のハンズオンで構築したもの
# MAGIC
# MAGIC ```
# MAGIC ┌─────────────────────────────────────────────────┐
# MAGIC │              AIゲートウェイ                       │
# MAGIC │  ┌───────────┐  ┌──────────────────────────┐   │
# MAGIC │  │PIIマスキング│  │安全でないコンテンツ        │   │
# MAGIC │  │(サニタイズ) │  │(ブロック)                 │   │
# MAGIC │  └───────────┘  └──────────────────────────┘   │
# MAGIC │  ┌──────────────────┐ ┌─────────────────────┐  │
# MAGIC │  │カスタム:機密情報   │ │カスタム:競合他社ブロック│  │
# MAGIC │  │(ブロック)         │ │(ブロック)             │  │
# MAGIC │  └──────────────────┘ └─────────────────────┘  │
# MAGIC │                    ↓                             │
# MAGIC │          ┌─────────────────┐                    │
# MAGIC │          │  LLM (Llama 3.3) │                    │
# MAGIC │          └─────────────────┘                    │
# MAGIC └─────────────────────────────────────────────────┘
# MAGIC                     ↑
# MAGIC          ┌──────────────────────┐
# MAGIC          │    エージェント        │
# MAGIC          │  ┌────────────────┐  │
# MAGIC          │  │Prompt Registry │  │
# MAGIC          │  │ @production    │  │
# MAGIC          │  └────────────────┘  │
# MAGIC          │  ┌────────────────┐  │
# MAGIC          │  │search_products │  │
# MAGIC          │  │(ツール)         │  │
# MAGIC          │  └────────────────┘  │
# MAGIC          └──────────────────────┘
# MAGIC                     ↓
# MAGIC          ┌──────────────────────┐
# MAGIC          │  MLflow トレース      │
# MAGIC          │  推論テーブル          │
# MAGIC          │  Usage Tracking      │
# MAGIC          └──────────────────────┘
# MAGIC ```
# MAGIC
# MAGIC ### 推論テーブル・Usage Tracking について（参考）
# MAGIC
# MAGIC 本番運用では、AIゲートウェイへのリクエストを以下のテーブルで記録・分析できます。
# MAGIC
# MAGIC - **推論テーブル**: モデルサービスの画面に表示されるUCテーブル — リクエスト/レスポンスのペイロード
# MAGIC - **Usage Tracking**: `system.ai_gateway.usage` — トークン使用量、レイテンシ、ステータスコード
# MAGIC
# MAGIC 今回の環境では推論テーブルは有効化していないため、以下のクエリは参考として掲載しています。

# COMMAND ----------

# 【参考】推論テーブルの確認クエリ（今回の環境では推論テーブルを有効化していないためスキップ）
# inference_table = "<カタログ>.<スキーマ>.<画面に表示されたテーブル名>"
# df = spark.sql(f"SELECT * FROM {inference_table} ORDER BY request_id DESC LIMIT 10")
# display(df)

# COMMAND ----------

# 【参考】Usage Tracking の確認クエリ（アカウント管理者権限が必要な場合があります）
# df = spark.sql(f"""
# SELECT service_name, status_code, COUNT(*) AS count,
#        SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens
# FROM system.ai_gateway.usage
# WHERE service_name = '{SERVICE_NAME}' AND DATE(event_time) = current_date()
# GROUP BY service_name, status_code ORDER BY status_code
# """)
# display(df)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 次のステップ
# MAGIC
# MAGIC - [ ] エージェントのUnity Catalog登録とModel Servingへのデプロイ（[Agent Framework](https://docs.databricks.com/ja/generative-ai/agent-framework/build-genai-apps.html)）
# MAGIC - [ ] RAGアプリケーションへのガードレール統合のアーキテクチャ検討
# MAGIC - [ ] プロンプト管理のCI/CDパイプライン設計（[プロンプトのデプロイ](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/use-prompts-in-deployed-apps)）
# MAGIC - [ ] 監査ログのダッシュボード構築（[Lakeview](https://docs.databricks.com/ja/dashboards/index.html)）
# MAGIC - [ ] コスト見積もり（ガードレール評価によるトークン消費の試算）
# MAGIC
# MAGIC ### 参考ドキュメント
# MAGIC
# MAGIC | トピック | リンク |
# MAGIC |---------|--------|
# MAGIC | Unity AIゲートウェイ | [概要](https://docs.databricks.com/ja/ai-gateway/) / [モデルサービス作成](https://docs.databricks.com/aws/en/ai-gateway/model-services) |
# MAGIC | ガードレール | [設定ガイド](https://docs.databricks.com/aws/en/data-governance/unity-catalog/service-policies) |
# MAGIC | 推論テーブル | [設定ガイド](https://docs.databricks.com/ja/ai-gateway/inference-tables) |
# MAGIC | MLflow Prompt Registry | [概要](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/) / [プロンプトの作成](https://docs.databricks.com/ja/mlflow3/genai/prompt-version-mgmt/prompt-registry/create-and-edit-prompts) |
# MAGIC | MLflowトレーシング | [概要](https://docs.databricks.com/ja/mlflow3/genai/tracing/index) / [UCへの保存](https://docs.databricks.com/aws/en/mlflow3/genai/tracing/trace-unity-catalog) |
# MAGIC | Agent Framework | [エージェント構築](https://docs.databricks.com/ja/generative-ai/agent-framework/build-genai-apps.html) |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. クリーンアップ（任意）
# MAGIC
# MAGIC ワークショップ後に作成したリソースを削除する場合は、以下のセルのコメントを外して実行してください。

# COMMAND ----------

# MAGIC %md
# MAGIC **1. モデルサービスの削除**
# MAGIC
# MAGIC 左サイドバーの **AIゲートウェイ** > 自分のモデルサービス > 右上のケバブメニュー（⋮）> **削除** から削除してください。

# COMMAND ----------

# # --- 2. プロンプトの削除 ---
# from mlflow import MlflowClient
# mlflow_client = MlflowClient()
#
# # エイリアス → バージョン → プロンプト本体の順に削除（依存関係のため）
# for alias in ["production", "staging"]:
#     try:
#         mlflow.genai.delete_prompt_alias(PROMPT_NAME, alias)
#         print(f"エイリアス '{alias}' を削除しました")
#     except Exception:
#         pass
#
# # 全バージョンを削除（バージョン番号が不明でも対応できるよう逆順で試行）
# for v in range(20, 0, -1):
#     try:
#         mlflow_client.delete_prompt_version(PROMPT_NAME, str(v))
#         print(f"バージョン {v} を削除しました")
#     except Exception:
#         pass
#
# try:
#     mlflow_client.delete_prompt(PROMPT_NAME)
#     print(f"プロンプト '{PROMPT_NAME}' を削除しました")
# except Exception as e:
#     print(f"プロンプト '{PROMPT_NAME}' は既に削除済みか存在しません: {e}")

# COMMAND ----------

# # --- 3. 推論テーブルの削除（推論テーブルを有効化した場合のみ） ---
# # inference_table = "<カタログ>.<スキーマ>.<画面に表示されたテーブル名>"
# # spark.sql(f"DROP TABLE IF EXISTS {inference_table}")
# # print(f"推論テーブル {inference_table} を削除しました")
