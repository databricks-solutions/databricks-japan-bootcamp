# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase ワークショップ 講師準備ノートブック（v6 マスター/ブランチ方式）
# MAGIC
# MAGIC ワークショップ環境（マスター project 群）を **Databricks 上だけで** 準備する。ローカル CLI / jq / psql は不要。
# MAGIC
# MAGIC **使い方**:
# MAGIC 1. 最初にこのノートブックを **Run all** してウィジェットを表示する（確認が既定値のため、この時点では環境を変更しない）
# MAGIC 2. 上部の入力値を設定し、`5. 実行確認`を`環境構築を実行`へ変更する
# MAGIC 3. もう一度 **Run all** する
# MAGIC
# MAGIC | ウィジェット | 説明 |
# MAGIC |---|---|
# MAGIC | 1. 参加者数 | 想定参加者数。8名/project でマスターを自動シャーディング（unarchived ブランチ上限 10/project のため） |
# MAGIC | 2. project 接頭辞 | master project id は `<接頭辞>-1, -2, …` |
# MAGIC | 3. 参加者グループ | 権限を付与するワークスペースグループ名（社内ハンズオンは `users`、顧客環境は参加者専用グループ） |
# MAGIC | 4. 権限モード | `can_manage` = 参加者が自分でブランチを切る（推奨・スライド通り） / `precreate` = 講師がブランチを事前作成し参加者は CAN USE のみ |
# MAGIC | 5. 実行確認 | `環境構築を実行`を選んだ場合のみproject作成以降を実行 |
# MAGIC
# MAGIC やること（Run all で全部実行される・冪等）:
# MAGIC 1. マスター project をシャーディング作成 → 2. スキーマ＋シード投入 → 3. master（production）を protected 化 →
# MAGIC 4. 参加者へ権限付与（precreate モードではブランチ事前作成も） → 5. 動作確認＋参加者割り当て表を出力
# MAGIC
# MAGIC 片付けは別ノートブック **`facilitator_cleanup`** で行う。

# COMMAND ----------

from typing import Protocol, cast


class _LibraryUtils(Protocol):
    def restartPython(self) -> None: ...


class _WidgetUtils(Protocol):
    def text(self, name: str, default_value: str, label: str) -> None: ...

    def dropdown(self, name: str, default_value: str, choices: list[str], label: str) -> None: ...

    def get(self, name: str) -> str: ...


class _NotebookUtils(Protocol):
    def exit(self, value: str) -> None: ...


class _DbUtils(Protocol):
    library: _LibraryUtils
    widgets: _WidgetUtils
    notebook: _NotebookUtils


dbutils = cast(_DbUtils, globals()["dbutils"])

# COMMAND ----------

# MAGIC %md
# MAGIC 追加インストールは `psycopg` のみ。`databricks-sdk` は DBR 同梱版をそのまま使う
# MAGIC （`-U databricks-sdk` は protobuf 6.x を引き込み、DBR 同梱の googleapis-common-protos / grpcio-status と競合するため upgrade しない。
# MAGIC このノートブックは raw REST API しか使わないので同梱版で十分）
# MAGIC
# MAGIC `psycopg[binary]` は使わない。Serverless で aarch64 が割り当てられると、binary 同梱の OpenSSL が
# MAGIC `FATAL FIPS SELFTEST FAILURE` で import 時に SIGABRT し Python カーネルごと落ちるため。
# MAGIC extra なしの `psycopg` はイメージ同梱のシステム libpq を使う純 Python 実装で動き、x86_64 / aarch64 の両方で動作する

# COMMAND ----------

# MAGIC %pip install psycopg -q

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %md ## 設定（上部ウィジェットで入力）

# COMMAND ----------

dbutils.widgets.text("participant_count", "8", "1. 参加者数")
dbutils.widgets.text("project_prefix", "workshop-master", "2. project 接頭辞")
dbutils.widgets.text("participant_group", "users", "3. 参加者グループ")
dbutils.widgets.dropdown("permission_mode", "can_manage", ["can_manage", "precreate"], "4. 権限モード")
dbutils.widgets.dropdown("confirm_run", "確認のみ", ["確認のみ", "環境構築を実行"], "5. 実行確認")

