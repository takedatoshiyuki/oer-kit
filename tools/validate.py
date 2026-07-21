#!/usr/bin/env python3
"""metadata.yaml の検証 (docs/design.md §9)。

JSON Schema 検証に加え、スキーマでは表現しない運用ポリシーを検査する:
- slug とディレクトリ名の一致
- 語彙キーが vocabularies/*.yaml に存在すること
- hosted は content/ を持つこと (警告) / referenced は持たないこと (警告)
- NC 系ライセンスは非推奨 (警告)
- description が quotedDescription の丸写しでないこと

使い方:
    python3 tools/validate.py                # resources/ 全件
    python3 tools/validate.py resources/xxx  # 指定ディレクトリのみ
    python3 tools/validate.py --check-quotes # 引用文が原文のままかキャッシュと照合
終了コード: エラーがあれば 1 (警告のみなら 0)
"""

from __future__ import annotations

import argparse
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

    page_text = _squash("\n".join(visible_lines(cache_path.read_text(encoding="utf-8",
                                                                     errors="ignore"))))
    errors = []
    for value in _text_values(quoted["text"]):
        # 原文が改行で分かれている場合があるので行ごとに照合する
        for line in [l for l in value.splitlines() if len(l.strip()) >= 10]:
            if _squash(line) not in page_text:
                errors.append(f"quotedDescription が原文と一致しない（改変の疑い）: 「{line[:40]}…」")
                break
    return errors, []


def validate_resource(slug, resource_dir, meta, validator, vocabs, check_quotes=False):
    errors, warnings = [], []

    if meta is None:
        return [f"metadata.yaml が空、または読み込めない"], []

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
    vocabs = load_all_vocabs(load_config())

    total = error_count = warning_count = 0
    for slug, resource_dir, meta in iter_resources(args.paths or None):
        total += 1
        errors, warnings = validate_resource(slug, resource_dir, meta, validator, vocabs,
                                             check_quotes=args.check_quotes)
        error_count += len(errors)
        warning_count += len(warnings)
        mark = "NG" if errors else ("WARN" if warnings else "OK")
        print(f"[{mark}] {slug}")
        for message in errors:
            print(f"  ERROR: {message}")
        for message in warnings:
            print(f"  warn:  {message}")

    print(f"---\n{total} 件検証: エラー {error_count} / 警告 {warning_count}")
    return 1 if error_count else 0


if __name__ == "__main__":
    sys.exit(main())
