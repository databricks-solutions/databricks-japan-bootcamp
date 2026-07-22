# 参考出力

参加者がローカルで生成した `out/` と比較するための例。

| ディレクトリ | 内容 |
|---|---|
| `before/` | BladeBridge標準変換。`NO CYCLE` と `UPDATE ... FROM` が残る |
| `solution/` | 完成overrideを適用した変換結果。`FAIL 0` の想定 |
| `solution/teradata-overrides.json` | エージェントが作る移植可能なoverrideテンプレートの完成例 |

Lakebridgeのバージョンにより、空白やコメントなどは異なる場合がある。

`inherit_from` の `__BLADEBRIDGE_BASE_CONFIG__` は、`tools/prepare_overrides.py` が参加者環境の絶対パスへ展開する。ユーザー名やローカルのインストールパスをリファレンスへコミットしない。
