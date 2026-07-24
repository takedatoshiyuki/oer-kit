# 利用ガイド（導入者向け）

このシステムで OER（オープンな教育資源）のカタログを作り、公開するためのガイドです。
設計の背景や根拠は[設計書](design.md)に、ツールの詳細は [tools/README.md](../tools/README.md) に
あります。ここでは「使うために必要なこと」だけを順に説明します。

## 1. これは何か

教育資源のメタデータを `metadata.yaml`（1教材=1ファイル）で管理し、

- **検証**（スキーマ・語彙・引用照合・重複検査）
- **公開サイト生成**（Quarto。schema.org/LRMI 準拠の JSON-LD 埋め込み）
- **外部教材の収集支援**（クロール・説明文抽出・AI下書き生成・教材ファイル収集）

をコマンドラインで行う道具立てです。想定する使い方は3つあります:

| 使い方 | 例 | 運用モード（`review_policy`） |
|--------|-----|------------------------------|
| 収集して公開する | 各大学の OCW や個人公開の教材を横断カタログ化 | `aggregator` |
| 組織として公開する | 大学・機関が自組織の教材を公開 | `institutional` |
| 個人で公開する | 自分の授業資料・スライドを公開 | `personal` |

## 2. セットアップ

必要なもの:

- Python 3.10+ と `pyyaml` `jsonschema` `requests`（収集系を使うなら追加で `pandas`）
- [Quarto](https://quarto.org/)（サイト生成。`brew install --cask quarto` 等）
- `make`

最初に [config.yaml](../config.yaml) を自分の環境に合わせて編集します:

```yaml
site_name: ○○大学 OER カタログ        # サイト名
base_url: https://oer.example.ac.jp    # 公開URL (恒久IDの基底。ここだけで定義)
review_policy: institutional           # aggregator / institutional / personal
feedback_url: https://github.com/.../issues   # 誤り報告・削除依頼の窓口
```

`base_url` は全ページの ID・JSON-LD・サイトマップに使われます。**公開後に変えると
リンクが壊れる**ので、確定してから公開してください（変更する場合は旧URLからの
リダイレクトを恒久維持します）。

## 3. 自作の教材を公開する（hosted）

`personal` / `institutional` の基本形です。1教材=1ディレクトリを作ります:

```
resources/intro-statistics/
├── metadata.yaml     # メタデータ（これが正）
├── content/          # 編集可能なソース (Markdown, スライド原稿, ipynb …)
└── assets/           # 画像・データなど
```

`metadata.yaml` の最小形:

```yaml
name:
  ja: 統計学入門スライド
description:
  ja: 記述統計から仮説検定までを扱う講義スライド。表計算ソフトの演習課題つき。
inLanguage: [ja]
license: CC-BY-4.0          # 自作教材は CC0-1.0 / CC-BY-4.0 / CC-BY-SA-4.0 を推奨
creator:
  - type: Person
    name: 山田 太郎
learningResourceType: [slide]   # 語彙: vocabularies/learning-resource-types.yaml
about: [natural_sciences_math]  # 語彙: vocabularies/subjects.yaml
datePublished: "2026-07-24"     # 年のみ ("2026") でも可
```

ポイント:

- **ソース形式で置く**こと（PDF だけにしない）。再利用者が編集・翻案できることが OER の要件です
- `license` は Creative Commons のみ。改変禁止（ND）は受け入れません
- 語彙フィールド（`learningResourceType` / `about` など）は `vocabularies/` のキーを書きます

検証してからサイトを生成します:

```sh
python3 tools/validate.py          # スキーマ + 語彙 + 運用ポリシーの検査
make preview                       # ローカルで表示確認
make site                          # 公開一式を _site/ へ生成
```

## 4. 外部の教材を目録化する（referenced）

本体をホストせず、メタデータと短い内容紹介だけを載せる「目録エントリ」です。
他サイトの教材を発見可能にしたいとき（`aggregator` の中心機能）に使います。

```yaml
mode: referenced
externalUrl: https://ocw.example.ac.jp/courses/123/   # 教材本体の所在
name:
  ja: ○○学入門
description:
  ja: （自分の言葉で書いた2〜3文の内容紹介。原文の丸写しは検証で拒否されます）
inLanguage: [ja]
license: CC-BY-NC-4.0        # ← ページにライセンス表示がある場合
creator:
  - type: Organization
    name: ○○大学
sourceCollection:            # どのサイトの教材か
  name: ○○大学OCW
  url: https://ocw.example.ac.jp/
  kind: organizational       # organizational / personal / platform
datePublished: "2020"
dateAccessed: "2026-07-24"   # 最終確認日 (必須)
learningResourceType: [course]
about: [engineering]
metadataProvenance:
  method: manual             # AI で作った場合は ai_generated + generator + confidence
```

### ライセンス欄の選び方

出典ページの表示を確認して、次のどちらかを記入します（両方省略は不可）:

| 出典ページの状態 | 記入するもの |
|------------------|--------------|
| CC ライセンス表示がある | `license: CC-BY-4.0` など（旧版 CC も可） |
| CC ではないが「教育利用可」等の条件が明記 | `usageTerms: {url, summary, reuse: allowed_with_conditions}` |
| 規約が複製・転載を明示的に禁止 | `usageTerms: {..., reuse: not_allowed}` |
| 何も書かれていない（個人ページに多い） | `usageTerms: {..., reuse: unspecified}` |

`not_allowed` / `unspecified` の教材も目録化できます（ページに「視聴のみ」等の警告が
自動表示され、教材ファイルの収集は行われません）。

### 便利なツール

```sh
python3 tools/fetch.py <url>                        # ページ取得 (キャッシュ・取得日記録)
python3 tools/extract.py <url>                      # 説明文の候補を抽出 (引用の下ごしらえ)
python3 tools/extract.py <url> --materials          # 教材ファイルリンクを抽出
python3 tools/wayback.py --save <url>               # Web アーカイブに保存 → archivedAt に記入
python3 tools/validate.py --check-quotes            # 引用が原文のままかを機械照合
```

出典の説明文をそのまま見せたい場合は `quotedDescription` に入れます（ページに引用として
表示されます。CC0 のカタログデータには含まれません）。`description` は必ず自分の言葉で
書いてください——引用の丸写しは検証が拒否します。

個人サイトの教材は消えやすいので、登録時に `wayback.py --save` でスナップショットを作り
`archivedAt` に記録することを強く推奨します（無いと validate が警告します）。

## 5. サイト単位の一括収集（aggregator 向け）

数百件規模の収集は次のパイプラインで行います（名大の授業413件で実証済み）:

```
discover (sitemap からURL列挙)
  → fetch --batch (一括取得)
  → make_drafts (パーサで下書き生成)     ※サイトごとにパーサを書く
  → generate (LLM で内容紹介を生成)      ※機械検査つき。ローカルLLMも可
  → review_sheet (面で確認) → approve (公開)
  → harvest (教材ファイルをコーパス層へ。権利ゲートつき)
```

各ステップの詳細・実測に基づく注意点は [tools/README.md](../tools/README.md) を
参照してください。

## 6. レビューと公開（モード別）

| モード | 公開の条件 | 流れ |
|--------|-----------|------|
| `aggregator` | 機械検査 + AI生成と信頼度の明示 + 誤り報告窓口 | `approve.py --all` で未レビューのまま公開可（ページに「未確認」と明示される）。人手は[レビューシート](../tools/README.md#レビューの回し方)での面の確認とサンプリングに充てる |
| `institutional` | 組織のレビュー | 下書きを PR にし、[チェックリスト](review-checklist.md)で確認 → `approve.py --by "氏名"` |
| `personal` | 本人の確認 | 自分で確認して `approve.py --by "自分の名前"` |

公開は `make site` で `_site/` に生成される一式（HTML・JSON-LD・catalog.json・
sitemap.xml）を任意の静的ホスティング（GitHub Pages 等）に置くだけです。
GitHub を使う場合は同梱の CI（[.github/workflows/](../.github/workflows/)）が
PR ごとの検証と週次のリンク切れ確認を行います。

## 7. ライセンスの決まりごと

- **メタデータは CC0**（このリポジトリの記述・catalog.json）。誰でも許諾なしで利用できます
- **教材コンテンツは各リソースの `license` / `usageTerms` に従う**
- 自作教材の既定は CC0 / CC BY を推奨。他の教材を改変した場合は元ライセンスの
  継承義務に従います（[設計書 §7.2](design.md) の早見表参照）
- 出典からの引用（`quotedDescription`）は CC0 の対象外で、ページ表示のみに使われます

## 8. よくあるエラー

| メッセージ | 意味と対処 |
|-----------|-----------|
| `AI生成メタデータは公開前レビューが必要` | `institutional`/`personal` では `metadataProvenance.reviewedBy` に確認者名が必要 |
| `'license' is a required property` ほか license/usageTerms 関連 | hosted は `license` 必須。referenced は `license` か `usageTerms` のどちらかが必須 |
| `description が quotedDescription の丸写し` | 内容紹介を自分の言葉で書き直す（CC0 で出せないため） |
| `externalUrl の重複` | 同じ教材を二重登録している。既存エントリを確認 |
| `description が N 件で同一` | サイト共通の定型文を掴んでいる。抽出方法を疑う（[diagnose.py](../tools/README.md#重複が出たときの調べ方diagnosepy)） |
| `語彙キー '...' が無い` | `vocabularies/` に定義されたキーを使う（必要なら語彙に追加） |
| `slug '...' がディレクトリ名と不一致` | `slug` はディレクトリ名と一致させる（省略可） |
| `NC 系ライセンスは非推奨` (警告) | 掲載は可能。営利形態の教育機関で使えなくなる旨の注意喚起 |

## ドキュメントマップ

| 文書 | 対象 |
|------|------|
| このガイド | システムを導入して使う人 |
| [サイトの使い方](../site/guide.qmd) | 公開されたカタログの閲覧者（サイトに掲載される） |
| [設計書](design.md) | 設計の全体像・根拠・決定の記録 |
| [レビュー チェックリスト](review-checklist.md) | レビュー担当者 |
| [tools/README.md](../tools/README.md) | 全コマンドのリファレンスと運用ノート |
