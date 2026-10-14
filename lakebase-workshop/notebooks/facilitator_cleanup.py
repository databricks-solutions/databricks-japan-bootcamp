# Databricks notebook source
# MAGIC %md
# MAGIC # Lakebase ワークショップ 片付けノートブック
# MAGIC
# MAGIC `facilitator_setup` で作成したマスター project 群を削除する。**取り消し不可（purge=完全削除）**。
# MAGIC
# MAGIC **使い方**:
# MAGIC 1. 一度実行してウィジェットを出す
# MAGIC 2. `1. project 接頭辞` にセットアップ時と同じ接頭辞を入れる（例: `workshop-master`）
# MAGIC 3. まず Run all → 削除対象の一覧だけが表示される（この時点では何も消えない）
# MAGIC 4. 一覧を確認したら `2. 削除確認` に **接頭辞と同じ文字列** を入力して再度 Run all → 削除実行
# MAGIC
# MAGIC 参加者ブランチは TTL（24h）で自動削除されるので個別対応は不要。
# MAGIC project ごと消すため、ブランチ・エンドポイント・ロール・データもすべて消える。

# COMMAND ----------

from typing import Any, Protocol, cast


class _WidgetUtils(Protocol):
    def text(self, name: str, default_value: str, label: str) -> None: ...

    def get(self, name: str) -> str: ...


class _DbUtils(Protocol):
    widgets: _WidgetUtils


dbutils = cast(_DbUtils, globals()["dbutils"])

# COMMAND ----------

dbutils.widgets.text("project_prefix", "workshop-master", "1. project 接頭辞")
dbutils.widgets.text("confirm", "", "2. 削除確認（接頭辞を再入力）")

# COMMAND ----------

PROJECT_PREFIX = dbutils.widgets.get("project_prefix").strip()
CONFIRMED = dbutils.widgets.get("confirm").strip() == PROJECT_PREFIX and PROJECT_PREFIX != ""

# COMMAND ----------

import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()


JsonObject = dict[str, Any]


def api(method: str, path: str, body: JsonObject | None = None) -> JsonObject:
    response = w.api_client.do(method, path, body=body)
    if response is None:
        return {}
    if not isinstance(response, dict):
        raise TypeError(f"Expected object response from {method} {path}, got {type(response).__name__}")
    return cast(JsonObject, response)


projects = api("GET", "/api/2.0/postgres/projects").get("projects", [])
targets = [
    p["name"].rsplit("/", 1)[-1]
    for p in projects
    if p["name"].rsplit("/", 1)[-1].startswith(f"{PROJECT_PREFIX}-")
]

print(f"接頭辞 '{PROJECT_PREFIX}-' に一致する project: {len(targets)} 件")
for pid in targets:
    print(f"  - projects/{pid}")
if not targets:
    print("削除対象なし。接頭辞を確認してください。")

# COMMAND ----------

# MAGIC %md ## 削除実行（`2. 削除確認` が一致しているときだけ動く）

# COMMAND ----------

if not CONFIRMED:
    print("削除確認が未入力のため何もしません。")
    print(f"上の一覧を確認し、ウィジェット『2. 削除確認』に '{PROJECT_PREFIX}' と入力して再実行すると削除します。")
else:
    for pid in targets:
        # protected 解除（protected な project は削除できないため）
        try:
            api(
                "PATCH",
                f"/api/2.0/postgres/projects/{pid}/branches/production?update_mask=spec.is_protected",
                {"name": f"projects/{pid}/branches/production", "spec": {"is_protected": False}},
            )
            print(f"[unprotect] projects/{pid}/branches/production")
            time.sleep(3)
        except Exception as e:
            print(f"[warn] unprotect 失敗（続行）: {e}")
        # 完全削除（purge。soft delete だと同じ project id での再作成が 7 日間ブロックされる）
        api("DELETE", f"/api/2.0/postgres/projects/{pid}?purge=true")
        print(f"[deleted] projects/{pid} (purge)")

    remaining = [
        p["name"]
        for p in api("GET", "/api/2.0/postgres/projects").get("projects", [])
        if p["name"].rsplit("/", 1)[-1].startswith(f"{PROJECT_PREFIX}-")
    ]
    print(f"\n完了。残存する対象 project: {len(remaining)} 件")
