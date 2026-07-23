#!/usr/bin/env python3
"""レビュー支援ビューの生成（docs/review-checklist.md）。

413件を1件ずつ精読するのは現実的でないので、**機械が確認済みの項目は載せず**、
人にしか判断できないものだけを一覧にする。並べて見ることで、1件ずつでは分からない
「部局に対して主題分野の推定が妥当か」を面で判断できる。

出す情報:
- 優先度（confidence=low → 引用文なし → 通常）
- 部局・年度と、それに対する about / educationalLevel の機械推定
- description と引用文（丸写しでないかの最終確認。機械検査は通過済み）
- 原ページへのリンク

チェックした slug をコピーして tools/approve.py に渡すと承認できる。

使い方:
    python3 tools/review_sheet.py [--out .cache/review.html] [--open]
"""

from __future__ import annotations

import argparse
import collections
import html
import subprocess
import sys
from pathlib import Path

from common import CACHE_DIR, REPO_ROOT, iter_resources, load_all_vocabs, load_config, localized


def gather(paths=None):
    rows = []
    for slug, directory, meta in iter_resources(paths):
        meta = meta or {}
        provenance = meta.get("metadataProvenance", {})
        quoted = (meta.get("quotedDescription") or {}).get("text")
        quoted_text = ""
        if quoted:
            quoted_text = quoted if isinstance(quoted, str) else next(iter(quoted.values()))
        ext = meta.get("extensions") or {}
        low = "confidence=low" in provenance.get("notes", "")
        rows.append({
            "slug": slug,
            "name": localized(meta.get("name"), "ja") or "",
            "faculty": ext.get("faculty", ""),
            "target": ext.get("targetAudience", ""),
            "year": str(meta.get("datePublished", "")),
            "about": "、".join(meta.get("about") or []),
            "level": "、".join(meta.get("educationalLevel") or []),
            "lrt": "、".join(meta.get("learningResourceType") or []),
            "description": localized(meta.get("description"), "ja") or "",
            "quoted": quoted_text,
            "materials": len(meta.get("materials") or []),
            "url": meta.get("externalUrl", ""),
            "reviewed": bool(provenance.get("reviewedBy")),
            "priority": 0 if low else (1 if not quoted_text else 2),
            "flag": "低信頼" if low else ("引用なし" if not quoted_text else ""),
        })
    rows.sort(key=lambda r: (r["priority"], r["slug"]))
    return rows


