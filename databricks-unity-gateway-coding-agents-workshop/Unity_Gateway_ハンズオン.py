# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Unity GatewayでClaude Codeを使う
# MAGIC
# MAGIC **ugは、Claude CodeをDatabricksのUnity GatewayにつなぐCLIです。** ワークスペースで公開したモデルや予算・ポリシーを使って開発し、その利用状況まで確認します。
# MAGIC
# MAGIC **DatabricksのUnity Gatewayを使うと、使い慣れたClaude CodeやCodexから、対応するGLM・KimiなどのOSS系モデルも選べます。** `ug claude`や`ug codex`で接続し、モデルの選択肢を広げながら、権限・予算・ポリシー・利用記録をDatabricksで管理できます。この本編ではClaude Codeを使って体験します。
# MAGIC
# MAGIC このワークショップ単独で受講できます。演習用のモデルサービスとポリシーはセクション4で作成します。既存のサービス・ポリシーがある場合は、任意で再利用できます。
# MAGIC
# MAGIC 実行環境を選べます。**PCに導入したくない場合はブラウザコース**で、DatabricksのWeb Terminalを使います。**ローカルコース**ではPCへの導入・ユーザー設定の適用・終了後の復元まで体験します。どちらも画面の設定はDatabricksで行います。
# MAGIC
# MAGIC | コース | `ug`を実行する場所 | 認証・設定の範囲 |
# MAGIC |---|---|---|
# MAGIC | ブラウザ（推奨） | このNotebookのServerless Web Terminal | Web Terminalの本人の認証を再利用。Serverless環境のユーザー設定へ適用 |
# MAGIC | ローカル | 自分のPCのターミナル | 本人がOAuthでログイン。PCのユーザー設定へ適用 |
# MAGIC
# MAGIC **ブラウザコースでも、ワークスペースの共通設定・予算・モデルサービスへの変更は他の利用者に影響します。** 演習用ワークスペースと、自分が管理するサービスを使います。まずはセクション1.1でClaude Codeを起動するところまで進めましょう。
# MAGIC
# MAGIC | 章 | 内容 | 目安 |
# MAGIC |---|---|---|
# MAGIC | 0 | 開始前の確認とugの導入 | 10〜15分 |
# MAGIC | 1 | Coding Agent設定・ugで接続 | 20分 |
# MAGIC | 2 | 開発課題・Smart Routing | 15分 |
# MAGIC | 3 | 予算管理・Smart defaults | 10分 |
# MAGIC | 4 | モデルサービス・ポリシーの作成とClaude Codeからの利用 | 25分 |
# MAGIC | 5 | 予算フォールバック・標準のUsage Dashboard | 10分 |
# MAGIC | 6 | 統合トレースをGenie Codeで分析 | 10分 |
# MAGIC | 7 | 振り返り・復元 | 10分 |
# MAGIC
# MAGIC 本編は画面操作が中心です。Pythonセルは手順に沿って実行し、表示されたJSONやコマンドを使います。準備の詳細は、<a href="$./事前準備ガイド">別の事前準備ガイド</a>で確認できます。
# MAGIC 本編と準備ガイドの2つを、ファイル名を変えずに同じWorkspaceフォルダへPython Notebookとしてインポートしてください。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 0. 始める前に3つだけ確認
# MAGIC
# MAGIC - **環境**：演習用ワークスペースでNotebookを実行できる。設定公開と予算作成を行うため、ワークスペース管理者権限がある。
# MAGIC - **実行環境**：ブラウザコースは、このNotebookをServerlessへ接続し、Web Terminalを利用できる。ローカルコースはPCにPython 3.12以降・Databricks CLI・uv・Claude Codeを準備する。詳しくは<a href="$./事前準備ガイド">準備ガイドの「1. 実行環境の準備」</a>を確認する。
# MAGIC - **元の設定**：既存のAgent configurationのJSONを保存した。ローカルコースでは、普段の接続先と起動方法も控えた。
# MAGIC
# MAGIC **講師・管理者へ**：権限・プレビューと、演習開始前のトレース収集は<a href="$./事前準備ガイド">事前準備ガイド</a>に沿って準備してください。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 0.1 実行するターミナルを準備する
# MAGIC
# MAGIC #### ブラウザコース
# MAGIC
# MAGIC 1. **この本編Notebook**をServerlessに接続します。右側の **Terminal, Logs** からWeb Terminalを開きます。Web Terminalが無効なら、講師・管理者が[利用条件](https://docs.databricks.com/aws/ja/compute/web-terminal)を確認します。
# MAGIC 2. 以下をWeb Terminalで実行します。PC側で実行するコマンドではありません。`uv`はこの検証環境に導入済みでした。見つからない場合は[uvの公式手順](https://docs.astral.sh/uv/getting-started/installation/)で、このWeb Terminal内へ導入します。
# MAGIC 3. **以後も同じNotebookの同じTerminalセッションを使います。** 別Notebookで開いたTerminalは別環境になる場合があります。準備ガイドを読むために画面を切り替えた場合も、Terminal右側のセッション一覧で本編のセッションを選びます。
# MAGIC
# MAGIC ```bash
# MAGIC export PATH="$HOME/.local/bin:$PATH"
# MAGIC uv --version
# MAGIC uv tool install --python 3.12 git+https://github.com/databricks/unity-gateway@03952a3fec7e6c35e4e90d2528e54b4ec147b41c
# MAGIC curl -fsSL https://claude.ai/install.sh | bash -s 2.1.323
# MAGIC ug --version
# MAGIC ug --help
# MAGIC claude --version
# MAGIC ```
# MAGIC
# MAGIC `ug`は実機検証したコミット、Claude Codeは実機検証したバージョンに固定しています。すでに別バージョンを導入済みの場合は、講師が動作を確認してから更新してください。Claude Codeは[公式のネイティブ版](https://code.claude.com/docs/en/setup#install-claude-code)を使うため、npmは不要です。
# MAGIC
# MAGIC #### ローカルコース
# MAGIC
# MAGIC **PCのターミナル**にPython 3.12以降・Databricks CLI・uv・Claude Codeを準備します。ugはブラウザコースと同じ検証済みコミットを使います。既に導入済みの場合は、会社や導入元の更新手順に従ってください。
# MAGIC
# MAGIC ```bash
# MAGIC export PATH="$HOME/.local/bin:$PATH"
# MAGIC uv tool install --python 3.12 git+https://github.com/databricks/unity-gateway@03952a3fec7e6c35e4e90d2528e54b4ec147b41c
# MAGIC ug --version
# MAGIC ```
# MAGIC
# MAGIC 会社がClaude CodeやUGの設定を管理している場合は、<a href="$./事前準備ガイド">準備ガイドの「1. 実行環境の準備」と「6. 開始前の記録と終了後の復元」</a>を確認してください。
# MAGIC
# MAGIC どちらも接続は、ワークスペースの設定を公開した後、セクション1.1で行います。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 0.2 Notebookを準備する
# MAGIC
# MAGIC まず次のPythonセルを**演習開始前に実行**し、入力欄を作成します。ワークスペースURL・自分のユーザー・選択したコースが表示され、分析の開始時刻も初期値として記録されます。
# MAGIC
# MAGIC 実行後、Notebook左側の「パラメータ」パネルを開き、`terminal`で`browser`または`local`を選びます。既定は`browser`です。`catalog`・`schema`には、セクション4でサービスを作成する保存先を指定します。既定値は`unity-gateway-workshop.hands_on`です。**コース・保存先・再利用するサービスを変更したら、この設定セルを再実行します。** `budget_id`など他の入力欄は、使う章で案内します。
# MAGIC
# MAGIC 保存先の準備やモデル一覧の変更が必要な場合は、<a href="$./事前準備ガイド">準備ガイドの「4. Notebookの設定」</a>を参照してください。
# MAGIC SQLでハイフンを含むカタログ名を指定するときは、`` `unity-gateway-workshop`.hands_on ``のように、その名前をバッククォートで囲みます。

# COMMAND ----------

import copy
import hashlib
import json
import re
import shlex
from datetime import datetime, timezone

