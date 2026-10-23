"""ノートブックに表示する図。02（概要）と 03（データ処理の流れ）から使う。"""


def pipeline_flow_html(schema: str) -> str:
    """03 で作るもの（テーブル・AI Search インデックス・UC関数）と、エージェントのツールの関係の図（HTML）。①〜⑤ は 03 の章の番号。"""
    return _PIPELINE_FLOW.replace("__SCHEMA__", schema)


_PIPELINE_FLOW = """
<style>
.flow{display:grid;grid-template-columns:185px minmax(165px,1fr) 120px minmax(165px,1fr) 120px minmax(130px,1fr) 150px 30px 165px;gap:16px 0;align-items:center;
      font-family:sans-serif;font-size:13px;max-width:1280px;margin:8px 0}
.flow .h{font-weight:bold;color:#555;text-align:center;font-size:12px}
.flow .b{border-radius:8px;padding:8px 10px;text-align:center;line-height:1.45}
.flow .src{background:#f1f3f5;border:1px solid #adb5bd}
.flow .tbl{background:#fff4e6;border:1px solid #f59f00}
.flow .idx{background:#ebfbee;border:1px solid #40c057}
.flow .fn{background:#f3f0ff;border:1px solid #7950f2}
.flow .tool{background:#1b3139;color:#fff}
.flow .a{position:relative;text-align:center;padding:0 14px 0 4px}
.flow .a:before{content:"";position:absolute;left:0;right:8px;top:50%;border-top:2px solid #868e96}
.flow .a:after{content:"";position:absolute;right:0;top:calc(50% - 6px);border-top:6px solid transparent;border-bottom:6px solid transparent;border-left:10px solid #868e96}
.flow .a span{position:relative;display:inline-block;background:#e7f5ff;border:1px solid #339af0;border-radius:14px;padding:3px 8px;font-size:12px;white-space:nowrap}
.flow .a small{display:block;font-size:11px;color:#666;background:none;border:0}
.flow .to{text-align:center;color:#1b3139;font-size:18px}
.flow .s{font-size:11px;color:#666}
.flow .tool .s{color:#cfd8dc}
.flow code{font-size:12px;background:none}
.flow .tag{display:inline-block;font-size:10px;color:#fff;background:#868e96;border-radius:4px;padding:0 6px;margin-bottom:2px}
.flow .tbl .tag{background:#f59f00}
.flow .idx .tag{background:#2f9e44}
.flow .fn .tag{background:#7950f2}
.legend{font-family:sans-serif;font-size:12px;color:#555}
.legend span{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle;margin:0 4px 0 12px}
</style>
<div style="overflow-x:auto"><div class="flow">
  <div class="h">元のデータ<br>（01_準備 で配置）</div><div class="h">処理</div><div class="h">テーブル</div><div class="h">処理</div>
  <div class="h">テーブル</div><div class="h">処理</div><div class="h">検索インデックス・関数</div><div></div><div class="h">エージェントのツール<br>（04 以降で使う）</div>

  <div class="b src"><span class="tag">Volume のファイル</span><br><b>PDF</b><br><span class="s">取扱説明書・サービス技術情報・保証規定</span></div>
  <div class="a"><span>① ai_parse_document<small>パース</small></span></div>
  <div class="b tbl"><span class="tag">テーブル</span><br><code>docs_parsed</code><br><span class="s">本文・見出し・表</span></div>
  <div class="a"><span>② ai_prep_search<small>チャンク分割・型番</small></span></div>
  <div class="b tbl"><span class="tag">テーブル</span><br><code>doc_chunks</code><br><span class="s">チャンク＋型番</span></div>
  <div class="a"><span>④ AI Search<small>画面で作る</small></span></div>
  <div class="b idx"><span class="tag">AI Search インデックス</span><br><code>doc_chunks_index</code></div>
  <div class="to">⇒</div>
  <div class="b tool"><code>search_documents</code><br><span class="s">文書を検索</span></div>

  <div class="b tbl"><span class="tag">テーブル</span><br><code>repair_requests</code><br><span class="s">過去の修理受付（対応メモに個人情報あり）</span></div>
  <div class="a" style="grid-column:2 / 5"><span>③ ai_mask<small>個人情報のマスク</small></span></div>
  <div class="b tbl"><span class="tag">テーブル</span><br><code>past_cases</code><br><span class="s">マスク済みの事例</span></div>
  <div class="a"><span>④ AI Search<small>コードで作る</small></span></div>
  <div class="b idx"><span class="tag">AI Search インデックス</span><br><code>past_cases_index</code></div>
  <div class="to">⇒</div>
  <div class="b tool"><code>search_past_cases</code><br><span class="s">過去の事例を検索</span></div>

  <div class="b tbl"><span class="tag">テーブル</span><br><code>products</code>・<code>production_lots</code><br><span class="s">製品・製造ロット</span></div>
  <div class="a" style="grid-column:2 / 7"><span>⑤ UC関数を作る</span></div>
  <div class="b fn"><span class="tag">UC関数</span><br><code>get_product_info</code><br><span class="s">製造番号 → 型番・ロット・保証</span></div>
  <div class="to">⇒</div>
  <div class="b tool"><code>get_product_info</code><br><span class="s">製品情報を照会（MCP 経由）</span></div>
</div></div>
<div class="legend">①〜⑤ はこのノートブックの章の番号。すべて Unity Catalog のスキーマ <code>__SCHEMA__</code> に作られます。</div>
"""


