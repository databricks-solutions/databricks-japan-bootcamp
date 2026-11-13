# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Unity Gatewayハンズオン：事前準備ガイド
# MAGIC
# MAGIC 講師・管理者は開催前にこのガイドを確認してください。参加者は、ブラウザまたはローカルの実行環境・権限で困ったときに該当箇所だけ参照します。ブラウザコースのTerminalは、このガイドではなく**本編Notebook**から開きます。
# MAGIC 配布するNotebookは本編とこのガイドの2つです。ファイル名を変えず、同じWorkspaceフォルダへPython Notebookとしてインポートしてください。
# MAGIC
# MAGIC <a href="$./Unity_Gateway_ハンズオン">本編Notebookへ戻る</a>
# MAGIC
# MAGIC | 確認したいこと | 参照する節 |
# MAGIC |---|---|
# MAGIC | ブラウザ／ローカルの選択・ツールの導入・認証 | 1. 実行環境の準備 |
# MAGIC | 必要な権限と担当者 | 2. ワークスペースと権限 |
# MAGIC | どのプレビューを有効にするか | 3. プレビュー |
# MAGIC | 新規作成先・既存サービス・モデルの指定 | 4. Notebookの設定 |
# MAGIC | 演習のトレースを分析できるようにする | 5. 観測データの準備 |
# MAGIC | 既存設定の保存・復元 | 6. 開始前の記録と終了後の復元 |

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. 実行環境の準備
# MAGIC
# MAGIC ### ブラウザコース（推奨）
# MAGIC
# MAGIC PCへツールを導入せず、DatabricksのServerless Web Terminalで実施します。講師は、利用者がNotebookをServerlessへ接続できること、ワークスペースでWeb Terminalが有効なこと、GitHubとClaude Codeの配布先への接続を確認します。Serverless環境バージョン1ではWeb Terminalを利用できません。
# MAGIC
# MAGIC 1. <a href="$./Unity_Gateway_ハンズオン">本編Notebook</a>を開いてServerlessに接続します。
# MAGIC 2. 本編の **Terminal, Logs** からTerminalを開き、本編0.1の導入コマンドを実行します。ugはPython 3.12以降を使い、Claude Codeはnpm不要のネイティブ版を導入します。検証したugのコミットとClaude Codeのバージョンは本編で固定しています。
# MAGIC 3. 本編0.2の設定セルを実行して入力欄を作り、左側の「パラメータ」パネルで`terminal`を`browser`にします。入力を変更した場合は設定セルを再実行します。
# MAGIC 4. 本編セクション1でCoding Agent設定を公開した後、1.1に表示されるブロック全体を同じTerminalで実行します。
# MAGIC
# MAGIC **別Notebookで開いたTerminalは別環境になる場合があります。** インストールしたツール・ホームディレクトリ・localhostが同じとは扱いません。全章で同じ本編のセッションを使います。別の資料を開いた後は、Terminalのセッション一覧で本編を選び直してください。
# MAGIC
# MAGIC 本編1.1では、Web Terminalに用意された本人の`DATABRICKS_TOKEN`を、ugが受け取る`DATABRICKS_BEARER`へ環境変数で渡します。ブラウザでの追加OAuth認証、PATの発行、認証後URLの手動転送は不要です。掲載コマンドはトークンの値を出力・ファイル保存しません。
# MAGIC
# MAGIC **この接続方法は、固定版ug本体の外部bearer認証処理を使い、本教材で実機確認したものです。** 公開のWeb Terminal向けセットアップ手順としての保証は未確認のため、ug更新時には再検証します。認証経路を標準のOAuthに揃える必要がある場合はローカルコースを選びます。
# MAGIC
# MAGIC **認証情報はClaude Codeと、そのツールが起動するコマンドにも渡ります。** `env`・`printenv`・`set`などによる環境変数の全表示や、認証情報の出力をAgentへ依頼しないでください。会話・ログ・トレースへ記録される可能性があるため、演習では配布したサンプルコードを使います。通常起動時はug自身も`OAUTH_TOKEN`を設定するので、configure後に`DATABRICKS_BEARER`だけを解除しても認証情報の隔離にはなりません。
# MAGIC
# MAGIC `UG_SKIP_OS_SETTINGS=1`を併用すると、ワークスペースの公開設定を読み取り、Serverless環境のユーザー設定へ適用できます。sudoは不要です。公開設定がある環境では`ug configure --user`が拒否されるため、**`--user`は付けません**。このコースでは端末全体への強制適用やMDM配布を行いません。`ug claude`経由で起動します。
# MAGIC
# MAGIC この環境設定はTerminalセッション内で有効です。新しいセッションや環境の再作成後は、本編0.1の導入状態を確認し、1.1のブロックを再実行します。作成したコードを残す場合は、自分のWorkspaceフォルダやGitへ保存します。Serverlessのホーム内のファイルが環境再作成後も残るとは扱いません。
# MAGIC
# MAGIC ### ローカルコース
# MAGIC
# MAGIC PCへの導入・通常のOAuth認証・ユーザー設定の適用・終了後の復元まで体験します。ブラウザコースと同じく`UG_SKIP_OS_SETTINGS=1`を使い、OS全体の管理設定への書き込みを省きます。macOS/Linuxのターミナルを想定し、Python 3.12以降、[Databricks CLI](https://docs.databricks.com/aws/ja/dev-tools/cli/install)、[uv](https://docs.astral.sh/uv/getting-started/installation/)、[Claude Code](https://code.claude.com/docs/en/setup)を準備します。
# MAGIC
# MAGIC ```bash
# MAGIC python3 --version
# MAGIC databricks --version
# MAGIC uv --version
# MAGIC claude --version
# MAGIC ```
# MAGIC
# MAGIC 続いてugを導入します。既に導入済みなら、導入元の更新手順を使ってください。
# MAGIC
# MAGIC ```bash
# MAGIC export PATH="$HOME/.local/bin:$PATH"
# MAGIC uv tool install --python 3.12 git+https://github.com/databricks/unity-gateway@03952a3fec7e6c35e4e90d2528e54b4ec147b41c
# MAGIC ug --version
# MAGIC ```
# MAGIC
# MAGIC ### 個人で試す場合
# MAGIC
# MAGIC 本編0.2の設定セルを実行し、`terminal`を`local`にします。本編セクション1でワークスペースの共通設定を公開してから、1.1に表示される`UG_SKIP_OS_SETTINGS=1`を含むブロック全体をPCで実行し、本人がOAuthで認証します。CLIからプロファイル名を求められた場合は、自分で名前を選択します。
# MAGIC
# MAGIC この演習ではugの接続状態と本人のユーザー設定が更新されます。作業ディレクトリを分けても設定は共通なので、開始前にセクション6で利用状況と復元方法を記録してください。毎回`ug claude`で起動します。通常のugにはOS全体の管理設定へ適用する機能もありますが、今回の演習では使いません。
# MAGIC
# MAGIC ### 組織の管理端末で使う場合
# MAGIC
# MAGIC 会社がClaude CodeやUGの設定・起動方法を管理している場合は、演習用ワークスペースへ切り替えてよいか、終了後の復元方法と担当者を開催前に確認します。会社が案内する起動手順を使い、切り替えが難しい場合はブラウザコースを選びます。組織へのMDM配布はこのワークショップの演習範囲外です。必要なIT管理者は[公式のMDM配布手順](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-rollout)を参照してください。
# MAGIC
# MAGIC 参考: [ugのセットアップ](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-ug-cli)

