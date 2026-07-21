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

from common import SITE_DIR, iter_resources, load_all_vocabs, load_config
from jsonld import build_jsonld


def main() -> int:
    config = load_config()
    vocabs = load_all_vocabs(config)

    docs = []
    entries = []  # (page_url, lastmod)
    jsonld_dir = SITE_DIR / "jsonld"
    jsonld_dir.mkdir(parents=True, exist_ok=True)

    for slug, _resource_dir, meta in iter_resources():
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

    print(f"{len(docs)} 件 → {catalog_path}, {jsonld_dir}/ / {sitemap_note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
