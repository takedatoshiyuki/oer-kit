#!/usr/bin/env python3
"""ページから説明文の候補を抽出する（`quotedDescription` の下ごしらえ）。

原文をそのまま採る作業なので LLM に書かせてはいけない（改変・幻覚が混じる）。
コードで候補を挙げ、選択だけを人／LLM に任せる。3段階で探す:

1. JSON-LD (schema.org の description)
2. og:description / meta description
   — ただしサイト共通のボイラープレート（「○○大学 OCW は…」等）は除外する。
     同一サイトの複数ページに同じ文が出たら定型文とみなす（--corpus で判定）
3. ラベル付きセクション（概要／講義の概要／授業の内容／Course Description …）

使い方:
    python tools/extract.py <html ファイル|URL>            # 候補を列挙
    python tools/extract.py <ファイル> --corpus <ディレクトリ>  # 定型文を除外して列挙
    python tools/extract.py --survey <ディレクトリ>          # コーパス全体の的中率を測る
"""

from __future__ import annotations

import argparse
import collections
import html as html_module
import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

MATERIAL_EXTENSIONS = ("pdf", "ppt", "pptx", "doc", "docx", "xls", "xlsx",
                       "zip", "ipynb", "csv", "tsv", "mp4", "mp3", "vtt", "srt")

# 説明文の見出しラベル（サイト間で表記がまちまちなので辞書で吸収する）
DESCRIPTION_LABELS = [
    "講義の概要", "授業の概要", "コース概要", "科目の概要", "講義概要", "授業概要",
    "授業のねらい", "講義目的", "授業の目的", "ねらい", "目的",
    "講義の内容", "授業の内容", "講義内容", "授業内容", "概要",
    "Course Description", "Course Summary", "Description", "Overview",
    "Abstract", "Summary", "Syllabus", "Aim", "Objectives",
]
# 上から順に優先（具体的なラベルほど説明文である確度が高い）
LABEL_PRIORITY = {label: i for i, label in enumerate(DESCRIPTION_LABELS)}

MIN_LENGTH = 30      # これ未満は説明文とみなさない
MAX_LINES = 8        # ラベル直後から拾う最大行数
BOILERPLATE_MIN_PAGES = 3   # 同一文がこの数以上のページに出たら定型文


def visible_lines(html: str) -> list[str]:
    body = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", html,
                  flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", "\n", body)
    text = html_module.unescape(text)
    return [l.strip() for l in text.splitlines() if l.strip()]


def from_jsonld(html: str):
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict):
                continue
            for graph_node in (node.get("@graph") or [node]):
                if not isinstance(graph_node, dict):
                    continue
                desc = graph_node.get("description")
                if isinstance(desc, str) and len(desc.strip()) >= MIN_LENGTH:
                    yield {"method": "jsonld", "label": graph_node.get("@type", ""),
                           "text": desc.strip()}


