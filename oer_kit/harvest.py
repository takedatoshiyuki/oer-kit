#!/usr/bin/env python3
"""教材ファイルの収集 — コーパス層 (docs/design.md §7.4)。

カタログ (公開・メタデータCC0) とコーパス (取得ファイル・git外) を分離する
二層構成のコーパス側。resources/・drafts/ の `materials` を archive_dir へ
ダウンロードし、権利情報つきマニフェストを書く。

権利ゲート:
- usageTerms.reuse が not_allowed のリソース (視聴のみ。例: UTokyo Channel) は
  規約が複製 (ダウンロード) を禁止しているため取得しない
- 取得したファイルには license / usageTerms・クレジット素材を manifest に併記し、
  下流 (LLM 学習データ・LMS) が権利で絞り込めるようにする

使い方:
    python tools/harvest.py drafts/nagoya-u-course-0001 [--limit 2] [--force]
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import mimetypes
import re
import sys
import time
from pathlib import Path

import requests

from .common import PROJECT_ROOT, expand_license, iter_resources, load_config, localized


def archive_root(config) -> Path:
    root = Path(config.get("archive_dir", "archive")).expanduser()
    return root if root.is_absolute() else PROJECT_ROOT / root


def safe_filename(url: str) -> str:
    name = Path(url.split("?")[0]).name or "file"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)


def repair_candidates(url: str):
    """壊れたパーセントエンコードの復元候補を優先順に返す。

    名大の一部ページは、空白を含むファイル名のリンクのエンコードが崩れている
    (実測): `%20` が `20%25` / `20%` に化ける、`%25` のまま残る、など。
    例: `western20%25blot.pdf` → `western%20blot.pdf`
        `4_amino20%acids.pdf`  → `4_amino%20acids.pdf`
        `answers%25for%25HW.pdf` → `answers%20for%20HW.pdf`
    """
    seen = {url}
    for candidate in (re.sub(r"20%25", "%20", url),
                      re.sub(r"20%", "%20", url),
                      re.sub(r"%25", "%20", url),
                      re.sub(r"20%25", "%20", re.sub(r"%25", "%20", url))):
        if candidate not in seen:
            seen.add(candidate)
            yield candidate


def build_credit(meta, lang) -> str:
    """クレジット表示の素材 (例: © 2005 岩崎 雄吾（名古屋大学）)。書式はサイト要求に応じ調整。"""
    year = str(meta.get("datePublished", ""))[:4]
    creators = "、".join(localized(a["name"], lang) for a in meta.get("creator", []))
    publisher = "、".join(localized(p["name"], lang) for p in meta.get("publisher", []))
    parts = [p for p in (year, creators) if p]
    credit = "© " + " ".join(parts) if parts else ""
    return f"{credit}（{publisher}）" if publisher else credit


def download(url: str, dest: Path, session: requests.Session, timeout=120):
    r = session.get(url, timeout=timeout, stream=True)
    if r.status_code == 404:
        for candidate in repair_candidates(url):
            r2 = session.get(candidate, timeout=timeout, stream=True)
            if r2.ok:
                r = r2
                break
    r.raise_for_status()
    sha = hashlib.sha256()
    size = 0
    tmp = dest.with_suffix(dest.suffix + ".part")
    with open(tmp, "wb") as f:
        for chunk in r.iter_content(chunk_size=1 << 16):
            f.write(chunk)
            sha.update(chunk)
            size += len(chunk)
    head = tmp.read_bytes()[:5]
    type_mismatch = ""
    if dest.suffix.lower() == ".pdf" and not head.startswith(b"%PDF"):
        if head[:1] == b"<":
            # HTML が返っている = サインイン要求・エラーページ。保存しない
            tmp.unlink()
            raise ValueError("PDF でなく HTML が返された (サインイン要求・エラーページの可能性)")
        # PDF ではないが実体のあるファイル (拡張子の誤り)。保存して印を残す
        type_mismatch = f"拡張子は .pdf だが内容が異なる (先頭バイト {head.hex()})"
    tmp.rename(dest)
    return sha.hexdigest(), size, r.headers.get("Content-Type", ""), type_mismatch


def harvest_resource(slug, meta, config, session, limit=0, force=False):
    lang = (meta.get("inLanguage") or ["ja"])[0]
    materials = meta.get("materials") or []
    if not materials:
        print(f"[skip] {slug}: materials なし")
        return 0

    terms = meta.get("usageTerms") or {}
    if terms.get("reuse") in ("not_allowed", "unspecified"):
        reason = ("利用条件が複製を禁止 (not_allowed)" if terms["reuse"] == "not_allowed"
                  else "利用条件の記載がなく複製の許諾がない (unspecified)")
        print(f"[skip] {slug}: {reason} のため取得しない (§7.4)")
        return 0

    out_dir = archive_root(config) / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    rights = {}
    if meta.get("license"):
        rights["license"] = expand_license(meta["license"])
    if terms:
        rights["usageTerms"] = {"url": terms["url"], "reuse": terms["reuse"],
                                "summary": localized(terms["summary"], lang)}

    manifest = {
        "slug": slug,
        "source": meta.get("externalUrl"),
        "title": localized(meta.get("name"), lang),
        "rights": rights,
        "credit": build_credit(meta, lang),
        "harvestedAt": datetime.date.today().isoformat(),
        "files": [],
    }

    count = 0
    from .common import crawler_settings
    from .fetch import robots_allows
    user_agent, sleep_seconds = crawler_settings(config)
    for material in materials[: limit or len(materials)]:
        url = material["contentUrl"]
        dest = out_dir / safe_filename(url)
        entry = {"name": material["name"], "url": url, "file": dest.name}
        if not robots_allows(url, user_agent):
            entry["skipped"] = "robots.txt が許可していない"
            print(f"  - {dest.name} (robots.txt)")
            manifest["files"].append(entry)
            continue
        if dest.exists() and not force:
            entry["skipped"] = "既存"
            print(f"  = {dest.name} (既存)")
        else:
            try:
                sha256, size, content_type, type_mismatch = download(url, dest, session)
            except Exception as error:
                entry["error"] = f"{type(error).__name__}: {error}"[:200]
                print(f"  ! {dest.name}: {entry['error']}")
                manifest["files"].append(entry)
                continue
            entry.update({"sha256": sha256, "bytes": size,
                          "contentType": content_type or mimetypes.guess_type(url)[0] or ""})
            if type_mismatch:
                entry["warning"] = type_mismatch
            print(f"  + {dest.name} ({size:,} bytes)"
                  + (f"  ※{type_mismatch}" if type_mismatch else ""))
            count += 1
            time.sleep(sleep_seconds)
        manifest["files"].append(entry)

    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with open(archive_root(config) / "harvest_log.jsonl", "a", encoding="utf-8") as f:
        for entry in manifest["files"]:
            f.write(json.dumps({"slug": slug, "harvestedAt": manifest["harvestedAt"],
                                **entry}, ensure_ascii=False) + "\n")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help="リソースディレクトリ (resources/ or drafts/)")
    parser.add_argument("--limit", type=int, default=0, help="1リソースあたりの最大取得数")
    parser.add_argument("--force", action="store_true", help="既存ファイルも再取得")
    args = parser.parse_args()

    config = load_config()
    session = requests.Session()
    session.headers["User-Agent"] = config["crawler"]["user_agent"]

    total = 0
    for slug, _resource_dir, meta in iter_resources(args.paths):
        print(f"[harvest] {slug} → {archive_root(config) / slug}")
        total += harvest_resource(slug, meta or {}, config, session,
                                  limit=args.limit, force=args.force)
    print(f"---\n{total} ファイル取得")
    return 0


if __name__ == "__main__":
    sys.exit(main())
