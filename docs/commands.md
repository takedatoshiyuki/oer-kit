# tools/ — 検証・ビルド・クロール補助

設計: [docs/design.md](../docs/design.md) §7.3・§8・§9。設定は [config.yaml](../config.yaml)
（`base_url` はここだけで定義。公開URL確定時にここを変えれば全出力に反映される）。

## 必要環境

| 用途 | 環境 |
|------|------|
| validate / jsonld / build_catalog / convert_legacy | `python3`（pyyaml, jsonschema, pandas） |
| discover / wayback / fetch(requests) | 上記 + requests |
| fetch --engine playwright（JSレンダリング） | `~/Dropbox/Projects/genai_activities/.venv/bin/python3`（playwright 入り。取得層の正本 `common_knowledge.web` を config.yaml の lib_paths 経由で使用） |

## コマンド一覧

```sh
# 管理UI (ダッシュボード + 新規教材の作成/レビュー/承認/取り下げ)。127.0.0.1 のみ・追加依存なし
# 「＋ 新規教材」: フォームでメタデータ作成 (ライセンス選択の説明つき) → ファイルを
# アップロードして content/ ・assets/ に組織化 → 下書きとしてレビュー/承認フローへ
oer-kit ui   # または python3 -m oer_kit.ui --port 8765

# 公開の取り下げ。差し戻し (--demote: drafts へ戻す) と恒久取り下げ (--reason 必須) を区別。
# 恒久取り下げは withdrawn.yaml に記録され、以後の収集 (make-drafts) から除外・再登録は validate がエラー
oer-kit withdraw <slug>... --reason "本人からの削除依頼 (Issues #12)" [--by 氏名]
oer-kit withdraw <slug>... --demote

# 検証 (スキーマ + 語彙キー + 運用ポリシー + 横断重複)。CI で必須にする
# 対象を絞って指定しても、重複検査は既存リソース全件と突き合わせる
python3 tools/validate.py [resources/<slug> ...]

# レビュー支援: 引用文が原文のままかキャッシュと照合する (改変・要約の混入を検出)
python3 tools/validate.py --check-quotes [resources/<slug> ...]

# JSON-LD 生成 (1件を標準出力 / 全件を _site/jsonld/ へ)
python3 tools/jsonld.py --print <slug>
python3 tools/jsonld.py

# catalog.json + sitemap.xml + 全 JSON-LD (§8.1 の配信物一式)
python3 tools/build_catalog.py

# sitemap から URL 列挙 (robots.txt → sitemap.xml 再帰)
python3 tools/discover.py https://ocw.kyoto-u.ac.jp/ --limit 100 --out urls.tsv

# ページ取得 (キャッシュ付き。.cache/pages/ へ保存、取得日を access_log.tsv に記録)
python3 tools/fetch.py <url> [--force]

# Wayback スナップショット確認 / referenced 全件のリンク生存確認
python3 tools/wayback.py <url>
python3 tools/wayback.py --check

# 旧クローラ収集データ (科研STOER output/*.xlsx) → referenced 下書き
python3 tools/convert_legacy.py "<path>/output/ocw_kyoto_u.xlsx" --limit 10 --with-source

# ページから説明文の候補を抽出 (quotedDescription の下ごしらえ)
python3 tools/extract.py <html|url> [--corpus <同一サイトのディレクトリ>]
python3 tools/extract.py --survey <コーパス>   # サイト別の的中率を測る

# 重複の原因調査: 各リソースの出力と原ページの抽出候補を1つの Markdown に集める
python3 tools/diagnose.py [--slugs a b c] [--out report.md]

# description (CC0の自作要約) の一括生成。quotedDescription には触れない
python3 tools/generate.py --provider mock drafts/<slug>      # API不要の試運転
python3 tools/generate.py --limit 10                         # まず10件で実測 (要 OPENAI_API_KEY)
python3 tools/generate.py --base-url http://localhost:11434/v1 --model qwen3 --api-key dummy  # ローカルLLM

# 教材ファイルリンクの抽出 (metadata.yaml の materials に貼れる YAML で出力)
python3 tools/extract.py <html|url> --materials [--base-url <url>]

# 各回が別ページの講座は --follow で深さ1巡回 (由来が materials[].page に入る)
python3 tools/extract.py <コースURL> --materials --follow              # コースURL配下を各回とみなす (京大 ?video_id= 型)
python3 tools/extract.py <コースURL> --materials --follow "/content/"  # 別パス型は正規表現で指定 (UTokyo Channel /content/?id= 型)

# 他の oer-kit プロジェクトからの取り込み (連合。§7.6)。GitHub URL / サイトURL / ローカルパス
oer-kit ingest https://github.com/taro/my-oer [--prefix taro] [--kind personal]

# 教材ファイルの収集 (コーパス層 → archive_dir。権利ゲート・sha256・manifest付き)
python3 tools/harvest.py drafts/<slug> [--limit N] [--force]
```

