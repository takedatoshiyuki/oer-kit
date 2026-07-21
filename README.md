# OER リポジトリ

教育資源（スライド・教科書・演習・動画・データ等）をオープンライセンスで公開・再利用可能にする
リポジトリ。メタデータは schema.org / LRMI（AMB プロファイル）準拠。

**設計の全体像は [docs/design.md](docs/design.md) を参照。**

## 構造

```
docs/design.md      設計書（フォーマットとメタデータの仕様・根拠）
config.yaml         公開URL等の設定（base_url はここだけで定義）
schemas/            metadata.yaml の JSON Schema（正規仕様）
vocabularies/       統制語彙（教材タイプ・利用者・教育段階・主題分野）
tools/              検証・JSON-LD生成・カタログ構築・クロール補助（→ tools/README.md）
resources/<slug>/   教材本体。1リソース = 1ディレクトリ
  ├── metadata.yaml   メタデータ（正）
  ├── content/        編集可能なソース（Markdown, pptx, ipynb …）
  └── assets/         画像・データ・字幕など
```

## リソースの追加手順

1. `resources/` に slug 名（小文字英数字とハイフン）のディレクトリを作る
2. [記入例](resources/intro-statistics-slides/metadata.yaml) を参考に `metadata.yaml` を書く
   （必須: name / description / inLanguage / license / creator / learningResourceType / about / datePublished）
3. `content/` に編集可能なソースを、`assets/` に付随ファイルを置く
4. `python3 tools/validate.py` を通す（スキーマ + 語彙キー + 運用ポリシーの検証）
5. `make site` で公開一式（HTML + JSON-LD + catalog.json + sitemap.xml）を `_site/` に生成
   （`make preview` でローカル確認。詳細は [tools/README.md](tools/README.md)）

## ライセンス方針

- **メタデータ・スキーマ・語彙・ドキュメント**: CC0 1.0（[LICENSE.md](LICENSE.md)）
- **教材コンテンツ**: 各リソースの `metadata.yaml` の `license` に従う。自作の既定は CC0 推奨、
  派生物は元素材の継承義務に従う。継承ルールは [docs/design.md](docs/design.md) §7.2。
- **ND 系（改変禁止）**: 本体はホストしないが、`mode: referenced` のリンク参照エントリとして
  メタデータと短い内容紹介のみを目録化できる（AI生成可・公開前の人手レビュー必須。同 §7.3）。
