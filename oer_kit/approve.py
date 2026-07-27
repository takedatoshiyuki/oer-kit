#!/usr/bin/env python3
"""レビュー承認の反映 — reviewedBy を記入し、drafts/ から resources/ へ移す。

`tools/review_sheet.py` で確認した slug をここに渡す。承認は次の順で行う:

1. `metadataProvenance.reviewedBy` にレビュー者名を記入
2. `tools/validate.py` 相当の検査（スキーマ・語彙・横断重複）を通す
3. **通ったものだけ** resources/ へ移動する

検査に落ちたものは drafts/ に残るので、直して再実行すればよい。

使い方:
    python tools/approve.py --by "山田 太郎" nagoya-u-course-0001 nagoya-u-course-0002
    python tools/approve.py --by "山田 太郎" --from-file approved.txt
    python tools/approve.py --by "山田 太郎" --all --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import jsonschema
import yaml

from .common import (
    RESOURCES_DIR,
    PROJECT_ROOT,
    SCHEMA_PATH,
    iter_resources,
    load_all_vocabs,
    load_config,
)
from .validate import check_duplicates, validate_resource

DRAFTS_DIR = PROJECT_ROOT / "drafts"


def with_reviewer(path: Path, reviewer: str) -> dict:
    """reviewedBy を加えた meta を返す（メモリ上のみ。書き込みは write_meta）。"""
    meta = yaml.safe_load(path.read_text(encoding="utf-8"))
    provenance = meta.setdefault("metadataProvenance", {})
    reviewers = list(provenance.get("reviewedBy") or [])
    if reviewer not in reviewers:
        reviewers.append(reviewer)
    provenance["reviewedBy"] = reviewers
    return meta


def write_meta(path: Path, meta: dict) -> None:
    """承認済み meta を書き戻す（下書き向けの注意書きは落とす）。"""
    raw = path.read_text(encoding="utf-8")
    header = "\n".join(l for l in raw.splitlines()
                       if l.startswith("#") and "要レビュー" not in l
                       and "reviewedBy 記入後" not in l)
    body = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100)
    path.write_text((header + "\n" if header.strip() else "") + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*")
    parser.add_argument("--by", help="レビュー者名（reviewedBy に記入）。"
                        "aggregator 運用では省略可（未レビューのまま公開し、ページに明示）")
    parser.add_argument("--from-file", help="slug を並べたファイル（空白・改行区切り）")
    parser.add_argument("--all", action="store_true", help="drafts/ 全件を承認する")
    parser.add_argument("--dry-run", action="store_true", help="検査だけ行い、移動しない")
    args = parser.parse_args()

    slugs = list(args.slugs)
    if args.from_file:
        slugs += Path(args.from_file).read_text(encoding="utf-8").split()
    if args.all:
        slugs += [d.name for d in DRAFTS_DIR.iterdir() if d.is_dir()]
    slugs = sorted(set(slugs))
    if not slugs:
        parser.error("slug か --from-file か --all を指定")

    with open(SCHEMA_PATH, encoding="utf-8") as f:
        validator = jsonschema.Draft202012Validator(json.load(f))
    config = load_config()
    vocabs = load_all_vocabs(config)
    policy = config["review_policy"]
    if policy != "aggregator" and not args.by:
        parser.error(f"review_policy={policy} では --by (レビュー者) が必須")

    # 横断検査は承認対象＋既存リソースをまとめて見る
    existing = [(slug, meta or {}) for slug, _d, meta in iter_resources()]

    approved, rejected = [], []
    entries = []
    for slug in slugs:
        draft_dir = DRAFTS_DIR / slug
        metadata_path = draft_dir / "metadata.yaml"
        if not metadata_path.exists():
            rejected.append((slug, ["drafts/ に無い"]))
            continue
        if args.by:
            meta = with_reviewer(metadata_path, args.by)
        else:
            meta = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        errors, _warnings = validate_resource(slug, draft_dir, meta, validator, vocabs,
                                              policy=policy)
        if errors:
            rejected.append((slug, errors))
        else:
            approved.append((slug, draft_dir, metadata_path, meta))
            entries.append((slug, meta))

    duplicate_slugs = set()
    for level, message in check_duplicates(entries, existing):
        if level == "ERROR":
            found = re.search(r"\(([^)]+)\)", message)
            names = [s.strip() for s in found.group(1).split(",")] if found else []
            duplicate_slugs.update(n for n in names if n in {a[0] for a in approved})
            rejected.append(("／".join(names), [message]))
    approved = [a for a in approved if a[0] not in duplicate_slugs]

    for slug, errors in rejected:
        print(f"[保留] {slug}")
        for e in errors:
            print(f"    {e}")

    if args.dry_run:
        print(f"---\n(dry-run) 承認可 {len(approved)} 件 / 保留 {len(rejected)} 件"
              "（ファイルは変更していない）")
        return 0

    RESOURCES_DIR.mkdir(exist_ok=True)
    moved = 0
    for slug, draft_dir, metadata_path, meta in approved:
        destination = RESOURCES_DIR / slug
        if destination.exists():
            print(f"[保留] {slug}: resources/ に同名が既にある")
            continue
        write_meta(metadata_path, meta)
        shutil.move(str(draft_dir), str(destination))
        moved += 1

    print(f"---\n承認 {moved} 件 → resources/ ／ 保留 {len(rejected)} 件")
    if moved:
        print("次: make site でカタログを再生成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
