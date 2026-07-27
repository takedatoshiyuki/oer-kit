#!/usr/bin/env python3
"""旧クローラの収集結果 (科研STOER output/*.xlsx) → referenced エントリの下書き変換。

course 単位の行を mode: referenced の metadata.yaml 下書きにする。機械変換なので:
- description は TODO のまま (§7.3 の AI 生成 → 人手レビューで作成する)
- about・dateAccessed など埋められない項目は欠落のまま出力し、validate.py に
  検出させる (下書きは検証を通るまで resources/ に移さない)
- 元ページの本文テキストは --with-source で .cache/legacy_source/ に退避
  (AI 生成の入力用。公開物ではない)

使い方:
    python tools/convert_legacy.py <output/ocw_xxx.xlsx> [--out drafts] [--limit 10]
        [--all] [--with-source]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import pandas
import yaml

from .common import CACHE_DIR, LICENSE_URL, PROJECT_ROOT

TODO_DESCRIPTION = "TODO: 内容紹介を作成する (2〜3文・客観的記述。docs/design.md §7.3)"

# 旧データの license_url → SPDX ID (4.0 のみ。旧版 CC は URL のまま残す)
URL_TO_SPDX = {url: spdx for spdx, url in LICENSE_URL.items()}

MATERIAL_TYPE_TO_LRT = {
    "course": "course",
    "lecture notes": "script",
    "video": "video",
    "text": "text",
}


def normalize_license(value):
    """CC の URL なら SPDX ID か正規 URL に。CC 以外 (サイト独自の権利ページ等) は None。"""
    if not isinstance(value, str) or not value.strip():
        return None
    url = value.strip().replace("http://", "https://")
    if not url.endswith("/"):
        url += "/"
    if "creativecommons.org/" not in url:
        return None
    return URL_TO_SPDX.get(url, url)


def slugify(url: str, prefix: str) -> str:
    segments = [s for s in urlparse(url).path.split("/") if s]
    tail = "-".join(segments[-2:]) if segments else "top"
    tail = re.sub(r"[^a-z0-9]+", "-", tail.lower()).strip("-")
    slug = f"{prefix}-{tail}"[:60].strip("-")
    return re.sub(r"-+", "-", slug)


def row_to_metadata(row: dict, generated_date: str) -> dict:
    meta = {
        "mode": "referenced",
        "externalUrl": row["url"],
        "name": {"ja": str(row["title"]).strip()},
        "description": {"ja": TODO_DESCRIPTION},
        "inLanguage": ["en" if str(row.get("language", "")).lower().startswith("en") else "ja"],
    }

    license_value = normalize_license(row.get("license_url"))
    if license_value:
        meta["license"] = license_value
    elif row.get("license_url"):
        # CC 以外の権利表記はそのまま採用できない。原典を extensions に残しレビューで判断する
        meta["extensions"] = {"legacyLicenseUrl": str(row["license_url"]).strip()}

    author = str(row.get("author") or "").strip()
    organization = str(row.get("organization") or "").strip()
    if author:
        meta["creator"] = [{"type": "Person", "name": author}]
    elif organization:
        meta["creator"] = [{"type": "Organization", "name": organization}]
    if organization:
        meta["publisher"] = [{"type": "Organization", "name": organization}]

    date = str(row.get("date") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        meta["datePublished"] = date

    material_type = str(row.get("material_type") or "").strip().lower()
    meta["learningResourceType"] = [MATERIAL_TYPE_TO_LRT.get(material_type, "course")]

    tags = str(row.get("tags") or "").strip()
    if tags:
        meta["keywords"] = [t for t in re.split(r"[,、;\s]+", tags) if t]

    meta["metadataProvenance"] = {
        "method": "manual",
        "generatedDate": generated_date,
        "notes": ("tools/convert_legacy.py による旧収集データ(2023)からの機械変換ドラフト。"
                  "description の作成、about・dateAccessed 等の補完、再クロールでの現況確認が必要"),
    }
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xlsx", help="旧クローラの output/*.xlsx")
    parser.add_argument("--out", default=str(PROJECT_ROOT / "drafts"), help="下書きの出力先")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--all", action="store_true",
                        help="course 行だけでなく全行を変換する")
    parser.add_argument("--with-source", action="store_true",
                        help="本文テキストを .cache/legacy_source/ に退避 (AI生成の入力用)")
    args = parser.parse_args()

    df = pandas.read_excel(args.xlsx)
    if not args.all and "material_type" in df.columns:
        df = df[df["material_type"] == "course"]
    df = df[df["url"].notna() & df["title"].notna()]
    if args.limit:
        df = df.head(args.limit)

    import datetime
    generated_date = datetime.date.today().isoformat()
    prefix = Path(args.xlsx).stem.replace("_", "-")
    out_dir = Path(args.out)
    source_dir = CACHE_DIR / "legacy_source"

    count = 0
    seen_slugs = set()
    for _, row in df.iterrows():
        row = {k: ("" if pandas.isna(v) else v) for k, v in row.to_dict().items()}
        slug = slugify(row["url"], prefix)
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        meta = row_to_metadata(row, generated_date)
        meta["slug"] = slug

        draft_dir = out_dir / slug
        draft_dir.mkdir(parents=True, exist_ok=True)
        header = ("# 機械変換ドラフト (要レビュー)。validate.py が通るまで resources/ に移さない。\n"
                  f"# 変換元: {Path(args.xlsx).name}\n")
        body = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100)
        (draft_dir / "metadata.yaml").write_text(header + body, encoding="utf-8")

        if args.with_source:
            text = "\n\n".join(str(row.get(col) or "") for col in ("description", "contents"))
            if text.strip():
                source_dir.mkdir(parents=True, exist_ok=True)
                (source_dir / f"{slug}.txt").write_text(
                    f"source_url: {row['url']}\n---\n{text}", encoding="utf-8")
        count += 1

    print(f"{count} 件の下書き → {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
