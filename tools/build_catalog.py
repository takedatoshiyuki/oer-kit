#!/usr/bin/env python3
"""catalog.json と sitemap.xml の生成 (docs/design.md §8.1)。

- _site/jsonld/<slug>.json  各リソースの JSON-LD
- _site/catalog.json        全リソースの JSON-LD を束ねた一括ハーベスト用ファイル
- _site/sitemap.xml         目録ページの URL 一覧

使い方:
    python3 tools/build_catalog.py
"""

from __future__ import annotations

import datetime
import json
import sys
from xml.sax.saxutils import escape

import re

from common import SITE_DIR, iter_resources, load_all_vocabs, load_config, localized
from jsonld import build_jsonld


def enrich_search_index(metas) -> int:
    """Quarto の検索インデックスに description 等を足す。

    Quarto は見出し単位で索引を作り、front matter の description（タイトル直下の
    リード文）は索引に入らない。表示を重複させずに検索性を上げるため、ビルド後に
    各リソースの冒頭エントリへ description・別名・著者・主題キーを追記する。
    """
    path = SITE_DIR / "search.json"
    if not path.exists():
        return 0
    index = json.loads(path.read_text(encoding="utf-8"))
    enriched = 0
    for entry in index:
        if entry.get("section"):
            continue
        found = re.search(r"(?:^|/)r/([^/]+)/", entry.get("href", ""))
        meta = metas.get(found.group(1)) if found else None
        if not meta:
            continue
        lang = (meta.get("inLanguage") or ["ja"])[0]
        extra = [localized(meta.get("description"), lang) or "",
                 localized(meta.get("alternateName"), lang) or ""]
        extra += [localized(a["name"], lang) for a in meta.get("creator", [])]
        extra += [t for t in meta.get("teaches", []) if isinstance(t, str)]
        addition = " ".join(x for x in extra if x)
        if addition:
            entry["text"] = (entry.get("text", "") + " " + addition).strip()
            enriched += 1
    path.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    return enriched


def main() -> int:
    config = load_config()
    vocabs = load_all_vocabs(config)

    docs = []
    entries = []  # (page_url, lastmod)
    metas = {}
    jsonld_dir = SITE_DIR / "jsonld"
    jsonld_dir.mkdir(parents=True, exist_ok=True)

    for slug, _resource_dir, meta in iter_resources():
        metas[slug] = meta
        doc = build_jsonld(slug, meta, config, vocabs)
        (jsonld_dir / f"{slug}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        docs.append(doc)
        lastmod = meta.get("dateModified") or meta.get("datePublished")
        entries.append((f"{config['base_url']}/r/{slug}", lastmod))

    catalog = {
        "name": config["site_name"],
        "url": config["base_url"],
        "generatedAt": datetime.date.today().isoformat(),
        "resources": docs,
    }
    catalog_path = SITE_DIR / "catalog.json"
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")

    # sitemap.xml は Quarto (quarto render site) の生成物を優先し、無いときだけ作る
    sitemap_path = SITE_DIR / "sitemap.xml"
    if sitemap_path.exists():
        sitemap_note = "sitemap.xml は既存 (Quarto 生成) を維持"
    else:
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for page_url, lastmod in entries:
            lines.append("  <url>")
            lines.append(f"    <loc>{escape(page_url)}</loc>")
            if lastmod:
                lines.append(f"    <lastmod>{lastmod}</lastmod>")
            lines.append("  </url>")
        lines.append("</urlset>")
        sitemap_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        sitemap_note = f"sitemap: {sitemap_path}"

    enriched = enrich_search_index(metas)
    print(f"{len(docs)} 件 → {catalog_path}, {jsonld_dir}/ / {sitemap_note}"
          + (f" / 検索索引を補強 {enriched} 件" if enriched else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