from databricks.sdk import WorkspaceClient

dbutils.widgets.dropdown("terminal", "browser", ["browser", "local"], "実行するターミナル")
dbutils.widgets.text("catalog", "unity-gateway-workshop", "新規サービスのカタログ")
dbutils.widgets.text("schema", "hands_on", "新規サービスのスキーマ")
dbutils.widgets.text("existing_service", "", "既存サービスの完全修飾名（再利用する場合のみ）")
dbutils.widgets.text("budget_id", "", "予算ID（セクション3.1で入力）")
dbutils.widgets.text("analysis_start_utc", datetime.now(timezone.utc).isoformat(timespec="seconds"), "分析開始時刻（タイムゾーン付き）")

TERMINAL = dbutils.widgets.get("terminal").strip()
if TERMINAL not in {"browser", "local"}:
    raise ValueError("terminalにはbrowserまたはlocalを指定してください。")
CATALOG = dbutils.widgets.get("catalog").strip()
SCHEMA = dbutils.widgets.get("schema").strip()
EXISTING_SERVICE = dbutils.widgets.get("existing_service").strip()

# UIで選択するモデルと同じ名前にします。個人のサービス名は設定しません。
SYSTEM_MODELS = [
    "system.ai.claude-opus-5",
    "system.ai.claude-sonnet-5",
    "system.ai.claude-haiku-4-5",
]

w = WorkspaceClient()
current_user = w.current_user.me().user_name


def workshop_service_name(catalog, schema, user_name, existing_service=""):
    """通常は演習用の新しい名前を生成し、再利用時は指定された名前を保持する。"""
    local_name = user_name.split("@")[0].lower()
    username = re.sub(r"[^a-z0-9_]+", "_", local_name).strip("_") or "user"
    # +などの追加文字を含む名前が、通常の名前と同じサービス名になるのを避ける。
    if re.search(r"[^a-z0-9_.-]", local_name) or len(username) > 220:
        suffix = hashlib.sha256(user_name.encode("utf-8")).hexdigest()[:10]
        username = f"{username[:220]}_{suffix}"
    name = existing_service.strip() or f"{catalog}.{schema}.coding_agent_{username}"
    parts = name.split(".")
    if len(parts) != 3 or any(not part or "/" in part or part != part.strip() for part in parts):
        raise ValueError("モデルサービス名はcatalog.schema.serviceの完全修飾名で指定してください。")
    return name


WORKSHOP_SERVICE = workshop_service_name(CATALOG, SCHEMA, current_user, EXISTING_SERVICE)
SERVICE_CATALOG, SERVICE_SCHEMA, SERVICE_ID = WORKSHOP_SERVICE.split(".")
print(f"ワークスペース: {w.config.host}")
print(f"ユーザー: {current_user}")
print(f"コース: {'ブラウザ（このNotebookのWeb Terminal）' if TERMINAL == 'browser' else 'ローカル（PCのターミナル）'}")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 準備用セル：そのまま実行
# MAGIC
# MAGIC 次のセルは、後の章で使う設定表示を準備します。そのまま実行したら、セクション1へ進みます。

# COMMAND ----------

CONFIG_API = "/api/ai-gateway/v2/coding-agent-configs"
SERVER_FIELDS = {
    "name", "create_time", "update_time", "retrieved_time", "created_user_id",
    "updated_user_id", "workspace_id", "spec_version", "etag",
}
CLAUDE_AGENT = "CODING_AGENT_CLAUDE_CODE"


def read_agent_config(client):
    response = client.api_client.do("GET", CONFIG_API)
    configs = response.get("coding_agent_configs", [])
    if len(configs) > 1:
        raise RuntimeError("複数の公開設定が返りました。対象を管理者に確認してください。")
    return configs[0] if configs else None


def editable_config(config):
    return {k: copy.deepcopy(v) for k, v in (config or {}).items() if k not in SERVER_FIELDS}


def configure_claude(config, models, *, smart_routing):
    if not models or len(models) != len(set(models)):
        raise ValueError("モデル名を重複なく1つ以上指定してください。")
    if any(len(name.split(".")) != 3 for name in models):
        raise ValueError("モデルにはcatalog.schema.serviceの完全修飾名を指定してください。")
    if smart_routing and any(not name.startswith("system.ai.") for name in models):
        raise ValueError("Smart Routingではsystem.aiだけを指定してください。")
    result = editable_config(config)
    agents = result.setdefault("enabled_agents", [])
    matches = [a for a in agents if a.get("agent") == CLAUDE_AGENT]
    if len(matches) > 1:
        raise ValueError("Claude Codeの設定が重複しています。UIで確認してください。")
    if not matches:
        agents.append({"agent": CLAUDE_AGENT, "config": {}})
    claude = next(a for a in agents if a.get("agent") == CLAUDE_AGENT)["config"]
    claude["models"] = {"model_services": list(models)}
    defaults = claude.setdefault("default_models", {})
    defaults["default_model"] = models[0]
    # 現在設定されているモデル系列も含め、一覧外の既定値を残さないようにします。
    for key, old_model in list(defaults.items()):
        if old_model not in models:
            defaults[key] = models[0]
    for family in ("opus", "sonnet", "haiku"):
        match = next((m for m in models if f"claude-{family}" in m), models[0])
        defaults[f"default_{family}_model"] = match
    claude.setdefault("smart_routing", {})["enabled"] = smart_routing
    claude.setdefault("tracing", {})["enabled"] = True
    result.setdefault("default_agent", CLAUDE_AGENT)
    for tier in result.get("smart_defaults", {}).get("tiers", []):
        if tier.get("recommended_agent") == CLAUDE_AGENT and tier.get("recommended_model") not in models:
            raise ValueError("既存のSmart defaultsが一覧外のモデルを指定しています。UIで確認してください。")
    return result


def configured_claude_models(config):
    """この演習で使用するClaude Codeの明示的なモデル一覧を取得する。"""
    agents = [a for a in config.get("enabled_agents", []) if a.get("agent") == CLAUDE_AGENT]
    if len(agents) != 1:
        raise ValueError("先にセクション1でClaude Codeを有効にしてください。")
    models = agents[0].get("config", {}).get("models", {}).get("model_services")
    if not isinstance(models, list) or not models:
        raise ValueError("先にセクション1でClaude Codeのモデル取得元をmodel_servicesの一覧に設定してください。unity_catalog_locationのままではこの例を生成できません。")
    return models


def publish_agent_config(client, baseline, proposed, fields, *, apply=False):
    """既定では表示のみ。反映直前に変更の有無を確認します。"""
    if not set(fields) <= {"default_agent", "enabled_agents", "smart_defaults"}:
        raise ValueError("この演習で更新しない項目が指定されています。")
    print(json.dumps(proposed, ensure_ascii=False, indent=2))
    if not apply:
        print("表示のみです。UIで設定済みの場合はコードからの反映は不要です。")
        return None
    latest = read_agent_config(client)
    version = lambda c: (c.get("name"), c.get("update_time")) if c else None
    if version(latest) != version(baseline) or editable_config(latest) != editable_config(baseline):
        raise RuntimeError("設定が変更されています。作成セルを再実行して内容を確認してください。")
    if latest:
        name = latest["name"]
        if not name.startswith("coding-agent-configs/") or len(name.split("/")) != 2:
            raise ValueError("設定のリソース名を確認してください。")
        body = {field: copy.deepcopy(proposed[field]) for field in fields}
        return client.api_client.do(
            "PATCH", f"/api/ai-gateway/v2/{name}",
            query={"update_mask": ",".join(fields)}, body=body,
        )
    return client.api_client.do("POST", CONFIG_API, body=editable_config(proposed))