# COMMAND ----------

# MAGIC %md
# MAGIC ### ブラウザコースで困った場合
# MAGIC
# MAGIC | 表示・症状 | 確認すること |
# MAGIC |---|---|
# MAGIC | `ug: command not found`／`.local/bin is not on your PATH` | 同じ本編のTerminalで`export PATH="$HOME/.local/bin:$PATH"`を実行。本編0.1の導入先も確認 |
# MAGIC | Claudeが未導入・npmがない | 本編0.1のClaude Codeネイティブインストーラーを実行。npmの導入は不要 |
# MAGIC | 認証情報が見つからない | 本編NotebookのWeb Terminalを開き直す。PCのターミナルや別Notebookのセッションで実行していないか確認 |
# MAGIC | ブラウザ認証が始まり、`localhost:8020`で接続エラー | 本編1.1の環境設定が適用されていない。処理を`Ctrl+C`で止め、同じTerminalで1.1のブロック全体を再実行 |
# MAGIC | sudoの要求／`--user`が拒否される | 本編1.1の`UG_SKIP_OS_SETTINGS=1`を含むブロックを使い、`--user`を付けない |
# MAGIC | しばらく使った後に認証エラー | Terminalを再接続し、1.1の環境設定と接続をやり直す。古いトークンをコピーして使い続けない |
# MAGIC | Claude Desktopについての警告 | この演習の対象はTerminal内のClaude Code。`Configuration Complete`と通常の応答を確認する |
# MAGIC
# MAGIC 2026年11月13日にServerless環境バージョン6、Python 3.12.3、ug `0.2.1+137.g03952a3`、Claude Code `2.1.323`で、追加ブラウザ認証・sudoなしの設定適用、モデル応答、CSV読み取り、コード作成、Pythonでの在庫集計、`ug usage --all`を確認しました。在庫数22・在庫金額572,000の出力を、作成されたコードの独立実行でも確認しています。サブエージェントへの読み取り作業の委譲も完了し、ルーティング記録に`system.ai.glm-5-3`が選ばれたことを確認しました。生成されたug・Claudeの設定ファイルに、今回使用した認証トークンの値が保存されていないことも確認しました。ワークスペースの共通設定・権限・予算・サービスを変更せずに行った検証です。
# MAGIC
# MAGIC Smart Routing・ポリシー・Smart defaults・トレースの演習には、それぞれの公開設定・権限・事前準備が必要です。上記の接続検証だけで、予算到達時の切り替えやトレース到着まで確認済みとは扱いません。講師は開催環境で使用する章を事前確認してください。
# MAGIC
# MAGIC 参考: [Web Terminalの利用条件](https://docs.databricks.com/aws/ja/compute/web-terminal) / [検証したugの認証実装](https://github.com/databricks/unity-gateway/blob/03952a3fec7e6c35e4e90d2528e54b4ec147b41c/src/ucode/databricks.py#L1950) / [ユーザー領域への公開設定適用](https://github.com/databricks/unity-gateway/blob/03952a3fec7e6c35e4e90d2528e54b4ec147b41c/docs/managed-workspace-policy.md)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. ワークスペースと権限
# MAGIC
# MAGIC 各自の演習用ワークスペースで、管理者による設定と開発者による利用の両方を体験します。**セクション1の設定公開と3の予算作成を自分で行うには、ワークスペース管理者権限が必要です。** Notebookを実行できるWorkspace accessとPython実行環境も準備してください。
# MAGIC
# MAGIC | 操作 | 必要な権限・担当者 |
# MAGIC |---|---|
# MAGIC | ブラウザコースのWeb Terminal | ワークスペースでWeb Terminalが有効。本人が本編Notebookを対応するServerless環境で実行できること |
# MAGIC | Coding Agent設定の公開・ワークスペースのプレビュー有効化 | ワークスペース管理者 |
# MAGIC | 予算の作成（本編3） | Governance HubのCost画面から、ワークスペース管理者が自分のワークスペースに限定して作成。作成者にBudget Managerが付く。Unity Gateway側やアカウント全体の予算作成はアカウント管理者 |
# MAGIC | モデルの呼び出し | 親カタログの`USE CATALOG`、親スキーマの`USE SCHEMA`、モデルサービスの`EXECUTE`。Smart Routingの候補すべてに必要 |
# MAGIC | モデルサービスの新規作成 | 保存先スキーマの`CREATE SERVICE`と親への`USE CATALOG`・`USE SCHEMA`。配信先モデルの`EXECUTE`と親へのアクセスも必要 |
# MAGIC | サービスへのポリシー設定・配信先変更 | 対象サービスの所有者、または`MANAGE`。既定以外のポリシー評価モデルを選ぶ場合は、そのモデルサービスの`EXECUTE`と親への`USE CATALOG`・`USE SCHEMA`も必要 |
# MAGIC | 標準のUsage Dashboard（任意） | アカウント管理者が初期作成。閲覧者はダッシュボードの閲覧権限。個別のデータ権限で実行する場合は、参照システムテーブル・SQL Warehouseの利用権限も必要 |
# MAGIC | 統合トレースの初期設定（任意・一度だけ） | メタストア管理者。保存先の`USE CATALOG`・`USE SCHEMA`・`CREATE TABLE`も必要 |
# MAGIC | 統合トレースの閲覧（任意） | トレーステーブルの`SELECT`と親への`USE CATALOG`・`USE SCHEMA`、利用するSQL Warehouseの`CAN USE` |
# MAGIC
# MAGIC カタログ・スキーマは利用可能なものを指定します。未作成ならカタログエクスプローラーで **Create catalog**、そのカタログ内で **Create schema** を選んで作成するか、管理者に準備を依頼してください。
# MAGIC
# MAGIC 参考: [Coding Agent設定](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-configure-govern) / [予算の権限](https://docs.databricks.com/aws/ja/admin/account-settings/budget-permissions) / [モデルサービスの要件](https://docs.databricks.com/aws/ja/ai-gateway/model-services#requirements) / [ポリシーの要件](https://docs.databricks.com/aws/ja/data-governance/unity-catalog/service-policies/create-service-policy#prerequisites)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. プレビュー
# MAGIC
# MAGIC ワークスペース側はユーザーメニューの **Previews**、アカウント側はアカウントコンソールの **Previews** で確認します。
# MAGIC
# MAGIC **すでに有効なら変更は不要です。** 無効な場合だけ、下表の管理者が有効化します。Betaでも既定で有効な場合があり、[公式のリリース区分](https://docs.databricks.com/aws/ja/release-notes/release-types#platform-releases)では、Betaの一般的な既定値はPremiumでON、EnterpriseでOFFと説明されています。個別設定や機能ごとの継承もあるため、利用環境の実際の有効状態を確認してください。
# MAGIC
# MAGIC | プレビュー名 | 設定する場所・担当者 | 使用する演習 |
# MAGIC |---|---|---|
# MAGIC | **[Unity Gateway Managed Configuration](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-configure-govern)** | ワークスペース／ワークスペース管理者 | セクション1以降のCoding Agent設定。必須 |
# MAGIC | **[Governance Hub](https://docs.databricks.com/aws/ja/admin/governance-hub#enable-governance-hub)** | アカウントコンソール／アカウント管理者 | 本編3の予算作成。開催前に有効化すると、参加者はワークスペース管理者として自分のワークスペースの予算を作成できる |
# MAGIC | **[Unity Gateway Service Policies](https://docs.databricks.com/aws/ja/data-governance/unity-catalog/service-policies/create-service-policy#prerequisites)** | ワークスペース／ワークスペース管理者 | セクション4のポリシー作成・利用。有効化済みならそのまま使用 |
# MAGIC | **[Enhanced Unity Gateway](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#requirements)** | アカウントコンソール／アカウント管理者 | [Smart Routing](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-model-selection#smart-routing)、[Smart defaults](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-costs#adjust-recommendations-as-spending-increases)、[統合トレース](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#enable-the-unified-trace-table) |
# MAGIC
# MAGIC 表の「設定する場所」はプレビューを有効にする場所です。**Enhanced Unity Gatewayはアカウント単位で有効化**しますが、Coding Agentの公開設定はワークスペース単位、統合トレースの保存先はメタストア単位で別途設定します。Smart Routingは有効化後、ワークスペースへの反映に1～2分かかる場合があります。
# MAGIC
# MAGIC **Governance Hubもアカウント単位のBetaです。** アカウント管理者が開催前に **Previews > Governance Hub** を有効にし、参加者のワークスペース管理者権限で **Governance > Cost > View all budgets** を開けることを確認します。有効化後、データの表示まで最大1日かかる場合があるため、当日直前の準備は避けます。以後のワークスペースに限定した予算作成は、ワークスペース管理者が行えます。
# MAGIC
# MAGIC コンプライアンスセキュリティプロファイルを使用していない環境では、**Enhanced Unity Gateway**でもService Policiesが有効になります。必要なプレビューが表示されない場合は、Databricks担当者へ確認してください。
# MAGIC
# MAGIC Smart Routing・Smart defaults・統合トレースの準備ができない場合は、その部分を省略できます。Smart Routingを省略する場合は、本編セクション1のUI設定を`smart_routing.enabled: false`にし、コード例も`smart_routing=False`で作成します。プレビューをONにするだけでは、統合トレースの保存先作成や閲覧権限の付与は完了しません。
# MAGIC
# MAGIC 参考: [プレビューの管理](https://docs.databricks.com/aws/ja/admin/workspace-settings/manage-previews) / [Service Policiesの要件](https://docs.databricks.com/aws/ja/data-governance/unity-catalog/service-policies/create-service-policy#prerequisites)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Notebookの設定
# MAGIC
# MAGIC このワークショップではClaude Codeを使います。Unity Gatewayは、Claude CodeやCodexから、AgentのAPI形式に対応するGLM・KimiなどのOSS系モデルを使う構成にも対応しています。`ug`は接続先・認証・モデルの設定と起動をまとめて行います。仕組みとAPI要件は本編4.2を参照してください。
# MAGIC
# MAGIC 講師がOSS系モデルへの切り替えも紹介する場合は、開催前に対象モデルのAPI対応・利用権限・Coding Agent設定での許可を確認し、`/model`で選択して、ファイル読み取り・コード作成・ツール実行まで試してください。Notebookの`SYSTEM_MODELS`はClaudeモデルを使う標準演習用の初期値です。OSS系モデルの追加を行う場合は、既存の公開設定を保存し、同じワークスペースの利用者への影響も確認します。
# MAGIC
# MAGIC 本編セクション0.2の入力は、次のタイミングで使います。最初にすべて埋める必要はありません。
# MAGIC
# MAGIC | 入力・変数 | 指定する内容・タイミング |
# MAGIC |---|---|
# MAGIC | `terminal` | `browser`は本編のWeb Terminal、`local`はPC。既定は`browser`。変更後は0.2と1.1のセルを再実行 |
# MAGIC | `catalog`・`schema` | セクション4でモデルサービスを新規作成する保存先。既定値は`unity-gateway-workshop.hands_on` |
# MAGIC | `existing_service` | 既存サービスを再利用する場合だけ完全修飾名を指定。通常は空欄 |
# MAGIC | `budget_id` | 本編3で予算を作成した後、3.1を試す場合だけ入力。3.1のセルがその場で最新値を読むため、0.2の再実行は不要 |
# MAGIC | `analysis_start_utc` | 初回実行時刻が初期値。演習開始前に0.2を実行し、過去の記録を使う場合だけ開始時刻を変更 |
# MAGIC | `SYSTEM_MODELS` | 開催環境で提供される、Messages API対応の`system.ai`モデルを2～3個指定。講師は開催前に確認 |
# MAGIC
# MAGIC ### 作成済みのサービスを再利用する場合
# MAGIC
# MAGIC `existing_service`へ自分のサービスの完全修飾名を入力し、本編0.2の設定セルを再実行します。入力した名前は`catalog`・`schema`より優先されます。
# MAGIC
# MAGIC 完全修飾名は`カタログ名.スキーマ名.サービス名`の形式です。既存サービスを再利用する場合はサービスの新規作成を省略し、同等のポリシーも設定済みならポリシーの作成を省略します。Messages APIに対応していない場合だけ、本編セクション4.2で配信先を変更します。
# MAGIC
# MAGIC [AI Governanceワークショップ](https://github.com/databricks-solutions/databricks-japan-bootcamp/tree/main/databricks-llmops-ai-governance-workshop)で作成したモデルサービスも、この方法で再利用できます。そのNotebookで表示された完全修飾名を指定してください。別のアプリも同じサービスを使う場合は、配信先の変更がそのアプリにも影響するため、変更前のルーティングを保存して確認します。
# MAGIC
# MAGIC ### 過去のトレースを分析する場合
# MAGIC
# MAGIC `analysis_start_utc`へタイムゾーン付きの開始時刻（例：`2026-11-10T00:00:00+00:00`）を指定し、本編6.1の指示生成セルを再実行します。分析終了時刻は、そのセルの実行時刻で固定されます。全セルを再実行する必要はありません。

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. 観測データの準備
# MAGIC
# MAGIC ### 統合トレース：演習開始前に設定する
# MAGIC
# MAGIC **本編6で当日の操作を分析する場合は、開発課題を始める前に保存先と閲覧権限を準備してください。** メタストア管理者が **Govern > Traces > Set up tracing** で初期設定します。新しいテーブルでは記録の到着に最大1時間かかる場合があるため、開催前に到着も確認します。有効化前の操作は記録されません。
# MAGIC
# MAGIC 保存先にDefault Storageのカタログを使う場合は、**[Zerobus Ingest Default Storage](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#requirements)**も確認します。この機能は**一般提供（GA）で、通常は既定で有効**です。コンプライアンスセキュリティプロファイルを使用する環境など、一部のワークスペースではワークスペース管理者が **Previews** から明示的に有効化します。
# MAGIC
# MAGIC 保存先はメタストア単位の共通テーブルです。同じメタストアに接続されたワークスペースで共有し、参加者ごとに作成する必要はありません。アカウント全体で必ず1つという意味ではありません。MLflowエクスペリメントのトレース保存先とも異なります。
# MAGIC
# MAGIC 初期状態ではテーブル所有者だけが閲覧できます。共有する前にUCのアクセス制御を準備してください。分析指示の本人条件はアクセス制御の代わりにはなりません。
# MAGIC
# MAGIC 初期設定で選んだ保存先の完全修飾名（`カタログ.スキーマ.unity_gateway_otel_spans`）を控え、参加者へ案内できるようにします。本編では「自分が利用したモデルのログを確認したい」から始め、同じGenie Codeの会話で「ポリシーで拒否されたのあった？」などと続けます。保存先を取得できない場合は、このテーブル名を直接伝えて分析へ進みます。開催前に、参加者と同じ権限で分析できることを確認してください。
# MAGIC
# MAGIC 準備できない場合は分析編を省略するか、閲覧を許可された事前記録で進めます。
# MAGIC
# MAGIC 参考: [初期設定と保存先](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#enable-the-unified-trace-table) / [閲覧権限](https://docs.databricks.com/aws/ja/ai-gateway/unified-trace-table#permissions-and-access-control)
# MAGIC
# MAGIC ### 標準のUsage Dashboard
# MAGIC
# MAGIC アカウント管理者が **Govern > Create Usage Dashboard** から初期作成し、閲覧範囲とデータ権限を設定します。未準備なら本編5.2は講師の準備済み画面で紹介しても構いません。
# MAGIC
# MAGIC 基になる`system.ai_gateway.usage`は通常1時間以内に記録が利用可能になり、新しいワークスペースではさらに時間がかかる場合があります。当日の操作が表示されることを完了条件にはしません。
# MAGIC
# MAGIC Usage Dashboardと統合トレースは別のデータソースです。それぞれの権限・対象期間・反映時刻を確認してください。
# MAGIC
# MAGIC 参考: [モデルの使用状況・標準ダッシュボード](https://docs.databricks.com/aws/ja/ai-gateway/usage-tracking)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. 開始前の記録と終了後の復元
# MAGIC
# MAGIC Coding Agent設定はワークスペース内で共有されます。演習用のワークスペースを使い、次の情報を手元に保存します。
# MAGIC
# MAGIC 1. **Unity Gateway > Govern > Agent configuration > Edit configuration** に既存のJSONがある場合は、そのコピー。
# MAGIC 2. ローカルコースは、これまでugを使っていたか、PCで普段使っているワークスペースURL、Claude Codeの起動方法。会社がClaude CodeやUGを管理している場合は、会社が案内する復元手順も確認します。
# MAGIC 3. 既存サービスを再利用・変更する場合は、変更前のルーティングとポリシー。
# MAGIC
# MAGIC Notebookのコードは既定では設定・分析指示の表示までです。設定をコードで反映する場合だけ、各章の`APPLY_...`を明示的に`True`へ変更します。他のAgent・MCP・Skillsなどの設定は保持します。
# MAGIC
# MAGIC ### ブラウザコースの終了
# MAGIC
# MAGIC Claude Codeを終了し、残すコードを自分のWorkspaceフォルダやGitへ保存します。PCに演習用の設定を適用していないため、PCの復元操作は不要です。現在のTerminalで環境変数を解除する場合は`unset DATABRICKS_BEARER UG_SKIP_OS_SETTINGS`を実行します。ワークスペースの共通設定・予算・サービスの復元は、本編7に沿って別途行います。
# MAGIC
# MAGIC ### ローカルコース：PCの設定を戻す
# MAGIC
# MAGIC Claude Codeを終了し、本編セクション7に沿ってワークスペース側の設定を先に戻します。その後、PCの設定は演習前の利用状況に合う方法を選びます。会社がClaude CodeやUGの設定・起動方法を管理している場合は、会社の案内を優先してください。
# MAGIC
# MAGIC | 演習前の利用状況 | 終了後の操作 |
# MAGIC |---|---|
# MAGIC | ugを使っていなかった | 下の注意点を確認して`ug revert`を実行します。UGが保持するバックアップの復元や、UGが新規作成した設定の削除後、普段の方法でClaude Codeを起動します |
# MAGIC | 既にugを使っていた | 保存した普段のURLで`ug configure --workspace https://普段のワークスペースURL --agent claude`を実行し、`ug claude`で起動します。続けて`ug revert`は実行しません |
# MAGIC | 会社がClaude CodeやUGの設定・起動方法を管理 | 会社の設定・復元・起動手順に従います。参加者判断で管理設定を解除しません |
# MAGIC
# MAGIC 起動後は`/status`で普段の接続先・モデルになっていることを確認し、通常の呼び出しで認証も確認します。普段のワークスペースへの再設定では、その時点で公開されている設定を適用します。演習前のローカルの手動調整まで完全に復元する操作ではありません。
# MAGIC
# MAGIC ### `ug revert`の影響範囲とバックアップ
# MAGIC
# MAGIC - **Claudeだけに限定されません。** 他のUG管理Agent・MCP設定も復元対象となり、UGの保存済みセットアップ状態を消去します。
# MAGIC - **管理設定のバックアップは最初にUGが変更する前の状態です。** `ug configure`を実行するたびに保存し直されるわけではないため、既存のug利用者は「演習開始直前に戻る」と考えて実行しないでください。
# MAGIC - この演習はOS管理設定への書き込みを省きます。以前のug利用で作成した管理設定やバックアップがある場合は、その履歴も復元に関わるため、普段のワークスペースへの再設定または会社の手順を選びます。復元結果を確認し、管理設定に関する問題は端末管理者へ確認してください。
# MAGIC
# MAGIC ワークスペースのAgent configuration・予算・サービスの配信先は、PCの復元とは別です。本編セクション7に沿って、開始前に保存した情報から戻します。再利用したサービス・ポリシーは削除しません。
# MAGIC
# MAGIC 会社の配布処理や起動コマンドが設定を再適用する場合は、`ug revert`後も会社の復元手順が必要です。バックアップがない、会社設定へ自動的に戻る、普段の接続へ戻らない場合は、変更前の記録とコマンドの出力を端末管理者へ伝えて確認します。
# MAGIC 復元後、今のシェルに設定した環境変数を解除する場合は、Agentを終了して`unset UG_SKIP_OS_SETTINGS`を実行します。
# MAGIC
# MAGIC 参考: [ugのコマンドとrevert](https://docs.databricks.com/aws/ja/ai-gateway/coding-agent-ug-cli) / [検証したugのバックアップ・復元仕様](https://github.com/databricks/unity-gateway/blob/03952a3fec7e6c35e4e90d2528e54b4ec147b41c/docs/os-managed-settings-design.md#backup-model)
# MAGIC
# MAGIC <a href="$./Unity_Gateway_ハンズオン">本編Notebookへ戻る</a>
