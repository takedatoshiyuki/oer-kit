#!/usr/bin/env python3
"""ページ取得 (キャッシュ付き)。取得層の正本 common_knowledge.web を使う。

- キャッシュ: .cache/pages/<ホスト>/<パス>/ に保存 (旧 libwebpage.py の方式を整理)
- エンジン: auto = common_knowledge.web (Playwright) が使えればそれ、無ければ requests
- 取得履歴を .cache/access_log.tsv に記録する (dateAccessed の根拠)

使い方:
    python3 tools/fetch.py <url> [--engine auto|requests|playwright] [--force]

備考: Playwright は genai-activities 環境に入っている。JSレンダリングが要る場合:
    ~/Dropbox/Projects/genai_activities/.venv/bin/python3 tools/fetch.py <url>
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from common import CACHE_DIR, add_lib_paths, load_config

PAGES_DIR = CACHE_DIR / "pages"
ACCESS_LOG = CACHE_DIR / "access_log.tsv"


def _safe_segment(segment: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]", "_", segment)
    return segment.strip(".") or "_"


def cache_path_for(url: str) -> Path:
    parsed = urlparse(url, allow_fragments=False)
    segments = [s for s in parsed.path.split("/") if s]
    if segments and re.search(r"\.html?$", segments[-1]):
        filename = segments.pop()
    elif parsed.query:
        filename = f"{parsed.query}.html"
    else:
        filename = "index.html"
    parts = [_safe_segment(s) for s in [parsed.netloc, *segments, filename]]
    return PAGES_DIR.joinpath(*parts)


def _log_access(url: str, engine: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(ACCESS_LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.date.today().isoformat()}\t{engine}\t{url}\n")


def fetch_html(url: str, engine: str = "auto", force: bool = False,
               config: dict | None = None) -> tuple[str, bool]:
    """HTML を返す。戻り値は (html, キャッシュヒットしたか)。"""
    config = config or load_config()
    cache_path = cache_path_for(url)
    if cache_path.exists() and not force:
        return cache_path.read_text(encoding="utf-8"), True

    user_agent = config["crawler"]["user_agent"]
    html = None
    if engine in ("auto", "playwright"):
        try:
            add_lib_paths(config)
            from common_knowledge.web import render_html
            html = render_html(url, user_agent=user_agent)
        except Exception as error:
            if engine == "playwright":
                raise
            print(f"note: Playwright 不可のため requests へフォールバック ({type(error).__name__})",
                  file=sys.stderr)
    if html is None:
        r = requests.get(url, headers={"User-Agent": user_agent}, timeout=60)
        r.raise_for_status()
        html = r.text

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    _log_access(url, engine)
    return html, False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--engine", choices=["auto", "requests", "playwright"], default="auto")
    parser.add_argument("--force", action="store_true", help="キャッシュを無視して再取得")
    args = parser.parse_args()

    html, hit = fetch_html(args.url, engine=args.engine, force=args.force)
    cache_path = cache_path_for(args.url)
    print(f"{'cache' if hit else 'fetched'}: {len(html)} chars → {cache_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