# COMMAND ----------

import math

PARTICIPANT_COUNT = int(dbutils.widgets.get("participant_count"))
PROJECT_PREFIX = dbutils.widgets.get("project_prefix").strip()
PARTICIPANT_GROUP = dbutils.widgets.get("participant_group").strip()
PERMISSION_MODE = dbutils.widgets.get("permission_mode")
CONFIRM_RUN = dbutils.widgets.get("confirm_run")

PARTICIPANTS_PER_MASTER = 8   # 1 master あたりの参加者数（上限9。unarchived ブランチ 10/project 制約）
PG_VERSION = 17
DATABASE = "databricks_postgres"  # project 既定 DB をそのまま使う
BRANCH_TTL = "86400s"             # precreate モードのブランチ有効期限（24h で自動削除）

NUM_MASTERS = max(1, math.ceil(PARTICIPANT_COUNT / PARTICIPANTS_PER_MASTER))
MASTER_IDS = [f"{PROJECT_PREFIX}-{i + 1}" for i in range(NUM_MASTERS)]

print(f"参加者 {PARTICIPANT_COUNT} 名 → master project {NUM_MASTERS} 個: {MASTER_IDS}")
print(f"権限モード: {PERMISSION_MODE}（付与先グループ: {PARTICIPANT_GROUP}）")

if PARTICIPANT_COUNT < 1 or not PROJECT_PREFIX or not PARTICIPANT_GROUP:
    raise ValueError("参加者数、project接頭辞、参加者グループを確認してください")
if CONFIRM_RUN != "環境構築を実行":
    print("\n確認のみです。上の設定を確認し、ウィジェット「5. 実行確認」を")
    print("「環境構築を実行」に変更してから、もう一度Run allしてください。")
    dbutils.notebook.exit("設定確認待ち")

# COMMAND ----------

# MAGIC %md ## 共通ヘルパー（REST クライアント）

# COMMAND ----------

import time
from typing import Any, TypedDict, cast

from databricks.sdk import WorkspaceClient
from databricks.sdk.errors import NotFound
from psycopg import sql

w = WorkspaceClient()  # ノートブック実行ユーザーとして自動認証
me = w.current_user.me().user_name
print(f"実行ユーザー: {me}")


JsonObject = dict[str, Any]


def api(method: str, path: str, body: JsonObject | None = None) -> JsonObject:
    response = w.api_client.do(method, path, body=body)
    if response is None:
        return {}
    if not isinstance(response, dict):
        raise TypeError(f"Expected object response from {method} {path}, got {type(response).__name__}")
    return cast(JsonObject, response)


class PermissionGrant(TypedDict, total=False):
    permission_level: str
    inherited: bool


class AccessControlEntry(TypedDict, total=False):
    group_name: str
    all_permissions: list[PermissionGrant]


class PermissionsResponse(TypedDict, total=False):
    access_control_list: list[AccessControlEntry]


def verify_group_permission(project_id: str, group_name: str, expected_permission: str) -> None:
    """Fail setup unless the expected project permission is explicitly assigned."""
    response = cast(
        PermissionsResponse,
        api("GET", f"/api/2.0/permissions/database-projects/{project_id}"),
    )
    group_entries = [
        entry
        for entry in response.get("access_control_list", [])
        if entry.get("group_name") == group_name
    ]
    grants = [grant for entry in group_entries for grant in entry.get("all_permissions", [])]
    direct_matches = [
        grant
        for grant in grants
        if grant.get("permission_level") == expected_permission and not grant.get("inherited", False)
    ]
    if not direct_matches:
        actual = ", ".join(
            sorted(
                f"{grant.get('permission_level', 'UNKNOWN')} "
                f"({'inherited' if grant.get('inherited', False) else 'direct'})"
                for grant in grants
            )
        ) or "none"
        raise RuntimeError(
            f"projects/{project_id}: group '{group_name}' is missing explicit "
            f"{expected_permission}; actual permissions: {actual}"
        )
    print(f"[verify] projects/{project_id}: group '{group_name}' -> {expected_permission} (direct)")


