# OERリポジトリ設計書 — フォーマットとメタデータ

- 版: 0.2
- 日付: 2026-07-21
- 状態: 主要方針は決定済み（#2 は意図的に先送り。#4〜#6 は仮置きのまま運用し、必要が生じた時点で見直す）
- 文書の分担: 本書は**システム（oer-kit）の設計と決定記録**。開発を駆動した収集プロジェクト
  （oer-world）の現況・固有の決定・再開手順は oer-world 側の `docs/status.md` にある。
  2026-07-24 のモジュール分割以前の記述にはパスが旧構成（`tools/` 等）のままの箇所がある

## 1. 目的とスコープ

教育資源（講義スライド・教科書・演習・動画・データ等）をオープンライセンスで公開・再利用可能にする
リポジトリの、**コンテンツフォーマット**と**メタデータプロファイル**を定義する。
検索システムやサイト生成などの実装は対象外とし、それらが依拠する「データの形」を先に固める。

本プロジェクトの目的はカタログ化に留まらず、**オープンな知識の収集**にある（2026-07-21 拡張）:
(a) LLM のオープンな学習データとしての利用、(b) 別途開発中の LMS-NG（学習者モデル中心の次世代
LMS。`@lms-ng/oer-bridge` が本リポジトリの metadata.yaml を読む。LMS-NG docs/20）での素材利用。
このためカタログ層（発見・公開）に加えて、教材ファイルそのものを権利情報つきで収集する
**コーパス層**を持つ（§7.4）。

### 設計の前提と決定状況

| # | 項目 | 仮の決定 | 備考 |
|---|------|----------|------|
| 1 | 主対象 | 高等教育・生涯学習 | 初等中等は拡張フィールドで対応可能にしておく |
| 2 | 公開URL | **先送りを決定（2026-07-21）**: 当面プレースホルダ `https://oer.example.ac.jp/` で設計・実装を進める。軌道に乗れば OE Japan や NII のような公共組織に運営を担ってもらうことを想定 | 移管に耐えるID設計を §4.1 に規定（BASE_URL の一元化、w3id.org 名前空間の検討、移転時の301リダイレクト） |
| 3 | ライセンス方針 | **決定（2026-07-21）**: 二層構造。メタデータは一律 CC0、コンテンツは各リソースの `license` が正（自作の既定は CC0 推奨、派生物は元ライセンスの継承義務に従う）。NC系は許容するが非推奨、**ND系は受け入れない** | 詳細は §7.2。メタデータCC0 は Europeana・DPLA と同じ流通前提 |
| 4 | DOI付与 | 当面なし（Zenodo連携で後付け可能） | 論文引用されうる教材が増えたら検討 |
| 5 | IRDB/JPCOAR連携 | 当面なし（マッピング表のみ用意） | 機関リポジトリ経由の発信が必要になったら OAI-PMH アダプタを追加 |
| 6 | 多言語 | 日本語主体、英語は任意併記 | メタデータは多言語対応の構造にしておく |
| 7 | 主題分野 `about` の必須化 | **決定（2026-07-21）: 必須** | SPARC Rosetta Stone の Required に合わせた。スキーマと §5.2 に反映済み |
| 9 | リンク参照エントリ（レファラトリ機能） | **決定（2026-07-21）: 導入** | ND系・外部教材は本体をホストせず、メタデータと短い内容紹介のみで目録化（`mode: referenced`）。AI生成メタデータは人手レビュー後に公開。詳細は §7.3 |
| 10 | CC 以外の外部教材の目録化 | **決定（2026-07-21）**: 独自条件で再利用可の教材（例: 名大の授業）は `usageTerms` 付きで目録化。視聴のみ（例: UTokyo Channel）も**「再利用不可」ラベルを明示して**目録化 | §7.3 の対象区分。目録ページの警告表示とカタログのカテゴリで再利用可否を判別可能にする |
| 11 | 目的の拡張: オープンな知識の収集 | **決定（2026-07-21）**: カタログに加え、教材ファイルを権利情報つきで収集するコーパス層を持つ | LLM のオープン学習データと LMS-NG（oer-bridge）での利用が目的。§7.4 |
| 12 | レビュー方針の3類型 | **決定（2026-07-21）**: 利用者類型に応じた運用モード（`aggregator` / `institutional` / `personal`）を `config.yaml` の `review_policy` で切り替える。本リポジトリは `aggregator` | §9.1。`reviewedBy` のスキーマ一律強制は廃止し、validate.py のポリシー検査へ移行 |
| 13 | 個人公開資料の収集 | **決定（2026-07-21）**: 組織単位に加えて、個人のホームページ・スライド共有サイトの授業資料も目録化する | §7.5。出典種別（`sourceCollection.kind`）・利用条件記載なし（`unspecified`）・アーカイブ確保・削除依頼対応の4規律を追加 |
| 8 | 図書館目録（OPAC）への導出 | 当面なし | Rosetta Stone は MARC21 への出口を持つ。国内では JPCOAR→IRDB→CiNii Research 経路（§8.2）が実質的な代替。大学図書館OPAC収載が必要になったら MARC21/NACSIS-CAT 列をマッピング表に追加 |

## 2. 既存プラクティスの調査まとめ

### 2.1 メタデータ標準の系譜と現在地