def messages_supported(service):
    return "anthropic/v1/messages" in service.get("supported_api_types", [])

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. UIでCoding Agentを設定する
# MAGIC
# MAGIC 1. **Unity Gateway > Govern > Agent configuration > Edit configuration** を開きます。
# MAGIC 2. Claude Codeを有効にし、モデルの取得元を`models.model_services`の一覧にします。`SYSTEM_MODELS`と同じモデルを指定します。
# MAGIC 3. `default_models`に一覧内の既定モデルを指定し、`smart_routing.enabled`と`tracing.enabled`を`true`にします。
# MAGIC 4. **Save** で公開します。既存の既定Agent・Codex・MCP・Skills設定は残してください。この演習では`ug claude`でAgentを明示して起動します。
# MAGIC
# MAGIC 次のセルはUIに設定するJSONの例を表示します。モデル名をUIと合わせてから実行してください。
# MAGIC
# MAGIC 参考: [Coding Agentの設定](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-configure-govern) / [設定項目](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-config-schema)

# COMMAND ----------

phase1_baseline = read_agent_config(w)
phase1_config = configure_claude(phase1_baseline, SYSTEM_MODELS, smart_routing=True)
APPLY_PHASE1 = False  # UIで設定済みならFalseのまま。コードで反映する場合だけTrueへ変更。
publish_agent_config(w, phase1_baseline, phase1_config, ["enabled_agents"], apply=APPLY_PHASE1)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 1.1 選んだ環境へ適用してClaude Codeを起動
# MAGIC
# MAGIC 次のセルを実行すると、`terminal`で選んだコースのコマンドが表示されます。**ブラウザはこの本編NotebookのWeb Terminal、ローカルはPCのターミナル**へ、表示されたブロック全体をコピーして実行します。
# MAGIC
# MAGIC #### ブラウザコースの接続方法
# MAGIC
# MAGIC Web Terminalに用意されている本人の`DATABRICKS_TOKEN`を、ug用の`DATABRICKS_BEARER`へ環境変数として渡します。**PATの発行・認証用URLのコピー・別Terminalからのコールバックは不要です。** これは固定版ugの実装を利用した検証済みの接続方法です。認証情報はAgentの実行環境にも渡るため、環境変数の全表示を依頼せず、この演習のサンプルコードで進めます。適用範囲と制約は<a href="$./事前準備ガイド">準備ガイド1</a>を確認してください。
# MAGIC
# MAGIC `UG_SKIP_OS_SETTINGS=1`により、公開設定を取得してServerless環境のユーザー設定へ適用します。sudoやOS全体の管理設定への書き込みは行いません。**`--user`への置き換えはできません。** 検証したugでは、ワークスペースが公開設定を持つ場合に`--user`は拒否されます。会社のPCの管理設定を解除するための手順ではありません。
# MAGIC
# MAGIC この設定は今のTerminalセッション内で有効です。Terminalを新しく開いたら、同じブロックを再実行します。認証が期限切れになった場合はTerminalを再接続してから実行してください。常に`ug claude`経由で起動します。
# MAGIC
# MAGIC #### ローカルコースの接続方法
# MAGIC
# MAGIC 初回は本人がブラウザでOAuth認証します。このコースでも`UG_SKIP_OS_SETTINGS=1`を使い、OS全体の管理設定への書き込みを省きます。本人のユーザー設定へ適用し、毎回`ug claude`で起動します。接続先の固定をマシン全体へ配布する操作は行いません。
# MAGIC
# MAGIC ugの接続状態やユーザー設定は作業フォルダを分けても共通です。会社が管理しているOS設定があれば引き続き優先されるため、会社の案内を確認してください。開始前の記録・終了後の復元はセクション7と<a href="$./事前準備ガイド">準備ガイドのセクション6</a>を参照してください。
# MAGIC
# MAGIC #### 起動後の確認（両コース共通）
# MAGIC
# MAGIC 初回にテーマ・作業フォルダの信頼・フックの確認が出た場合は、内容と対象フォルダを確認して進めます。Claude Code内で`/status`を入力します。
# MAGIC
# MAGIC - **Anthropic base URL**が自分のワークスペースの`/ai-gateway/anthropic`になっている。
# MAGIC - **Model**が設定したモデルになっている。
# MAGIC - `/model`で指定したモデルの一覧が表示される。
# MAGIC
# MAGIC 他のワークスペースが表示された場合は、`ug configure`に指定したURLと適用先を確認してください。公開設定を変更した後は、同じTerminalで`ug configure --workspace ... --agent claude`を再実行してから起動します。ブラウザコースでは上記の環境変数が設定された状態で実行します。
# MAGIC
# MAGIC 参考: [Web Terminal](https://docs.databricks.com/aws/ja/compute/web-terminal) / [ugのユーザー設定モード（検証した実装）](https://github.com/databricks/unity-gateway/blob/03952a3fec7e6c35e4e90d2528e54b4ec147b41c/src/ucode/managed_files.py#L187) / [公開設定の適用と保存](https://github.com/databricks/unity-gateway/blob/03952a3fec7e6c35e4e90d2528e54b4ec147b41c/docs/managed-workspace-policy.md)

# COMMAND ----------

def build_terminal_commands(workspace_url, terminal):
    """認証情報の値を取得せず、選択したコースの接続コマンドを表示用に生成する。"""
    if terminal not in {"browser", "local"}:
        raise ValueError("terminalにはbrowserまたはlocalを指定してください。")
    configure = f"ug configure --workspace {shlex.quote(workspace_url)} --agent claude"
    if terminal == "browser":
        return "\n".join([
            'if [ -n "${DATABRICKS_TOKEN:-}" ]; then',
            '  export PATH="$HOME/.local/bin:$PATH"',
            '  export UG_SKIP_OS_SETTINGS=1',
            '  export DATABRICKS_BEARER="$DATABRICKS_TOKEN"',
            f"  {configure} &&",
            '  mkdir -p "$HOME/ug-workshop" &&',
            '  cd "$HOME/ug-workshop" &&',
            "  ug claude",
            "else",
            '  echo "この本編NotebookのWeb Terminalを開き直してください。認証情報が見つかりません。"',
            "fi",
        ])
    return "\n".join([
        'export PATH="$HOME/.local/bin:$PATH"',
        'export UG_SKIP_OS_SETTINGS=1',
        f"{configure} &&",
        'mkdir -p "$HOME/ug-workshop" &&',
        'cd "$HOME/ug-workshop" &&',
        "ug claude",
    ])


