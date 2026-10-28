# コマンドリファレンス — 検証・ビルド・収集補助

設計: [design.md](design.md) §7.3・§8・§9。設定はプロジェクト直下の `config.yaml`
（`base_url` はここだけで定義。公開URL確定時にここを変えれば全出力に反映される）。
導入の流れは[利用ガイド](user-guide.md)を参照。

すべて `oer-kit <コマンド>` で実行する（`oer-kit --help` で一覧、
`oer-kit <コマンド> --help` で各オプション）。oer-kit をインストールしていない場合は
`PYTHONPATH=<oer-kitの場所> python -m oer_kit.<モジュール名>` でも同じ。

## 必要環境

| 用途 | 必要なもの |
|------|------|
| 全コマンド | Python 3.10+（pyyaml・jsonschema・requests。`pip install` で入る） |
| サイト生成（`make site`） | `config.yaml` の `site_engine` に応じて [Hugo](https://gohugo.io/) 0.132 以上 または [Quarto](https://quarto.org/) |
| convert-legacy（旧収集データの変換） | `pip install "oer-kit[legacy] @ git+…"`（pandas・openpyxl） |
| fetch の JS レンダリング（Playwright） | Playwright を入れた Python 環境で、`config.yaml` の `lib_paths` から取得層 `common_knowledge.web` を読み込めること（無ければ requests で取得する） |

## コマンド一覧

```sh
# 新しいプロジェクトを作る (engine を省略すると対話で選択。design.md §8.4)
oer-kit init <ディレクトリ> [--engine hugo|quarto]

# 管理UI (ダッシュボード + 新規教材の作成/レビュー/承認/取り下げ)。127.0.0.1 のみ・追加依存なし
# 「＋ 新規教材」: フォームでメタデータ作成 (ライセンス選択の説明つき) → ファイルを
# アップロードして content/ ・assets/ に組織化 → 下書きとしてレビュー/承認フローへ
oer-kit ui [--port 8765] [--no-open]

# 公開の取り下げ。差し戻し (--demote: drafts へ戻す) と恒久取り下げ (--reason 必須) を区別。
# 恒久取り下げは withdrawn.yaml に記録され、以後の収集 (make-drafts) から除外・再登録は validate がエラー
oer-kit withdraw <slug>... --reason "本人からの削除依頼 (Issues #12)" [--by 氏名]
oer-kit withdraw <slug>... --demote

# 検証 (スキーマ + 語彙キー + 運用ポリシー + 横断重複)。CI で必須にする
# 対象を絞って指定しても、重複検査は既存リソース全件と突き合わせる
oer-kit validate [resources/<slug> ...]

# レビュー支援: 引用文が原文のままかキャッシュと照合する (改変・要約の混入を検出)
oer-kit validate --check-quotes [resources/<slug> ...]

# サイト入力の生成 (site_engine に応じて Quarto / Hugo 用。通常は make 経由で呼ばれる)
oer-kit prerender

# JSON-LD 生成 (1件を標準出力 / 全件を _site/jsonld/ へ)
oer-kit jsonld --print <slug>
oer-kit jsonld

# catalog.json + sitemap.xml + 全 JSON-LD (§8.1 の配信物一式)
oer-kit build-catalog

# sitemap から URL 列挙 (robots.txt → sitemap.xml 再帰)
oer-kit discover https://ocw.kyoto-u.ac.jp/ --limit 100 --out urls.tsv

# ページ取得 (キャッシュ付き。.cache/pages/ へ保存、取得日を access_log.tsv に記録)
# robots.txt 遵守・連絡先入り User-Agent 必須・間隔1秒以上 (§7.7 収集の礼儀)
oer-kit fetch <url> [--force]
oer-kit fetch --batch urls.tsv [--concurrency 2]

# サイト別パーサ (プロジェクトの parsers/<site>.py) で referenced の下書きを一括生成
oer-kit make-drafts --site <パーサ名> --urls urls.tsv [--limit N] [--overwrite]

# Wayback スナップショット確認・保存 / referenced 全件のリンク生存確認
oer-kit wayback <url>
oer-kit wayback --save <url>
oer-kit wayback --check

# 旧クローラ収集データ (科研STOER output/*.xlsx) → referenced 下書き
oer-kit convert-legacy "<path>/output/ocw_kyoto_u.xlsx" --limit 10 --with-source

# ページから説明文の候補を抽出 (quotedDescription の下ごしらえ)
oer-kit extract <html|url> [--corpus <同一サイトのディレクトリ>]
oer-kit extract --survey <コーパス>   # サイト別の的中率を測る

# 重複の原因調査: 各リソースの出力と原ページの抽出候補を1つの Markdown に集める
oer-kit diagnose [--slugs a b c] [--out report.md]

# description (CC0の自作要約) の一括生成。quotedDescription には触れない
oer-kit generate --provider mock drafts/<slug>      # API不要の試運転
oer-kit generate --limit 10                         # まず10件で実測 (要 OPENAI_API_KEY)
oer-kit generate --base-url http://localhost:11434/v1 --model qwen3 --api-key dummy  # ローカルLLM

# 教材ファイルリンクの抽出 (metadata.yaml の materials に貼れる YAML で出力)
oer-kit extract <html|url> --materials [--base-url <url>]

# 各回が別ページの講座は --follow で深さ1巡回 (由来が materials[].page に入る)
oer-kit extract <コースURL> --materials --follow              # コースURL配下を各回とみなす (京大 ?video_id= 型)
oer-kit extract <コースURL> --materials --follow "/content/"  # 別パス型は正規表現で指定 (UTokyo Channel /content/?id= 型)

# 他の oer-kit プロジェクトからの取り込み (連合。§7.6)。GitHub URL / サイトURL / ローカルパス
oer-kit ingest https://github.com/taro/my-oer [--prefix taro] [--kind personal]

# 教材ファイルの収集 (コーパス層 → archive_dir。権利ゲート・sha256・manifest付き)
oer-kit harvest drafts/<slug> [--limit N] [--force]
```

### 説明文の抽出方針（oer-kit extract）

原文の転載は**コードで行う**（LLM に書かせると改変・幻覚が混じり、「原文のまま」を保証できない）。
3段階で候補を挙げる: ①JSON-LD の description → ②og:description / meta description →
③ラベル付きセクション（概要／講義の概要／授業の内容／Course Description …）。

②には罠があり、多くのサイトで meta にサイト共通の紹介文（「○○大学 OCW は…」）が入っている。
同一サイト内で3ページ以上に現れる文を定型文として自動除外する（`--corpus`／`--survey` 時）。

**LLM が必要なのは次の3つだけ**:

1. 候補が複数あるときの選択（名大のコースページは「講義の概要／講義の内容／講義内容（表の見出し・誤検出）／
   og:description」の4候補が出る）。**同じサイトでも正解の手段はページごとに違う**
   （0001 はラベル節、0002 は og:description が本文説明）ため、固定ルールでは決められない
2. ラベルも meta も無いサイト（上智など）からの抽出
3. `description`（自作・CC0 で提供する要約）の作成 — これは転載であってはならないので、
   そもそもコードで作るものではない

### description の生成（oer-kit generate）

`quotedDescription`（原文の転載）はコードの仕事、`description`（CC0 で提供する自作要約）は
LLM／人の仕事、という分担（§7.3）の後者。**生成物は必ず機械検査してから書き戻す**:
引用文の丸写し（連続40字以上の一致を含む）、評価語（「わかりやすい」「必見」等）、
短すぎる出力は不採用にする。

過剰帰属への対処は LMS-NG docs/09・20 の実測に基づく。素朴な単発プロンプトは
根拠のない断定を混ぜるので、**2段構造を出力スキーマで強制**する — まず原文から
読み取れた事実を列挙させ（`facts`）、その事実だけで要約を書かせ、情報が足りなければ
`confidence: low` を返させる（書けないときは書かせない）。

プロバイダは OpenAI 互換の `/chat/completions` を叩くだけなので、`--base-url` を
差し替えればローカル LLM（Ollama・llama.cpp・vLLM）でも同じコードで動く。
`--provider mock` は API 不要（パイプラインの試運転用）。

モデル選択（2026-07 時点）: 無料枠が gpt-5.4-mini 等の小型モデル群で 10M トークン/日、
gpt-5.4 等で 1M/日。413件の実測見積もりは最悪ケースでも約4.6M なので**小型モデル枠なら
1日で完走**する（大型枠は現実シナリオで約97万トークンと上限すれすれ）。小型モデルで
通るプロンプトはローカル LLM へも移植しやすい。

### 重複が出たときの調べ方（oer-kit diagnose）

`oer-kit validate` が「description が同一」と言ったら、`oer-kit diagnose` で判断材料を集める。
各リソースの現在の出力と、原ページから本来取れたはずの候補が並ぶので、
「定型文を掴んでいたのか」「正しい説明文はどれか」「どの手段で取れるか」が一覧で分かる。

集めるのはコード、吟味は人／LLM という分担にしてある（ツール側から LLM API は呼ばない）。
理由: 診断はまれにしか起きず、結果は**ルールの修正**（`oer_kit/extract.py` のラベル辞書・
定型文しきい値、生成プロンプト）という人が承認すべき変更になるため。
CI を決定的・無料・オフラインに保つ意味もある。

## サイトのビルド

プロジェクト直下の Makefile が一括実行する（`oer-kit init` が選んだエンジン用の
Makefile と公開用 CI を配置する）。

```sh
make site      # 検証 → prerender → レンダリング → catalog (公開一式を _site/ へ)
make preview   # ローカルプレビュー
make clean
```

- `oer-kit prerender` が `config.yaml` の `site_engine` に従ってサイト入力を作る:
  - **quarto**: `site/_quarto.in.yml` + `config.yaml` → `site/_quarto.yml`、各リソース →
    `site/r/<slug>/index.qmd`（JSON-LD を `<head>` に埋め込み）。hosted の `content/`・
    `assets/` はページ配下へコピーされ、Markdown/ipynb は Quarto が HTML にレンダリング
    する（ビルド時のコード実行は無効化してある）
  - **hugo**: `site/hugo.in.yaml` + `config.yaml` → `site/hugo.yaml`、各リソース →
    `site/content/r/<slug>/index.md`（JSON-LD は front matter 経由でレイアウトが埋め込む）。
    hosted の `content/`・`assets/` は `site/static/r/<slug>/` へコピーされ、加工せず
    そのまま配信される。数式は `transform.ToMath` でビルド時に MathML へ変換
- レンダリング結果は `site/_site/` に出力され、`make` が `_site/` へ同期する
- 手書きページ: quarto は `site/index.qmd`（カタログ listing）・`site/about.qmd`・
  `site/guide.qmd`、hugo は `site/content/_index.md` と `site/layouts/`。サイト設定の変更は
  `*.in.yml` / `*.in.yaml` に対して行う（生成された設定ファイルは prerender が上書きする）
- sitemap.xml はサイトエンジンの生成物を優先し、build-catalog はフォールバックのみ
  （フォールバックで自分が作った sitemap は毎回再生成する）

## ワークフロー

**hosted リソースの追加**（組織・個人）: `oer-kit ui` の「＋ 新規教材」（または
`resources/<slug>/` を手で作成）→ `oer-kit validate` → 承認（`personal` は本人が
`oer-kit approve --by`、`institutional` は PR でレビュー）→ push すると CI が公開する。

**referenced エントリの量産（§7.3 パイプライン）**:
`oer-kit discover`（URL列挙）→ `oer-kit fetch --batch`（取得・キャッシュ）→
`oer-kit make-drafts`（プロジェクトの `parsers/<site>.py` で下書き生成。旧データからは
`oer-kit convert-legacy`。metadata.yaml の正規仕様は
[resource.schema.json](../oer_kit/schema/resource.schema.json)）→ `oer-kit generate`
（内容紹介。機械検査つき）→ `oer-kit validate --check-quotes` →
`oer-kit review-sheet` で面の確認（[チェックリスト](review-checklist.md)）→
`oer-kit approve`（drafts/ から resources/ へ）→ `oer-kit wayback --check` でリンク・
スナップショット確認。

**他の oer-kit プロジェクトから**: `oer-kit ingest <GitHub URL | サイトURL>`（クロール不要。§7.6）。

## 出力先

- `_site/` — ビルド成果物（ページ・jsonld/・catalog.json・sitemap.xml）。Git 管理外
- `.cache/` — 取得キャッシュ・取得ログ・旧データの本文退避。Git 管理外
- `drafts/` — レビュー前の下書き。Git 管理外

## レビューの回し方

413件を1件ずつ精読するのは現実的でないので、**機械が確認済みの項目は出さず**、
人にしか判断できないものだけを一覧にする。

```sh
oer-kit review-sheet --open                          # レビュー支援ビュー (.cache/review.html)
oer-kit approve --by "氏名" --dry-run <slug>...      # 検査のみ (無変更)
oer-kit approve --by "氏名" <slug>...                # 承認 → resources/ へ移動
oer-kit approve --by "氏名" --from-file approved.txt
```

`oer-kit review-sheet` は**部局 × 主題分野の対応表**を先頭に出す。1件ずつ見ていては
気づけない機械推定の誤りが、面で見ると一目で分かる（実測: 「教養教育院」が
「教育」に部分一致して 126件が education に誤分類されていたのを即座に検出）。

`oer-kit approve` は `reviewedBy` を記入 → 検査（スキーマ・語彙・横断重複）→ **通ったものだけ**
`resources/` へ移動する。落ちたものは `drafts/` に残るので直して再実行すればよい。
承認後は `resources/` の変更を Git にコミットするまでを1セットにする
（移動だけで終わると、公開リポジトリと手元がずれる）。
