# oer-kit — OER カタログの構築キット

教育資源（OER）のカタログを作り、公開するための Python モジュールです。
メタデータスキーマ（schema.org / LRMI・[AMB](https://dini-ag-kim.github.io/amb/latest/) 準拠）、
検証、収集支援、Quarto によるサイト生成を提供します。

3つの使い方を想定しています（[設計書 §9.1](docs/design.md)）:

| 利用者 | 例 | 運用モード |
|--------|-----|-----------|
| 収集して公開する | 各大学の OCW や個人公開の教材を横断カタログ化 | `aggregator` |
| 組織として公開する | 大学・機関が自組織の教材を公開 | `institutional` |
| 個人で公開する | 自分の授業資料・スライドを公開 | `personal` |

## インストールとプロジェクト作成

```sh
pip install "oer-kit @ git+https://github.com/takedatoshiyuki/oer-kit"   # または pip install -e .
oer-kit init my-oer && cd my-oer
# config.yaml を編集 → resources/ に教材を追加 → oer-kit validate → make site
oer-kit ui        # 管理UI (ダッシュボード + レビュー/承認) をブラウザで開く
```

pip でインストールしない場合は、プロジェクト側から `PYTHONPATH` で参照できます:

```sh
make site OER_KIT=../oer-kit
```

## 何が入っているか

```
oer_kit/            Python パッケージ (ui / validate / prerender / build_catalog /
                    discover / fetch / extract / make_drafts / generate /
                    review_sheet / approve / harvest / wayback / diagnose …)
oer_kit/schema/     metadata.yaml の正規仕様 (JSON Schema 2020-12)
oer_kit/scaffold/   プロジェクトの雛形 (config・語彙・サイトテンプレート・CI・Makefile)
docs/               設計書・利用ガイド・レビュー チェックリスト・コマンド一覧
examples/resources/ 記入例 (hosted / referenced ND / 個人公開)
```

## ドキュメント

| 文書 | 内容 |
|------|------|
| [利用ガイド](docs/user-guide.md) | セットアップから公開までの手順（まずこれを読む） |
| [設計書](docs/design.md) | 設計の全体像・根拠・決定の記録 |
| [コマンド一覧](docs/commands.md) | 全コマンドのリファレンスと運用ノート |
| [レビュー チェックリスト](docs/review-checklist.md) | レビュー担当者向け |

## ライセンス

コード・スキーマ・語彙・文書は [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)。
このキットで作られる各プロジェクトのライセンス方針は雛形の
[LICENSE.md](oer_kit/scaffold/LICENSE.md)（メタデータ CC0 / コンテンツは各リソースの表示）を参照。