print(build_terminal_commands(w.config.host, TERMINAL))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. 開発課題とSmart Routing
# MAGIC
# MAGIC Smart Routingは、サブエージェントへ渡す作業に合うモデルを選びます。メインセッションは既定モデルで動作します。モデルを手動で選び直さず、作業を分担させてみます。
# MAGIC
# MAGIC Claude Codeに次の内容を入力してください。外部サービスへの接続や追加ライブラリは不要です。
# MAGIC
# MAGIC ```text
# MAGIC 在庫を集計する小さなPython CLIを作ってください。
# MAGIC products.csvには以下を保存してください。
# MAGIC id,name,category,price,stock
# MAGIC A001,Laptop,devices,120000,3
# MAGIC A002,Mouse,accessories,3000,10
# MAGIC A003,Monitor,devices,30000,5
# MAGIC A004,Keyboard,accessories,8000,4
# MAGIC A005,Headset,accessories,6000,0
# MAGIC
# MAGIC 作業をサブエージェントに分担してください。
# MAGIC 1. summarize.pyを作成。標準ライブラリのcsvを使い、総在庫数・在庫金額・カテゴリ別在庫金額を表示してください。
# MAGIC 2. 作成されたコードを別のサブエージェントでレビューし、unittestで集計値を確認してください。
# MAGIC 最後にpython3 summarize.py products.csvとテストを実行してください。
# MAGIC ```
# MAGIC
# MAGIC 期待する集計値は総在庫数 **22**、在庫金額 **572,000**、devices **510,000**、accessories **62,000** です。
# MAGIC
# MAGIC ### 確認すること
# MAGIC
# MAGIC - Claude Codeがファイルを作成し、コードとテストを実行できた。
# MAGIC - サブエージェントのルーティング通知で、選ばれたモデルを確認できた。
# MAGIC - 必ず違うモデルが選ばれるとは限りません。同じモデルが選ばれても正常です。
# MAGIC
# MAGIC 通知を見逃した場合は、Claude Codeを終了し、同じTerminalで`~/.ucode/claude-smart-routing-decisions.jsonl`を確認できます。その後、`ug claude`で再開します。ブラウザコースでは別NotebookのTerminalへ移らないでください。記録がない場合は、設定の再適用とサブエージェントへの作業の委譲を確認してください。
# MAGIC
# MAGIC 参考: [Smart Routingの動作と制限](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-costs#understand-smart-routing)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. 予算を設定する
# MAGIC
# MAGIC **Governance Hubから、自分のワークスペースを対象にしたUnity Gatewayの予算を作成します。** この手順はワークスペース管理者で実施できます。開催前に、アカウント管理者が **Governance Hub** プレビューを有効にしておきます（<a href="$./事前準備ガイド">準備ガイド3</a>）。
# MAGIC
# MAGIC 1. ワークスペース上部の切替メニューから **Manage account** を選び、アカウントコンソールを開きます。**Governance > Cost** でGovernance Hubのコスト画面へ進みます。
# MAGIC 2. 右上のスコープを**自分が管理するワークスペース**にし、**Budgets > View all budgets > Add budget** へ進みます。
# MAGIC 3. 対象製品を **Unity Gateway**、対象ワークスペースを自分の演習環境に設定します。共有の予算、またはユーザー別の上限を設定します。金額は自分の環境に合わせて決めてください。
# MAGIC 4. **Send alert** は通知、**Block usage** は利用停止です。違いを確認して保存します。作成者にはその予算の管理権限が付きます。
# MAGIC 5. Smart defaultsも試す場合は、作成した予算の`budget_configuration_id`を控え、Notebook左側の「パラメータ」パネルの`budget_id`に入力します。そのまま下の**3.1のセルだけ**を実行します。
# MAGIC
# MAGIC Claude Codeを終了し、**同じTerminal**で`ug usage`、必要に応じて`ug usage --all`を実行します。確認後は`ug claude`で再開します。ブラウザコースでは、セクション1.1の環境設定が有効な状態で実行します。予算が表示されない場合は、適用対象のユーザー・ワークスペースと **Block usage** の設定を確認してください。
# MAGIC
# MAGIC **予算を消化する必要はありません。** 利用停止は近リアルタイムの推定に基づくため、請求額の厳密な上限ではありません。
# MAGIC
# MAGIC 予算はGovernance HubのUIで作成します。Unity Gateway側やアカウント全体を対象にした予算作成では、アカウント管理者の権限が必要になります。
# MAGIC
# MAGIC 参考: [Governance Hubの利用権限](https://docs.databricks.com/aws/ja/admin/governance-hub#access-and-permissions) / [Cost画面の予算管理](https://docs.databricks.com/aws/ja/admin/governance-hub/cost#view-and-manage-budgets) / [Unity Gatewayの予算](https://docs.databricks.com/aws/ja/ai-gateway/budgets)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 3.1 Smart defaults：次回起動の既定モデルを変える
# MAGIC
# MAGIC 例は「予算を80%消化したら、次回起動の既定モデルをHaikuにする」です。実行中の会話のモデルは変わりません。Smart Routingとは別の設定です。
# MAGIC
# MAGIC 左側の「パラメータ」パネルの`budget_id`に、直前に作成した予算のIDを入力し、**次のセルだけ**を実行します。IDを変更した場合もこのセルだけ再実行します。セクション0.2へ戻る必要はありません。
# MAGIC
# MAGIC 表示された`smart_defaults`を、UIのAgent configurationのJSONへ`enabled_agents`と同じ階層で追加して保存します。HaikuはClaude Codeのモデル一覧にも含めてください。
# MAGIC
# MAGIC この機能はBetaです。アカウントの **Enhanced Unity Gateway** プレビューが必要です。体験が難しい場合は設定内容の確認までで進めてください。

# COMMAND ----------

BUDGET_ID = dbutils.widgets.get("budget_id").strip()
smart_defaults_config = None
if not BUDGET_ID:
    print("Smart defaultsは任意です。試す場合は、左側のパラメータのbudget_idに作成した予算のIDを入力し、このセルだけ再実行してください。")
else:
    smart_defaults_baseline = read_agent_config(w)
    smart_defaults_config = editable_config(smart_defaults_baseline or phase1_config)
    haiku = next((m for m in configured_claude_models(smart_defaults_config) if "claude-haiku" in m), None)
    if not haiku:
        raise ValueError("先にHaikuをClaude Codeのモデル一覧に追加してください。")
    smart_defaults_config["smart_defaults"] = {
        "budget_id": BUDGET_ID,
        "tiers": [{"spending_percentage": 0.8, "recommended_agent": CLAUDE_AGENT, "recommended_model": haiku}],
    }
    APPLY_SMART_DEFAULTS = False
    publish_agent_config(w, smart_defaults_baseline, smart_defaults_config, ["smart_defaults"], apply=APPLY_SMART_DEFAULTS)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. モデルサービスとポリシーを作り、Claude Codeから使う
# MAGIC
# MAGIC 前半は`system.ai`のモデルサービスを直接利用しました。この章では、自分のモデルサービスを作り、その入口にポリシーを設定します。Claude Code側は自分のサービス名を指定して呼び出します。
# MAGIC
# MAGIC ```text
# MAGIC Claude Code → 自分のモデルサービス → 配信先モデル（Haikuなど）
# MAGIC                  入力ポリシー
# MAGIC ```
# MAGIC
# MAGIC ### 4.1 モデルサービスを新規作成する
# MAGIC
# MAGIC 1. 次のセルを実行して、作成先とサービス名を表示します。カタログ・スキーマが未作成なら、<a href="$./事前準備ガイド">準備ガイドの「2. ワークスペースと権限」</a>を参照して準備します。
# MAGIC 2. カタログエクスプローラーで、表示されたカタログ・スキーマを開き、**Create > Service > Model service** を選びます。**Unity Gateway > Create** からも作成できます。
# MAGIC 3. 名前には表示された短いサービス名を入力します。配信先は、Messages APIに対応する **Claude Haiku 4.5**（配信先モデル名の例：`system.ai.databricks-claude-haiku-4-5`）を選びます。提供されていない場合は、開催環境で確認済みのMessages API対応モデルを選んでください。
# MAGIC 4. 主配信先を1つ、トラフィックを100%にして作成します。完全修飾名が`WORKSHOP_SERVICE`と一致することを確認します。
# MAGIC
# MAGIC **作成済みの場合**：セクション0.2の`existing_service`にその完全修飾名を入力し、0.2の設定セルを再実行してください。既存サービスは作り直さず、4.2へ進みます。同名のサービスが既にある場合も、ルーティングと所有者を確認して再利用してください。
# MAGIC
# MAGIC 参考: [モデルサービスの作成・必要な権限](https://docs.databricks.com/aws/ja/ai-gateway/model-services)
# MAGIC
# MAGIC 次のセルは作成する名前を表示するだけです。サービスの作成はUIで行います。

# COMMAND ----------

if EXISTING_SERVICE:
    print(f"作成を省略し、既存サービスを再利用: {WORKSHOP_SERVICE}")
else:
    print(f"カタログ: {SERVICE_CATALOG} / スキーマ: {SERVICE_SCHEMA}")
    print(f"作成時の短いサービス名: {SERVICE_ID}")
    print(f"作成予定の完全修飾名: {WORKSHOP_SERVICE}")
    print("配信先の例: system.ai.databricks-claude-haiku-4-5")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.2 サービスと対応APIを確認する
