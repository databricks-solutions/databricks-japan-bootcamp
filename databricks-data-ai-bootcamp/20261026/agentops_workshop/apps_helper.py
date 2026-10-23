"""アプリ（Databricks Apps）の作成とデプロイ。03（作成を先に始める）と 06（デプロイ）から使う。

アプリのリソースとして、使うものを宣言する。宣言すると、アプリのサービスプリンシパルに必要な権限
（親のカタログ・スキーマの USE も含む）が自動で付くので、権限を手で付ける必要はない。
"""
from datetime import timedelta

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.apps import (App, AppDeployment, AppResource, AppResourceExperiment,
                                         AppResourceExperimentExperimentPermission, AppResourceServingEndpoint,
                                         AppResourceServingEndpointServingEndpointPermission, AppResourceUcSecurable,
                                         AppResourceUcSecurableUcSecurablePermission, AppResourceUcSecurableUcSecurableType)


def _uc(key: str, name: str, kind: str, permission: str) -> AppResource:
    return AppResource(name=key, uc_securable=AppResourceUcSecurable(
        securable_full_name=name, securable_type=AppResourceUcSecurableUcSecurableType[kind],
        permission=AppResourceUcSecurableUcSecurablePermission[permission]))


def app_spec(app_name: str, experiment_id: str, llm_endpoint: str, doc_index: str, case_index: str,
             product_function: str, trace_tables: list[str]) -> App:
    resources = [
        # トレースの送り先の実験（app.yaml の MLFLOW_EXPERIMENT_ID になる）
        AppResource(name="experiment", experiment=AppResourceExperiment(
            experiment_id=experiment_id, permission=AppResourceExperimentExperimentPermission.CAN_EDIT)),
        # エージェントが使うモデル
        AppResource(name="llm-endpoint", serving_endpoint=AppResourceServingEndpoint(
            name=llm_endpoint, permission=AppResourceServingEndpointServingEndpointPermission.CAN_QUERY)),
        # ツールが使う検索インデックスと UC関数
        _uc("doc-index", doc_index, "TABLE", "SELECT"),
        _uc("case-index", case_index, "TABLE", "SELECT"),
        _uc("product-function", product_function, "FUNCTION", "EXECUTE"),
    ]
    # トレースを Unity Catalog のテーブルに書き込む権限（各テーブルに MODIFY と SELECT）
    for t in trace_tables:
        kind = t.rsplit("_", 1)[-1]
        resources += [_uc(f"trace-{kind}-modify", t, "TABLE", "MODIFY"), _uc(f"trace-{kind}-select", t, "TABLE", "SELECT")]
    return App(name=app_name, description="修理受付 回答支援エージェント", resources=resources)


def create_app(w: WorkspaceClient, spec: App) -> None:
    """アプリを作る（計算資源の起動を始めるだけで、完了は待たない）。すでにあれば何もしない。"""
    if spec.name in [a.name for a in w.apps.list()]:
        print(f"アプリ {spec.name} は作成済みです")
        return
    w.apps.create(app=spec)
    print(f"アプリ {spec.name} の作成を始めました（起動に2〜3分かかります。06 でデプロイします）")


def deploy_app(w: WorkspaceClient, spec: App, source_code_path: str):
    """アプリの設定を最新にしてから、フォルダのコードをデプロイする。"""
    if spec.name not in [a.name for a in w.apps.list()]:
        w.apps.create(app=spec)
    w.apps.wait_get_app_active(spec.name, timeout=timedelta(minutes=20))   # 起動が終わっていなければ待つ
    w.apps.update(name=spec.name, app=spec)
    deployment = w.apps.deploy_and_wait(app_name=spec.name, app_deployment=AppDeployment(source_code_path=source_code_path),
                                        timeout=timedelta(minutes=20))
    return w.apps.get(spec.name), deployment
