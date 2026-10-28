"""他の oer-kit プロジェクトからの取り込み — 連合モデル (docs/design.md §7.6)。

個人・組織が oer-kit で公開したプロジェクトは同じスキーマを話すので、
サイト固有のパーサなしで取り込める。指定できる取り込み元は3種類:

- **GitHub リポジトリ URL** (例: https://github.com/taro/my-oer):
  config.yaml と resources/*/metadata.yaml を raw.githubusercontent 経由で読む
- **公開サイト URL** (例: https://taro.github.io/my-oer):
  catalog.json (CC0 の JSON-LD) を読み、スキーマへ逆写像する
- **ローカルパス**: 同一マシン上のプロジェクトディレクトリを直接読む

取り込んだものは `mode: referenced` の下書き (drafts/) になり、
externalUrl は先方の公開ページ、メタデータ (CC0) は先方の記述を引き継ぐ。
その後は通常のレビュー → 承認フローに乗る。

方針:
- 先方の hosted リソースのみ取り込む (先方が目録化しただけの referenced は
  又貸しになるためスキップ)
- 取り下げ済み (withdrawn.yaml) の URL はスキップ
- 自分自身 (base_url が同じ) は取り込まない

使い方:
    oer-kit ingest https://github.com/taro/my-oer
    oer-kit ingest https://taro.github.io/my-oer --kind personal
    oer-kit ingest ../my-oer --prefix taro
"""

from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import requests
import yaml

from .common import DRAFTS_DIR, RESOURCES_DIR, load_config, load_yaml, localized
from .withdraw import withdrawn_urls


def _slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "-", value.lower())).strip("-")


# ---- 取り込み元の読み出し (3ルートとも {config, resources:[(slug, meta)]} を返す) ----

def read_local(path: Path):
    config = load_yaml(path / "config.yaml")
    resources = []
    for directory in sorted((path / "resources").iterdir()):
        metadata = directory / "metadata.yaml"
        if metadata.exists():
            resources.append((directory.name, load_yaml(metadata)))
    return config, resources, str(path)


def read_github(url: str, session: requests.Session):
    match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git|/.*)?$", url)
    owner, repo = match.group(1), match.group(2)
    raw = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD"
    response = session.get(f"{raw}/config.yaml", timeout=30)
    if response.status_code != 200:
        raise SystemExit(f"config.yaml を取得できない ({response.status_code})。"
                         "公開リポジトリの oer-kit プロジェクトか確認してください")
    config = yaml.safe_load(response.text)
    listing = session.get(
        f"https://api.github.com/repos/{owner}/{repo}/contents/resources", timeout=30)
    listing.raise_for_status()
    resources = []
    for entry in listing.json():
        if entry.get("type") != "dir":
            continue
        meta_response = session.get(f"{raw}/resources/{entry['name']}/metadata.yaml",
                                    timeout=30)
        if meta_response.status_code == 200:
            resources.append((entry["name"], yaml.safe_load(meta_response.text)))
    return config, resources, f"https://github.com/{owner}/{repo}"


def read_site(url: str, session: requests.Session, vocabs_reverse):
    base = url.rstrip("/")
    response = session.get(f"{base}/catalog.json", timeout=30)
    if response.status_code != 200:
        raise SystemExit(f"catalog.json を取得できない ({response.status_code})")
    catalog = response.json()
    config = {"site_name": catalog.get("name", base), "base_url": catalog.get("url", base)}
    resources = []
    for doc in catalog.get("resources", []):
        meta = _from_jsonld(doc, vocabs_reverse)
        if meta:
            slug = doc.get("id", "").rstrip("/").rsplit("/", 1)[-1] or _slugify(meta["name"]["ja"])
            resources.append((slug, meta))
    return config, resources, base


def _from_jsonld(doc, vocabs_reverse):
    """catalog.json の JSON-LD 1件を metadata.yaml 形へ逆写像する (主要フィールドのみ)。"""
    lang = (doc.get("inLanguage") or ["ja"])[0]
    license_url = (doc.get("license") or {}).get("id", "")
    if not license_url:
        return None   # v1 は CC ライセンスのあるものだけ
    def concepts(field):
        keys = []
        for node in doc.get(field) or []:
            key = vocabs_reverse.get(node.get("id", ""))
            if key:
                keys.append(key)
        return keys
    meta = {
        "name": {lang: doc.get("name", "")},
        "description": {lang: doc.get("description", "")},
        "inLanguage": doc.get("inLanguage") or ["ja"],
        "license": license_url,
        "creator": [{"type": a.get("type", "Person"), "name": a.get("name", "")}
                    for a in doc.get("creator") or []] or [{"type": "Person", "name": "不明"}],
        "learningResourceType": concepts("learningResourceType") or ["other"],
        "about": concepts("about") or ["generic"],
        "datePublished": str(doc.get("datePublished", ""))[:10] or None,
        "_jsonld_id": doc.get("id", ""),
        "_hosted": True,   # catalog からは判別困難。id が外部なら referenced とみなす
    }
    if doc.get("keywords"):
        meta["keywords"] = doc["keywords"]
    return meta


