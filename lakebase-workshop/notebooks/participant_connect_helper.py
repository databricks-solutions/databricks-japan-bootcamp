# Databricks notebook source
# MAGIC %md
# MAGIC # 手動接続フォールバック用ヘルパー
# MAGIC
# MAGIC 標準手順はDatabricks AppsのAdd resource方式です。このノートブックは
# MAGIC Database resourceを利用できない場合や接続診断が必要な場合だけ使用し、
# MAGIC アプリをLakebase（自分のブランチ）に繋ぐための接続値
# MAGIC （`LAKEBASE_CONNECTION_STRING` / `ENDPOINT_NAME` / 任意の`PGUSER`上書き値）を自動で表示します。
# MAGIC 通常はスライドの手順（Lakebase UI の Copy snippet など）で取得できます。
# MAGIC 値が合っているか確認したいとき・うまくいかないときにこのノートブックを使ってください。
# MAGIC 追加インストールは不要です。
# MAGIC
# MAGIC **使い方**
# MAGIC 1. 一度実行すると上部に入力欄（ウィジェット）が出ます
# MAGIC 2. `1. master project`（割り当て表の id）・`2. 自分のブランチ名`・`3. 自分のアプリ名` を入れて **Run all**
# MAGIC    → 接続値がそのまま貼れる形で表示されます

# COMMAND ----------

from typing import NoReturn, Protocol, TypedDict, cast


class _Widgets(Protocol):
    def text(self, name: str, default_value: str, label: str) -> None: ...

    def get(self, name: str) -> str: ...


class _Notebook(Protocol):
    def exit(self, value: str) -> NoReturn: ...


class _Dbutils(Protocol):
    widgets: _Widgets
    notebook: _Notebook


class _EndpointHosts(TypedDict):
    host: str


class _EndpointStatus(TypedDict):
    hosts: _EndpointHosts


class _Endpoint(TypedDict):
    name: str
    status: _EndpointStatus


class _EndpointListResponse(TypedDict, total=False):
    endpoints: list[_Endpoint]


class _AppResponse(TypedDict, total=False):
    service_principal_client_id: str


dbutils = cast(_Dbutils, globals()["dbutils"])


dbutils.widgets.text("master_project", "", "1. master project（割り当て表の id）")
dbutils.widgets.text("branch_name", "", "2. 自分のブランチ名")
dbutils.widgets.text("app_name", "", "3. 自分のアプリ名（作成後でOK）")

# COMMAND ----------

MASTER = dbutils.widgets.get("master_project").strip()
BRANCH = dbutils.widgets.get("branch_name").strip()
APP_NAME = dbutils.widgets.get("app_name").strip()

# COMMAND ----------

from databricks.sdk import WorkspaceClient  # ty: ignore[unresolved-import]

w = WorkspaceClient()


def api(method: str, path: str) -> object:
    return w.api_client.do(method, path) or {}


if not MASTER or not BRANCH:
    print("上のウィジェットに『1. master project』と『2. 自分のブランチ名』を入力して Run all してください。")
    print("（master project の id は講師の割り当て表にあります）")
    dbutils.notebook.exit("入力待ち")

# --- PGHOST / ENDPOINT_NAME: 自分のブランチのエンドポイントを API から直接取得 ---
try:
    endpoint_response = cast(
        _EndpointListResponse,
        api(
            "GET",
            f"/api/2.0/postgres/projects/{MASTER}/branches/{BRANCH}/endpoints",
        ),
    )
    eps = endpoint_response.get("endpoints", [])
except Exception:
    print(f"ブランチが見つかりません: projects/{MASTER}/branches/{BRANCH}")
    print("・master project の id が割り当て表と一致しているか")
    print("・ブランチ名が自分で付けた名前と一致しているか（大文字小文字も）")
    print("を確認してください。")
    dbutils.notebook.exit("branch not found")

ep = next((e for e in eps if (e.get("status") or {}).get("hosts", {}).get("host")), None)
if ep is None:
    print("エンドポイントがまだ準備中です。数十秒待ってからもう一度 Run all してください。")
    dbutils.notebook.exit("endpoint not ready")

PGHOST = ep["status"]["hosts"]["host"]
ENDPOINT_NAME = ep["name"]  # API が返す正式なリソース名をそのまま使う（手で組み立てない）

# --- PGUSER: アプリの service principal Client ID を API から取得 ---
PGUSER = None
if APP_NAME:
    try:
        app = cast(_AppResponse, api("GET", f"/api/2.0/apps/{APP_NAME}"))
        PGUSER = app.get("service_principal_client_id")
    except Exception:
        print(f"アプリが見つかりません: {APP_NAME}（アプリ名を確認してください）\n")

# COMMAND ----------

# MAGIC %md ## 結果 — この値をアプリの環境変数に設定する

# COMMAND ----------

# LAKEBASE_CONNECTION_STRING はユーザー名なしで構成する
# （アプリはユーザー名を接続文字列から読まない。host / db / sslmode だけ使われる）
CONNECTION_STRING = f"postgresql://{PGHOST}/databricks_postgres?sslmode=require"

rows = [
    ("LAKEBASE_CONNECTION_STRING", CONNECTION_STRING),
    ("PGUSER（任意の上書き）", PGUSER or "DATABRICKS_CLIENT_ID が自動利用されます"),
    ("ENDPOINT_NAME", ENDPOINT_NAME),
]

width = max(len(k) for k, _ in rows)
print("=" * 70)
print(f"あなたのブランチ: projects/{MASTER}/branches/{BRANCH}")
print("=" * 70)
for k, v in rows:
    print(f"{k.ljust(width)}  =  {v}")
print("=" * 70)
print("LAKEBASE_CONNECTION_STRING と ENDPOINT_NAME をアプリの環境変数")
print("（Edit → Environment）に設定してDeployし直してください。")
print("PGUSERは未設定でも、Databricks Appsが渡すDATABRICKS_CLIENT_IDを自動利用します。")
print("LAKEBASE_CONNECTION_STRING は Lakebase UI の Connection details → Copy snippet の")
print("接続文字列をそのまま貼ったものでも同じように動きます。")
if PGUSER:
    print("あわせて、自分のブランチの Roles & Databases でこの PGUSER（service principal）の")
    print("ロールを作成しておくこと（作成していないと接続エラーになります）。")