# MAGIC
# MAGIC カタログエクスプローラーで、自分のサービスの **ルーティング** と **ポリシー** を確認します。対応APIは次のセルでも確認できます。
# MAGIC
# MAGIC **Claude Codeは`anthropic/v1/messages`への対応が必要です。** 新規作成では対応するHaikuなどを選びます。Chat Completions APIだけを公開する既存サービスは、そのままではClaude Codeから利用できません。再利用する場合は、サービスの対応APIに`anthropic/v1/messages`が含まれることを確認してください。これは権限不足やポリシーによる拒否とは別の問題です。
# MAGIC
# MAGIC #### なぜClaude CodeやCodexからOSS系モデルを使えるのか
# MAGIC
# MAGIC Agentが必要とするAPI形式をDatabricks側が提供するため、対応するOSS系モデルも同じAgentから呼び出せます。たとえば、Claude CodeはMessages APIでUnity Gatewayを呼び出し、その先の対応モデルサービスでGLMやKimiを利用できます。**Claude Codeという開発ツールを使いながら、応答するモデルを選べる**ことが、この仕組みの価値です。
# MAGIC
# MAGIC | Agent | 接続に必要なAPI | 利用するモデル |
# MAGIC |---|---|---|
# MAGIC | Claude Code | Anthropic Messages API | Claude、対応するGLM・Kimiなど |
# MAGIC | Codex | OpenAI Responses API | GPT、対応するOSS系モデル |
# MAGIC
# MAGIC `ug` CLIは接続先・認証・モデルの設定とAgentの起動を担当し、モデルへのAPI接続を提供するのはDatabricks側のUnity Gatewayです。接続先などを手動で設定する方法もありますが、この演習では`ug`で設定をまとめて適用します。
# MAGIC
# MAGIC モデルの選択画面に表示されるには、対象モデルへの権限があり、ワークスペースのCoding Agent設定で利用が許可されている必要があります。`ug claude`または`ug codex`で起動した後、`/model`で利用可能なモデルを確認します。GLMなどが表示されない場合は、講師・管理者に設定を確認してください。標準の演習はClaudeモデルだけでも進められます。
# MAGIC
# MAGIC 対応モデル・API・ツール呼び出しなどの機能は、Agentと開催環境によって異なります。このNotebookでは次のセルでサービスの対応APIを確認し、4.5で通常の開発操作とポリシーの動作を確かめます。
# MAGIC
# MAGIC 対応APIにMessages APIがない場合だけ、下記の手順で同じサービスの配信先を変更し、この確認セルを再実行します。既に対応している場合は4.3へ進みます。ポリシーによる拒否が表示されたことだけでは、通常のコード作成にも使えるとは判断できません。
# MAGIC
# MAGIC 参考: [OSSモデルをClaude Code・Codexで使う](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-open-source-models) / [Claude Codeの接続・手動設定](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-claude) / [Codexの接続・手動設定](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-codex) / [クライアントごとのAPI要件](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-configure-govern#choose-model-sources-for-each-agent)

# COMMAND ----------

from databricks.sdk.errors import NotFound

print(f"利用するモデルサービス: {WORKSHOP_SERVICE}")
workshop_service = None
can_use_in_claude = False
try:
    workshop_service = w.api_client.do("GET", f"/api/2.1/unity-catalog/model-services/{WORKSHOP_SERVICE}")
except NotFound as e:
    print(f"{WORKSHOP_SERVICE}を取得できません。新規作成の場合は4.1を完了してください。再利用の場合はexisting_serviceの完全修飾名・接続先（{w.config.host}）・アクセス権限を確認してください。")
    print(f"APIエラー: {e}")
else:
    can_use_in_claude = messages_supported(workshop_service)
    print("対応API:", workshop_service.get("supported_api_types", []))
    print("現在のルーティング:", json.dumps(workshop_service.get("config", {}).get("routing", {}), ensure_ascii=False, indent=2))
    if not can_use_in_claude:
        print("Messages APIが対応APIにありません。セクション4.2で配信先を変更し、この確認セルを再実行してください。")

# COMMAND ----------

# MAGIC %md
# MAGIC #### Messages APIに非対応の場合だけ配信先を変更する
# MAGIC
# MAGIC ここでは、**サービス名と付与済みのポリシーを引き継ぎ、配信先のモデルを変更する**ことを体験します。Claude Codeに接続するために、別のサービスを作り直す必要はありません。既にMessages APIに対応している場合は変更不要です。
# MAGIC
# MAGIC 1. 自分の演習用サービスの **ルーティング** を開き、現在の配信先と設定を保存します。他の利用者も使うサービスの場合は、影響範囲を管理者と確認してください。
# MAGIC 2. 配信先の編集画面で、Messages APIに対応するDatabricks提供モデルを選びます。本編の例は **Claude Haiku** です。発展として **GLM 5.3** や **Kimi K3** などの対応するOSS系モデルを選ぶと、Claude Codeを使いながら応答モデルを変更する構成を試せます。表示されるモデルと自分の権限を確認して選んでください。
# MAGIC 3. この演習では主配信先を1つ、トラフィックを100%にします。サービス名・付与済みポリシー・レート制限を維持して保存します。
# MAGIC 4. **セクション4.2の確認セルを再実行**し、自分のサービスの`supported_api_types`に`anthropic/v1/messages`が含まれることを確認します。含まれない場合は登録へ進まず、配信先と権限を確認してください。
# MAGIC 5. **ポリシー** の画面で、既存のポリシーが同じサービスに残っていることを確認します。
# MAGIC
# MAGIC | モデル候補 | UIで選択する配信先モデル名の例 |
# MAGIC |---|---|
# MAGIC | Claude Haiku 4.5 | `system.ai.databricks-claude-haiku-4-5` |
# MAGIC | GLM 5.3 | `system.ai.databricks-glm-5-3` |
# MAGIC | Kimi K3 | `system.ai.databricks-kimi-k3` |
# MAGIC
# MAGIC これらは2026年11月10日に開催環境の対応APIと配信先を確認した例です。前半のCoding Agentモデル一覧に指定する`system.ai.claude-haiku-4-5`などの**モデルサービス名**と、上表の**配信先モデル名**は異なります。モデルの提供状況は環境に合わせて確認してください。
# MAGIC
# MAGIC API対応を確認できても、ツール呼び出しやコード実行を含む動作はモデルごとに確認が必要です。セクション4.5の通常操作とポリシーの両方を試します。サービスの配信先を変更しても、自作サービスがSmart Routingの対象になるわけではありません。
# MAGIC
# MAGIC 参考: [モデルサービスの更新と権限](https://docs.databricks.com/aws/ja/ai-gateway/model-services#update-a-model-service) / [対応Agentとモデル](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-supported-agents)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.3 入力ポリシーを1つ作成する
# MAGIC
# MAGIC Claude Codeの通常の開発操作を通しつつ、競合企業の比較を拒否するポリシーを作ります。**既存サービスで同等のポリシーを設定済みの場合は作成不要です。** ポリシー名・判定基準・Enforceモードを確認し、4.4へ進んでください。
# MAGIC
# MAGIC 1. 自分のモデルサービスで **Policies > New policy** を開きます。
# MAGIC 2. **Name**を`block_competitor_comparison`、**Guardrail type**を**Custom**、**Implementation**を**LLM-as-a-judge**にします。
# MAGIC 3. **Phase**は**Input guardrails（ON CALL）**、**Rank**は`30`にします。**Evaluator model service**は既定の選択を使います。変更する場合は、そのモデルサービスへの権限を確認してください。
# MAGIC 4. **Prompt**に次の判定基準を入力します。
# MAGIC
# MAGIC ```text
# MAGIC あなたは業務用コーディングアシスタントへの入力を審査します。
# MAGIC 入力がDatabricksとBigQueryまたはSnowflakeの機能・価格・優劣の比較を
# MAGIC 求めている場合にフラグしてください。
# MAGIC 通常のコード作成、CSVの読み取り、在庫集計、ファイル操作、
# MAGIC または比較を求めていない単なる製品名の言及はフラグしないでください。
# MAGIC ```
# MAGIC
# MAGIC 5. **Mode**を**Enforce**にして **Create policy** を選びます。この演習では自分の演習用サービスで拒否を確認します。反映に1～2分かかる場合があるため、次の接続設定を進めてから検証します。
# MAGIC
# MAGIC JSONや`ALLOW`・`DENY`などの出力形式はプロンプトに指定しません。Databricksが構造化出力の指示を追加します。LLMによる判定には揺らぎがあるため、本番導入時はLogモードで判定を確認し、調整してからEnforceへ移行します。
# MAGIC
# MAGIC 既存のポリシーを再利用する場合は、そのポリシーに指定された競合企業や判定基準に合わせて動作を確認します。この例に合わせて作り直す必要はありません。
# MAGIC
# MAGIC 参考: [LLM-as-a-judgeポリシーの作成・検証](https://docs.databricks.com/aws/ja/data-governance/unity-catalog/service-policies/create-service-policy#create-an-llm-as-a-judge-policy)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.4 Coding Agent設定へ追加（Messages APIに対応している場合）
# MAGIC
# MAGIC 1. **Unity Gateway > Govern > Agent configuration > Edit configuration** を開きます。
# MAGIC 2. Claude Codeの`smart_routing.enabled`を`false`にします。Smart Routingの対象は`system.ai`だけなので、自作サービスを使う後半では無効にします。
# MAGIC 3. Claude Codeの`models.model_services`に、4.1で表示された完全修飾名`WORKSHOP_SERVICE`を追加して保存します。新規・再利用のどちらも同じ手順です。既存のモデルも残します。
# MAGIC 4. Claude Codeを終了し、**セクション1.1と同じTerminal**で`ug configure --workspace ... --agent claude`を再実行してから、`ug claude`で起動します。ブラウザコースでは環境変数の設定を維持します。Terminalを開き直した場合は、1.1のブロック全体を再実行します。
# MAGIC 5. `/model`で自分のサービスを選びます。画面の案内に従い、このセッションだけの選択にできます。
# MAGIC
# MAGIC UIで設定するJSONを次のセルで表示できます。Messages APIに対応しない場合は設定を生成しません。

