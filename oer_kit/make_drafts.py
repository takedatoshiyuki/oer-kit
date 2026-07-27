#!/usr/bin/env python3
"""サイトパーサを使った referenced 下書きの一括生成。

取得済みキャッシュ (fetch.py --batch) を parsers/<site>.py で解析し、
drafts/<slug>/metadata.yaml を生成する。description は自作要約が必要なため
TODO のまま出力し、別途 (AI生成 → 人手レビュー) で埋める。
あわせて description 作成用のダイジェストを .cache/<site>_digest.jsonl に書く。

使い方:
    python3 tools/make_drafts.py --site nagoya_u --urls .cache/urls_nagoya_courses_ja.tsv
        [--limit N] [--overwrite]
"""

from __future__ import annotations

import argparse
import collections
import datetime
import importlib
import json
import re
import sys

import yaml

from .common import PROJECT_ROOT, load_yaml
from .fetch import cache_path_for

TODO_DESCRIPTION = "TODO: 内容紹介を作成する (2〜3文・客観的記述。docs/design.md §7.3)"
DRAFTS_DIR = PROJECT_ROOT / "drafts"


def site_entry(parser_name: str) -> dict:
    sites = load_yaml(PROJECT_ROOT / "sites.yaml")["sites"]
    for entry in sites:
        if entry.get("parser") == parser_name:
            return entry
    raise SystemExit(f"sites.yaml に parser: {parser_name} のサイトが無い")


def slug_for(parser_name: str, url: str) -> str | None:
    m = re.search(r"/courses/(\d+)-", url)
    if not m:
        return None
    prefix = parser_name.replace("_", "-")
    return f"{prefix}-course-{m.group(1)}"


def build_metadata(parsed: dict, url: str, site: dict, slug: str, today: str) -> dict:
    name = {"ja": parsed["name_ja"]}
    if parsed.get("name_en"):
        name["en"] = parsed["name_en"]

    meta: dict = {
        "slug": slug,
        "mode": "referenced",
        "externalUrl": url,
        "type": ["LearningResource", "Course"],
        "name": name,
        "description": {"ja": TODO_DESCRIPTION},
    }

    if parsed.get("quoted"):
        labels = "・".join(f"「{l}」" for l in parsed.get("quoted_labels", []))
        # 再利用可のサイトは規約に基づく転載、視聴のみ (no_reuse) のサイトは
        # 著作権法32条の引用として扱う (東大の試作エントリで確定した書式)。
        # 規約が教材のみを対象としページ本文に及ばないサイト (例: 北大) は
        # sites.yaml の quote_basis: quotation で引用扱いを強制できる
        basis = ("同サイトの利用条件に基づく転載"
                 if site["license_status"] in ("cc", "custom_reuse")
                 and site.get("quote_basis") != "quotation"
                 else "著作権法32条の引用")
        meta["quotedDescription"] = {
            "text": {"ja": parsed["quoted"]},
            "source": url,
            "note": f"{site['name']} {labels}より（{basis}）",
        }

    meta["inLanguage"] = parsed.get("inLanguage") or ["ja"]
    if parsed.get("license"):
        # コースページに CC 表記がある場合はそれが正 (例: 京大はコンテンツごとに CC が異なる)
        meta["license"] = parsed["license"]
    else:
        # reuse はサイト既定 (license_status から導出)。ページ単位でマークが違う
        # サイト (例: 北大の 制限資料/無表記) はパーサが usage_reuse で上書きする
        default_reuse = ("allowed_with_conditions"
                         if site["license_status"] == "custom_reuse" else "not_allowed")
        meta["usageTerms"] = {
            "url": site["license_url"],
            "summary": {"ja": site["usage_summary"]},
            "reuse": parsed.get("usage_reuse") or default_reuse,
        }

    if parsed.get("creators"):
        # 所属付きの講師リスト (外部講師が多いサイト向け。無い所属はサイトの機関名)
        meta["creator"] = [{"type": "Person", "name": c["name"],
                            "affiliation": {"name": c.get("affiliation")
                                            or site["organization"]}}
                           for c in parsed["creators"]]
    elif parsed.get("lecturers"):
        meta["creator"] = [{"type": "Person", "name": person,
                            "affiliation": {"name": site["organization"]}}
                           for person in parsed["lecturers"]]
    else:
        meta["creator"] = [{"type": "Organization", "name": site["organization"]}]
    meta["publisher"] = [{"type": "Organization", "name": site["organization"]}]
    # どのサイトの目録エントリかを一目で分かるようにする
    meta["sourceCollection"] = {"name": site["name"], "url": site["url"]}

    if parsed.get("year"):
        meta["datePublished"] = str(parsed["year"])
    meta["dateAccessed"] = today

    meta["learningResourceType"] = parsed.get("learningResourceType") or ["course"]
    about = parsed.get("about") or "generic"
    meta["about"] = about if isinstance(about, list) else [about]
    if parsed.get("tags"):
        meta["keywords"] = parsed["tags"]
    meta["audience"] = parsed.get("audience") or ["student"]
    if parsed.get("educationalLevel"):
        meta["educationalLevel"] = [parsed["educationalLevel"]]
    if parsed.get("materials"):
        meta["materials"] = [dict(m, page=url) for m in parsed["materials"]]

    extensions = {k: v for k, v in (("faculty", parsed.get("faculty")),
                                    ("term", parsed.get("term")),
                                    ("targetAudience", parsed.get("target"))) if v}
    if extensions:
        meta["extensions"] = extensions

    meta["metadataProvenance"] = {
        "method": "ai_generated",
        "generator": "claude-fable-5",
        "generatedDate": today,
        "notes": ("oer_kit.make_drafts + parsers による自動生成。"
                  "description は未作成。about・educationalLevel は機械推定のため要確認"),
    }
    return meta