def agent_flow_html() -> str:
    """02: 1件の相談を、エージェントがツールを使って回答案にするまでの流れと、各ツールが使うデータの図（HTML）。"""
    return _AGENT_FLOW


def er_html() -> str:
    """02: テーブル（列とキー）と、UC関数の図（HTML）。"""
    return _ER


def architecture_html() -> str:
    """02: データからアプリ・トレースまでのアーキテクチャの図（HTML）。"""
    return _ARCHITECTURE


_BASE_CSS = """
<style>
.dg{font-family:sans-serif;font-size:13px;color:#1b3139;max-width:1200px;margin:8px 0}
.dg .b{border-radius:8px;padding:8px 10px;line-height:1.5}
.dg .in{background:#f1f3f5;border:1px solid #adb5bd}
.dg .ag{background:#ff3621;color:#fff}
.dg .tl{background:#fff;border:1px solid #ced4da;color:#1b3139}
.dg .out{background:#ebfbee;border:1px solid #40c057}
.dg .tr{background:#fff9db;border:1px solid #fab005}
.dg .tbl{background:#fff4e6;border:1px solid #f59f00}
.dg .idx{background:#ebfbee;border:1px solid #40c057}
.dg .fn{background:#f3f0ff;border:1px solid #7950f2}
.dg .app{background:#1b3139;color:#fff}
.dg .grp{border:1px dashed #868e96;border-radius:10px;padding:10px 12px 12px}
.dg .gt{font-size:12px;font-weight:bold;color:#555;margin-bottom:8px}
.dg .tag{display:inline-block;font-size:10px;color:#fff;background:#868e96;border-radius:4px;padding:0 6px;margin-bottom:2px}
.dg .tbl .tag{background:#f59f00}.dg .idx .tag{background:#2f9e44}.dg .fn .tag{background:#7950f2}
.dg .s{font-size:11px;color:#666}
.dg .ag .s,.dg .app .s{color:#ffe3e0}
.dg .app .s{color:#cfd8dc}
.dg .tl .s{color:#666}
.dg .ln{position:relative;width:2px;height:38px;margin:-12px auto 0;background:#868e96}
.dg .down{text-align:center;color:#868e96;font-size:12px;margin:6px 0}
.dg .down b{font-size:18px;margin-right:6px}
.dg .arr{text-align:center;color:#868e96;font-size:22px;line-height:1}
.dg code{font-size:12px;background:none}
.dg table.er{border-collapse:collapse;font-size:12px;width:100%;background:#fff}
.dg table.er td{border-top:1px solid #f1d3a5;padding:3px 8px}
.dg table.er td.k{color:#e67700;font-weight:bold;width:34px}
</style>
"""

_AGENT_FLOW = _BASE_CSS + """
<div class="dg" style="overflow-x:auto">
<div style="display:grid;grid-template-columns:260px 40px 1fr 40px 270px;align-items:center;min-width:1000px">
  <div class="b in"><b>オペレーターが入れる相談の文章（例）</b><br>
    お客様からのお電話です。2026年8月3日に購入された炊飯器が、炊いている途中で電源が切れてしまうそうです。製造番号は RC5-2604B-00871 です。
    <div class="s" style="margin-top:6px">製造番号・購入日・症状は、エージェントが文章から読み取る</div></div>
  <div class="arr">➜</div>
  <div class="b ag">
    <b>回答支援エージェント</b>（LangGraph ＋ Claude）<br>
    <span class="s">相談とツールの結果を読み、次に呼ぶツールを決める（くり返す）→ そろったら回答の形式にまとめる</span>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px">
      <div class="b tl"><b>① 製品情報の照会</b><br><code>get_product_info</code><br><span class="s">UC関数（MCP 経由）。製造番号から型番・ロット・保証の状態</span></div>
      <div class="b tl"><b>② 文書の検索</b><br><code>search_documents</code><br><span class="s">AI Search。相談に関係する文書を検索</span></div>
      <div class="b tl"><b>③ 過去事例の検索</b><br><code>search_past_cases</code><br><span class="s">AI Search。似た症状の過去の対応を検索</span></div>
    </div>
  </div>
  <div class="arr">➜</div>
  <div class="b out"><b>返すもの</b><br>
    ・（調べた結果）型番・ロット・保証の状態・無償点検の対象か<br>
    ・お客様への回答案（手順は番号付き）<br>
    ・次の対応（5つから1つ）<br>
    ・根拠にした文書</div>
  <div></div><div></div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:0 10px">
    <div><div class="ln"></div><div class="b tbl"><span class="tag">テーブル</span><br><code>products</code>・<code>production_lots</code><br><span class="s">製品（型番・保証の月数）と製造ロット（製造月・工場）</span></div></div>
    <div><div class="ln"></div><div class="b idx"><span class="tag">AI Search インデックス</span><br><code>doc_chunks_index</code><br><span class="s">元は PDF の取扱説明書・サービス技術情報・保証規定</span></div></div>
    <div><div class="ln"></div><div class="b idx"><span class="tag">AI Search インデックス</span><br><code>past_cases_index</code><br><span class="s">元は過去の修理履歴の対応メモ（個人情報をマスク）</span></div></div>
  </div>
  <div></div><div></div>
</div>
<div class="b tr" style="margin-top:10px;min-width:976px"><b>MLflow トレース</b>: ①〜③の呼び出しと結果、回答の作成までが、すべて記録される（ノートブックでも、アプリでも）</div>
</div>
"""