def project_exists(project_id: str) -> bool:
    try:
        api("GET", f"/api/2.0/postgres/projects/{project_id}")
        return True
    except NotFound:
        return False


def wait_endpoint_ready(project_id: str, branch: str = "production", timeout_s: int = 300) -> dict:
    """ブランチの primary エンドポイントが host 付きで返るまで待つ。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        eps = api("GET", f"/api/2.0/postgres/projects/{project_id}/branches/{branch}/endpoints").get("endpoints", [])
        for ep in eps:
            host = (ep.get("status") or {}).get("hosts", {}).get("host")
            if host:
                return {"name": ep["name"], "host": host}
        time.sleep(5)
    raise TimeoutError(f"endpoint not ready: {project_id}/{branch}")


def pg_connect(project_id: str, branch: str = "production"):
    """実行ユーザーの Postgres ロール（owner に自動作成される）で接続する。"""
    import psycopg

    ep = wait_endpoint_ready(project_id, branch)
    cred = api("POST", "/api/2.0/postgres/credentials", {"endpoint": ep["name"]})
    return psycopg.connect(
        host=ep["host"],
        port=5432,
        dbname=DATABASE,
        user=me,
        password=cred["token"],
        sslmode="require",
        connect_timeout=15,
    )

# COMMAND ----------

# MAGIC %md ## 1. マスター project の作成

# COMMAND ----------

for pid in MASTER_IDS:
    if project_exists(pid):
        print(f"[skip] projects/{pid} は既に存在")
        continue
    print(f"[create] projects/{pid} ...")
    api(
        "POST",
        f"/api/2.0/postgres/projects?project_id={pid}",
        {"spec": {"display_name": f"Lakebase Workshop master ({pid})", "pg_version": PG_VERSION}},
    )
    # 作成は非同期。GET が通るまで待つ
    for _ in range(60):
        if project_exists(pid):
            break
        time.sleep(5)
    ep = wait_endpoint_ready(pid)
    print(f"  ready: {ep['host']}")

# COMMAND ----------

# MAGIC %md ## 2. スキーマ＋シードデータ投入（sql/*.postgres.sql と同内容・冪等）

# COMMAND ----------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    customer VARCHAR(120) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'new',
    priority VARCHAR(20) NOT NULL DEFAULT 'medium',
    owner VARCHAR(80) NOT NULL DEFAULT 'unassigned',
    category VARCHAR(80) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT tickets_status_check CHECK (status IN ('new', 'in_progress', 'waiting', 'resolved')),
    CONSTRAINT tickets_priority_check CHECK (priority IN ('urgent', 'high', 'medium', 'low'))
);

CREATE TABLE IF NOT EXISTS ticket_comments (
    id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author VARCHAR(80) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_updated_at ON tickets(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_comments_ticket_id ON ticket_comments(ticket_id);
"""

