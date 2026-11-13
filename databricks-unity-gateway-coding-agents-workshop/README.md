# Unity Gateway × Coding Agents ワークショップ

DatabricksのUnity Gatewayを通じてClaude Codeを使い、モデルの選択、Smart Routing、予算、ガードレール、利用状況・トレースを体験します。**推奨のブラウザコースなら、参加者のPCへのツール導入は不要です。**

**使い慣れたClaude CodeやCodexから、対応するGLM・KimiなどのOSS系モデルも選べる**ことがUnity Gatewayの特徴です。モデルの選択肢を広げながら、権限・予算・ポリシー・利用記録をDatabricksで管理できます。本編の標準演習はClaude CodeとClaudeモデルで進め、OSS系モデルへの切り替えは発展として扱います。

## 教材とファイル構成

**このディレクトリの教材だけで受講できます。** 別のワークショップの受講やリソース作成は必要ありません。

| ファイル | 役割 | Workspaceへインポート |
|---|---|---|
| [Unity_Gateway_ハンズオン.py](./Unity_Gateway_ハンズオン.py) | 参加者が順に進める本編 | 必要 |
| [事前準備ガイド.py](./事前準備ガイド.py) | 講師の開催準備、コース別の導入、権限・プレビュー、保存・復元 | 必要 |
| README.md | 教材の入口と進め方 | 不要 |
| tests/test_workshop.py | 教材コードの保守・検証 | 不要 |

参加者向け資料は**2つのNotebook**です。組織へのMDM配布は演習範囲外です。

## 前提条件

- Unity Gatewayを利用できるDatabricksワークスペース。ブラウザコースでは、ServerlessとWeb Terminalを利用できること。
- 対象モデルを呼び出せる権限。モデルサービスを新規作成する場合は、保存先のカタログ・スキーマと必要な作成権限。
- Coding Agent設定の公開と予算作成を行うワークスペース管理者。プレビュー・トレース・ダッシュボードの準備は、準備ガイドに従って担当管理者が実施。

## 始め方

1. **講師・管理者**は開催前に準備ガイドを確認し、演習用ワークスペース、利用権限、必要なプレビューを準備します。トレースを分析する場合は、収集を事前に有効にし、記録の到着と閲覧権限も確認します。
2. **参加者**は上記2つのPythonファイルを、ファイル名を変えずに同じWorkspaceフォルダへPython Notebookとしてインポートします。Notebook間のリンクは、この配置を前提にしています。
3. **本編のセクション0から**進めます。0.2の設定セルを実行して入力欄を作り、左側の「パラメータ」パネルでコースと保存先を選択します。変更後は設定セルを再実行します。
4. ワークスペースのCoding Agent設定を公開した後、**本編1.1で表示されるコマンドを、選んだコースのターミナルへコピー**してClaude Codeを起動します。

### 実行環境を選ぶ

| コース | 実行場所 | 認証・設定 |
|---|---|---|
| **ブラウザ（推奨）** | 本編Notebookに接続したServerlessのWeb Terminal | Terminalにある本人の認証を再利用し、実行環境のユーザー設定へ適用。追加OAuth認証・PAT発行・sudoは不要 |
| ローカル | 参加者のPCのターミナル | Python 3.12以降・Databricks CLI・uv・Claude Codeを準備。本人のOAuth認証でユーザー設定を適用し、終了後の復元も体験 |

ブラウザコースは、**全章で本編Notebookの同じTerminalセッション**を使います。準備ガイドは手順を読むために開き、コマンドは本編側で実行します。別NotebookのTerminalでは環境が異なる場合があります。導入コマンドと認証・ユーザー設定の指定は、本編0.1・1.1にまとめています。

両コースとも検証済みのugコミットを使用します。会社がAgent設定を管理しているPCでは会社の案内を確認し、ローカルの設定変更が難しい場合はブラウザコースを選びます。

**両コースとも`UG_SKIP_OS_SETTINGS=1`を指定してOS全体への管理設定の書き込みを省き、毎回`ug claude`で起動します。** ワークスペースの公開設定はユーザー領域へ適用されます。既存のOS管理設定がある場合はAgentの設定優先順位で引き続き適用されます。

## モデルサービスを新規作成する場合・再利用する場合

| 進め方 | 設定と操作 |
|---|---|
| **単独受講・新規作成** | `existing_service`は空欄にします。`catalog`・`schema`を指定し、本編4で自分のモデルサービスとポリシーを作成します |
| **既存サービスを再利用（任意）** | `existing_service`に`カタログ.スキーマ.サービス名`を入力します。サービスの新規作成を省略し、同等のポリシーも設定済みならその作成も省略します |