def render(rows, config, vocabs) -> str:
    subject_labels = {k: localized(v["prefLabel"], "ja") for k, v in vocabs["about"].items()}
    level_labels = {k: localized(v["prefLabel"], "ja") for k, v in vocabs["educationalLevel"].items()}

    # 部局 × 主題分野の対応表（機械推定の妥当性を面で確認する）
    matrix = collections.defaultdict(collections.Counter)
    for r in rows:
        matrix[r["faculty"] or "(不明)"][r["about"] or "(なし)"] += 1
    matrix_rows = []
    for faculty, counter in sorted(matrix.items(), key=lambda x: -sum(x[1].values())):
        cells = "、".join(f"{subject_labels.get(k, k)} {n}" for k, n in counter.most_common())
        matrix_rows.append(f"<tr><td>{html.escape(faculty)}</td>"
                           f"<td>{sum(counter.values())}</td><td>{html.escape(cells)}</td></tr>")

    body = []
    for r in rows:
        flag = (f'<span class="flag">{r["flag"]}</span>' if r["flag"] else "")
        quoted = html.escape(r["quoted"][:300]) + ("…" if len(r["quoted"]) > 300 else "")
        body.append(f"""<tr data-slug="{html.escape(r['slug'])}" data-flag="{html.escape(r['flag'])}"
 data-faculty="{html.escape(r['faculty'])}"{' class="reviewed"' if r["reviewed"] else ""}>
<td><input type="checkbox" class="pick" {"checked disabled" if r["reviewed"] else ""}></td>
<td class="slug"><a href="{html.escape(r['url'])}" target="_blank" rel="noopener">{html.escape(r['slug'].replace('nagoya-u-course-', '#'))}</a>{flag}</td>
<td><b>{html.escape(r['name'])}</b><div class="meta">{html.escape(r['faculty'])} / {html.escape(r['year'])}年
 / 教材{r['materials']}件{' / ' + html.escape(r['target'][:40]) if r['target'] else ''}</div></td>
<td class="cls">{html.escape(subject_labels.get(r['about'], r['about']))}<br>
<span class="meta">{html.escape(level_labels.get(r['level'], r['level']))}</span></td>
<td class="desc">{html.escape(r['description'])}</td>
<td class="quote">{quoted or '<span class="meta">（引用文なし）</span>'}</td>
</tr>""")

    unreviewed = sum(1 for r in rows if not r["reviewed"])
    return f"""<!doctype html>
<meta charset="utf-8"><title>レビュー — {config['site_name']}</title>
<style>
body{{font-family:system-ui,"Hiragino Sans",sans-serif;margin:1.5rem;color:#222;line-height:1.5}}
h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:2rem}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid #ddd;padding:.5rem;vertical-align:top;text-align:left}}
th{{position:sticky;top:0;background:#f6f6f6;z-index:1}}
.meta{{color:#777;font-size:11.5px}}
.slug{{white-space:nowrap;font-variant-numeric:tabular-nums}}
.desc{{width:32%}} .quote{{width:26%;color:#555;background:#fafafa}}
.cls{{white-space:nowrap}}
.flag{{display:inline-block;margin-left:.4rem;padding:0 .35rem;border-radius:3px;
 background:#fde8c8;color:#8a4b00;font-size:11px}}
tr.reviewed{{opacity:.45}}
#bar{{position:sticky;top:0;background:#fff;padding:.6rem 0;border-bottom:2px solid #333;z-index:2}}
button{{padding:.4rem .8rem;margin-right:.5rem;cursor:pointer}}
#out{{width:100%;height:5rem;font-family:ui-monospace,monospace;font-size:12px;margin-top:.5rem}}
.note{{background:#f0f6ff;border-left:3px solid #4a7;padding:.6rem .8rem;margin:1rem 0}}
</style>
<h1>メタデータ・レビュー — {len(rows)}件（未承認 {unreviewed}件）</h1>

<div class="note">
機械で確認済みのもの（<b>載せていない</b>）: 必須項目・型・語彙キー、引用文が原文のままか、
description が引用の丸写しでないか、リポジトリ横断の重複、リンク生存。<br>
<b>ここで見るのは</b>: ①事実の取り違え ②主題分野・教育段階の推定が部局に対して妥当か
③description が自分の言葉になっているか。判断は
<a href="../docs/review-checklist.md">docs/review-checklist.md</a>。
</div>

<h2>部局 × 主題分野の推定（面で妥当性を確認する）</h2>
<table><tr><th>開講部局</th><th>件数</th><th>推定された主題分野</th></tr>
{"".join(matrix_rows)}</table>

<h2>個別レビュー</h2>
<div id="bar">
<button onclick="filter('')">すべて</button>
<button onclick="filter('低信頼')">低信頼のみ</button>
<button onclick="filter('引用なし')">引用なし</button>
<button onclick="pickAll()">表示中を全選択</button>
<button onclick="emit()">承認リストを出す</button>
<span id="count" class="meta"></span>
<textarea id="out" placeholder="ここに承認する slug が出ます。コピーして tools/approve.py に渡してください"></textarea>
</div>
<table>
<tr><th>承認</th><th>ID</th><th>講義</th><th>分類</th><th>description（CC0・自作要約）</th>
<th>引用文（原文・機械照合済み）</th></tr>
{"".join(body)}
</table>
<script>
const rows = () => [...document.querySelectorAll('tr[data-slug]')];
function filter(flag) {{
  rows().forEach(r => r.style.display =
    (!flag || r.dataset.flag === flag) ? '' : 'none');
  count();
}}
function pickAll() {{
  rows().filter(r => r.style.display !== 'none').forEach(r => {{
    const c = r.querySelector('.pick'); if (!c.disabled) c.checked = true;
  }});
  count();
}}
function emit() {{
  const picked = rows().filter(r => {{
    const c = r.querySelector('.pick'); return c.checked && !c.disabled;
  }}).map(r => r.dataset.slug);
  document.getElementById('out').value = picked.join(' ');
  count();
}}
function count() {{
  const n = rows().filter(r => {{
    const c = r.querySelector('.pick'); return c.checked && !c.disabled;
  }}).length;
  document.getElementById('count').textContent = `選択 ${{n}} 件`;
}}
document.addEventListener('change', e => {{ if (e.target.classList.contains('pick')) count(); }});
count();
</script>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="対象（省略時は drafts/ 全件）")
    parser.add_argument("--out", default=str(CACHE_DIR / "review.html"))
    parser.add_argument("--open", action="store_true", help="生成後にブラウザで開く")
    args = parser.parse_args()

    paths = [Path(p) for p in args.paths] if args.paths else \
        sorted(d for d in (REPO_ROOT / "drafts").iterdir() if d.is_dir())
    config = load_config()
    rows = gather(paths)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(rows, config, load_all_vocabs(config)), encoding="utf-8")
    print(f"{len(rows)} 件 → {out}")
    if args.open:
        subprocess.run(["open", str(out)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
