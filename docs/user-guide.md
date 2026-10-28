# 利用ガイド（導入者向け）

このシステムで OER（オープンな教育資源）のカタログを作り、公開するためのガイドです。
設計の背景や根拠は[設計書](design.md)に、コマンドの詳細は [commands.md](commands.md) に
あります。ここでは「使うために必要なこと」だけを順に説明します。
個人で数件の教材を公開したいだけなら、[§3 の最短手順](#個人で数件の教材を公開する最短手順)から読めば足ります。

## 1. これは何か

教育資源のメタデータを `metadata.yaml`（1教材=1ファイル）で管理し、

- **検証**（スキーマ・語彙・引用照合・重複検査）
- **公開サイト生成**（Quarto または Hugo。schema.org/LRMI 準拠の JSON-LD 埋め込み）
- **外部教材の収集支援**（クロール・説明文抽出・AI下書き生成・教材ファイル収集）

をコマンドラインで行う道具立てです。想定する使い方は3つあります:

| 使い方 | 例 | 運用モード（`review_policy`） |
|--------|-----|------------------------------|
| 収集して公開する | 各大学の OCW や個人公開の教材を横断カタログ化 | `aggregator` |
| 組織として公開する | 大学・機関が自組織の教材を公開 | `institutional` |
| 個人で公開する | 自分の授業資料・スライドを公開 | `personal` |

## 2. セットアップ

必要なもの:

- Python 3.10+ と `make`
- サイトエンジンのどちらか一方（下の「エンジンの選び方」）:
  [Hugo](https://gohugo.io/) 0.132 以上（`brew install hugo` 等）または
  [Quarto](https://quarto.org/)（`brew install --cask quarto` 等）

oer-kit をインストールして、プロジェクト（1サイト = 1ディレクトリ）を作ります:

```sh
pip install "oer-kit @ git+https://github.com/takedatoshiyuki/oer-kit"
oer-kit init my-oer --engine hugo      # または --engine quarto（省略すると対話で選択）
cd my-oer
```

旧クローラの収集データ（Excel）を変換する場合だけ `oer-kit[legacy]` で入れます。

**エンジンの選び方**: 教材ページに**文献リスト**（BibTeX からの引用）・**実行可能な
コード例**（実行結果や図表をビルド時に生成）・**章や図表への相互参照**を含めたい
場合は Quarto、それ以外（資料ファイルの配布・目録）は Hugo を選びます。Hugo は
ビルドが速く、件数が増えても破綻しません。**数式（LaTeX 記法）はどちらでも使えます**。
エンジンは `config.yaml` の `site_engine` に記録され、`make` と公開用 CI もそれに
合わせて配置されます。

次に `config.yaml` を自分の環境に合わせて編集します:

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

`personal` / `institutional` の基本形です。**`oer-kit ui` の「＋ 新規教材」フォームを使えば、
メタデータの記入（ライセンス選択の説明つき）とファイルのアップロードまで画面上で完結します**。

### 個人で数件の教材を公開する（最短手順）

収集（クロール・AI下書き生成・一括承認）は不要です。自分の教材を置いて、
自分で確認して、GitHub Pages で公開するだけです:

1. §2 のとおりインストールして `oer-kit init my-oer --engine hugo`
   （資料ファイルの配布が目的なら Hugo。文献リスト等を書くなら Quarto）
2. `config.yaml` に `site_name`・`base_url`（例: `https://<ユーザー名>.github.io/my-oer`）・
   `review_policy: personal` を書く
3. `oer-kit ui` で管理画面を開き、「＋ 新規教材」でメタデータを記入して
   ファイル（PDF・docx・xlsx・スライド原稿・Markdown など）をアップロード
4. 内容を確認して承認する（`personal` では承認者名 = 自分の名前が必須）
5. `make preview` で表示を確認し、GitHub に push して公開（§6「GitHub Pages で公開する」）
6. 横断カタログ（OER World など）に載せてもらう（§6「カタログに登録してもらう」）

内容紹介（`description`）は自分で書きます。AI による一括生成（`oer-kit generate`）は
収集向けの機能で、自作教材では作者自身の説明のほうが正確です。

### 教材ディレクトリの構成

以下は手作業（またはフォームが作るもの）の説明です。1教材=1ディレクトリを作ります:

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
- `content/` のファイルは、Hugo ではそのまま配布されます（Markdown もソースのまま）。
  Quarto では Markdown・`.qmd` が HTML ページに変換されて表示されます

検証してからサイトを生成します:

```sh
oer-kit validate                   # スキーマ + 語彙 + 運用ポリシーの検査
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
oer-kit fetch <url>                        # ページ取得 (キャッシュ・取得日記録)
oer-kit extract <url>                      # 説明文の候補を抽出 (引用の下ごしらえ)
oer-kit extract <url> --materials          # 教材ファイルリンクを抽出
oer-kit wayback --save <url>               # Web アーカイブに保存 → archivedAt に記入
oer-kit validate --check-quotes            # 引用が原文のままかを機械照合
```

出典の説明文をそのまま見せたい場合は `quotedDescription` に入れます（ページに引用として
表示されます。CC0 のカタログデータには含まれません）。`description` は必ず自分の言葉で
書いてください——引用の丸写しは検証が拒否します。

個人サイトの教材は消えやすいので、登録時に `oer-kit wayback --save` でスナップショットを作り
`archivedAt` に記録することを強く推奨します（無いと validate が警告します）。

## 5. サイト単位の一括収集（aggregator 向け）

### 収集の前に（必ず読む — design.md §7.7）

1. **まず既存カタログの取り込みを検討する**。収集したいサイトが既にどこかの
   oer-kit プロジェクト（例: OER World）に収録されていれば、原サイトを
   クロールせず `oer-kit ingest <カタログURL>` で取り込める。重複クロールは
   相手サイトにも自分にも無駄
2. **対象サイトの利用条件と robots.txt を確認する**。目録化（メタデータ+リンク）は
   広く許容されるが、教材ファイルの取得（harvest）は再利用可のものに限る
3. **連絡先を名乗る**。`config.yaml` の `crawler.user_agent` にメールアドレスか
   URL を含める（含めるまで収集コマンドは動かない）。サイト管理者から
   問い合わせや停止依頼が来たら応じる
4. ツールの既定（robots.txt 遵守・毎秒1リクエスト・キャッシュ第一）を
   緩めない。急ぐ理由ができたときは、まずサイト管理者に相談する


数百件規模の収集は次のパイプラインで行います（名大の授業413件で実証済み）:

```
discover (sitemap からURL列挙)
  → fetch --batch (一括取得)
  → make_drafts (パーサで下書き生成)     ※サイトごとにパーサを書く
  → generate (LLM で内容紹介を生成)      ※機械検査つき。ローカルLLMも可
  → review_sheet (面で確認) → approve (公開)
  → harvest (教材ファイルをコーパス層へ。権利ゲートつき)
```

各ステップの詳細・実測に基づく注意点は [commands.md](commands.md) を
参照してください。

## 6. レビューと公開（モード別）

| モード | 公開の条件 | 流れ |
|--------|-----------|------|
| `aggregator` | 機械検査 + AI生成と信頼度の明示 + 誤り報告窓口 | `oer-kit approve --all` で未レビューのまま公開可（ページに「未確認」と明示される）。人手はレビューシート（`oer-kit review-sheet`）での面の確認とサンプリングに充てる |
| `institutional` | 組織のレビュー | 下書きを PR にし、[チェックリスト](review-checklist.md)で確認 → `oer-kit approve --by "氏名"` |
| `personal` | 本人の確認 | 自分で確認して `oer-kit approve --by "自分の名前"`（管理UIの承認ボタンでも可） |

公開は `make site` で `_site/` に生成される一式（HTML・JSON-LD・catalog.json・
sitemap.xml）を任意の静的ホスティングに置くだけです。

### GitHub Pages で公開する

`oer-kit init` が配置するワークフロー（プロジェクトの `.github/workflows/publish.yml`。
選んだエンジンに応じて Hugo 用か Quarto 用が入る）が、main への push ごとに
サイトを生成して配信します。手順:

```sh
gh repo create <リポジトリ名> --public --source . --push   # リポジトリ作成 + push
gh api repos/{owner}/{repo}/pages -X POST -f build_type=workflow   # Pages を有効化
```

（Web UI の場合: リポジトリ作成 → push → Settings → Pages → Source を
「GitHub Actions」にする）

その後 `config.yaml` の `base_url` を公開URL（例:
`https://<ユーザー名>.github.io/<リポジトリ名>`）に変更して push します。
**`base_url` が実際の公開URLと一致していないと、JSON-LD の ID・サイトマップ・
ページ内の絶対リンクが壊れます。**

補足:

- 無料プランの Pages は**公開リポジトリ**が前提です（メタデータは CC0、`drafts/`・
  `archive/`・`.cache/` は Git 管理外なので、公開されるのはレビュー済みリソースと
  ツール・文書のみ）
- `<ユーザー名>.github.io/<リポジトリ名>` はサブパス配信ですが、サイトは対応済みです。
  独自ドメインを使う場合は Pages のカスタムドメイン設定後に `base_url` を差し替えます
- あわせて PR ごとの検証（validate）と週次のリンク切れ確認も同梱の CI が行います

### カタログに登録してもらう

公開したプロジェクトは、他の oer-kit カタログ（例:
[OER World](https://takedatoshiyuki.github.io/oer-world/)）が**リポジトリの URL だけで
取り込めます**（連合。[設計書 §7.6](design.md)）。クロールは不要で、相手側は次の
1行で取り込みます:

```sh
oer-kit ingest https://github.com/<ユーザー名>/my-oer      # 公開サイトの URL でも可
```

- 取り込まれると、相手のカタログに「あなたのページを指す目録エントリ」ができます
  （教材本体はあなたのサイトに置かれたまま。出典種別は「個人公開」と表示）
- 依頼はカタログの誤り報告・依頼窓口へ（OER World は
  [GitHub Issues](https://github.com/takedatoshiyuki/oer-world/issues)）。掲載の
  取り下げも同じ窓口で受け付けます
- 取り込み済みの教材をあとで修正しても、相手のカタログには自動では反映されません。
  大きく変えたときは窓口で再取り込みを依頼してください（新しく追加した教材は
  再取り込みで追加されます）
- リポジトリは公開（public）にしておく必要があります

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
| `description が N 件で同一` | サイト共通の定型文を掴んでいる。抽出方法を疑う（[diagnose](commands.md#重複が出たときの調べ方diagnosepy)） |
| `語彙キー '...' が無い` | `vocabularies/` に定義されたキーを使う（必要なら語彙に追加） |
| `slug '...' がディレクトリ名と不一致` | `slug` はディレクトリ名と一致させる（省略可） |
| `NC 系ライセンスは非推奨` (警告) | 掲載は可能。営利形態の教育機関で使えなくなる旨の注意喚起 |

## ドキュメントマップ

| 文書 | 対象 |
|------|------|
| このガイド | システムを導入して使う人 |
| [サイトの使い方](../oer_kit/scaffold/site/guide.qmd) | 公開されたカタログの閲覧者（Quarto 雛形のサイトに掲載される） |
| [設計書](design.md) | 設計の全体像・根拠・決定の記録 |
| [レビュー チェックリスト](review-checklist.md) | レビュー担当者 |
| [commands.md](commands.md) | 全コマンドのリファレンスと運用ノート |