### 説明文の抽出方針（extract.py）

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

### description の生成（generate.py）

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

### 重複が出たときの調べ方（diagnose.py）

`validate.py` が「description が同一」と言ったら、`diagnose.py` で判断材料を集める。
各リソースの現在の出力と、原ページから本来取れたはずの候補が並ぶので、
「定型文を掴んでいたのか」「正しい説明文はどれか」「どの手段で取れるか」が一覧で分かる。

集めるのはコード、吟味は人／LLM という分担にしてある（ツール側から LLM API は呼ばない）。
理由: 診断はまれにしか起きず、結果は**ルールの修正**（`extract.py` のラベル辞書・
定型文しきい値、生成プロンプト）という人が承認すべき変更になるため。
CI を決定的・無料・オフラインに保つ意味もある。

## サイトのビルド (Quarto)

リポジトリ直下の Makefile が一括実行する。Quarto は Homebrew でインストール
（`brew install --cask quarto`）。

```sh
make site      # 検証 → prerender → quarto render → catalog (公開一式を _site/ へ)
make preview   # ローカルプレビュー
make clean
```

- `tools/prerender.py` が `site/_quarto.in.yml` + `config.yaml` から `site/_quarto.yml` を生成し、
  各リソースを `site/r/<slug>/index.qmd`（JSON-LD を `<head>` に埋め込み）へ変換する。
  hosted の `content/`・`assets/` はページ配下へコピーされ、Markdown/ipynb は Quarto が
  そのままレンダリングする（ビルド時のコード実行は無効化してある）
- 手書きページは `site/index.qmd`（カタログ listing）と `site/about.qmd`。
  サイト設定の変更は `site/_quarto.in.yml` に対して行う
- sitemap.xml は Quarto 生成を優先し、build_catalog はフォールバックのみ

## ワークフロー

**hosted リソースの追加**: `resources/<slug>/` 作成 → `metadata.yaml` 記入 →
`validate.py` → PR → マージ後 `build_catalog.py`。

**referenced エントリの量産（§7.3 パイプライン）**:
`discover.py`（URL列挙）→ `fetch.py`（取得・キャッシュ）→ `extract.py`（説明文の候補抽出）→
AI で metadata.yaml 下書き生成（[resource.schema.json](../schemas/resource.schema.json) を
出力制約に使う。旧データからは `convert_legacy.py`）→ **人手レビュー**
（[チェックリスト](../docs/review-checklist.md)、`validate.py --check-quotes`、
`metadataProvenance.reviewedBy` 記入）→ `validate.py` が通ったら `drafts/` から `resources/` へ
移動して PR → `wayback.py --check` でリンク・スナップショット確認 → `archivedAt` 記入。

## 出力先

- `_site/` — ビルド成果物（jsonld/, catalog.json, sitemap.xml）。Git 管理外
- `.cache/` — 取得キャッシュ・取得ログ・旧データの本文退避。Git 管理外
- `drafts/` — レビュー前の下書き。Git 管理外

## レビューの回し方

413件を1件ずつ精読するのは現実的でないので、**機械が確認済みの項目は出さず**、
人にしか判断できないものだけを一覧にする。

```sh
python3 tools/review_sheet.py --open       # レビュー支援ビュー (.cache/review.html)
python3 tools/approve.py --by "氏名" --dry-run <slug>...   # 検査のみ (無変更)
python3 tools/approve.py --by "氏名" <slug>...             # 承認 → resources/ へ移動
python3 tools/approve.py --by "氏名" --from-file approved.txt
```

`review_sheet.py` は**部局 × 主題分野の対応表**を先頭に出す。1件ずつ見ていては
気づけない機械推定の誤りが、面で見ると一目で分かる（実測: 「教養教育院」が
「教育」に部分一致して 126件が education に誤分類されていたのを即座に検出）。

`approve.py` は `reviewedBy` を記入 → 検査（スキーマ・語彙・横断重複）→ **通ったものだけ**
`resources/` へ移動する。落ちたものは `drafts/` に残るので直して再実行すればよい。
