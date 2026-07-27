#!/usr/bin/env python3
"""ページ取得 (キャッシュ付き)。取得層の正本 common_knowledge.web を使う。

- キャッシュ: .cache/pages/<ホスト>/<パス>/ に保存 (旧 libwebpage.py の方式を整理)
- エンジン: auto = common_knowledge.web (Playwright) が使えればそれ、無ければ requests
- 取得履歴を .cache/access_log.tsv に記録する (dateAccessed の根拠)

使い方:
    python tools/fetch.py <url> [--engine auto|requests|playwright] [--force]
    python tools/fetch.py --batch urls.tsv [--concurrency 2]   # 一括 (ブラウザ使い回し)

備考: Playwright は genai-activities 環境に入っている。JSレンダリングが要る場合:
    ~/Dropbox/Projects/genai_activities/.venv/bin/python tools/fetch.py <url>
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from .common import CACHE_DIR, add_lib_paths, load_config

PAGES_DIR = CACHE_DIR / "pages"
ACCESS_LOG = CACHE_DIR / "access_log.tsv"


def _safe_segment(segment: str) -> str:
    segment = re.sub(r"[^A-Za-z0-9._-]", "_", segment)
    segment = segment.strip(".") or "_"
    # パーセントエンコードされた日本語は膨らむ。macOS のパス要素上限 (255バイト) を避けつつ
    # 短縮ハッシュで一意性を保つ
    if len(segment) > 120:
        digest = hashlib.sha256(segment.encode()).hexdigest()[:12]
        segment = f"{segment[:100]}_{digest}"
    return segment


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
        # サーバが charset を明示しないと requests は ISO-8859-1 を仮定し、
        # 日本語ページが二重符号化で壊れる (九大 QOCW で実害) → 本文から推定する
        if "charset" not in (r.headers.get("Content-Type") or "").lower():
            r.encoding = r.apparent_encoding
        html = r.text

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8")
    _log_access(url, engine)
    return html, False


def batch_fetch(urls, engine="auto", force=False, concurrency=2,
                config: dict | None = None) -> int:
    """複数URLの一括取得。Playwright ではブラウザを使い回す (common_knowledge.web.render_pages)。

    キャッシュ済みは飛ばす (再開可能)。戻り値は失敗数。
    """
    config = config or load_config()
    todo = [u for u in urls if force or not cache_path_for(u).exists()]
    print(f"{len(urls)} URL 中 {len(urls) - len(todo)} 件はキャッシュ済み → {len(todo)} 件を取得",
          flush=True)
    if not todo:
        return 0

    failures = []

    if engine in ("auto", "playwright"):
        try:
            add_lib_paths(config)
            from common_knowledge.web import render_pages

            def save(index, url, info):
                # on_result 内の例外は render_pages 全体を落とすので、必ずここで握る
                try:
                    if info.get("error"):
                        failures.append(url)
                        print(f"  ! {url}: {info['error'][:100]}", flush=True)
                        return
                    cache_path = cache_path_for(url)
                    cache_path.parent.mkdir(parents=True, exist_ok=True)
                    cache_path.write_text(info["content"], encoding="utf-8")
                    _log_access(url, "playwright")
                except Exception as error:
                    failures.append(url)
                    print(f"  ! save {url}: {type(error).__name__}: {error}"[:150], flush=True)
                finally:
                    done = index + 1
                    if done % 20 == 0 or done == len(todo):
                        print(f"  {done}/{len(todo)}", flush=True)

            render_pages(todo, concurrency=concurrency,
                         sleep_seconds=config["crawler"]["sleep_seconds"],
                         retries=1, extra_wait=1.0,
                         user_agent=config["crawler"]["user_agent"],
                         on_result=save, keep_results=False)
            print(f"完了: 失敗 {len(failures)} 件", flush=True)
            return len(failures)
        except ImportError as error:
            if engine == "playwright":
                raise
            print(f"note: render_pages 不可のため逐次 requests ({error})", file=sys.stderr)

    for url in todo:
        try:
            fetch_html(url, engine="requests", force=force, config=config)
        except Exception as error:
            failures.append(url)
            print(f"  ! {url}: {type(error).__name__}", flush=True)
    print(f"完了: 失敗 {len(failures)} 件", flush=True)
    return len(failures)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?")
    parser.add_argument("--batch", help="URL一覧ファイル (1行1URL。ヘッダ行 'url' は無視)")
    parser.add_argument("--engine", choices=["auto", "requests", "playwright"], default="auto")
    parser.add_argument("--concurrency", type=int, default=2, help="--batch 時の並行数")
    parser.add_argument("--force", action="store_true", help="キャッシュを無視して再取得")
    args = parser.parse_args()

    if args.batch:
        urls = [l.strip() for l in open(args.batch, encoding="utf-8")
                if l.strip() and l.strip() != "url"]
        return 1 if batch_fetch(urls, engine=args.engine, force=args.force,
                                concurrency=args.concurrency) else 0

    if not args.url:
        parser.error("URL か --batch を指定")
    html, hit = fetch_html(args.url, engine=args.engine, force=args.force)
    cache_path = cache_path_for(args.url)
    print(f"{'cache' if hit else 'fetched'}: {len(html)} chars → {cache_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
