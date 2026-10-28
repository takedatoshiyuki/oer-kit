"""公開の取り下げ — カタログ (resources/) からの削除 (docs/design.md §7.5)。

2種類を区別する:

- **差し戻し** (`--demote`): resources/ → drafts/ へ戻す。品質修正のための一時的な
  取り下げで、再公開を前提とする
- **取り下げ** (既定。`--reason` 必須): resources/ (または drafts/) → withdrawn/ へ移し、
  `withdrawn.yaml` に記録する。オプトアウト依頼等の恒久的な削除。記録された URL は
  以後の収集 (make-drafts) から自動的に除外され、再登録しようとすると validate が
  エラーにする — 「消す」だけでなく「もう集めない」という意思を残す

どちらもファイルは失われない (withdrawn/ は Git 管理外のローカル保管)。
公開サイトから消すには、この後 `make site` の再実行 (と push) が必要。
Web アーカイブ (Wayback 等) 上の複製の削除は各アーカイブの手続きによる。

使い方:
    oer-kit withdraw <slug>... --reason "本人からの削除依頼 (Issues #12)" [--by 氏名]
    oer-kit withdraw <slug>... --demote
"""

from __future__ import annotations

import argparse
import datetime
import shutil
import sys

import yaml

from .common import DRAFTS_DIR, PROJECT_ROOT, RESOURCES_DIR, load_yaml, localized

WITHDRAWN_LIST = PROJECT_ROOT / "withdrawn.yaml"
WITHDRAWN_DIR = PROJECT_ROOT / "withdrawn"


def load_withdrawn() -> list:
    if WITHDRAWN_LIST.exists():
        return load_yaml(WITHDRAWN_LIST) or []
    return []


def withdrawn_urls() -> set:
    return {entry.get("externalUrl") for entry in load_withdrawn()
            if entry.get("externalUrl")}


def _locate(slug: str):
    for base in (RESOURCES_DIR, DRAFTS_DIR):
        directory = base / slug
        if (directory / "metadata.yaml").exists():
            return directory
    return None


def demote(slugs: list[str]):
    """resources/ → drafts/ へ差し戻す (再公開前提の一時取り下げ)。"""
    moved, held = [], []
    for slug in slugs:
        source = RESOURCES_DIR / slug
        if not (source / "metadata.yaml").exists():
            held.append({"slug": slug, "reasons": ["resources/ に無い"]})
            continue
        destination = DRAFTS_DIR / slug
        if destination.exists():
            held.append({"slug": slug, "reasons": ["drafts/ に同名がある"]})
            continue
        DRAFTS_DIR.mkdir(exist_ok=True)
        shutil.move(str(source), str(destination))
        moved.append(slug)
    return {"moved": moved, "held": held}


def withdraw(slugs: list[str], reason: str, by: str = ""):
    """withdrawn/ へ移し、withdrawn.yaml に記録する (恒久的な取り下げ)。"""
    if not reason.strip():
        return {"error": "取り下げには --reason (理由) が必須です"}
    records = load_withdrawn()
    moved, held = [], []
    for slug in slugs:
        source = _locate(slug)
        if source is None:
            held.append({"slug": slug, "reasons": ["resources/ にも drafts/ にも無い"]})
            continue
        destination = WITHDRAWN_DIR / slug
        if destination.exists():
            held.append({"slug": slug, "reasons": ["withdrawn/ に同名がある"]})
            continue
        meta = load_yaml(source / "metadata.yaml") or {}
        WITHDRAWN_DIR.mkdir(exist_ok=True)
        shutil.move(str(source), str(destination))
        record = {
            "slug": slug,
            "name": localized(meta.get("name"), "ja") or "",
            "date": datetime.date.today().isoformat(),
            "reason": reason.strip(),
        }
        if meta.get("externalUrl"):
            record["externalUrl"] = meta["externalUrl"]
        if by:
            record["by"] = by
        records.append(record)
        moved.append(slug)
    WITHDRAWN_LIST.write_text(
        yaml.safe_dump(records, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8")
    return {"moved": moved, "held": held}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slugs", nargs="+")
    parser.add_argument("--demote", action="store_true",
                        help="恒久取り下げでなく drafts/ への差し戻しにする")
    parser.add_argument("--reason", default="", help="取り下げの理由 (取り下げ時は必須)")
    parser.add_argument("--by", default="", help="対応者名")
    args = parser.parse_args()

    if args.demote:
        result = demote(args.slugs)
    else:
        result = withdraw(args.slugs, args.reason, args.by)
        if result.get("error"):
            parser.error(result["error"])

    for item in result["held"]:
        print(f"[保留] {item['slug']}: {item['reasons'][0]}")
    verb = "差し戻し" if args.demote else "取り下げ"
    print(f"---\n{verb} {len(result['moved'])} 件 / 保留 {len(result['held'])} 件")
    if result["moved"]:
        print("次: make site で公開サイトから消える (要 push)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