# COMMAND ----------

phase2_config = None
if can_use_in_claude:
    phase2_baseline = read_agent_config(w)
    phase2_source = phase2_baseline or phase1_config
    current_models = configured_claude_models(phase2_source)
    phase2_models = list(dict.fromkeys([*current_models, WORKSHOP_SERVICE]))
    phase2_config = configure_claude(phase2_source, phase2_models, smart_routing=False)
    APPLY_PHASE2 = False
    publish_agent_config(w, phase2_baseline, phase2_config, ["enabled_agents"], apply=APPLY_PHASE2)
else:
    print("対応APIの確認が完了するまで、Coding Agent設定への追加は実行しません。")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 4.5 通常の操作とポリシーを確認する
# MAGIC
# MAGIC 自分のサービスを選べた場合は、Claude Codeで次を確認します。
# MAGIC
# MAGIC 1. **通常の操作**：「products.csvを読み、在庫数が最も多い商品を教えてください」。ファイル読み取りが動き、Mouseと回答できることを確認します。
# MAGIC 2. **ポリシーによる拒否**：「DatabricksとBigQueryを比較してください」と質問します。既存のポリシーを再利用する場合は、そこで指定した競合企業や判定基準に合わせます。
# MAGIC 3. 拒否メッセージに`block_competitor_comparison`、または再利用したポリシー名が表示されることを確認します。Claude Codeが再試行し、複数回拒否される場合があります。
# MAGIC 4. `/clear`または新しいセッションで、通常の操作に戻れることを確認します。
# MAGIC
# MAGIC ### トレースで確認
# MAGIC
# MAGIC **Unity Gateway > Govern > Traces** で、ユーザー・時刻・サービス名を絞り込み、該当する呼び出しを開きます。
# MAGIC
# MAGIC - 対象サービスが`WORKSHOP_SERVICE`である。
# MAGIC - Claude Codeからの呼び出しが`anthropic/v1/messages`の経路になっている。
# MAGIC - 拒否の場合は`DENY`とポリシー名を確認する。
# MAGIC
# MAGIC **HTTPステータスだけでは判断しません。ポリシー拒否でもHTTP 200になる場合があります。** また、ポリシー評価の失敗でも拒否されるため、詳細の理由を確認してください。
# MAGIC
# MAGIC Coding Agentの呼び出しは統合トレースで確認します。MLflowエクスペリメントの作成は不要です。セクション1の`tracing.enabled`だけでは保存先の作成は行われません。
# MAGIC
# MAGIC 統合トレースが未設定の場合、アカウントの **Enhanced Unity Gateway** プレビューを有効にしたうえで、メタストア管理者が **Govern > Traces > Set up tracing** からカタログ・スキーマを選択して保存します。**記録の収集は有効化後に始まるため、設定後に通常の操作とポリシーの確認を再実行します。** 準備できない場合はトレース閲覧を省略してください。設定済みでも記録が表示されない場合は、保存先へのアクセス権限と反映状況を確認します。
# MAGIC
# MAGIC 参考: [Coding Agentの利用状況とトレース](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-observability#tracing)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 予算フォールバックと標準ダッシュボード
# MAGIC
# MAGIC ### 5.1 サービスの予算フォールバックを確認する
# MAGIC
# MAGIC 自分のモデルサービスの **ルーティング** を開きます。**予算フォールバック** が表示される環境では、配信先としきい値を設定できます。表示されない場合は説明までで進めてください。
# MAGIC
# MAGIC 例として「予算を80%消化したら、安いモデルへ切り替える」構成を考えます。OpusからHaikuへの切り替えが一例ですが、自分のサービスの配信先をこの例に合わせて変更する必要はありません。配信先の選択では、API互換性、品質、費用を確認します。
# MAGIC
# MAGIC ```text
# MAGIC 予算のしきい値に達する前：同じサービス名 → 通常の配信先
# MAGIC 予算のしきい値に達した後：同じサービス名 → 予算フォールバック先
# MAGIC ```
# MAGIC
# MAGIC **同じセッション内でも、次のモデル呼び出しから配信先が変わります。** 実行中の応答を途中から別のモデルへ引き継ぐ動きではありません。設定後の配信先も対応API・ポリシーが期待どおり動くか確認します。
# MAGIC
# MAGIC | 機能 | いつ変わるか | 変わるもの |
# MAGIC |---|---|---|
# MAGIC | Smart Routing | サブエージェントへの作業の委譲時 | 作業に使うモデル |
# MAGIC | Smart defaults | 次回の起動時 | 既定のAgent・モデル |
# MAGIC | サービスの予算フォールバック | 予算のしきい値に達した後の呼び出し時 | 同じサービスの配信先 |
# MAGIC | 可用性フォールバック | 429・5xxなどで通常の配信先が失敗した場合 | 再試行する配信先 |
# MAGIC
# MAGIC **予算を使い切る操作は行いません。** 予算フォールバックは、予算による利用停止を回避する機能ではありません。事前に取得した切り替え前後のトレースや録画がある場合は講師が紹介します。
# MAGIC
# MAGIC この章はUIで確認します。予算フォールバックの公開API・更新項目は、通常の可用性フォールバックと同じとは扱いません。

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.2 標準のUsage Dashboardで利用状況を確認する（3分）
# MAGIC
# MAGIC Unity Gatewayには、**あらかじめ用意されたテンプレートから作成できるUsage Dashboard**があります。自分でSQLやグラフを作る前に、標準の画面で利用状況・支出・Coding Agent・Smart Routing・パフォーマンスを確認できます。
# MAGIC
# MAGIC 1. **Unity Gateway > Govern > Usage Dashboard** を開きます。新しいタブにダッシュボードが表示されます。環境によっては **View Dashboard** ボタンから開きます。
# MAGIC 2. 日付範囲を選びます。アカウント範囲のダッシュボードでは **Workspace ID** でも絞れます。閲覧を許可された範囲のデータを使って確認してください。
# MAGIC 3. 次のタブで、これまでの演習と対応する指標を確認します。
# MAGIC
# MAGIC | タブ | 確認する内容 |
# MAGIC |---|---|
# MAGIC | Overview（概要）・Spend（支出） | リクエスト・トークン・利用者・支出の推移、モデル別の内訳 |
# MAGIC | Coding Agents | Agentの利用状況、セッション、サブエージェント、トークン消費量 |
# MAGIC | Smart Routing | 利用状況、選択されたモデルの構成、推定節約額 |
# MAGIC | Performance | 応答時間、キャッシュヒット率、エラー、レート制限 |
# MAGIC
# MAGIC **未作成の場合**：アカウント管理者が **Govern > Create Usage Dashboard** から、**Account usage**または**Workspace usage**を選んで初期作成します。公開時にはデータ権限を共有するか、閲覧者個別の権限で実行するかを選びます。自動選択されるSQL Warehouseと参照システムテーブルへの権限も必要です。ワークショップでは講師の準備済み画面で紹介しても構いません。
# MAGIC
# MAGIC 基になる`system.ai_gateway.usage`の記録は**通常1時間以内**に利用可能になります。新しいワークスペースではさらに時間がかかる場合があります。ダッシュボードを再読み込みしても未到着の記録は表示されないため、当日の操作が見えない場合は、閲覧権限のある過去データか講師の画面で確認します。
# MAGIC
# MAGIC この標準ダッシュボードは利用状況・支出を把握する入口です。次章では**統合トレースのUCテーブル**を使い、自分の呼び出しやポリシー拒否をGenie Codeで詳しく分析します。ダッシュボードのUsageデータと統合トレースは別のデータソースなので、対象範囲・期間・反映時刻を確認して読み取ります。
# MAGIC
# MAGIC 参考: [モデルの使用状況・組み込みダッシュボード](https://docs.databricks.com/aws/ja/ai-gateway/usage-tracking)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. 統合トレースをGenie Codeで分析する
# MAGIC
# MAGIC 今回使ったCoding Agentの呼び出しは、収集を準備した場合、統合トレースのUnity Catalogテーブルに記録されます。**データを別の場所へコピーせず、自然言語でSQLを作り、そのまま分析する**ことを体験します。Genie Codeへ指示するのはDatabricksの画面で行います。開発用のClaude Codeとは入力先が異なります。
# MAGIC
# MAGIC ### 6.1 Genie Codeに保存先を探してもらう（2分）
# MAGIC
# MAGIC 1. **Govern > Traces**で、演習中の自分の呼び出しを確認します。通常の呼び出しと、セクション4のポリシー拒否を探してください。
# MAGIC 2. 左側の「パラメータ」パネルの`analysis_start_utc`が演習開始前の時刻になっていることを確認し、次のセルを実行します。**保存先を探す指示と、サービス名・対象モデル・期間を埋めた3つの分析指示**が表示されます。
# MAGIC 3. サイドバーから **Genie Code** を開き、出力の **「0. 統合トレースの保存先を特定する」** を貼り付けます。テーブル名の事前入力は不要です。
# MAGIC 4. 提示された保存先と、その判断の根拠を確認します。特定できない場合や候補が複数ある場合は、講師・メタストア管理者が控えている保存先を確認します。以降は**同じGenie Codeの会話**で進めてください。
# MAGIC
# MAGIC 分析対象は、前半の`SYSTEM_MODELS`と自分の`WORKSHOP_SERVICE`です。本人のモデル呼び出しを`SPAN_KIND_SERVER`に絞り、Client側のspanとの二重計上を避けます。1行を1つの会話や開発タスクとして数えません。
# MAGIC
# MAGIC 保存先の`SELECT`・親への`USE CATALOG`・`USE SCHEMA`と、クエリ実行環境の利用権限が必要です。SQLエディターを使う場合は`CAN USE`のあるSQL Warehouseを選択してください。本人への絞り込みは分析条件であり、UCのアクセス制御は管理者が別途設定します。
# MAGIC
# MAGIC 参考: [Genie Codeで統合トレースを分析](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#write-queries-with-genie-code) / [トレースのスキーマ](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table-reference)