HEADER = """# 一括生成の下書き (要レビュー)。docs/review-checklist.md に沿って確認し、
# reviewedBy 記入後に resources/ へ移動する。description は未作成 (TODO)。
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, help="parsers/ のモジュール名 (例: nagoya_u)")
    parser.add_argument("--urls", required=True, help="対象URLの一覧ファイル")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true", help="既存の下書きも書き直す")
    args = parser.parse_args()

    sys.path.insert(0, str(PROJECT_ROOT))   # パーサはプロジェクト側 (parsers/<site>.py)
    module = importlib.import_module(f"parsers.{args.site}")
    site = site_entry(args.site)
    today = datetime.date.today().isoformat()

    slugger = getattr(module, "slug_for", None) or (lambda u: slug_for(args.site, u))

    urls = [l.strip() for l in open(args.urls, encoding="utf-8")
            if l.strip() and l.strip() != "url"]
    from .withdraw import withdrawn_urls
    blocked = withdrawn_urls()
    if blocked:
        before = len(urls)
        urls = [u for u in urls if u not in blocked]
        if before != len(urls):
            print(f"取り下げ済み (withdrawn.yaml) のため {before - len(urls)} 件をスキップ")

    # 既に別 slug で公開済みの URL は重複を作らない (手作業の先行エントリなど)
    from .common import RESOURCES_DIR
    published = {m.get("externalUrl") for d in RESOURCES_DIR.iterdir() if d.is_dir()
                 for m in [load_yaml(d / "metadata.yaml")] if m and m.get("externalUrl")} \
        if RESOURCES_DIR.is_dir() else set()
    overlap = published & set(urls)
    if overlap:
        urls = [u for u in urls if u not in overlap]
        print(f"公開済みリソースと同じ URL のため {len(overlap)} 件をスキップ")
    if args.limit:
        urls = urls[:args.limit]

    digest_path = PROJECT_ROOT / ".cache" / f"{args.site}_digest.jsonl"
    stats = {"created": 0, "exists": 0, "no_cache": 0, "parse_failed": 0, "no_slug": 0,
             "boilerplate_dropped": 0}

    # 1周目: 全ページを解析し、サイト内で繰り返す引用文＝定型文を洗い出す
    # (パーサ個別のルールでは拾いきれない案内文を頻度で落とす。extract.py と同じ原理)
    parsed_all = {}
    for url in urls:
        slug = slugger(url)
        cache_path = cache_path_for(url) if slug else None
        if not slug or not cache_path.exists():
            continue
        parsed = module.parse_course(cache_path.read_text(encoding="utf-8", errors="ignore"), url)
        if parsed:
            parsed_all[url] = (slug, parsed)
    quoted_counts = collections.Counter(
        re.sub(r"\s+", "", p["quoted"])[:200] for _s, p in parsed_all.values() if p.get("quoted"))
    boilerplate = {key for key, n in quoted_counts.items() if n >= 3}
    if boilerplate:
        print(f"サイト内で繰り返す引用文 {len(boilerplate)} 種を定型文として除外")

    # 2周目: 下書きを書き出す
    with open(digest_path, "w", encoding="utf-8") as digest:
        for url in urls:
            slug = slugger(url)
            if not slug:
                stats["no_slug"] += 1
                continue
            cache_path = cache_path_for(url)
            if not cache_path.exists():
                stats["no_cache"] += 1
                continue
            draft_dir = DRAFTS_DIR / slug
            if (draft_dir / "metadata.yaml").exists() and not args.overwrite:
                stats["exists"] += 1
                continue
            if url not in parsed_all:
                stats["parse_failed"] += 1
                print(f"  ! parse失敗: {url}")
                continue
            _slug, parsed = parsed_all[url]

            if parsed.get("quoted") and re.sub(r"\s+", "", parsed["quoted"])[:200] in boilerplate:
                parsed = dict(parsed, quoted="", quoted_labels=[])
                stats["boilerplate_dropped"] += 1

            meta = build_metadata(parsed, url, site, slug, today)
            draft_dir.mkdir(parents=True, exist_ok=True)
            body = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100)
            (draft_dir / "metadata.yaml").write_text(HEADER + body, encoding="utf-8")
            stats["created"] += 1

            digest.write(json.dumps({
                "slug": slug, "name": parsed["name_ja"], "faculty": parsed.get("faculty"),
                "year": parsed.get("year"), "level": parsed.get("educationalLevel"),
                "materials": len(parsed.get("materials") or []),
                "quoted": (parsed.get("quoted") or "")[:300],
            }, ensure_ascii=False) + "\n")

    print(f"生成 {stats['created']} / 既存スキップ {stats['exists']} / キャッシュ無し {stats['no_cache']} "
          f"/ parse失敗 {stats['parse_failed']} / URL形式外 {stats['no_slug']} "
          f"/ 定型文として引用を除外 {stats['boilerplate_dropped']}")
    print(f"ダイジェスト → {digest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
