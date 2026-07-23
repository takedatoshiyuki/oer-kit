#!/usr/bin/env python3
"""metadata.yaml の検証 (docs/design.md §9)。

JSON Schema 検証に加え、スキーマでは表現しない運用ポリシーを検査する:
- slug とディレクトリ名の一致
- 語彙キーが vocabularies/*.yaml に存在すること
- hosted は content/ を持つこと (警告) / referenced は持たないこと (警告)
- NC 系ライセンスは非推奨 (警告)
- description が quotedDescription の丸写しでないこと
- リポジトリ横断の重複 (同じ externalUrl の二重登録、description の使い回し)

使い方:
    python3 tools/validate.py                # resources/ 全件
    python3 tools/validate.py resources/xxx  # 指定ディレクトリのみ
    python3 tools/validate.py --check-quotes # 引用文が原文のままかキャッシュと照合
終了コード: エラーがあれば 1 (警告のみなら 0)
"""

from __future__ import annotations

import argparse
import collections
import html as html_module
import json
import re
import sys

import jsonschema

from common import SCHEMA_PATH, VOCAB_FILES, iter_resources, load_all_vocabs, load_config


def _squash(text: str) -> str:
    """比較用に空白・記号ゆれを落とす。"""
    return re.sub(r"[\s　]+", "", text)


def _text_values(value):
    return [value] if isinstance(value, str) else list(value.values())


def check_quote_verbatim(meta):
    """quotedDescription が取得済みページの本文に「そのまま」含まれるか照合する。

    AI 生成メタデータで最も起きやすい事故（要約・改変されたものが引用として載る）を
    人手ではなく機械で捕まえる。キャッシュが無ければ検査をスキップする。
    """
    quoted = meta.get("quotedDescription")
    if not quoted:
        return [], []
    from extract import visible_lines
    from fetch import cache_path_for

    source = quoted.get("source") or meta.get("externalUrl")
    cache_path = cache_path_for(source)
    if not cache_path.exists():
        return [], [f"引用の照合をスキップ（キャッシュ無し: {source} → tools/fetch.py で取得）"]

    html = cache_path.read_text(encoding="utf-8", errors="ignore")
    # 可視テキストに加えて meta 由来の説明文も照合対象にする。
    # og:description / meta description から引いた引用は、本文と文言が異なることがあり
    # (サイト側が要約して入れている)、可視テキストだけでは原理的に検証できない
    haystack = visible_lines(html)
    for pattern in (r'property=["\']og:description["\'][^>]*content=["\']([^"\']*)',
                    r'content=["\']([^"\']*)["\'][^>]*property=["\']og:description',
                    r'name=["\']description["\'][^>]*content=["\']([^"\']*)'):
        haystack += [html_module.unescape(m) for m in re.findall(pattern, html, re.I)]
    page_text = _squash("\n".join(haystack))
    errors = []
    for value in _text_values(quoted["text"]):
        # 原文が改行で分かれている場合があるので行ごとに照合する
        for line in [l for l in value.splitlines() if len(l.strip()) >= 10]:
            if _squash(line) not in page_text:
                errors.append(f"quotedDescription が原文と一致しない（改変の疑い）: 「{line[:40]}…」")
                break
    return errors, []


def check_duplicates(entries, existing=()):
    """リポジトリ横断の重複検査。1件ずつの検証では見えない事故を捕まえる。

    - 同じ externalUrl を二重に目録化していないか
    - description が使い回されていないか（サイト共通の定型文を掴んだ、
      AI が雛形的な文を量産した、などの兆候）
    - 数字だけ違う description（年度違いの雛形）

    entries: 今回検証した [(slug, meta)]、existing: 既存の [(slug, meta)]
    """
    findings = []
    pool = list(entries) + [e for e in existing
                            if e[0] not in {slug for slug, _ in entries}]
    checked_slugs = {slug for slug, _ in entries}

    def group(key_func, values_func):
        groups = collections.defaultdict(list)
        for slug, meta in pool:
            for value in values_func(meta):
                key = key_func(value)
                if key:
                    groups[key].append(slug)
        # 今回検証した対象を含む重複だけを報告する
        return {k: sorted(set(v)) for k, v in groups.items()
                if len(set(v)) > 1 and checked_slugs & set(v)}

    for url, slugs in group(lambda v: v, lambda m: [m.get("externalUrl")]).items():
        findings.append(("ERROR", f"externalUrl の重複 ({', '.join(slugs)}): {url}"))

    # 未記入プレースホルダ (下書き) は重複ではなく「未作成」なので対象外
    def real_descriptions(m):
        return [v for v in _text_values(m.get("description", "")) if not v.startswith("TODO")]

    descriptions = group(_squash, real_descriptions)
    for _key, slugs in descriptions.items():
        findings.append(("ERROR",
                         f"description が {len(slugs)} 件で同一 ({', '.join(slugs[:5])}"
                         f"{' ほか' if len(slugs) > 5 else ''}): "
                         "サイト共通の定型文を掴んでいないか確認すること"))

    templated = group(lambda v: re.sub(r"\d+", "#", _squash(v)), real_descriptions)
    for key, slugs in templated.items():
        if key in {re.sub(r"\d+", "#", k) for k in descriptions}:
            continue   # 完全一致として既に報告済み
        findings.append(("warn",
                         f"description が数字以外同一 ({', '.join(slugs[:5])}"
                         f"{' ほか' if len(slugs) > 5 else ''}): 年度違いの雛形になっていないか"))

    for _key, slugs in group(_squash,
                             lambda m: _text_values((m.get("quotedDescription") or {}).get("text", ""))).items():
        findings.append(("warn",
                         f"quotedDescription が {len(slugs)} 件で同一 ({', '.join(slugs[:5])}"
                         f"{' ほか' if len(slugs) > 5 else ''}): "
                         "シリーズ共通の説明なら妥当、サイト定型文なら差し替えること"))

    return findings


