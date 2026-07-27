#!/usr/bin/env python3
"""重複検査に引っかかった群について、判断材料を1か所に集める。

`validate.py` の横断検査が「description が同一」と言うとき、直すべきなのは
個々の記述ではなく**抽出方法か生成指示**であることが多い（docs/review-checklist.md）。
その判断には「各リソースの出力」と「原ページから本来取れたはずの候補」を
並べて見る必要があるので、それを集めて Markdown で出す。

集めるのはコード、吟味するのは人／LLM という分担にしている。
出力をそのまま Claude 等に読ませて原因を特定し、直す先は
`extract.py` のラベル辞書・定型文しきい値か、生成プロンプト。

使い方:
    python tools/diagnose.py                    # 重複が出た群すべて
    python tools/diagnose.py --slugs a b c      # 指定した群だけ
    python tools/diagnose.py --out report.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .common import PROJECT_ROOT, iter_resources, localized
from .extract import extract_candidates, find_boilerplate
from .fetch import PAGES_DIR, cache_path_for
from .validate import check_duplicates


def _slugs_in(message: str) -> list[str]:
    m = re.search(r"\(([^)]+)\)", message)
    if not m:
        return []
    return [s.strip() for s in m.group(1).replace(" ほか", "").split(",") if s.strip()]


def all_entries():
    """resources/ と drafts/（レビュー前）の両方を対象にする。"""
    entries = [(slug, meta or {}) for slug, _d, meta in iter_resources()]
    drafts_dir = PROJECT_ROOT / "drafts"
    if drafts_dir.is_dir():
        draft_paths = sorted(d for d in drafts_dir.iterdir() if d.is_dir())
        entries += [(slug, meta or {}) for slug, _d, meta in iter_resources(draft_paths)]
    return entries


def gather_groups(target_slugs=None):
    """(見出し, [slug]) の群を返す。"""
    entries = all_entries()
    if target_slugs:
        return [("指定された群", list(target_slugs))], dict(entries)
    groups = []
    for level, message in check_duplicates(entries):
        slugs = _slugs_in(message)
        if len(slugs) > 1:
            groups.append((f"[{level}] {message.split(':')[0]}", slugs))
    return groups, dict(entries)


def candidates_for(meta):
    """原ページのキャッシュから、本来取れたはずの説明文候補を出す。"""
    url = meta.get("externalUrl")
    if not url:
        return None, []
    path = cache_path_for(url)
    if not path.exists():
        return path, []
    host_dir = PAGES_DIR / path.relative_to(PAGES_DIR).parts[0]
    boilerplate = find_boilerplate(host_dir.rglob("*.html"))
    html = path.read_text(encoding="utf-8", errors="ignore")
    # 定型文も「除外された事実」を見たいので、除外前後の両方を取る
    kept = extract_candidates(html, boilerplate)
    allc = extract_candidates(html, set())
    dropped = [c for c in allc if not any(c["text"] == k["text"] for k in kept)]
    return path, kept + [dict(c, boilerplate=True) for c in dropped]


def render(groups, metas) -> str:
    out = ["# 重複の原因調査", "",
           "`validate.py` の横断検査で重複と判定された群について、各リソースの出力と",
           "原ページから抽出できる候補を並べたもの。", "",
           "## 判断してほしいこと", "",
           "1. 並んでいる `description` は、原ページの内容を反映しているか。",
           "   サイト共通の定型文（「○○大学 OCW は…」）を掴んでいないか",
           "2. 掴んでいる場合、正しい説明文は下の「抽出候補」のどれか。",
           "   どの手段（JSON-LD / meta / ラベル）で取れるか",
           "3. 直す先は `extract.py` のラベル辞書・定型文しきい値か、生成プロンプトか。",
           "   **個々の metadata.yaml を手直しするのは最後の手段**（原因が残るため）", ""]

    for heading, slugs in groups:
        out += [f"## {heading}", ""]
        for slug in slugs:
            meta = metas.get(slug)
            if meta is None:
                out += [f"### {slug}", "", "（リソースが見つからない）", ""]
                continue
            lang = (meta.get("inLanguage") or ["ja"])[0]
            out += [f"### {slug}", "",
                    f"- 外部URL: {meta.get('externalUrl', '(hosted)')}",
                    f"- タイトル: {localized(meta.get('name'), lang)}",
                    "", "**現在の description**", "",
                    f"> {localized(meta.get('description'), lang)}", ""]
            quoted = meta.get("quotedDescription")
            if quoted:
                text = quoted["text"]
                value = text if isinstance(text, str) else next(iter(text.values()))
                out += ["**現在の quotedDescription（引用）**", "",
                        f"> {value[:200]}{'…' if len(value) > 200 else ''}", ""]

            path, candidates = candidates_for(meta)
            if path is None:
                out += ["（externalUrl が無く、原ページを参照できない）", ""]
            elif not path.exists():
                out += [f"（キャッシュ無し: `tools/fetch.py {meta['externalUrl']}` で取得してから再実行）", ""]
            elif not candidates:
                out += ["**抽出候補**: なし",
                        "（原ページに説明文が存在しない可能性。その場合は自作 description を書くしかない）", ""]
            else:
                out += ["**原ページからの抽出候補**", ""]
                for i, c in enumerate(candidates, 1):
                    mark = "  ← 定型文として除外済み" if c.get("boilerplate") else ""
                    text = re.sub(r"\s+", " ", c["text"])
                    out += [f"{i}. `[{c['method']}] {c['label']}`{mark}",
                            f"   > {text[:180]}{'…' if len(text) > 180 else ''}", ""]
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slugs", nargs="+", help="調査する slug（省略時は重複検査の結果を使う）")
    parser.add_argument("--out", help="Markdown の出力先（省略時は標準出力）")
    args = parser.parse_args()

    groups, metas = gather_groups(args.slugs)
    if not groups:
        print("重複は検出されていない", file=sys.stderr)
        return 0
    report = render(groups, metas)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
        print(f"{len(groups)} 群 → {args.out}", file=sys.stderr)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
