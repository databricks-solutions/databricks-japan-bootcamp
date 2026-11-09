# サンプルデータについて

このフォルダのサンプルデータ（7案件分の通話音声・損害写真・修理見積書）は、本ワークショップのために作成したものです。登場する会社名・人名・修理工場・番号はすべて架空です。

## 音声（`audio/case_01.wav` 〜 `case_07.wav`）

[Open JTalk](https://open-jtalk.sourceforge.net/) と以下の音響モデルを用いて合成しました。これらの音声を再配布するときは、このクレジットを添えてください。

音響モデル（オペレーター）：HTS Voice "Mei"

```
released by MMDAgent Project Team (https://www.mmdagent.jp/)
Copyright (c) 2009-2013 Nagoya Institute of Technology, Department of Computer Science
Licensed under the Creative Commons Attribution 3.0 license
https://creativecommons.org/licenses/by/3.0/
```

音響モデル（契約者）：HTS Voice "NIT ATR503 M001"

```
released by HTS Working Group (https://open-jtalk.sourceforge.net/)
Copyright (c) 2003-2012 Nagoya Institute of Technology, Department of Computer Science
              2003-2008 Tokyo Institute of Technology, Interdisciplinary Graduate School of Science and Engineering
Licensed under the Creative Commons Attribution 3.0 license
https://creativecommons.org/licenses/by/3.0/
```

## 損害写真（`image/case_01.jpg` 〜 `case_07.jpg`）

画像生成モデルで生成しました。実在の車種・メーカーを表すものではありません。

## 修理見積書（`form/`）

プログラムで生成しました。`case_05.jpg` は手書きの見積書をスキャンした想定の画像です。生成には次のフォントを使用しています（いずれも [SIL Open Font License 1.1](https://openfontlicense.org/)）。

- [BIZ UDGothic](https://github.com/googlefonts/morisawa-biz-ud-mincho)（Copyright 2022 The BIZ UDGothic Project Authors）
- [Yomogi](https://github.com/satsuyako/YomogiFont)（Copyright 2020 The Yomogi Project Authors）

## 正解データ（`ground_truth/estimate_answers.json`）

修理見積書に記載した値です。付録のノートブックで、抽出結果と突き合わせるのに使います。