| 標準 | 位置づけ | 本設計での扱い |
|------|----------|----------------|
| [Dublin Core](https://www.dublincore.org/) | 最小共通分母。OAI-PMH の必須フォーマット（oai_dc） | エクスポート先（マッピング表を定義） |
| IEEE LOM (2002) | 教育メタデータの古典。9カテゴリのXML。実装負荷が高く新規採用は減少 | 採用しない（概念の参照のみ） |
| [LRMI](https://www.dublincore.org/about/lrmi/)（DCMI管理） | schema.org に教育用プロパティ（`learningResourceType`, `educationalLevel`, `teaches`, `assesses`, `educationalUse`, `audience` 等）を追加した現行のWeb標準。SKOS統制語彙も提供 | **中核として採用** |
| [schema.org/LearningResource](https://schema.org/LearningResource) | LRMI語彙を持つ CreativeWork のサブタイプ。検索エンジンが直接解釈 | JSON-LD 出力の型 |
| [AMB（Allgemeines Metadatenprofil für Bildungsressourcen）](https://dini-ag-kim.github.io/amb/latest/) | schema.org/LRMI の**実装プロファイル**（独 DINI-AG KIM、2023年10月正式版）。JSON-LD + JSON Schema 検証 + SKOS語彙の組み合わせを規定。OER横断検索 [OERSI](https://oersi.org/) の基盤 | **プロファイル設計の雛形として採用**（語彙を日本向けに差し替え） |
| IEEE 2881 (Learning Metadata) | LRMI を出発点にした LOM の実質的後継 | 動向注視のみ（LRMI 準拠なら追従は容易） |
| [JPCOAR スキーマ 2.0](https://schema.irdb.nii.ac.jp/ja)（2022-12公開） | 日本の機関リポジトリ標準。IRDB が OAI-PMH でハーベスト | エクスポート先（マッピング表を定義） |
| [文部科学省 教育データ標準](https://www.mext.go.jp/a_menu/other/data_00001.htm)・[学習指導要領コード](https://www.mext.go.jp/a_menu/other/data_00002.htm) | 初等中等の教育内容を16桁コードで標準化。[学習指導要領LOD](https://jp-cos.github.io/) としてURI化も進む | K-12向けの拡張フィールドとして予約 |
| [SPARC OER Metadata Rosetta Stone](https://sparcopen.org/our-work/oer-metadata-rosetta-stone/)（2020〜） | 米加の図書館員コミュニティ（OER Discovery Working Group）による OER 向けプロファイル。MARC21・DC・schema.org/LRMI のクロスウォーク。DPLA MAP 5.0 が雛形。Required/Recommended/Optional の3層 | フィールド構成の妥当性チェックリストとして参照（§5 の3層構造・必須セットと整合することを確認済み） |
| SCORM / Common Cartridge / xAPI | LMS 取り込み・学習記録のパッケージング標準 | 対象外（必要になった時点でビルドで生成） |

**要点**: 2020年代の OER リポジトリの主流は「XMLの教育メタデータ標準（LOM）」から
「**schema.org/LRMI を JSON-LD で埋め込み、クローラブルにする**」方式へ移行した。
その最も整備された実例が AMB + OERSI（サイトマップ + JSON-LD をクロールして横断検索を構築）である。
本設計はこの路線に乗り、日本の文脈（JPCOAR・学習指導要領コード）への出口を確保する。

### 2.2 リポジトリ実装のパターン

| パターン | 例 | 特徴 |
|----------|-----|------|
| 専用リポジトリシステム | DSpace, EPrints, edu-sharing | 機能豊富だが運用コスト大。メタデータはシステム内DB |
| **Git ベース（docs-as-code）** | OpenStax（ソース公開）, 各種オープン教科書 | ソース形式で保持し、履歴・分岐・レビューを Git に委ねる。静的サイトで公開 |
| 既存プラットフォーム掲載 | OER Commons, MERLOT, YouTube | 手軽だがメタデータとソースの管理が分散 |

**採用**: Git ベース。理由は §3 の設計原則1・2 に述べるとおり、OER の本質（再利用・改変可能性）
と最も整合し、少人数でも運用できるため。加えて、本体をホストできない外部教材（ND系等）向けに
**リンク参照エントリ（レファラトリ機能）**を併設する（§7.3）。

### 2.3 その他の確立したプラクティス

- **ライセンス**: [UNESCO OER勧告（2019）](https://www.unesco.org/en/open-educational-resources)はオープンライセンスを OER の定義要件とする。実務上は Creative Commons が事実上の標準。帰属表示は TASL（Title / Author / Source / License）形式。
- **5R**（David Wiley）: Retain / Reuse / Revise / Remix / Redistribute。「改変できる形式で配る」ことが Revise/Remix の前提条件。
- **識別子**: 資料に恒久URL（クールURI）、人に [ORCID](https://orcid.org/)、機関に [ROR](https://ror.org/)、（必要なら）版に DOI。
- **アクセシビリティメタデータ**: schema.org の `accessMode` / `accessibilityFeature` / `accessibilityHazard` 等（EPUB/W3C 由来のプラクティス）。
- **言語タグ**: BCP 47（`ja`, `en` など）。JPCOAR へ出す場合のみ ISO 639-3（`jpn`）へ変換。

## 3. 設計原則

1. **ソースを配る** — PDF だけでなく編集可能な原稿形式（Markdown, PPTX, ipynb 等）を必ず保持・公開する。5R の Revise/Remix はフォーマットで保証する。
2. **メタデータは1リソース1ファイル、人間が書ける形式** — `metadata.yaml` を正とする。機械可読形式（JSON-LD）は そこから機械的に生成し、手書きしない。
3. **Web 標準準拠でクロール可能に** — 公開ページに schema.org/LRMI 準拠の JSON-LD を埋め込み、サイトマップを提供する。専用検索APIがなくても検索エンジンや OERSI 型のインデクサから見える。
4. **語彙は再発明しない** — 既存の統制語彙（HCRT, LRMI, ISCED, CC, SPDX）の URI を使い、日本語ラベルだけをこちらで付与する。
5. **検証可能にする** — `metadata.yaml` は JSON Schema で機械検証できる形に限定する（CI で強制）。

## 4. リポジトリ構造

```
OER/
├── README.md
├── docs/
│   └── design.md                  # 本設計書
├── schemas/
│   └── resource.schema.json       # metadata.yaml の JSON Schema（正規仕様）
├── vocabularies/                  # 統制語彙（キー → URI/ラベルの対応表）
│   ├── learning-resource-types.yaml
│   ├── educational-levels.yaml
│   ├── audiences.yaml
│   └── subjects.yaml
├── resources/                     # ★ 教材本体。1リソース = 1ディレクトリ
│   └── <slug>/
│       ├── metadata.yaml          # メタデータ（正）
│       ├── content/               # 編集可能なソース（Markdown, ipynb, pptx …）
│       └── assets/                # 画像・データ・字幕など付随ファイル
├── tools/                         # （将来）検証・JSON-LD生成・サイト生成スクリプト
└── _site/                         # （将来）ビルド成果物。Git 管理外
```

### 4.1 命名規則と恒久ID

- `slug` はディレクトリ名と一致させる。`^[a-z0-9][a-z0-9-]*$`（小文字英数字とハイフン）。
- 公開URLは `{BASE_URL}/r/{slug}` とし、これをリソースの恒久ID（JSON-LD の `id`）とする。
  **公開後の slug 変更は原則禁止**（やむを得ない場合はリダイレクトを恒久維持）。
- DOI を付与する場合は `sameAs` に併記する（IDの主はあくまで自リポジトリのURL）。
- **将来のドメイン移管への備え**（要確認事項#2: 公共組織への移管がありうる）:
  - BASE_URL はビルド設定の1箇所でのみ定義し、コンテンツ内の相互参照は相対パスで書く（絶対URLを原稿に埋め込まない）
  - 対外的な恒久IDレイヤとして [w3id.org](https://w3id.org/) の名前空間取得を検討する。コミュニティ運営の恒久リダイレクトサービスで、`https://w3id.org/<名前空間>/r/{slug}` を ID に据えればホスト移転後も URI を不変に保てる（本設計が参照する HCRT 等の語彙も同じ仕組みで公開されている）
  - 移転時は旧URLからの 301 リダイレクトを恒久維持する

### 4.2 コンテンツフォーマットの方針

「編集可能なソース」＋「すぐ使える配布形式」の両方を保持する。配布形式はビルドで生成できるものは生成する。

| 教材種別 | ソース形式（content/ に置く） | 配布形式（生成または同梱） |
|----------|------------------------------|---------------------------|
| 文書・教科書・教材テキスト | Markdown（CommonMark。数式・相互参照が要るなら Quarto/Pandoc 拡張） | HTML / PDF / EPUB |
| スライド | Marp・Quarto 等の Markdown、または PPTX | PDF / HTML |
| 演習・実習 | Jupyter Notebook (.ipynb) / Quarto (.qmd) | HTML |
| 動画 | 台本・字幕 (.vtt)・文字起こしをソースとして保持。動画ファイル本体は Git LFS か外部ホスティング（URLを `encoding` で参照） | mp4 (H.264) + .vtt |
| データ | CSV / JSON + データ説明（README） | 同左 |
| 図版 | SVG 推奨。作図ツールの元ファイル（.drawio 等）も保持 | PNG / SVG |

- PDF「のみ」の登録は非推奨（改変可能性が失われる）。やむを得ない場合は `metadata.yaml` にその旨を記す。
- 100MB を超えるファイルはリポジトリ直置きしない（Git LFS または外部URL参照）。

## 5. メタデータプロファイル

### 5.1 設計方法

AMB（schema.org/LRMI ベース）を雛形に、(a) 記入言語を日本語主体の多言語構造にし、
(b) ドイツ固有語彙を国際語彙＋日本向け語彙に差し替え、(c) 執筆負荷を下げる短縮記法
（SPDXライセンスID、語彙キー、素のORCID等）を導入した。短縮記法はビルド時に完全な URI へ展開して
AMB 互換の JSON-LD を出力する。

- **記入形式**: `metadata.yaml`（正規仕様は [resource.schema.json](../schemas/resource.schema.json)）
- **出力形式**: schema.org/AMB 準拠 JSON-LD（公開ページに `<script type="application/ld+json">` で埋め込み）

AMB 自体の必須は `@context` / `id` / `type` / `name` の4つと最小だが、本リポジトリでは
検索性と再利用可能性の観点から必須を下表のとおり広げる（運用ポリシーとしての必須）。

### 5.2 必須フィールド

| フィールド | 型 | schema.org 対応 | 説明 |
|-----------|----|----------------|------|
| `name` | 文字列 or 言語マップ | `name` | タイトル。`{ja: …, en: …}` 形式で多言語可 |
| `description` | 文字列 or 言語マップ | `description` | 概要（1〜3文。何をどこまで扱うか） |
| `inLanguage` | BCP47 のリスト | `inLanguage` | 教材本体の言語。例 `[ja]` |
| `license` | SPDX ID or CC URL | `license` | 許可リスト: `CC0-1.0`, `CC-BY-4.0`, `CC-BY-SA-4.0`,（非推奨）`CC-BY-NC-4.0`, `CC-BY-NC-SA-4.0`。自作の既定は CC0 推奨、派生物は継承ルール（§7.2）に従う。リンク参照型（§7.3）に限り ND 系も可 |
| `creator` | Person/Organization のリスト | `creator` | 著者。ORCID・所属を推奨 |
| `learningResourceType` | 語彙キーのリスト | `learningResourceType` | [HCRT語彙](https://w3id.org/kim/hcrt/scheme)（→ `vocabularies/learning-resource-types.yaml`） |
| `about` | 語彙キーのリスト | `about` | 主題分野。ISCED-F 2013 ベース（→ `vocabularies/subjects.yaml`）。SPARC Rosetta Stone の Required に合わせ必須 |
| `datePublished` | ISO 8601 日付 | `datePublished` | 初公開日。**実開講年度が分かる場合はそれを、不明なら公開年**を記す。粒度は `YYYY` / `YYYY-MM` / `YYYY-MM-DD` から選べる（年度しか分からない教材で精度を捏造しないため） |

自動導出（記入不要）: `id`（BASE_URL + slug）、`type`（既定 `["LearningResource"]`。
`type` フィールドで schema.org 型を追記可能、例 `Video`, `Course`, `PresentationDigitalDocument`）。

### 5.3 推奨フィールド

| フィールド | 型 | schema.org 対応 | 説明 |
|-----------|----|----------------|------|
| `keywords` | 文字列リスト | `keywords` | 自由キーワード |
| `audience` | 語彙キーのリスト | `audience` | 想定利用者。[LRMI Educational Audience Role](http://purl.org/dcx/lrmi-vocabs/educationalAudienceRole/)（student, teacher 等） |
| `educationalLevel` | 語彙キーのリスト | `educationalLevel` | 教育段階。本リポジトリ定義語彙（ISCED 2011 対応付き） |
| `teaches` | 文字列（学習目標）のリスト | `teaches` | 「〜できる」形式の学習成果。コンピテンシー語彙のURIも可 |
| `timeRequired` | ISO 8601 期間 | `timeRequired` | 標準学習時間。例 `PT90M`（90分）, `PT22H30M` |
| `image` | 相対パス or URL | `image` | サムネイル |
| `dateModified` | ISO 8601 日付 | `dateModified` | 最終更新日（Git から自動化可） |
| `publisher` | Organization のリスト | `publisher` | 公開主体 |
| `isBasedOn` | URL のリスト | `isBasedOn` | **改変元教材**。リミックスの系譜を残す（OERとして重要） |
| `accessibility` | オブジェクト | `accessMode` ほか | §7 参照 |

### 5.4 任意フィールド

| フィールド | 型 | schema.org 対応 | 説明 |
|-----------|----|----------------|------|
| `alternateName` | 文字列 or 言語マップ | `alternateName` | 別題・略称 |
| `contributor` | Person/Organization リスト | `contributor` | 翻訳者・編集協力など |
| `funder` | Organization リスト | `funder` | 助成機関 |
| `assesses` | 文字列リスト | `assesses` | 評価対象のコンピテンシー（試験・課題系教材） |
| `competencyRequired` | 文字列リスト | `competencyRequired` | 前提知識 |
| `educationalUse` | 文字列リスト | `educationalUse` | 想定用途（例: 反転授業の予習用） |
| `interactivityType` | `active` / `expositive` / `mixed` | `interactivityType` | LOM 由来の3値 |
| `duration` | ISO 8601 期間 | `duration` | 動画・音声の再生時間（`timeRequired` とは別物） |
| `hasPart` / `isPartOf` | URL リスト | 同名 | コース⇄回、教科書⇄章の関係 |
| `sameAs` | URL リスト | `sameAs` | DOI、他プラットフォーム上の同一物 |
| `version` | 文字列 | `version` | 大改訂の版（例 `2.0.0`。§8.3） |
| `conditionsOfAccess` | 文字列 | `conditionsOfAccess` | 登録の要否等（原則不要のはず） |
| `encoding` | `{format, contentUrl}` リスト | `encoding` | 配布ファイル形式の列挙。外部ホスト動画の参照にも使う |
| `curriculumAlignment` | `{code, label?}` リスト | `teaches`（概念参照として出力） | **K-12拡張**: 16桁の学習指導要領コード。[学習指導要領LOD](https://jp-cos.github.io/) の URI に展開 |
| `attributions` | TASL オブジェクトのリスト | `citation` | 収録した第三者素材の帰属表示（§7.2） |
| `mode` | `hosted` / `referenced` | — | 既定 `hosted`。`referenced` は外部教材の目録エントリ（§7.3） |
| `externalUrl` | URL | （JSON-LD の `id` に使用） | `referenced` で必須。教材本体の所在 |
| `dateAccessed` | ISO 8601 日付 | — | `referenced` で必須。外部教材を最後に確認した日 |
| `archivedAt` | URL | — | Webアーカイブ等のスナップショット（リンク切れ対策） |
| `metadataProvenance` | オブジェクト | `mainEntityOfPage` 経由で出力 | メタデータ自体の作成来歴。AI生成時は人手レビュー必須（§7.3）。`referenced` で必須 |
| `usageTerms` | `{url, summary, reuse}` | `usageInfo` | `referenced` 専用: CC 以外の利用条件。`reuse` は `allowed_with_conditions` / `not_allowed`。`license` と少なくとも一方が必須 |
| `quotedDescription` | `{text, source, note}` | （出力しない） | 出典の説明文の転載・引用。ページ表示のみで CC0 エクスポート対象外（§7.3-7） |
| `extensions` | 自由オブジェクト | — | スキーマ検証を通しつつ実験的項目を置く逃げ場 |

### 5.5 記入例（`resources/intro-statistics-slides/metadata.yaml`）

実ファイルは [resources/intro-statistics-slides/metadata.yaml](../resources/intro-statistics-slides/metadata.yaml) を参照。骨子:

```yaml
type: [LearningResource, PresentationDigitalDocument]
name:
  ja: 統計学入門 講義スライド
  en: Introduction to Statistics — Lecture Slides
description:
  ja: 記述統計・確率分布・推定・仮説検定までを扱う半期15回分の講義スライド一式。表計算ソフトによる演習課題を含む。
inLanguage: [ja]
license: CC-BY-4.0
creator:
  - type: Person
    name: 山田 太郎          # 例
    orcid: 0000-0000-0000-0000   # 例
    affiliation: {name: ○○大学}
datePublished: "2026-07-21"
learningResourceType: [slide, worksheet]
about: [natural_sciences_math]
keywords: [統計学, 記述統計, 仮説検定]
audience: [student, teacher]
educationalLevel: [bachelor]
teaches:
  - 記述統計量を用いてデータの分布を要約・説明できる
  - 帰無仮説検定の枠組みを説明し、t検定を適用できる
timeRequired: PT22H30M
```

### 5.6 JSON-LD 出力例（ビルドが生成するもの）

```json
{
  "@context": [
    "https://w3id.org/kim/amb/context.jsonld",
    { "@language": "ja" }
  ],
  "id": "https://oer.example.ac.jp/r/intro-statistics-slides",
  "type": ["LearningResource", "PresentationDigitalDocument"],
  "name": "統計学入門 講義スライド",
  "description": "記述統計・確率分布・推定・仮説検定までを扱う半期15回分の講義スライド一式。表計算ソフトによる演習課題を含む。",
  "inLanguage": ["ja"],
  "license": { "id": "https://creativecommons.org/licenses/by/4.0/" },
  "creator": [
    {
      "type": "Person",
      "name": "山田 太郎",
      "id": "https://orcid.org/0000-0000-0000-0000",
      "affiliation": { "type": "Organization", "name": "○○大学" }
    }
  ],
  "datePublished": "2026-07-21",
  "learningResourceType": [
    { "id": "https://w3id.org/kim/hcrt/slide",
      "prefLabel": { "ja": "スライド", "en": "Slide(s)" } },
    { "id": "https://w3id.org/kim/hcrt/worksheet",
      "prefLabel": { "ja": "ワークシート", "en": "Worksheet" } }
  ],
  "audience": [
    { "id": "http://purl.org/dcx/lrmi-vocabs/educationalAudienceRole/student",
      "prefLabel": { "ja": "学習者", "en": "student" } }
  ],
  "teaches": [
    { "name": "記述統計量を用いてデータの分布を要約・説明できる" }
  ],
  "timeRequired": "PT22H30M",
  "isAccessibleForFree": true
}
```

多言語タイトルは、初版では主言語（`inLanguage` の先頭）の値を JSON-LD に出力し、
他言語はページ表示にのみ使う（AMB が単一文字列を想定しているため）。

## 6. 統制語彙

| 用途 | 採用語彙 | ファイル | 出所 |
|------|----------|----------|------|
| 教材タイプ | HCRT（26概念、日本語ラベルは本リポジトリの参考訳） | `vocabularies/learning-resource-types.yaml` | https://w3id.org/kim/hcrt/scheme |
| 想定利用者 | LRMI Educational Audience Role（8概念） | `vocabularies/audiences.yaml` | http://purl.org/dcx/lrmi-vocabs/educationalAudienceRole/ |
| 教育段階 | 本リポジトリ定義（日本の学校段階 + ISCED 2011 対応） | `vocabularies/educational-levels.yaml` | 自作（ISCEDへ closeMatch） |
| 主題分野 | ISCED-F 2013 大分類（11分野）から開始 | `vocabularies/subjects.yaml` | UNESCO ISCED-F 2013 |

運用ルール:

- `metadata.yaml` には**キー**（例 `slide`）だけを書く。URI とラベルは語彙ファイルが持ち、ビルドで展開する。
- 語彙にない値が必要になったら、まず語彙ファイルへの追加を検討する（`{id, prefLabel}` の直書きは最後の手段）。
- 主題分野は利用実態を見て細分類（ISCED-F 3桁、または国内分類）を追加する。K-12 の教科は
  `curriculumAlignment`（学習指導要領コード）側で扱い、`subjects.yaml` と混ぜない。

## 7. アクセシビリティとライセンス運用

### 7.1 アクセシビリティメタデータ

schema.org のアクセシビリティ・プロパティ（EPUB Accessibility 由来）を `accessibility` ブロックにまとめて記入する。

```yaml
accessibility:
  accessMode: [textual, visual]          # 内容が依存する知覚モード
  accessModeSufficient: [[textual]]      # これだけで完結できるモードの組
  accessibilityFeature: [alternativeText, readingOrder]   # 提供している配慮
  accessibilityHazard: [noFlashingHazard, noMotionSimulationHazard, noSoundHazard]
  accessibilitySummary:
    ja: 全図版に代替テキストを付与。読み上げ順を確認済み。
```

最低ラインの運用目標: 動画には字幕（.vtt）、図版には代替テキスト、文書には見出し構造。
満たせない場合も**満たせていないことをメタデータに書く**（利用者が事前に判断できることが重要）。

### 7.2 ライセンスと帰属（方針決定済み）

「リポジトリとしては CC0 にしたいが、個別コンテンツは元のライセンスに従わざるを得ない」という要請は、
**メタデータとコンテンツのライセンスを分離する二層構造**で実現する（Europeana・DPLA が確立した方式）。

1. **メタデータは一律 CC0 1.0** — `metadata.yaml` の記述内容・`catalog.json`・語彙・スキーマは
   すべて CC0 で提供する（[LICENSE.md](../LICENSE.md)）。これによりハーベスト・転載・加工に
   許諾確認が不要になり、OERSI 型インデクサや他リポジトリへの流通を最大化できる。
2. **コンテンツは各リソースの `license` フィールドが正** — リソース全体のライセンスを1つだけ書く
   （ファイルごとの混在はリソース分割で解消する）。自作コンテンツの既定は CC0 を推奨。
   ただし派生物・第三者素材を含む場合は元素材の継承義務に従う:

| 元素材のライセンス | 派生教材でとりうるライセンス |
|--------------------|------------------------------|
| CC0 / パブリックドメイン | 任意（CC0 推奨） |
| CC BY | 帰属義務が残るため CC0 にはできない。実務上 CC BY を継承 |
| CC BY-SA | CC BY-SA（ShareAlike の継承義務） |
| CC BY-NC / BY-NC-SA | NC 系を継承（本リポジトリでは非推奨枠。登録時に注意喚起） |
| ND 系 | 改変不可のため派生物を作れない。**ホスト型リソースとしては受け入れない**（リンク参照エントリとして目録化する → §7.3） |

- BY-SA 系と NC 系は互換性がなく、同一教材内で結合できないことに注意。
- 著作権法上の適法な「引用」の範囲で用いる第三者素材はライセンス継承の対象外だが、
  出所を `attributions` に TASL 形式で必ず記載する:

```yaml
attributions:
  - title: Iris データセット
    author: R. A. Fisher
    source: https://archive.ics.uci.edu/dataset/53/iris
    license: CC-BY-4.0
    note: 演習用データとして同梱
```

- CC0 は法的な帰属義務を外すだけで、学術慣行としての出典明示への期待は変わらない。
  公開ページには TASL 形式の「引用・帰属表示例」を自動表示する（CC0 の教材にも表示する）。

### 7.3 ND系・外部教材の扱い — リンク参照エントリとAI生成メタデータ

ND（改変禁止）系の教材は 5R を満たさないため本体をホストしないが、発見可能にする価値はある。
そこでリポジトリ（本体保持）に**レファラトリ（所在情報の目録）**を併設する。MERLOT や OERSI が
採る確立したパターンであり、`mode: referenced` のエントリとして表現する。

運用ルール:

1. **本体を保持・再配布しない**。`externalUrl`（教材本体の所在）を JSON-LD の `id` とし、
   本リポジトリの目録ページは `mainEntityOfPage` として出力する。
2. **メタデータ＋短い内容紹介（2〜3文、客観的記述）のみを作成する**。原文の構成・表現をなぞる
   詳細な要約や縮約版は作らない（翻案に当たりうる。図書館の伝統的実務である「目録＋抄録」の
   範囲に留める）。
3. **AI解析による生成を許容する**（本文・字幕・書き起こしからのメタデータ抽出と内容紹介の生成）。
   ただし:
   - `metadataProvenance` に `method: ai_generated | ai_assisted`、`generator`（モデル名）、
     `generatedDate`、`confidence`（`high` / `low`）を記録する
   - **AI 生成であることを目録ページに明示する**（内容紹介の直下に出所・確認者の有無・確からしさ。
     `confidence: low` は「もとになる情報が少ない」旨を開いた状態で警告表示）。
     JSON-LD の `mainEntityOfPage` にも機械可読で出し、取り込み側が判別できるようにする
   - **公開前レビューの要否は運用モードで決まる**（§9.1）。本リポジトリ（`aggregator`）では
     機械検査＋信頼度明示＋誤り報告窓口を公開条件とし、未レビューであることをページに明示する
   - 生成した内容紹介もメタデータの一部として CC0 で提供する（§7.2 の二層構造どおり）
4. **法的な位置づけ（日本法）**: AI解析のための利用は著作権法30条の4（非享受利用）、
   所在検索・情報解析サービスとしての結果提供（軽微利用）は47条の5が根拠になる。
   書誌事実とごく短い紹介文は、そもそも原著作物の表現の複製・翻案に当たらない範囲で書く。
   CC ライセンスは権利制限規定による利用を妨げない（CC 4.0 §2(a)(2)）。
   本格運用の際は機関の知財担当への確認を推奨（47条の5 には政令基準の遵守要件がある）。
5. **リンク切れ対策**: `dateAccessed`（最終確認日）を必須とし、可能なら Web アーカイブの
   スナップショットを `archivedAt` に記録する。CI で定期リンクチェックを行う。
6. **対象の範囲（2026-07-21 決定）**: 外部教材は再利用可否で区分し、いずれも目録化できる。
   `license` か `usageTerms` の少なくとも一方が必須（スキーマで強制。ホスト型は `usageTerms` 不可）。
   - **CC ライセンス** — `license` に記録。旧版（2.x/3.0・国別ポート含む）は `referenced` に限り受理
     （ホスト型は 4.0 系のみ）
   - **独自条件で再利用可**（例: 名大の授業 = 非営利教育目的での複製・改変・配布可＋クレジット義務）
     — `usageTerms: {url, summary, reuse: allowed_with_conditions}` に記録
   - **再利用不可・視聴のみ**（例: UTokyo Channel = 利用規約が複製・頒布を禁止）
     — `usageTerms.reuse: not_allowed`。目録ページに警告表示、カタログに「再利用不可」カテゴリを
     付与して発見用途に限定する。ライセンス変化を `wayback.py --check` とあわせ定期確認する
   - **利用条件の記載なし**（個人ページに多い） — `usageTerms.reuse: unspecified`。
     著作権法上の原則により閲覧のみと扱う（明示的禁止 `not_allowed` とは区別して表示する）。
     コーパス層の取得は行わない

7. **出典の説明文の利用（`quotedDescription`）**: 出典サイトの「授業の内容」等の原文を使いたい場合は、
   `description`（自作・CC0）とは別の `quotedDescription: {text, source, note}` に入れる。
   - 目録ページにのみ**引用ブロック＋出所明示**で表示し、CC0 の `catalog.json` / JSON-LD には含めない
     （転載文を CC0 で再配布することになり、出典の権利と衝突するため）
   - 根拠は出典により異なる: 再利用許諾のあるサイト（名大型）は先方の利用条件に基づく転載、
     許諾のないサイト（東大型）は著作権法32条の引用（明瞭区別・出所明示・主従関係を満たす表示にする）

記入例: [resources/sample-external-nd-course/metadata.yaml](../resources/sample-external-nd-course/metadata.yaml)
（`referenced` エントリは `content/` ディレクトリを持たない）

### 7.4 教材ファイルの収集 — コーパス層

名大の授業のように、授業ページに教材ファイル（章別の講義ノート・課題等）が並ぶサイトでは、
ファイル単位の収集が「オープンな知識の収集」（§1 目的）の本体になる。カタログとは層を分ける:

| 層 | 置き場 | 公開 | 内容 |
|----|--------|------|------|
| カタログ層 | `resources/` → `_site/` | 公開（メタデータ CC0） | `materials`（ファイル名・URL・format・sha256）。JSON-LD では `hasPart` の CreativeWork として出力 |
| コーパス層 | `archive_dir`（config.yaml。Git 外） | 非公開が既定 | 取得ファイル + `manifest.json`（権利情報・クレジット素材・sha256・取得日） |

運用:

1. `materials` の候補は `extract.py --materials` で列挙し（拡張子ベースのリンク抽出）、
   レビューで表示名を整えて metadata.yaml に記載する
2. 取得は `harvest.py`。**権利ゲート**を持つ: `usageTerms.reuse: not_allowed`（視聴のみ。
   例: UTokyo Channel）は規約が複製（ダウンロード）を禁止しているため取得せず、カタログのみとする。
   PDF はマジックバイト検証（サインイン要求ページの混入防止）、取得間隔は crawler.sleep_seconds
3. manifest には `license` / `usageTerms`・クレジット素材（例: `© 2005 岩崎 雄吾（名古屋大学）`）を
   ファイルごとに引ける形で併記し、**下流が権利で絞り込める**ようにする
4. 取得の頑健性: 404 のときは壊れたパーセントエンコードの復元を試す
   （名大の一部リンクは `%20` が `20%25` / `20%` に化けている。実測で復元可能）。
   PDF として取得したものが HTML なら保存しない（サインイン要求・エラーページ）が、
   実体のある別形式なら保存して manifest に `warning` を残す
5. **各回が別ページの講座**は `extract.py --materials --follow` が深さ1で巡回して集める
   （コースURL配下のリンクを各回とみなす既定規則で京大の `?video_id=` 型に対応。
   UTokyo Channel の `/content/?id=` のような別パス型は正規表現で指定）。各ファイルの
   由来ページを `materials[].page` に記録する。**既定はコース1エントリ + materials** とし、
   各回ページ自体に十分な説明と独立の利用価値がある場合のみ、各回を独立の referenced
   エントリ（`isPartOf` でコースへ紐付け）に昇格させる

利用目的別の権利整理:

| 利用 | 可否の根拠 |
|------|-----------|
| 保存・解析（コーパス層に置く） | 著作権法30条の4（情報解析等の非享受利用）。ただし書（著作権者の利益を不当に害する場合）に留意 |
| LLM の学習 | 30条の4 が基本。ただし**学習データセットとして公開再配布**する場合はライセンス従属（CC・再利用許諾のあるもののみに絞る。manifest の rights で機械的に選別） |
| LMS-NG での教材提供 | 各ライセンス・利用条件に従う（名大型: 非営利教育目的＋クレジット表示。manifest の `credit` を利用） |
| 公開ミラー・再配布 | ライセンスが許すもののみ |

LMS-NG との接続（LMS-NG 側 docs/20 と対応）: OER=素材の共有地・LMS-NG=概念の座標系という分担。
`@lms-ng/oer-bridge` が本リポジトリの metadata.yaml / catalog.json を読み、`teaches` を概念版に
接地する。`materials` と manifest により、資源単位の発見からファイル単位の利用へ拡張できる。

### 7.5 個人公開資料の収集

組織単位の収集（§7.3〜7.4）に加え、**個人のホームページ・研究室サイト・スライド共有
プラットフォームで公開された授業資料**も目録化の対象とする（2026-07-21 決定）。
レファラトリの骨格（`referenced` + `usageTerms` + 来歴 + aggregator 運用）は出典の種類に
依存しないためそのまま適用でき、次の4点だけを追加規律とする:

1. **出典種別の明示**: `sourceCollection.kind: organizational | personal | platform`。
   個人公開はカタログに「個人公開」カテゴリを付与してまとめて絞り込めるようにする
   （個人サイトはサイト数が多く、サイト名カテゴリだけでは横断できないため）
2. **利用条件の記載なしに対応**: 個人ページはライセンス表示が無いことが多い。
   `usageTerms.reuse: unspecified` で「原則閲覧のみ」と明示し（§7.3-6）、明示的禁止とは
   区別する。CC 表示のあるスライド（SpeakerDeck 等では作者が任意で記載）は通常どおり
   `license` に記録する
3. **アーカイブの確保**: 個人サイトは組織サイトよりリンク切れが早い。`archivedAt` を
   強く推奨とし（validate が警告）、登録時に `wayback.py --save <url>`（Save Page Now）で
   スナップショットを作る
4. **削除・修正依頼への対応**: 誤り報告窓口（`feedback_url`）は、本人からの削除・修正依頼の
   窓口を兼ねる。公開情報の書誌的な目録化は通常のレファラトリ実務だが、本人が望まない場合は
   すみやかにエントリを取り下げる。取り下げは `oer-kit withdraw`（または管理UI）で行い、
   **差し戻し**（drafts へ戻す一時的な取り下げ）と**恒久取り下げ**（`withdrawn.yaml` に
   理由つきで記録）を区別する。記録された URL は以後の収集から自動除外され、
   再登録しようとすると validate がエラーにする — 削除の意思を再クロールが上書きしない

サイトレジストリ（`tools/sites.yaml`）には `kind` を記録する。個人サイトはパーサを
持たない一件ずつの登録が中心になるため、`extract.py`（汎用抽出）と手動記入で足りる。
収録の選定基準（何を目録に入れるか）は運用が固まった段階で「収録方針」として文書化する。

将来の方向（本プロジェクトの範囲外だが合意した立場・2026-07-21）: 個人公開物・組織公開物とも
Wayback Machine への保存を基本とし、**オプトアウトの依頼があるまで公開を維持する**。
消失は不可逆・公開停止は可逆という非対称があるため、保存と公開可否は分けて扱うのが
アーカイブの精神に適う。保存主体は Internet Archive（`wayback.py --save` は IA に取得を
依頼する形）、本リポジトリは発見可能性（メタデータと所在）を保存する、という分担。

### 7.6 oer-kit プロジェクト間の連合（取り込み）

個人・組織が oer-kit で公開したプロジェクトは**同じスキーマを話す**ため、収集側は
サイト固有のパーサなしで取り込める（`oer-kit ingest <GitHubリポジトリURL | 公開サイトURL |
ローカルパス>`、管理UIの「⇄ 取り込み」）。これにより:

- **個人**: `oer-kit init` → 管理UIの「＋ 新規教材」で作成 → GitHub Pages で公開するだけ
- **アグリゲータ**: URL を1つ指定すれば、先方の CC0 メタデータを引き継いだ
  `referenced` 下書きが生成され、通常のレビュー → 承認フローに乗る

スクレイピング型の収集（§7.3〜7.5）が「構造を知らない相手」への手段であるのに対し、
連合は「構造を共有する相手」への手段で、こちらが本筋。規律:

1. 先方の hosted リソースのみ取り込む（先方が目録化しただけの referenced は又貸しになる）
2. 取り下げ済み URL・自分自身・既存 slug はスキップ。二重取り込みは横断重複検査が
   承認段階で保留にする
3. 先方のメタデータ（CC0）は description まで引き継ぎ、`metadataProvenance` に
   取り込み元と日付を追記。先方が AI 生成なら confidence 等もそのまま透過する

AIメタデータ生成パイプライン（`tools/` 実装時の想定）:
取得 → テキスト抽出（PDF・字幕・書き起こし） → LLM によるスキーマ制約付き生成
（[resource.schema.json](../schemas/resource.schema.json) を出力制約に使う） → 人手レビュー（PR） → 公開

**コードと LLM の役割分担**（[tools/extract.py](../tools/extract.py) の実測に基づく）:

| 対象 | 手段 | 理由・実測 |
|------|------|-----------|
| `quotedDescription`（原文の転載） | **コード** | LLM に書かせると改変・幻覚が入り「原文のまま」を保証できない。JSON-LD → meta（サイト共通の定型文は自動除外）→ ラベル辞書の3段階で、説明文があるページなら 63〜100% 抽出できた（旧東大100%・ICU 84%・北大63%） |
| 候補が複数あるときの選択 | LLM／人手 | 名大のコースページは4候補（うち1つは表の見出しの誤検出）が出る |
| ラベルも meta も無いサイト | LLM | 例: 上智（候補0%） |
| `description`（CC0 の自作要約） | LLM／人手 | 転載ではない要約なので、そもそもコードで作るものではない。**説明文が存在しないページ**（例: 京大の最終講義ページは構造化メタデータのみで本文説明が無い）もこの経路で書く |

### 7.7 収集の礼儀（クローラ倫理。2026-07-28 実装）

収集機能の公開は対象サイトの負荷を増やしうる。oer-kit は「一度収集した結果を
catalog.json として共有し、重複クロールを構造的に不要にする」立場を取り（§7.6 の
連合が第一の入手経路）、そのうえで礼儀をツールに埋め込む:

1. **robots.txt の自動遵守** — fetch / batch / harvest は取得前にホストの robots.txt を
   確認し、許可されない URL をスキップする（結果は件数として報告）
2. **連絡先のない User-Agent では動かない** — `crawler.user_agent` にメールアドレスか
   URL が含まれるまで収集コマンドは実行を拒否する。収集先の管理者が発信元に連絡
   できることが収集の前提条件
3. **リクエスト間隔の下限1秒** — それ未満の設定は警告のうえ1秒に丸める
4. **規範の文書化** — user-guide の「収集の前に」節: (a) まず既存カタログの ingest を
   検討（federation-first）、(b) 対象サイトの利用条件と robots.txt の確認、(c) 連絡先を
   名乗る、(d) 削除・停止依頼への対応（§7.5 の削除依頼手順と共通）

キャッシュ第一（取得済みページは再取得しない・中断後の再開可能）も同じ目的に資する。

## 8. 相互運用性と配信

### 8.1 基本線（実装コストほぼゼロで効く施策）

1. 各リソースの公開ページに JSON-LD を埋め込む（§5.6）。
2. `sitemap.xml` を生成する。
2.1 **検索インデックスの充実**: 内容紹介（AI 生成の要約）は短いので、それだけに頼らず
   引用原文・キーワード・教材ファイル名・著者・学習目標も検索対象にする。Quarto の
   検索は**見出し単位**で索引を作るため、引用は見出し付きセクションにする（見出しの無い
   引用ブロックは索引に入らない）。front matter の `description` は索引に入らないので、
   `build_catalog.py` がビルド後に `search.json` の各ページ冒頭エントリへ追記する
   （表示を重複させずに検索性だけ上げる）。
3. 全リソースの JSON-LD を束ねた `catalog.json` を1ファイル公開する（簡易API・一括ハーベスト用。OERSI 型のインデクサ連携もこの形で足りる）。

### 8.2 エクスポートマッピング（必要になった時点で実装）

| 本プロファイル | oai_dc | JPCOAR 2.0 |
|----------------|--------|------------|
| `name` | dc:title | jpcoar:title |
| `creator` | dc:creator | jpcoar:creator / jpcoar:creatorName |
| `description` | dc:description | datacite:description |
| `keywords` / `about` | dc:subject | jpcoar:subject |
| `license`（URI） | dc:rights | dc:rights |
| `datePublished` | dc:date | datacite:date (Issued) |
| `inLanguage`（`ja`） | dc:language | dc:language（**ISO 639-3 の `jpn` に変換**） |
| `id` | dc:identifier | jpcoar:identifier |
| `learningResourceType` | dc:type | dc:type（COAR資源タイプの learning object 系） |
| `publisher` | dc:publisher | dc:publisher |

- LMS 連携（Common Cartridge / SCORM）や xAPI は、要望が出た教材からビルドで個別生成する方針とし、リポジトリの正データには持ち込まない。

### 8.3 バージョニング

- 日常の修正: Git 履歴 + `dateModified`（コミット日時から自動化可）で十分。
- 内容が変わる大改訂: `version` を上げ（`1.0.0` → `2.0.0`）、Git タグ `res/<slug>/v2.0.0` を打つ。旧版PDF等を残す場合は `assets/archive/` へ。
- 他教材の翻案として作った場合は必ず `isBasedOn` に元のURLを書く（リミックス系譜の保存）。

### 8.4 サイトエンジンの選択制（方針決定・v1 実装 2026-07-28）

プロジェクト初期化時に **Quarto / Hugo をオプションで選ぶ**（1プロジェクト1エンジン。
両対応の同時維持はしない）。初期化時に示す選択案内は、利用者が自分で判定できる
**教材の具体的な特徴**で書く:

> 教材ページに次のいずれかを含めたい場合は **Quarto** を選んでください:
> **文献リスト**（BibTeX からの引用・参考文献の自動生成）・
> **実行可能なコード例**（実行結果や図表をビルド時に生成）・**章や図表への相互参照**。
>
> 上記が不要なら **Hugo** を選んでください。ビルドが速く、件数が増えても破綻しません。
> **数式（LaTeX 記法）はどちらでも使えます**（Hugo は transform.ToMath でビルド時に
> MathML へ変換。クライアント JS 不要。2026-07-28 実装・検証済み）。

利用者3類型（§9.1）との対応は傾向にすぎない — aggregator はほぼ確実に Hugo だが、
組織・個人でも配布型なら Hugo で足りる。なおコード実行は自作教材に限る
（他者コンテンツをビルドで実行しない、という信頼モデルは両エンジン共通）。
数式が Hugo でも使えるため、**数理教材が多い oer-world の Hugo 移行も可能**
（Quarto は3,600頁超で dayjs の累積スタックオーバーフローも発生。V8 stack-size
拡大で当面回避中）。

根拠（oer-world 3,537件時点の実測）: Quarto はビルド15分超・search.json 16MB
（全訪問者がダウンロードする方式のため規模に線形悪化）。Hugo は Content Adapter
（`_content.gotmpl`）で catalog.json から直接ページ生成でき（ページファイル生成が不要）、
数千頁を数秒でビルド、タクソノミ一覧が標準装備。検索は Pagefind（静的分割
インデックス）で置き換える。

実装の境界: メタデータ層（validate / jsonld / build_catalog / ingest / UI）は
エンジン非依存を維持する。**連合（§7.6）は catalog.json を交換形式とするため、
相手プロジェクトのエンジンに関係なく取り込める**。エンジン固有なのは
scaffold のサイト雛形と prerender（ページ生成）のみ。

v1 実装（2026-07-28）:
- `config.yaml` の `site_engine: quarto | hugo`（既定 quarto）。`oer-kit init --engine hugo`
  または対話選択（上記の案内文を表示）
- prerender がエンジンで分岐: 本文 Markdown は共通、注意枠は Quarto = callout /
  Hugo = 太字見出し付き引用ブロック（純 Markdown）。JSON-LD は Hugo では front matter
  の `jsonld` を layouts/partials/head.html が `<head>` に埋め込む
- Hugo 雛形（`scaffold/site-hugo/`）: hugo.in.yaml（publishDir site/_site → rsync 同期は
  Quarto と同じ）・最小レイアウト・categories タクソノミ・依存なしの簡易クライアント
  検索（Hugo が searchindex.json を生成）。大規模カタログで検索を強化する場合は
  Pagefind への置き換えを検討

## 9. 検証とCI

### 9.1 運用モードとレビュー方針（利用者3類型）

本システム（スキーマ＋tools）の利用者は3類型を想定し、AI 生成メタデータのレビュー要件を
運用モード（`config.yaml` の `review_policy`）で切り替える。スキーマは一律強制せず、
validate.py がモードに応じて検査する:

| モード | 想定利用者 | AI生成メタデータの公開条件 |
|--------|-----------|---------------------------|
| `aggregator` | 1. OER を収集してカタログとコンテンツを公開する（**本リポジトリ**） | 機械検査（スキーマ・引用照合・横断重複）＋ **AI生成と信頼度の明示** ＋ 誤り報告窓口（`feedback_url`）。誤りの訂正は利用者の指摘に委ね、人手レビューは抽出・生成系の検証とサンプリングに充てる |
| `institutional` | 2. 組織として OER を公開する | 公開前に組織のレビュー（`reviewedBy` 必須） |
| `personal` | 3. 個人が自分の教材を公開する | 本人による確認（`reviewedBy` = 本人） |

`aggregator` を成り立たせている前提: 名大413件の一括生成のレビューで見つかった問題は
**すべてシステム側の欠陥**（分類の部分一致バグ・引用の省略記号・ラベル漏れ等）で、
個別データの手直しは1件も無かった。数百件規模で1件ずつの精読は現実的でなく、
効くのは面での検証（レビューシート）とシステムの修正である。個別の誤りは
「AI 生成・未確認」の明示と報告窓口で受け止める。

### 9.2 機械検証

- `metadata.yaml` は [schemas/resource.schema.json](../schemas/resource.schema.json)（JSON Schema 2020-12）で検証する。
  未知フィールドはエラー（typo検出のため）。実験的項目は `extensions` へ。
- CI（GitHub Actions 等）で PR ごとに実行するチェック:
  1. スキーマ検証（`check-jsonschema` / `ajv` 等。YAML→JSON変換して適用）
  2. 語彙キーの存在検証（`vocabularies/*.yaml` との突合）
  3. slug とディレクトリ名の一致、`license` 許可リスト、リンク切れ
  4. （将来）生成 JSON-LD を AMB 同梱の JSON Schema でも検証
- レビュー体制: リソース追加・変更は PR とする（[チェックリスト](review-checklist.md)・
  [PR テンプレート](../.github/pull_request_template.md)）。**機械で確認できることは機械に任せ、
  レビューでは人にしか判断できない項目に集中する**という分担にする:
  - 機械: 必須項目・型・語彙キー（スキーマ）、**引用文が原文のままか**（`--check-quotes` が
    キャッシュと文字列照合し改変を検出）、`description` が引用の丸写しでないか、リンク生存、
    **リポジトリ横断の重複**（同じ `externalUrl` の二重登録、`description` の使い回し）
    — 定型文の検出は抽出時（`extract.py`: 同一サイトのページ間）と検証時（`validate.py`:
    リポジトリ全体）の2段階で行う
  - 人: 事実の正しさ（著者・年・URL の取り違え）、**ライセンス／利用条件の読み取り**、
    内容紹介が自分の言葉になっているか、分類の妥当性
- CI（[.github/workflows/](../.github/workflows/)）: PR ごとに `validate` + `build_catalog`。
  外部リンクの確認は外部サイトを叩くため分離し、週1回 `linkcheck` で実施する。

## 10. 次のステップ

1. 要確認事項（§1）の決定 — 特に公開ドメインとライセンス方針
2. `tools/` — **実装済み（2026-07-21）**: 検証（validate）・JSON-LD 生成（jsonld）・
   catalog.json / sitemap.xml（build_catalog）・sitemap 探索（discover）・キャッシュ付き取得（fetch）・
   Wayback / リンク確認（wayback）・旧収集データの下書き変換（convert_legacy）。
   使い方は [tools/README.md](../tools/README.md)。静的サイト生成も **Quarto で実装済み（2026-07-21）**:
   `make site` で 検証 → prerender（metadata.yaml → ページ + JSON-LD 埋め込み）→ quarto render →
   catalog.json の一括ビルド。Quarto 採用の理由: 学術教材（数式・コード・ipynb）のネイティブ対応、
   ソース→配布形式（PDF/EPUB/スライド）の同一ツールチェーン化、Python 生態系との親和性
3. 実教材 2〜3 件でプロファイルを試し、フィールドの過不足を改訂
4. CI 導入（validate を PR 必須に）、公開、referenced エントリの量産（§7.3 パイプライン）

## 参考資料

- AMB 仕様: https://dini-ag-kim.github.io/amb/latest/ （リポジトリ: https://github.com/dini-ag-kim/amb）
- OERSI（AMBベースのOER横断検索）: https://oersi.org/
- LRMI（DCMI）: https://www.dublincore.org/about/lrmi/ ・概念スキーム: https://www.dublincore.org/specifications/lrmi/concept_schemes/
- schema.org LearningResource: https://schema.org/LearningResource
- HCRT 語彙: https://w3id.org/kim/hcrt/scheme
- JPCOAR スキーマガイドライン: https://schema.irdb.nii.ac.jp/ja
- 文部科学省 教育データ標準: https://www.mext.go.jp/a_menu/other/data_00001.htm ・学習指導要領コード: https://www.mext.go.jp/a_menu/other/data_00002.htm ・学習指導要領LOD: https://jp-cos.github.io/
- SPARC OER Metadata Rosetta Stone: https://sparcopen.org/our-work/oer-metadata-rosetta-stone/ （実体は Google Doc の living document。MARC21/DC/schema.org-LRMI クロスウォーク）
- UNESCO OER Recommendation (2019): https://www.unesco.org/en/open-educational-resources
- Creative Commons ライセンス: https://creativecommons.org/licenses/
