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
# 検証 (スキーマ + 語彙キー + 運用ポリシー)。CI で必須にする
python3 tools/validate.py [resources/<slug> ...]

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
```

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
`discover.py`（URL列挙）→ `fetch.py`（取得・キャッシュ）→ AI で metadata.yaml 下書き生成
（[resource.schema.json](../schemas/resource.schema.json) を出力制約に使う。旧データからは
`convert_legacy.py`）→ **人手レビュー**（description 作成・確認、`metadataProvenance.reviewedBy`
記入）→ `validate.py` が通ったら `drafts/` から `resources/` へ移動 → `wayback.py --check` で
リンク・スナップショット確認 → `archivedAt` 記入。

## 出力先

- `_site/` — ビルド成果物（jsonld/, catalog.json, sitemap.xml）。Git 管理外
- `.cache/` — 取得キャッシュ・取得ログ・旧データの本文退避。Git 管理外
- `drafts/` — レビュー前の下書き。Git 管理外