# COMMAND ----------

def build_trace_analysis(start_time, end_time, service_name, system_models, workspace_url):
    """保存先の探索と分析の指示を作成。テーブル名の入力・API・SQL実行は不要です。"""
    def utc_time(value):
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("分析時刻には+00:00や+09:00などのタイムゾーンを付けてください。")
        return parsed.astimezone(timezone.utc)

    start, end = utc_time(start_time), utc_time(end_time)
    if start >= end:
        raise ValueError("分析開始時刻は終了時刻より前にしてください。")

    def sql_string(value):
        return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"

    targets = list(dict.fromkeys([service_name, *system_models]))
    target_sql = ", ".join(sql_string(name) for name in targets)
    scope = f"""WHERE time >= to_timestamp({sql_string(start.isoformat())})
  AND time < to_timestamp({sql_string(end.isoformat())})
  AND kind = 'SPAN_KIND_SERVER'
  AND attributes:['enduser.id']::STRING = current_user()
  AND service_name IN ({target_sql})"""

    questions = {
        "1. 呼び出しと拒否の件数": "サービス別に、呼び出し件数、databricks.policy.actionがDENYの件数、status.codeがSTATUS_CODE_ERRORの件数を別々に集計してください。",
        "2. モデルサービス別トークンと応答時間": "service_nameごとに、入力・出力トークンの合計とdatabricks.latency_msのp95を集計してください。トークン情報のある件数と、応答時間のある件数も示してください。サービス名だけから自作サービスの実際の配信先モデルを推測しないでください。",
        "3. どのポリシーが拒否したか": "databricks.policy.actionがDENYの呼び出しを、サービス名とdatabricks.policy.nameごとに集計してください。HTTPステータスやOTelのstatus.codeだけで拒否を判定しないでください。",
    }
    prompts = {"0. 統合トレースの保存先を特定する": f"""このワークスペース（{workspace_url}）のUnity Gatewayのunified traceを分析したいです。
まず、このワークスペースが属するメタストアの統合トレース保存先を、閲覧権限の範囲で調べてください。
参照できる設定やUnity Catalogメタデータを確認し、テーブルの完全修飾名と特定の根拠を示してください。
MLflowエクスペリメントのトレースやannotationsテーブルとは区別してください。名前が似ていることだけで断定しないでください。
複数の候補がある場合や根拠が不足する場合は、推測で選ばず、候補と根拠を示して確認を求めてください。
調査ではプロンプト・応答本文やユーザーの一覧は表示せず、テーブルや設定も変更しないでください。
以降の分析では、この会話で確認した統合トレーステーブルを使います。"""}
    prompts.update({
        title: f"""この会話で確認したUnity Gatewayの統合トレーステーブルを使い、SELECT文をこのNotebookの新しいSQLセルに追加してください。
{question}
FROMには確認済みの保存先を指定し、次のWHEREを共通条件として使ってください。範囲は広げないでください。
{scope}
attributesのキーはドットを含むため、attributes:['gen_ai.usage.input_tokens']のようにブラケット構文で参照してください。
NULLのトークン数を0に置き換えないでください。プロンプト・応答本文とユーザーの一覧は表示しないでください。
テーブルの作成・変更は不要です。SQLを実行する前に、上記条件が入っていることを確認できるようにしてください。"""
        for title, question in questions.items()
    })
    return prompts


analysis_end_utc = datetime.now(timezone.utc).isoformat()
analysis_prompts = build_trace_analysis(
    dbutils.widgets.get("analysis_start_utc"), analysis_end_utc,
    WORKSHOP_SERVICE, SYSTEM_MODELS, w.config.host,
)
print(f"分析終了時刻: {analysis_end_utc}（このセルの実行時刻で固定）\n")
for title, prompt in analysis_prompts.items():
    print(f"【{title}】\n{prompt}\n")

# COMMAND ----------

