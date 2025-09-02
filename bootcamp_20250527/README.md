# Databricks Data + AI Boot Camp 資料リンク
2025年5月27日開催のDatabricks Boot Campで使用する資料のリンクをまとめています。

# ハンズオン環境セットアップ
以下の手順に従ってハンズオン環境をセットアップします。

- [ハンズオン環境セットアップ手順](setup.md)
    - Databricksワークスペースでは上記リンクではアクセスできないため、同じフォルダにある `setup.md` を参照してください。

## セル17の実施に時間がかかる場合の対処方法
セル17の中に**3箇所、Claude 3.7 Sonnetを呼び出している箇所**があります。その3箇所をMeta Llama 3.3の呼び出しに変更することで処理が短時間で終わる可能性があります。

- 置換前: `databricks-claude-3-7-sonnet`
- 置換後: `databricks-meta-llama-3-3-70b-instruct`

# データエンジニアリング ハンズオン
Databricksワークスペースで以下のノートブックを開きます。

- notebooks/data_engineering_hands_on/00_main.py

# AI/BIワークショップ
以下のスライドを使用します。

- [Databricks AI/BIクイックワークショップ](http://speakerdeck.com/databricksjapan/aibi-quick-workshop)