[AI Governanceワークショップ](../databricks-llmops-ai-governance-workshop/)で作成したモデルサービスも再利用できます。そちらのNotebookで表示された完全修飾名を指定してください。サービス名・既存ポリシーを引き継ぎ、今回のClaude Codeから利用する流れです。

Claude Codeには**Anthropic Messages APIへの対応**が必要です。本編4.2でサービスの対応APIを確認し、非対応の場合だけ、対応モデルへ配信先を変更します。既存のアプリも同じサービスを使う場合は影響があるため、変更前のルーティングを保存し、管理者と確認してください。再利用したサービス・ポリシーは演習終了時に削除しません。

トレースについては、このワークショップで使う**Unity Gatewayの統合トレース**を準備ガイド5に沿って設定します。既存アプリのMLflowトレースとは別のデータソースです。

## 内容と所要時間

目安は演習約100分と事前準備です。開催環境に合わせて、Smart defaults・予算フォールバック・トレース分析を説明や講師デモにできます。

| 章 | 内容 | 目安 |
|---|---|---|
| 0 | コース別の環境準備、既存設定・接続先の確認 | 事前準備 |
| 1 | Coding Agent設定、ugで接続、Claude Codeの起動 | 20分 |
| 2 | 小さな開発課題とSmart Routing | 15分 |
| 3 | 予算、ug usage、Smart defaults | 10分 |
| 4 | モデルサービス・ポリシーの作成または再利用、対応APIとOSS系モデル | 25分 |
| 5 | 予算フォールバックと標準のUsage Dashboard | 10分 |
| 6 | 統合トレースをGenie Codeで分析 | 10分 |
| 7 | 振り返りと設定の復元 | 10分 |

## 設定の影響と終了時の復元

**Coding Agentの公開設定・予算・UCサービス・ポリシーは共有リソースです。** どちらのコースでも、演習用ワークスペースを使い、変更前の公開設定と既存サービスのルーティングを保存します。`ug configure`自体は、公開設定を取得して実行環境へ適用する操作です。

ブラウザコースはPCの設定復元が不要です。残すコードはWorkspace filesなどへ保存します。Serverlessのホーム内のファイル・導入ツールが環境終了後も残るとは扱いません。

ローカルコースでは、ugの接続状態と本人のユーザー設定が更新されます。終了後は演習前のug利用状況に応じて、`ug revert`または普段のワークスペースへの再設定を選びます。具体的な手順と影響範囲は、本編7と準備ガイド6にまとめています。

## 確認した環境と範囲

2026年11月13日に、Serverless環境バージョン6、Python 3.12.3、ug `0.2.1+137.g03952a3`（コミット`03952a3fec7e6c35e4e90d2528e54b4ec147b41c`）、Claude Code `2.1.323`で確認しました。

追加OAuth認証・sudoなしの設定、Unity Gateway経由の応答、Claude CodeによるCSV読み取り・コード作成・Python実行、`ug usage --all`による予算表示、子Agentへの委譲とSmart Routingの選択モデル記録を確認済みです。

上記はWeb Terminal上の接続・開発操作の確認結果です。開催前には、講師がサービス・ポリシーの作成から統合トレース分析まで、使用する章を手動で通し確認します。予算を消化して切り替えを発生させる操作は完了条件にしません。

## 教材コードの確認

このディレクトリで実行します。Databricksへの接続や実リソースの変更は行いません。

```bash
python3 -m unittest discover -s tests -v
```

Notebookの設定反映フラグ`APPLY_...`は既定で`False`です。モデルサービス・ポリシー・予算の作成や配信先変更は、手順に沿ってUIで行います。

## 参考

- [Web Terminalの利用条件](https://docs.databricks.com/aws/en/compute/web-terminal)
- [Coding Agentの設定](https://docs.databricks.com/aws/en/ai-gateway/coding-agent-configure-govern)
- [Claude Code・CodexなどでOSSモデルを使う](https://docs.databricks.com/aws/en/ai-gateway/coding-agent-open-source-models)
- [ugのコマンド](https://docs.databricks.com/aws/en/ai-gateway/coding-agent-ug-cli)
- [モデルサービスの作成と更新](https://docs.databricks.com/aws/en/ai-gateway/model-services)
- [統合トレース](https://docs.databricks.com/aws/en/ai-gateway/unified-trace-table)

## Support and License

本コンテンツはDatabricksの公式サポート対象ではありません。不具合はこのリポジトリのGitHub Issueへ報告してください。利用条件はリポジトリルートの[LICENSE.md](../LICENSE.md)と[NOTICE.md](../NOTICE.md)を参照してください。