def from_meta(html: str):
    patterns = [
        ("og:description", r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']*)'),
        ("og:description", r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*property=["\']og:description'),
        ("meta description", r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']*)'),
    ]
    seen = set()
    for label, pattern in patterns:
        m = re.search(pattern, html, re.I)
        if m:
            text = html_module.unescape(m.group(1)).strip()
            if len(text) >= MIN_LENGTH and text not in seen:
                seen.add(text)
                yield {"method": "meta", "label": label, "text": text}


def from_labeled_section(html: str):
    lines = visible_lines(html)
    label_set = set(DESCRIPTION_LABELS)
    # 見出しになりうる短い行（次のラベルの手前で打ち切るため）
    for i, line in enumerate(lines):
        label = line.rstrip(":：").strip()
        if label not in label_set:
            continue
        collected = []
        for follow in lines[i + 1:i + 1 + MAX_LINES]:
            if follow.rstrip(":：").strip() in label_set:
                break
            if len(follow) < 8 and not collected:   # ラベル直後の短い装飾行は飛ばす
                continue
            if len(follow) < 8:
                break
            collected.append(follow)
        text = "\n".join(collected).strip()
        if len(text) >= MIN_LENGTH:
            yield {"method": "section", "label": label, "text": text}


def extract_candidates(html: str, boilerplate: set[str] | None = None):
    """候補を優先度順に返す。boilerplate に含まれる文は除外する。"""
    boilerplate = boilerplate or set()
    candidates = list(from_jsonld(html)) + list(from_meta(html)) + list(from_labeled_section(html))
    out, seen = [], set()
    for c in candidates:
        key = re.sub(r"\s+", "", c["text"])[:120]
        if key in seen:
            continue
        seen.add(key)
        c["boilerplate"] = key in boilerplate
        if not c["boilerplate"]:
            out.append(c)
    method_rank = {"jsonld": 0, "section": 1, "meta": 2}
    out.sort(key=lambda c: (method_rank[c["method"]],
                            LABEL_PRIORITY.get(c["label"], 99)))
    return out


def find_materials(html: str, base_url: str = ""):
    """ページ内の教材ファイルリンク (拡張子ベース) を {name, contentUrl} で列挙する。"""
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href = html_module.unescape(m.group(1))
        path = urlparse(href).path.lower()
        if not any(path.endswith(f".{ext}") for ext in MATERIAL_EXTENSIONS):
            continue
        url = urljoin(base_url, href) if base_url else href
        if url in seen:
            continue
        seen.add(url)
        label = re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        out.append({"name": label or Path(urlparse(url).path).name, "contentUrl": url})
    return out


def _page_label(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if not m:
        return ""
    title = html_module.unescape(m.group(1))
    return re.split(r"[|｜–—]", title)[0].strip()[:60]


def collect_materials(start_url: str, follow: str | None = None, max_pages: int = 30):
    """コースページから各回ページ (深さ1) をたどって教材ファイルを集める。

    名大のように1ページ完結のサイトはそのまま、京大 (?video_id=N) や
    UTokyo Channel (/content/?id=) のように各回が別ページのサイトは
    follow (正規表現) か既定規則 (コースURL配下のリンク) でたどる。
    取得は fetch.fetch_html 経由なのでキャッシュ・礼儀間隔・UA は共通。
    戻り値の各要素には由来ページを page として付す。
    """
    import time
    from .fetch import fetch_html
    from .common import load_config

    sleep_seconds = load_config()["crawler"]["sleep_seconds"]
    html, hit = fetch_html(start_url)
    materials = [dict(m, page=start_url) for m in find_materials(html, start_url)]

    prefix = start_url.rstrip("/")
    sub_urls = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"', html, re.I):
        url = urljoin(start_url, html_module.unescape(m.group(1))).split("#")[0]
        if url == start_url or url in sub_urls:
            continue
        if urlparse(url).netloc != urlparse(start_url).netloc:
            continue
        if follow:
            if not re.search(follow, url):
                continue
        elif not url.rstrip("/").startswith(prefix):
            continue
        sub_urls.append(url)

    for url in sub_urls[:max_pages]:
        sub_html, hit = fetch_html(url)
        if not hit:
            time.sleep(sleep_seconds)
        label = _page_label(sub_html)
        for m in find_materials(sub_html, url):
            name = f"{label} — {m['name']}" if label and label not in m["name"] else m["name"]
            materials.append({"name": name, "contentUrl": m["contentUrl"], "page": url})

    seen, out = set(), []
    for m in materials:
        if m["contentUrl"] in seen:
            continue
        seen.add(m["contentUrl"])
        out.append(m)
    return out, len(sub_urls[:max_pages])


def find_boilerplate(paths) -> set[str]:
    """同一サイト内で繰り返し出る文＝定型文のキー集合を返す。"""
    counter = collections.Counter()
    for path in paths:
        try:
            html = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for c in list(from_meta(html)) + list(from_jsonld(html)):
            counter[re.sub(r"\s+", "", c["text"])[:120]] += 1
    return {key for key, n in counter.items() if n >= BOILERPLATE_MIN_PAGES}


def survey(root: Path):
    """コーパスに対する抽出の的中率を測る（ホスト別）。"""
    print(f"{'host':26} {'pages':>6} {'JSON-LD':>8} {'meta有':>7} {'定型':>6} {'節':>5} {'有効':>6}")
    for host_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        files = list(host_dir.rglob("*.html"))
        if len(files) < 3:
            continue
        boilerplate = find_boilerplate(files)
        stats = collections.Counter()
        for path in files:
            html = path.read_text(encoding="utf-8", errors="ignore")
            raw_meta = list(from_meta(html))
            if list(from_jsonld(html)):
                stats["jsonld"] += 1
            if raw_meta:
                stats["meta"] += 1
            if raw_meta and all(re.sub(r"\s+", "", c["text"])[:120] in boilerplate for c in raw_meta):
                stats["boiler"] += 1
            if list(from_labeled_section(html)):
                stats["section"] += 1
            if extract_candidates(html, boilerplate):
                stats["ok"] += 1
        n = len(files)
        print(f"{host_dir.name:26} {n:>6} {stats['jsonld']:>8} {stats['meta']:>7} "
              f"{stats['boiler']:>6} {stats['section']:>5} {stats['ok']:>5} "
              f"({stats['ok']*100//n}%)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", help="HTML ファイルまたは URL")
    parser.add_argument("--corpus", help="定型文判定に使う同一サイトのディレクトリ")
    parser.add_argument("--survey", help="コーパス全体の的中率を測る")
    parser.add_argument("--materials", action="store_true",
                        help="説明文でなく教材ファイルリンクを抽出し、metadata.yaml に貼れる YAML で出す")
    parser.add_argument("--base-url", default="", help="--materials 時の相対URL解決に使う")
    parser.add_argument("--follow", nargs="?", const="", default=None, metavar="REGEX",
                        help="各回ページ (深さ1) もたどる。正規表現省略時はコースURL配下を各回とみなす")
    parser.add_argument("--max-pages", type=int, default=30, help="--follow 時にたどる最大ページ数")
    args = parser.parse_args()

    if args.survey:
        survey(Path(args.survey))
        return 0
    if not args.target:
        parser.error("HTML ファイル／URL か --survey を指定")

    if args.target.startswith("http"):
        from .fetch import fetch_html
        html, _hit = fetch_html(args.target)
        base_url = args.base_url or args.target
    else:
        html = Path(args.target).read_text(encoding="utf-8", errors="ignore")
        base_url = args.base_url

    if args.materials:
        import yaml
        if args.follow is not None:
            if not args.target.startswith("http"):
                parser.error("--follow は URL 指定時のみ (各回ページの取得が必要)")
            materials, visited = collect_materials(args.target, follow=args.follow or None,
                                                   max_pages=args.max_pages)
            print(f"各回ページ {visited} 件を巡回", file=sys.stderr)
        else:
            materials = find_materials(html, base_url)
        if not materials:
            print("教材ファイルリンクなし", file=sys.stderr)
            return 1
        print(yaml.safe_dump({"materials": materials}, allow_unicode=True,
                             sort_keys=False, width=120), end="")
        return 0

    boilerplate = find_boilerplate(Path(args.corpus).rglob("*.html")) if args.corpus else set()
    candidates = extract_candidates(html, boilerplate)
    if not candidates:
        print("候補なし（ラベル辞書に無い構造か、定型文のみ）", file=sys.stderr)
        return 1
    for i, c in enumerate(candidates, 1):
        print(f"--- 候補{i} [{c['method']}] {c['label']}")
        print(c["text"][:400] + ("…" if len(c["text"]) > 400 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
