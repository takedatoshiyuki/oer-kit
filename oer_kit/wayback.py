#!/usr/bin/env python3
"""Wayback Machine 連携とリンク確認 (docs/design.md §7.3 リンク切れ対策)。

- 単一 URL: スナップショットの有無を availability API で確認
- --check: referenced リソース全件について externalUrl の生存確認 (HEAD) と
  スナップショット確認を行い、TSV で報告する (読み取り専用。metadata.yaml は変更しない)

使い方:
    python tools/wayback.py https://example.org/some/page
    python tools/wayback.py --check
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

from .common import iter_resources, load_config

AVAILABILITY_API = "https://archive.org/wayback/available"


def availability(url: str, session: requests.Session) -> dict | None:
    r = session.get(AVAILABILITY_API, params={"url": url}, timeout=30)
    r.raise_for_status()
    snapshot = r.json().get("archived_snapshots", {}).get("closest")
    return snapshot if snapshot and snapshot.get("available") else None


def save_page_now(url: str, session: requests.Session):
    """Wayback Machine の Save Page Now でスナップショットを作る。

    個人サイトの資料は消えやすいので、目録化の時点で保存する (§7.5)。
    成功すればスナップショット URL (archivedAt に記入する値) を返す。
    """
    r = session.get(f"https://web.archive.org/save/{url}", timeout=180, allow_redirects=True)
    r.raise_for_status()
    final = r.url
    if "/web/" in final:
        return final
    # リダイレクトで snapshot URL にならない場合は availability で引き直す
    snapshot = availability(url, session)
    return snapshot["url"] if snapshot else None


def head_status(url: str, session: requests.Session) -> str:
    try:
        r = session.head(url, timeout=30, allow_redirects=True)
        return str(r.status_code)
    except requests.RequestException as error:
        return type(error).__name__


def check_referenced(session: requests.Session, sleep_seconds: float) -> int:
    print("slug\texternalUrl\thead\tarchivedAt(記載)\tsnapshot(実際)")
    problems = 0
    for slug, _resource_dir, meta in iter_resources():
        if meta.get("mode") != "referenced":
            continue
        url = meta["externalUrl"]
        status = head_status(url, session)
        try:
            snapshot = availability(url, session)
        except requests.RequestException:
            snapshot = None
        snapshot_url = snapshot["url"] if snapshot else "-"
        recorded = meta.get("archivedAt", "-")
        print(f"{slug}\t{url}\t{status}\t{recorded}\t{snapshot_url}")
        if not status.startswith(("2", "3")):
            problems += 1
        time.sleep(sleep_seconds)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="確認する URL")
    parser.add_argument("--check", action="store_true",
                        help="referenced リソース全件のリンク・スナップショット確認")
    parser.add_argument("--save", action="store_true",
                        help="URL のスナップショットを Save Page Now で作成 (archivedAt 用)")
    args = parser.parse_args()

    config = load_config()
    session = requests.Session()
    session.headers["User-Agent"] = config["crawler"]["user_agent"]

    if args.check:
        problems = check_referenced(session, config["crawler"]["sleep_seconds"])
        print(f"---\nリンク異常 {problems} 件", file=sys.stderr)
        return 1 if problems else 0

    if not args.url:
        parser.error("URL か --check を指定")
    if args.save:
        saved = save_page_now(args.url, session)
        if saved:
            print(f"archivedAt: {saved}")
            return 0
        print("保存できなかった (レート制限の可能性。時間をおいて再試行)", file=sys.stderr)
        return 1
    snapshot = availability(args.url, session)
    if snapshot:
        print(f"snapshot: {snapshot['url']} (timestamp {snapshot['timestamp']})")
    else:
        print("snapshot なし (Save Page Now での保存を検討: https://web.archive.org/save/)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
