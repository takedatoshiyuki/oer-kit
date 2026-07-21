# メタデータ・レビュー チェックリスト

AI 生成・機械変換されたメタデータは、**公開前に人手レビューを通す**（[設計書](design.md) §7.3）。
`metadataProvenance.method` が `ai_generated` / `ai_assisted` の場合、`reviewedBy` が無いと
`tools/validate.py` が拒否するため、レビューを経ないと公開できない。

## 手順

```sh
python3 tools/fetch.py <externalUrl>            # 原ページを取得（照合の材料）
python3 tools/validate.py --check-quotes drafts/<slug>
```

機械で確認できることは機械に任せ、レビューでは**人にしか判断できない項目**に集中する。

### 機械が確認済みのもの（レビューで見なくてよい）

| 項目 | 検査 |
|------|------|
| 必須項目の充足・型・語彙キー | JSON Schema + 語彙突合 |
| 引用文が原文のままか | `--check-quotes`（キャッシュと文字列照合。改変を検出） |
| `description` が引用文の丸写しでないか | 自動（CC0 で出せないため） |
| ND / 独自条件の整合（hosted で ND 不可など） | スキーマの条件分岐 |
| リンクの生存・アーカイブ有無 | `tools/wayback.py --check` |

## 人が確認すること

### 1. 事実の正しさ（最重要）

- [ ] **タイトル・著者・所属**が原ページと一致するか（AI は肩書きや氏名を取り違えることがある）
- [ ] **開講年度／公開年**（`datePublished`）の根拠は何か。年しか分からないなら年のみ記す
- [ ] `externalUrl` が教材本体に到達するか（一覧ページや検索結果ではないか）
- [ ] 他人の教材を、別人の作品として記載していないか

### 2. ライセンス・利用条件（法的に効くところ）

- [ ] `license` / `usageTerms` が**原サイトの表示と一致**するか。特に:
  - CC 表記があるか、独自条件か、それとも再利用禁止か
  - NC / SA / ND の別、バージョン（4.0 か旧版か）
- [ ] `usageTerms.summary` が条件を**過大にも過小にも**言っていないか
  （「自由に使える」と書いてしまう事故が起きやすい）
- [ ] `quotedDescription` を載せる根拠が `note` に書かれているか
  （先方の利用条件に基づく転載か、著作権法32条の引用か）

### 3. 内容紹介（`description`）

- [ ] **自分の言葉で書かれた要約**か（引用の言い換えではなく、何をどこまで扱う教材かを述べる）
- [ ] 2〜3文か。原文の構成をなぞる詳細な要約になっていないか（翻案のリスク）
- [ ] 教材を見ずには書けない具体性があるか。逆に、**根拠のない断定**（受講者数・評判・難易度など）が
      混じっていないか

### 4. 分類

- [ ] `about`（主題分野）・`educationalLevel`・`learningResourceType` が妥当か
- [ ] 迷ったら**付けない**（誤った分類は無分類より有害。`educationalLevel` は不明なら省略可）

## 承認

上記を確認したら `metadataProvenance.reviewedBy` に氏名を追記し、`drafts/` から
`resources/<slug>/` へ移動して PR を出す。`tools/validate.py` が通ることを確認してからマージする。

```yaml
metadataProvenance:
  method: ai_generated
  generator: claude-fable-5
  generatedDate: "2026-07-21"
  reviewedBy: [氏名]        # ← レビュー後に追記
```
