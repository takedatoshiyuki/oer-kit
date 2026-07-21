<!-- 教材・目録エントリの追加/変更の場合は以下を記入してください。
     ツールやドキュメントの変更のみの場合はこの節を削除して構いません。 -->

## 対象

- slug:
- 種別: hosted（本体を公開） / referenced（外部教材の目録エントリ）

## メタデータの作成方法

- [ ] 手作業
- [ ] AI 生成・AI 支援（`metadataProvenance` に generator と generatedDate を記入済み）

## レビュー確認

[docs/review-checklist.md](../docs/review-checklist.md) に沿って確認しました。

- [ ] 事実（タイトル・著者・年・URL）が原ページと一致
- [ ] ライセンス／利用条件が原サイトの表示と一致
- [ ] `description` は自分の言葉による要約（引用の丸写しでない）
- [ ] 分類（`about` / `educationalLevel` / `learningResourceType`）が妥当
- [ ] `metadataProvenance.reviewedBy` にレビュー者を記入
- [ ] `python3 tools/validate.py --check-quotes` が通る
