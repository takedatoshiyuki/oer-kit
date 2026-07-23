#!/usr/bin/env python3
"""metadata.yaml → schema.org/AMB 準拠 JSON-LD の生成 (docs/design.md §5.6)。

短縮記法 (SPDXライセンスID・語彙キー・素のORCID/ROR) を完全な URI へ展開する。
hosted は自リポジトリURLを id に、referenced は externalUrl を id にする。

使い方:
    python3 tools/jsonld.py --print <slug>   # 1件を標準出力へ
    python3 tools/jsonld.py                  # 全件を _site/jsonld/<slug>.json へ
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urljoin

from common import (
    SITE_DIR,
    expand_license,
    iter_resources,
    load_all_vocabs,
    load_config,
    localized,
    orcid_url,
    ror_url,
)

AMB_CONTEXT = "https://w3id.org/kim/amb/context.jsonld"


def concept(value, vocab):
    """語彙キー or {id, prefLabel} → AMB 概念オブジェクト。"""
    if isinstance(value, str):
        c = vocab[value]
        return {"id": c["id"], "prefLabel": c["prefLabel"]}
    out = {"id": value["id"]}
    if "prefLabel" in value:
        out["prefLabel"] = value["prefLabel"]
    return out


def text_or_concept(value):
    """自由文 → {name}, 概念参照 → {id, prefLabel}。"""
    if isinstance(value, str):
        return {"name": value}
    out = {"id": value["id"]}
    if "prefLabel" in value:
        out["prefLabel"] = value["prefLabel"]
    return out


def agent(a, lang):
    out = {"type": a.get("type", "Person"), "name": localized(a["name"], lang)}
    if a.get("orcid"):
        out["id"] = orcid_url(a["orcid"])
    elif a.get("ror"):
        out["id"] = ror_url(a["ror"])
    if a.get("url"):
        out["url"] = a["url"]
    affiliation = a.get("affiliation")
    if affiliation:
        org = {"type": "Organization", "name": localized(affiliation["name"], lang)}
        if affiliation.get("ror"):
            org["id"] = ror_url(affiliation["ror"])
        out["affiliation"] = org
    return out


def curriculum_teaches(align):
    """学習指導要領コード → teaches 概念 (URI があれば概念参照、なければ表示名)。"""
    label = align.get("label", "")
    if align.get("uri"):
        return {"id": align["uri"], "prefLabel": {"ja": label or align["code"]}}
    name = f"学習指導要領コード {align['code']}"
    if label:
        name += f"（{label}）"
    return {"name": name}


def build_jsonld(slug, meta, config, vocabs):
    lang = meta["inLanguage"][0]
    mode = meta.get("mode", "hosted")
    page_url = f"{config['base_url']}/r/{slug}"
    resource_id = meta["externalUrl"] if mode == "referenced" else page_url

    doc = {
        "@context": [AMB_CONTEXT, {"@language": lang}],
        "id": resource_id,
        "type": meta.get("type", ["LearningResource"]),
        "name": localized(meta["name"], lang),
        "description": localized(meta["description"], lang),
    }
    if meta.get("alternateName"):
        doc["alternateName"] = localized(meta["alternateName"], lang)
    doc["inLanguage"] = meta["inLanguage"]
    if meta.get("license"):
        doc["license"] = {"id": expand_license(meta["license"])}
    if meta.get("usageTerms"):
        terms = meta["usageTerms"]
        doc["usageInfo"] = {"id": terms["url"], "description": localized(terms["summary"], lang)}
    # quotedDescription (出典からの転載・引用文) は CC0 エクスポートに含めない (§7.3)。
    # ページ表示のみ prerender が行う。

    for field in ("creator", "contributor", "publisher", "funder"):
        if meta.get(field):
            doc[field] = [agent(a, lang) for a in meta[field]]

    for field in ("datePublished", "dateModified", "version", "interactivityType",
                  "timeRequired", "duration", "conditionsOfAccess"):
        if meta.get(field):
            doc[field] = meta[field]

    for field in ("learningResourceType", "about", "audience", "educationalLevel"):
        if meta.get(field):
            doc[field] = [concept(v, vocabs[field]) for v in meta[field]]

    if meta.get("keywords"):
        doc["keywords"] = meta["keywords"]

    teaches = [text_or_concept(v) for v in meta.get("teaches", [])]
    teaches += [curriculum_teaches(a) for a in meta.get("curriculumAlignment", [])]
    if teaches:
        doc["teaches"] = teaches
    for field in ("assesses", "competencyRequired", "educationalUse"):
        if meta.get(field):
            doc[field] = [text_or_concept(v) for v in meta[field]]

    if meta.get("image"):
        image = meta["image"]
        doc["image"] = image if image.startswith("http") else urljoin(f"{resource_id}/", image)

    for field in ("isBasedOn", "isPartOf", "hasPart", "sameAs"):
        if meta.get(field):
            doc[field] = meta[field]

    # materials (ファイルマニフェスト) は hasPart の CreativeWork として出力する
    if meta.get("materials"):
        import mimetypes
        parts = []
        for material in meta["materials"]:
            url = material["contentUrl"]
            if not url.startswith("http"):
                url = urljoin(f"{resource_id}/", url)
            media = {"type": "MediaObject", "contentUrl": url}
            fmt = material.get("format") or mimetypes.guess_type(url)[0]
            if fmt:
                media["encodingFormat"] = fmt
            parts.append({"type": "CreativeWork", "name": material["name"], "encoding": [media]})
        doc["hasPart"] = doc.get("hasPart", []) + parts

    if meta.get("encoding"):
        doc["encoding"] = []
        for enc in meta["encoding"]:
            item = {"type": "MediaObject", "encodingFormat": enc["format"]}
            if enc.get("contentUrl"):
                url = enc["contentUrl"]
                item["contentUrl"] = url if url.startswith("http") else urljoin(f"{resource_id}/", url)
            doc["encoding"].append(item)

    a11y = meta.get("accessibility", {})
    if a11y.get("accessMode"):
        doc["accessMode"] = a11y["accessMode"]
    if a11y.get("accessModeSufficient"):
        doc["accessModeSufficient"] = [
            {"type": "ItemList", "itemListElement": combo}
            for combo in a11y["accessModeSufficient"]
        ]
    for field in ("accessibilityFeature", "accessibilityHazard"):
        if a11y.get(field):
            doc[field] = a11y[field]
    if a11y.get("accessibilitySummary"):
        doc["accessibilitySummary"] = localized(a11y["accessibilitySummary"], lang)

    if meta.get("attributions"):
        doc["citation"] = []
        for att in meta["attributions"]:
            item = {"type": "CreativeWork", "name": att["title"]}
            if att.get("author"):
                item["author"] = att["author"]
            if att.get("source"):
                item["url"] = att["source"]
            if att.get("license"):
                item["license"] = expand_license(att["license"])
            doc["citation"].append(item)

    if meta.get("archivedAt"):
        doc["archivedAt"] = meta["archivedAt"]

    doc["isAccessibleForFree"] = True

    # メタデータレコード自体の情報 (目録ページ・提供者・更新日)
    provenance = meta.get("metadataProvenance", {})
    record = {
        "id": page_url,
        "provider": {"type": "Organization", "name": config["site_name"]},
    }
    record_date = provenance.get("generatedDate") or meta.get("dateModified") or meta.get("datePublished")
    if record_date:
        record["dateModified"] = record_date
    # メタデータの作成来歴を機械可読にする。description が AI 生成であることを
    # 取り込み側 (LMS-NG・アグリゲータ) が判別できるようにするため
    if provenance.get("method") in ("ai_generated", "ai_assisted"):
        creator = {"type": "SoftwareApplication"}
        if provenance.get("generator"):
            creator["name"] = provenance["generator"]
        record["creator"] = creator
        parts = ["description は AI 生成"]
        if provenance.get("confidence") == "low":
            parts.append("確からしさ: 低（要確認）")
        if provenance.get("reviewedBy"):
            parts.append(f"レビュー済み: {'、'.join(provenance['reviewedBy'])}")
        record["description"] = "。".join(parts)
    doc["mainEntityOfPage"] = [record]

    return doc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*", help="対象 slug (省略時は全件)")
    parser.add_argument("--print", dest="print_only", action="store_true",
                        help="ファイルに書かず標準出力へ")
    args = parser.parse_args()

    config = load_config()
    vocabs = load_all_vocabs(config)

    paths = None
    if args.slugs:
        from common import RESOURCES_DIR
        paths = [RESOURCES_DIR / s for s in args.slugs]

    out_dir = SITE_DIR / "jsonld"
    written = []
    for slug, _resource_dir, meta in iter_resources(paths):
        doc = build_jsonld(slug, meta, config, vocabs)
        if args.print_only:
            print(json.dumps(doc, ensure_ascii=False, indent=2))
        else:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{slug}.json"
            out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
            written.append(out_path)
    for p in written:
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
