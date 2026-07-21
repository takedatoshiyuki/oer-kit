#!/usr/bin/env python3
"""metadata.yaml の検証 (docs/design.md §9)。

JSON Schema 検証に加え、スキーマでは表現しない運用ポリシーを検査する:
- slug とディレクトリ名の一致
- 語彙キーが vocabularies/*.yaml に存在すること
- hosted は content/ を持つこと (警告) / referenced は持たないこと (警告)
- NC 系ライセンスは非推奨 (警告)

使い方:
    python3 tools/validate.py                # resources/ 全件
    python3 tools/validate.py resources/xxx  # 指定ディレクトリのみ
終了コード: エラーがあれば 1 (警告のみなら 0)
"""

from __future__ import annotations

import argparse
import json
import re
import sys

import jsonschema

from common import SCHEMA_PATH, VOCAB_FILES, iter_resources, load_all_vocabs, load_config


def validate_resource(slug, resource_dir, meta, validator, vocabs):
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

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="検証するリソースディレクトリ (省略時は全件)")
    args = parser.parse_args()

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft202012Validator(schema)
    vocabs = load_all_vocabs(load_config())

    total = error_count = warning_count = 0
    for slug, resource_dir, meta in iter_resources(args.paths or None):
        total += 1
        errors, warnings = validate_resource(slug, resource_dir, meta, validator, vocabs)
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
