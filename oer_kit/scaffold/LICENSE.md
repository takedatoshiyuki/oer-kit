# ライセンス

本リポジトリは二層のライセンス構造を採る（背景と継承ルール: [docs/design.md](docs/design.md) §7.2）。

## 1. メタデータ・スキーマ・語彙・ドキュメント — CC0 1.0

以下は [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/) で提供する。
帰属表示なしで自由に複製・加工・再配布できる（学術慣行としての出典明示は歓迎する）。

- `resources/*/metadata.yaml`（メタデータ記述）および生成される `catalog.json`
- `schemas/`（JSON Schema）
- `vocabularies/`（統制語彙。外部語彙の URI・原語ラベルは各出所に帰属）
- `docs/`・`README.md` などのドキュメント

例外: メタデータ中の `quotedDescription`（出典サイトの説明文の転載・引用）は CC0 の対象外で、
各出典の条件または引用の範囲で目録ページにのみ表示する（`catalog.json` には含めない）。

## 2. 教材コンテンツ — 各リソースの表示に従う

`resources/<slug>/` 配下の教材本体（`content/`, `assets/`）には、**各リソースの
`metadata.yaml` の `license` フィールドに記載されたライセンス**が適用される。

- 自作教材の既定は CC0 を推奨
- 他の教材の翻案・第三者素材を含む教材は、元素材のライセンスの継承義務に従う
- ND（改変禁止）系の教材は本リポジトリでは受け入れない

（本ファイルは方針の要約であり、個別の権利処理は各リソースの記載が優先する）