SEED_SQL = """
INSERT INTO tickets (id, title, customer, status, priority, owner, category, description, created_at, updated_at)
VALUES
    (1, 'ダッシュボードの表示が遅い', 'Sample Retail', 'new', 'high', 'Demo User 1', 'Performance', '月次ダッシュボードの初回表示に 20 秒以上かかる。営業会議前に改善状況を確認したい。', NOW() - INTERVAL '5 days', NOW() - INTERVAL '5 days'),
    (2, 'CSV エクスポートに古い列名が出る', 'Sample Foods', 'in_progress', 'medium', 'Demo User 2', 'Data Quality', '顧客一覧の CSV に deprecated_customer_id が残っている。アプリ画面側では非表示になっている。', NOW() - INTERVAL '3 days', NOW() - INTERVAL '1 day'),
    (3, '新規ユーザーがコメントを追加できない', 'Sample Manufacturing', 'waiting', 'urgent', 'Demo User 3', 'Access Control', '権限付与直後のユーザーが ticket_comments に書き込めない。管理者ユーザーでは再現しない。', NOW() - INTERVAL '2 days', NOW() - INTERVAL '8 hours'),
    (4, '問い合わせ分類の候補を増やしたい', 'Sample Software', 'resolved', 'low', 'Demo User 4', 'Product Request', 'サポートチームが使う分類に Billing と Security を追加したい。', NOW() - INTERVAL '8 days', NOW() - INTERVAL '6 days'),
    (5, '優先度の変更が監査画面に反映されない', 'Sample Healthcare', 'new', 'medium', 'Demo User 5', 'Audit', 'チケット詳細で priority を変更しても監査用ビューへの反映が遅れることがある。', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day')
ON CONFLICT (id) DO NOTHING;

INSERT INTO ticket_comments (id, ticket_id, author, body, created_at)
VALUES
    (1, 1, 'Demo User 1', 'ワークロード履歴を確認中。まずは集計クエリの実行時間を切り分けます。', NOW() - INTERVAL '4 days'),
    (2, 2, 'Demo User 2', '列名変更はアプリ側の表示だけでなく、エクスポート処理も確認します。', NOW() - INTERVAL '1 day'),
    (3, 3, 'Demo User 3', '権限の反映タイミングを確認するため、再現手順を整理しました。', NOW() - INTERVAL '7 hours')
ON CONFLICT DO NOTHING;

SELECT setval(pg_get_serial_sequence('tickets', 'id'), COALESCE((SELECT MAX(id) FROM tickets), 1), true);
SELECT setval(pg_get_serial_sequence('ticket_comments', 'id'), COALESCE((SELECT MAX(id) FROM ticket_comments), 1), true);
"""

# Lakebase が管理する databricks_superuser はメンバーに SET ROLE を許可しないため、
# 所有者には直接指定できない。専用の NOLOGIN ロールを所有者にし、既存の
# databricks_superuser メンバーが継承できるようにする。
OWNERSHIP_ROLE = "lakebase_workshop_ddl_owner"

for pid in MASTER_IDS:
    print(f"[seed] projects/{pid} ...")
    with pg_connect(pid) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute(SEED_SQL)
            cur.execute("SELECT current_user")
            facilitator_role = cur.fetchone()[0]
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (OWNERSHIP_ROLE,))
            if not cur.fetchone():
                cur.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(OWNERSHIP_ROLE)))
            cur.execute(
                sql.SQL("GRANT {} TO {} WITH INHERIT TRUE, SET TRUE").format(
                    sql.Identifier(OWNERSHIP_ROLE),
                    sql.Identifier(facilitator_role),
                )
            )
            cur.execute(
                sql.SQL("GRANT {} TO databricks_superuser WITH INHERIT TRUE, SET FALSE").format(
                    sql.Identifier(OWNERSHIP_ROLE)
                )
            )
            # CREATE is required only while changing the table owner. Revoke it immediately.
            cur.execute(sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(OWNERSHIP_ROLE)))
            cur.execute(sql.SQL("ALTER TABLE tickets OWNER TO {}").format(sql.Identifier(OWNERSHIP_ROLE)))
            cur.execute(sql.SQL("ALTER TABLE ticket_comments OWNER TO {}").format(sql.Identifier(OWNERSHIP_ROLE)))
            cur.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(OWNERSHIP_ROLE)))
            cur.execute("SELECT count(*) FROM tickets")
            print(f"  tickets: {cur.fetchone()[0]} 件")

# COMMAND ----------

# MAGIC %md ## 3. master（production ブランチ）を protected 化
# MAGIC
# MAGIC protected ブランチは削除・リセット・自動アーカイブ不可、protected ブランチを持つ project は削除不可。
# MAGIC これにより参加者へ CAN MANAGE を配っても master は守られる。

# COMMAND ----------

for pid in MASTER_IDS:
    api(
        "PATCH",
        f"/api/2.0/postgres/projects/{pid}/branches/production?update_mask=spec.is_protected",
        {"name": f"projects/{pid}/branches/production", "spec": {"is_protected": True}},
    )
    print(f"[protect] projects/{pid}/branches/production → protected")

# COMMAND ----------