_ER = _BASE_CSS + """
<div class="dg" style="overflow-x:auto">
<div style="display:grid;grid-template-columns:230px 250px 260px 250px;gap:0 20px;align-items:start;min-width:1070px">
  <div class="b tbl"><span class="tag">テーブル</span><br><code><b>products</b></code>（製品・10行）
    <table class="er"><tr><td class="k">PK</td><td>model_no（型番）</td></tr><tr><td></td><td>product_name</td></tr><tr><td></td><td>category</td></tr><tr><td></td><td>warranty_months（保証の月数）</td></tr></table></div>
  <div class="b tbl"><span class="tag">テーブル</span><br><code><b>production_lots</b></code>（製造ロット・783行）
    <table class="er"><tr><td class="k">PK</td><td>lot_no（ロット番号）</td></tr><tr><td class="k">FK</td><td>model_no</td></tr><tr><td></td><td>factory（製造工場）</td></tr><tr><td></td><td>production_month（製造月）</td></tr></table></div>
  <div class="b tbl"><span class="tag">テーブル</span><br><code><b>repair_requests</b></code>（過去の修理履歴・11,884行）
    <table class="er"><tr><td class="k">PK</td><td>request_id（受付ID）</td></tr><tr><td class="k">FK</td><td>model_no・lot_no</td></tr><tr><td></td><td>serial_no（製造番号）・purchase_date</td></tr><tr><td></td><td>symptom_category・result_category</td></tr><tr><td></td><td>operator_memo（対応メモ。<b>個人情報を含む</b>）</td></tr></table></div>
  <div class="b fn"><span class="tag">UC関数</span><br><code><b>get_product_info</b></code>
    <div class="s" style="margin-top:4px">製造番号の先頭（例: RC5-2604B-00871 → <b>RC5-2604B</b>）がロット番号。products と production_lots を引いて、型番・ロット・製造月・製造工場・保証の状態を返す（エージェントのツールになる）</div></div>
</div>
</div>
"""

_ARCHITECTURE = _BASE_CSS + """
<div class="dg" style="overflow-x:auto"><div style="min-width:1100px">
<div class="grp"><div class="gt">Unity Catalog（参加者ごとのスキーマ）　― 03_データパイプライン</div>
  <div style="display:grid;grid-template-columns:1fr 30px 1.3fr 30px 1fr 30px 1fr 30px 1fr;align-items:center">
    <div class="b in"><span class="tag">Volume</span><br>PDF（取扱説明書・サービス技術情報・保証規定）</div><div class="arr">➜</div>
    <div class="b tl"><b>AI関数</b><br><span class="s">ai_parse_document・ai_prep_search・ai_mask（パース・チャンク・マスク）</span></div><div class="arr">➜</div>
    <div class="b tbl"><span class="tag">テーブル</span><br>文書のチャンク・過去事例</div><div class="arr">➜</div>
    <div class="b idx"><span class="tag">AI Search インデックス</span><br>文書・過去事例</div><div class="arr"></div>
    <div class="b fn"><span class="tag">UC関数</span><br>製品情報の照会</div>
  </div>
</div>
<div class="down"><b>⬇</b>エージェントのツールとして使う</div>
<div style="display:grid;grid-template-columns:1fr 40px 1.2fr 40px 1fr;align-items:center">
  <div class="b in"><b>ノートブック</b><br><span class="s">動かす・評価する・改善する（mlflow.genai.evaluate）　― 04〜06</span></div>
  <div class="arr">⬅</div>
  <div class="b ag"><b>エージェント（app/agent_v2.py）</b><br><span class="s">LangGraph ＋ Claude。ノートブックとアプリで同じコードを使う</span></div>
  <div class="arr">➜</div>
  <div class="b app"><b>Databricks Apps</b><br><span class="s">API サーバー ＋ チャット画面（オペレーターが使う）　― 07</span></div>
</div>
<div class="down"><b>⬇</b>すべてのやり取りを記録</div>
<div class="b tr" style="text-align:center"><b>MLflow の実験 ＋ トレース（Unity Catalog のテーブル）</b><br>
  <span class="s">開発時・評価・アプリ（本番）のトレースが同じ実験に入る。MLflow の画面でも SQL でも見られる</span></div>
</div></div>
"""