# MAGIC %md
# MAGIC ### 6.2 Genie Codeへ指示し、結果を確認する（4分）
# MAGIC
# MAGIC 1. セクション6.1で保存先を確認した**同じGenie Codeの会話**を使います。
# MAGIC 2. 上の出力から **「1. 呼び出しと拒否の件数」** の指示を貼り付けます。
# MAGIC 3. 追加されたSQLセルのテーブル名・期間・本人の条件・`SPAN_KIND_SERVER`を確認して実行します。SQLエディターへコピーして実行しても構いません。
# MAGIC 4. **「2. モデルサービス別トークンと応答時間」** も同様に試し、どのサービスを使い、どれだけのトークンが記録されたかを確認します。結果を棒グラフにすると、前半の`system.ai`のモデルサービスごとの違いを見比べられます。自作サービスの名前から、実際に配信したモデルを推測しないでください。
# MAGIC
# MAGIC Smart Routingではメインセッションとサブエージェントで同じモデルが選ばれることもあります。モデルごとの記録があることだけで、Smart Routingによる選択だったとは判断しません。セクション2のルーティング通知と合わせて確認します。
# MAGIC
# MAGIC ### 6.3 ポリシー拒否を分析する（3分）
# MAGIC
# MAGIC **「3. どのポリシーが拒否したか」** を貼り付け、サービスとポリシーごとの拒否件数を確認します。セクション4で使ったサービス名・ポリシー名と一致していることを確認してください。
# MAGIC
# MAGIC **ポリシーによる拒否は、HTTP 200や`STATUS_CODE_OK`でも起こる場合があります。** `databricks.policy.action = 'DENY'`を使い、OTelのエラー件数とは分けて数えます。1つの拒否を詳しく調べるときは、Traces画面の`policy_evaluated`イベントも確認できます。
# MAGIC
# MAGIC ### 生成されたSQLを確認するポイント
# MAGIC
# MAGIC | 分析 | 確認する式・条件 |
# MAGIC |---|---|
# MAGIC | 呼び出し件数 | 確認済みテーブルの`SPAN_KIND_SERVER`に絞って`COUNT(*)`。期間・本人・対象サービスは指示と同じ |
# MAGIC | ポリシー拒否件数 | `COUNT_IF(attributes:['databricks.policy.action']::STRING = 'DENY')`。OTelエラー件数と別に集計 |
# MAGIC | 入出力トークン | `gen_ai.usage.input_tokens`・`gen_ai.usage.output_tokens`の`SUM`。NULLを0へ置換しない |
# MAGIC | p95応答時間 | `percentile_approx(attributes:['databricks.latency_ms']::DOUBLE, 0.95)` |
# MAGIC | ポリシー別の拒否 | `DENY`に絞り、`service_name`と`databricks.policy.name`で集計。拒否件数の合計を最初の集計と比べる |

# COMMAND ----------

# MAGIC %md
# MAGIC ### 結果の見方と、記録が見つからない場合
# MAGIC
# MAGIC | 状況 | 確認すること |
# MAGIC |---|---|
# MAGIC | 0件 | 保存先・開始時刻・対象サービス・本人の条件と、記録の到着を確認。勝手に他の利用者へ対象を広げない |
# MAGIC | 拒否が複数件 | Claude Codeの再試行も1回のモデル呼び出しとして記録される。質問した回数とは一致しない場合がある |
# MAGIC | トークン数がNULL | 拒否などでトークン情報が記録されない場合がある。0トークンと断定せず、正常な呼び出しとも比べる |
# MAGIC | 対応するサービスの記録がない | Messages API非対応でセクション4を省略した場合は、前半のモデルの記録で進める |
# MAGIC
# MAGIC 新しいテーブルでは到着に最大1時間かかる場合があります。収集を有効にする前の操作は記録されません。講師の案内で閲覧権限のある事前記録を使う場合は、`analysis_start_utc`をその期間に変更してセクション6.1を再実行します。全セルを再実行する必要はありません。
# MAGIC
# MAGIC 記録はbest-effortなので、ここで見えた件数を全リクエストの完全な監査記録とは扱いません。トークン数だけから請求額や開発者の生産性も断定しません。
# MAGIC
# MAGIC ### 6.4 同じデータをチームで活用する（1分）
# MAGIC
# MAGIC 同じUCテーブルや分析用VIEWを **Genie Agent** に登録すれば、管理者やチームの利用者が自然言語で継続的に分析できます。**AI/BIダッシュボード**で利用状況を可視化することもできます。共有する範囲・本文の扱い・UCのアクセス制御を準備してから展開します。この演習では、まずGenie Codeで同じ記録を分析できれば完了です。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. 振り返りと復元
# MAGIC
# MAGIC - UIで設定したモデル・Smart Routing・トレースを、`ug configure`で選んだ実行環境へ反映できた。
# MAGIC - `ug claude`を使い、サブエージェントのモデル選択と予算を確認した。
# MAGIC - 自分のモデルサービスを新規作成、または既存サービスを再利用し、クライアントの対応APIを確認した。
# MAGIC - 必要な場合は同じサービスの配信先を変更し、サービス名とポリシーを引き継いだ。
# MAGIC - 入力ポリシーを作成、または既存ポリシーを再利用し、Claude Codeからの呼び出しが拒否されることを確認した。
# MAGIC - Smart defaultsと、サービスの予算フォールバックの違いを理解した。
# MAGIC - 標準のUsage Dashboardで、利用状況・支出・Coding Agent・Smart Routingを確認できることを理解した。
# MAGIC - 統合トレースのUCテーブルをGenie Codeで分析し、利用状況・トークン数・ポリシー拒否を確認した（トレースを準備した場合）。
# MAGIC
# MAGIC ### 演習前の設定へ戻す場合
# MAGIC
# MAGIC Claude Codeを終了し、まずワークスペースのAgent configurationを開始前に保存したJSONへ戻します。作成した予算の扱いは環境の管理者と確認してください。セクション4でモデルサービスの配信先を変更した場合は、保存しておいたルーティングをUIで復元し、サービス名・ポリシーと復元後の対応APIを確認します。
# MAGIC
# MAGIC **ブラウザコース**：PCの設定の復元は不要です。作成したコードを残す場合は、Terminalを閉じる前に自分のWorkspaceフォルダやGitへ保存してください。`$HOME/ug-workshop`や導入したツール・設定は、Serverless環境を作り直した後も残るとは扱いません。環境変数を外す場合は、Claude Codeを終了して`unset DATABRICKS_BEARER UG_SKIP_OS_SETTINGS`を実行します。ワークスペース側の設定・予算・サービスの復元は、このコースでも別途必要です。
# MAGIC
# MAGIC **ローカルコース**：PCの設定は演習前の利用状況に合う方法を1つ選んで戻します。会社がClaude CodeやUGの設定・起動方法を管理している場合は、会社の手順を優先してください。
# MAGIC
# MAGIC | 演習前の利用状況 | PCの戻し方 |
# MAGIC |---|---|
# MAGIC | ugを使っていなかった | 準備ガイド6の影響範囲を確認して`ug revert`を実行し、UGのバックアップから復元します。その後、普段の方法でClaude Codeを起動します |
# MAGIC | 既にugを使っていた | 下のコマンドで普段のワークスペースへ再設定し、`ug claude`で起動します。続けて`ug revert`は実行しません |
# MAGIC | 会社がClaude CodeやUGの設定・起動方法を管理 | 会社が案内する設定・復元・起動手順に従います |
# MAGIC
# MAGIC **既存のug利用者向け：** 保存しておいた普段のワークスペースURLへ置き換えて実行します。
# MAGIC
# MAGIC ```bash
# MAGIC ug configure --workspace https://普段のワークスペースURL --agent claude
# MAGIC ug claude
# MAGIC ```
# MAGIC
# MAGIC 再設定は、そのワークスペースで現在公開されている設定の適用です。演習前のローカルの手動調整まで完全に復元するものではありません。起動後は`/status`で接続先・モデルを、通常の呼び出しで認証を確認してください。`ug revert`はClaudeだけに限定されず、他のUG管理Agent・MCP設定にも影響します。バックアップの基準と会社が管理している場合の扱いは、<a href="$./事前準備ガイド">準備ガイドの「6. 開始前の記録と終了後の復元」</a>を参照してください。
# MAGIC ローカルコースで復元・確認を終え、今のシェルに設定した環境変数を解除する場合は、Agentを終了して`unset UG_SKIP_OS_SETTINGS`を実行します。
# MAGIC
# MAGIC 新規作成したサービス・ポリシーは、継続利用する場合は残して構いません。不要なら、Agent configurationから参照を外し、他の利用者・アプリからの参照がないことを確認してからUIで削除します。**既存のサービス・ポリシーを再利用した場合は削除しません。** Notebookのコードセルはサービス・ポリシーの作成・配信先変更・削除を実行しません。
# MAGIC
# MAGIC 補足テーマ：Codex、MCP、Skills、既存Claudeサブスクでの利用。まずは今回のClaude Codeの流れを確認してから追加します。