# MAGIC %md ## 4. 参加者へ権限付与
# MAGIC
# MAGIC - `can_manage` モード: 参加者が自分でブランチを切れるよう CAN MANAGE を付与（ブランチ作成に必要）
# MAGIC - `precreate` モード: CAN USE のみ付与し、講師が participant-1..N のブランチを事前作成（TTL 24h）。
# MAGIC   参加者のアプリ SP 用ロール作成は CAN USE でも可能

# COMMAND ----------

if PERMISSION_MODE == "can_manage":
    for pid in MASTER_IDS:
        api(
            "PATCH",
            f"/api/2.0/permissions/database-projects/{pid}",
            {"access_control_list": [{"group_name": PARTICIPANT_GROUP, "permission_level": "CAN_MANAGE"}]},
        )
        print(f"[grant] projects/{pid}: group '{PARTICIPANT_GROUP}' → CAN_MANAGE")
else:  # precreate
    for i, pid in enumerate(MASTER_IDS):
        lo = i * PARTICIPANTS_PER_MASTER + 1
        hi = min((i + 1) * PARTICIPANTS_PER_MASTER, PARTICIPANT_COUNT)
        existing = {
            b["name"].rsplit("/", 1)[-1]
            for b in api("GET", f"/api/2.0/postgres/projects/{pid}/branches").get("branches", [])
        }
        for n in range(lo, hi + 1):
            branch_id = f"participant-{n}"
            if branch_id in existing:
                print(f"[skip] projects/{pid}/branches/{branch_id} は既に存在")
                continue
            api(
                "POST",
                f"/api/2.0/postgres/projects/{pid}/branches?branch_id={branch_id}",
                {"spec": {"source_branch": f"projects/{pid}/branches/production", "ttl": BRANCH_TTL}},
            )
            print(f"[branch] projects/{pid}/branches/{branch_id} (TTL 24h)")
        api(
            "PATCH",
            f"/api/2.0/permissions/database-projects/{pid}",
            {"access_control_list": [{"group_name": PARTICIPANT_GROUP, "permission_level": "CAN_USE"}]},
        )
        print(f"[grant] projects/{pid}: group '{PARTICIPANT_GROUP}' → CAN_USE")

# COMMAND ----------

# MAGIC %md ## 5. 権限preflight＋動作確認＋参加者割り当て表

# COMMAND ----------

expected_permission = "CAN_MANAGE" if PERMISSION_MODE == "can_manage" else "CAN_USE"
for pid in MASTER_IDS:
    verify_group_permission(pid, PARTICIPANT_GROUP, expected_permission)

print("権限API確認に成功しました。開始前に代表参加者でbranch作成または割り当て済みbranchの選択を確認してください。")

# COMMAND ----------

print("=== 参加者割り当て表（コピーして配布資料へ） ===\n")
for i, pid in enumerate(MASTER_IDS):
    ep = wait_endpoint_ready(pid)
    lo = i * PARTICIPANTS_PER_MASTER + 1
    hi = min((i + 1) * PARTICIPANTS_PER_MASTER, PARTICIPANT_COUNT)
    with pg_connect(pid) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tickets")
        n = cur.fetchone()[0]
    print(f"参加者 {lo}〜{hi} 番 → project: {pid}")
    print(f"    master endpoint host: {ep['host']}  (tickets {n} 件 / protected)")
    print("    Apps Database resource:")
    print("      Resource key: lakebase-demo")
    print("      Project: このproject")
    print("      Branch: 参加者自身のbranch")
    print("      Database: databricks_postgres")
    print("    ※ 接続値の手入力は不要。手動接続版を使う場合だけ")
    print("      participant_connect_helperで接続値を確認する")
if PERMISSION_MODE == "precreate":
    print("\nprecreate モード: 各参加者は自分の番号の participant-N ブランチを使う（TTL 24h で自動削除）")
print(f"\n注意: 1 master あたりのブランチは講師確認用も含めて 9 本まで（unarchived 上限 10）")
print("片付けはワークショップ終了後に facilitator_cleanup ノートブックで実行する")
