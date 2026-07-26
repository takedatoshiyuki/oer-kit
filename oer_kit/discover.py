#!/usr/bin/env python3
"""サイトの sitemap から URL を列挙する (旧 parsers/ocw_kyoto_u.py から汎用化)。

robots.txt の Sitemap: 行 → 無ければ /sitemap.xml を起点に、
sitemapindex を再帰的にたどって URL を列挙する。

使い方:
    python3 tools/discover.py https://ocw.kyoto-u.ac.jp/ [--limit 100] [--out urls.tsv]
"""

from __future__ import annotations

import argparse
import sys
import time
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests

from .common import load_config


def robots_sitemaps(site_url: str, session: requests.Session) -> list[str]:
    robots_url = urljoin(site_url, "/robots.txt")
    sitemaps = []
    try:
        r = session.get(robots_url, timeout=30)
        if r.ok:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemaps.append(line.split(":", 1)[1].strip())
    except requests.RequestException:
        pass
    return sitemaps or [urljoin(site_url, "/sitemap.xml")]


def iter_sitemap(sitemap_url: str, session: requests.Session, sleep_seconds: float,
                 seen: set[str]):
    """sitemap (urlset / sitemapindex) を再帰的にたどり URL を yield する。"""
    if sitemap_url in seen:
        return
    seen.add(sitemap_url)
    try:
        r = session.get(sitemap_url, timeout=30)
        r.raise_for_status()
        root = ElementTree.fromstring(r.content)
    except (requests.RequestException, ElementTree.ParseError) as error:
        print(f"warn: {sitemap_url}: {error}", file=sys.stderr)
        return
    time.sleep(sleep_seconds)

    tag = root.tag.rsplit("}", 1)[-1]
    locs = [el.text.strip() for el in root.iter()
            if el.tag.rsplit("}", 1)[-1] == "loc" and el.text]
    if tag == "sitemapindex":
        for sub in locs:
            yield from iter_sitemap(sub, session, sleep_seconds, seen)
    else:
        yield from locs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_url", help="サイトのトップ URL")
    parser.add_argument("--limit", type=int, default=0, help="列挙する最大件数 (0=無制限)")
    parser.add_argument("--out", help="TSV 出力先 (省略時は標準出力)")
    args = parser.parse_args()

    config = load_config()
    session = requests.Session()
    session.headers["User-Agent"] = config["crawler"]["user_agent"]
    sleep_seconds = config["crawler"]["sleep_seconds"]

    sitemaps = robots_sitemaps(args.site_url, session)
    print(f"sitemap: {sitemaps}", file=sys.stderr)

    urls = []
    seen: set[str] = set()
    for sitemap_url in sitemaps:
        for url in iter_sitemap(sitemap_url, session, sleep_seconds, seen):
            urls.append(url)
            if args.limit and len(urls) >= args.limit:
                break
        if args.limit and len(urls) >= args.limit:
            break

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write("url\n")
            f.writelines(u + "\n" for u in urls)
        print(f"{len(urls)} 件 → {args.out}", file=sys.stderr)
    else:
        for u in urls:
            print(u)
    return 0


if __name__ == "__main__":
    sys.exit(main())