def review_policy_findings(meta, policy):
    """運用モード (§9.1) に応じたレビュー要件の検査。"""
    provenance = meta.get("metadataProvenance") or {}
    if provenance.get("method") not in ("ai_generated", "ai_assisted"):
        return []
    if policy in ("institutional", "personal"):
        if not provenance.get("reviewedBy"):
            who = "組織のレビュー者" if policy == "institutional" else "本人"
            return [f"AI生成メタデータは公開前レビューが必要 "
                    f"(review_policy={policy}: reviewedBy に{who}を記入)"]
    else:  # aggregator: 未レビュー公開可。ただし信頼度の明示が公開条件
        if not provenance.get("confidence"):
            return ["aggregator 運用では confidence (high/low) の明示が公開条件 (§9.1)"]
    return []


def validate_resource(slug, resource_dir, meta, validator, vocabs, check_quotes=False,
                      policy="institutional"):
    errors, warnings = [], []

    if meta is None:
        return [f"metadata.yaml が空、または読み込めない"], []

    errors += review_policy_findings(meta, policy)

    for e in sorted(validator.iter_errors(meta), key=lambda e: e.json_path):
        errors.append(f"schema {e.json_path}: {e.message}")

    if "slug" in meta and meta["slug"] != resource_dir.name:
        errors.append(f"slug '{meta['slug']}' がディレクトリ名 '{resource_dir.name}' と不一致")

    for field, vocab in vocabs.items():
        for value in meta.get(field, []) or []:
            if isinstance(value, str) and value not in vocab:
                errors.append(
                    f"{field}: 語彙キー '{value}' が vocabularies/{VOCAB_FILES[field]} に無い"
                )

    # 個人サイトは組織サイトよりリンク切れが早い。アーカイブの確保を促す
    collection = meta.get("sourceCollection") or {}
    if collection.get("kind") == "personal" and not meta.get("archivedAt"):
        warnings.append("個人サイトの資料は archivedAt (Webアーカイブ) を強く推奨 "
                        "(tools/wayback.py --save <url> で保存できる。§7.5)")

    mode = meta.get("mode", "hosted")
    has_content = (resource_dir / "content").is_dir()
    if mode == "hosted" and not has_content:
        warnings.append("hosted だが content/ が無い (編集可能ソースを置くこと)")
    if mode == "referenced" and has_content:
        warnings.append("referenced は content/ を持たない設計 (docs/design.md §7.3)")

    license_value = meta.get("license", "")
    if isinstance(license_value, str) and (
        license_value.startswith("CC-BY-NC") or re.search(r"/by-nc(-sa|-nd)?/", license_value)
    ):
        warnings.append("NC 系ライセンスは非推奨 (営利形態の教育機関で使えない。§7.2)")

    # description (CC0 で出す自作要約) が引用文の丸写しだと CC0 宣言と衝突する
    quoted = meta.get("quotedDescription")
    if quoted:
        own = {_squash(v) for v in _text_values(meta.get("description", ""))}
        for value in _text_values(quoted["text"]):
            squashed = _squash(value)
            if any(o and (o in squashed or squashed in o) for o in own):
                errors.append("description が quotedDescription の丸写し "
                              "(CC0 で出せないため、自分の言葉で要約すること。§7.3-7)")
                break

    if check_quotes:
        quote_errors, quote_warnings = check_quote_verbatim(meta)
        errors += quote_errors
        warnings += quote_warnings

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="検証するリソースディレクトリ (省略時は全件)")
    parser.add_argument("--check-quotes", action="store_true",
                        help="quotedDescription を取得済みキャッシュと照合する (レビュー支援)")
    args = parser.parse_args()

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)
    config = load_config()
    vocabs = load_all_vocabs(config)
    policy = config["review_policy"]

    total = error_count = warning_count = 0
    entries = []
    for slug, resource_dir, meta in iter_resources(args.paths or None):
        total += 1
        entries.append((slug, meta or {}))
        errors, warnings = validate_resource(slug, resource_dir, meta, validator, vocabs,
                                             check_quotes=args.check_quotes, policy=policy)
        error_count += len(errors)
        warning_count += len(warnings)
        mark = "NG" if errors else ("WARN" if warnings else "OK")
        print(f"[{mark}] {slug}")
        for message in errors:
            print(f"  ERROR: {message}")
        for message in warnings:
            print(f"  warn:  {message}")

    # 横断検査。対象を絞って実行した場合も既存リソース全件と突き合わせる
    existing = [(s, m or {}) for s, _d, m in iter_resources()] if args.paths else []
    findings = check_duplicates(entries, existing)
    if findings:
        print("--- 横断検査（重複）")
        for level, message in findings:
            print(f"  {'ERROR' if level == 'ERROR' else 'warn '}: {message}")
            if level == "ERROR":
                error_count += 1
            else:
                warning_count += 1

    print(f"---\n{total} 件検証: エラー {error_count} / 警告 {warning_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