# ---- 変換と書き出し ------------------------------------------------------

def to_referenced(slug, their_meta, their_config, kind, today):
    """先方の hosted リソース → こちらの referenced 下書き。"""
    base_url = (their_config.get("base_url") or "").rstrip("/")
    external = their_meta.pop("_jsonld_id", "") or f"{base_url}/r/{slug}"
    their_meta.pop("_hosted", None)

    meta = {key: value for key, value in their_meta.items()
            if key in ("name", "description", "inLanguage", "license", "creator",
                       "learningResourceType", "about", "educationalLevel", "audience",
                       "keywords", "datePublished", "teaches", "timeRequired")}
    meta = {"mode": "referenced", "externalUrl": external, **meta}
    meta["sourceCollection"] = {
        "name": their_config.get("site_name", base_url),
        "url": base_url or external,
        "kind": kind,
    }
    meta["dateAccessed"] = today
    provenance = dict(their_meta.get("metadataProvenance") or {"method": "manual"})
    note = f"oer-kit ingest により {base_url or 'ローカル'} から取り込み ({today})。"
    provenance["notes"] = (provenance.get("notes", "").rstrip("。") + "。" + note).lstrip("。")
    if provenance.get("method") in ("ai_generated", "ai_assisted"):
        provenance.setdefault("confidence", "high")
    meta["metadataProvenance"] = provenance
    if not meta.get("datePublished"):
        meta["datePublished"] = today
    return meta


def ingest(source: str, prefix: str = "", kind: str = "personal", limit: int = 0):
    config = load_config()
    session = requests.Session()
    session.headers["User-Agent"] = config["crawler"]["user_agent"]

    # 逆写像用: 語彙 URI → キー
    from .common import load_all_vocabs
    vocabs = load_all_vocabs(config)
    vocabs_reverse = {concept["id"]: key
                      for field in vocabs.values() for key, concept in field.items()}

    if re.match(r"https://github\.com/", source):
        their_config, resources, origin = read_github(source, session)
    elif source.startswith("http"):
        their_config, resources, origin = read_site(source, session, vocabs_reverse)
    else:
        their_config, resources, origin = read_local(Path(source).expanduser().resolve())

    # 自分自身の取り込みを防ぐ。雛形のプレースホルダ (example.*) は未設定とみなし比較しない
    from .common import PROJECT_ROOT
    their_base = (their_config.get("base_url") or "").rstrip("/")
    own_base = config["base_url"].rstrip("/")
    if not source.startswith("http") and Path(source).expanduser().resolve() == PROJECT_ROOT:
        return {"error": "自分自身のプロジェクトは取り込めません"}
    if (their_base and their_base == own_base
            and "example." not in their_base):
        return {"error": "自分自身のプロジェクト (同じ base_url) は取り込めません"}

    prefix = _slugify(prefix) or _slugify(origin.rstrip("/").rsplit("/", 1)[-1])
    blocked = withdrawn_urls()
    today = datetime.date.today().isoformat()

    created, skipped = [], []
    for slug, their_meta in (resources[:limit] if limit else resources):
        if not their_meta:
            continue
        if their_meta.get("mode") == "referenced" and "_jsonld_id" not in their_meta:
            skipped.append((slug, "先方も referenced (又貸しになるため)"))
            continue
        meta = to_referenced(slug, dict(their_meta), their_config, kind, today)
        if meta["externalUrl"] in blocked:
            skipped.append((slug, "取り下げ済み (withdrawn.yaml)"))
            continue
        new_slug = _slugify(f"{prefix}-{slug}")
        meta["slug"] = new_slug
        if (DRAFTS_DIR / new_slug).exists() or (RESOURCES_DIR / new_slug).exists():
            skipped.append((slug, f"'{new_slug}' が既にある"))
            continue
        directory = DRAFTS_DIR / new_slug
        directory.mkdir(parents=True)
        (directory / "metadata.yaml").write_text(
            f"# oer-kit ingest による取り込み下書き (取り込み元: {origin})\n"
            + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        created.append(new_slug)
    return {"origin": origin, "site": their_config.get("site_name", ""),
            "created": created, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", help="GitHub リポジトリURL / 公開サイトURL / ローカルパス")
    parser.add_argument("--prefix", default="", help="slug の接頭辞 (既定: 取り込み元の名前)")
    parser.add_argument("--kind", choices=["personal", "organizational"], default="personal")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    result = ingest(args.source, prefix=args.prefix, kind=args.kind, limit=args.limit)
    if result.get("error"):
        parser.error(result["error"])
    for slug, reason in result["skipped"]:
        print(f"[skip] {slug}: {reason}")
    print(f"---\n{result['site'] or result['origin']} から {len(result['created'])} 件を"
          f"下書きに取り込み / スキップ {len(result['skipped'])} 件")
    if result["created"]:
        print("次: oer-kit ui (または validate → approve) でレビューして公開")
    return 0


if __name__ == "__main__":
    sys.exit(main())
