"""oer-kit ui — ローカル管理UI（ダッシュボード + レビュー/承認）。

プロジェクトの現在地（件数・検証状態・低信頼件数）を一望し、下書きを画面上で
確認してその場で承認する。追加依存なし（標準ライブラリの HTTP サーバ）。
127.0.0.1 のみで待ち受ける（ローカル専用。認証は持たない）。

使い方:
    oer-kit ui                 # http://127.0.0.1:8765 を開く
    oer-kit ui --port 8900 --no-open

できること:
- ダッシュボード: リソース/下書きの件数、信頼度・再利用区分・出典の内訳
- レビュー: 下書き（と公開済み）を一覧し、内容紹介と引用原文を並べて確認 →
  選択して承認（drafts/ → resources/ へ移動。検証と横断重複チェック付き）
- 検証の実行（スキーマ・語彙・運用ポリシー・横断重複。引用照合は CLI で）
- 取り下げ: 公開済みを差し戻し (drafts へ) / 恒久取り下げ (withdrawn.yaml に記録し再収集を防止)
- ビルド済みならページプレビュー（_site/ を配信）

収集・生成などの長時間処理は対象外（CLI を使う。docs/commands.md）。
"""

from __future__ import annotations

import argparse
import datetime
import json
import mimetypes
import re
import shutil
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jsonschema

from .approve import with_reviewer, write_meta
from .withdraw import demote as demote_slugs, withdraw as withdraw_slugs
from .common import (
    DRAFTS_DIR,
    RESOURCES_DIR,
    SCHEMA_PATH,
    SITE_DIR,
    iter_resources,
    load_all_vocabs,
    load_config,
    localized,
)
from .validate import check_duplicates, validate_resource

REUSE_LABEL = {
    "allowed_with_conditions": "条件付き再利用可",
    "not_allowed": "再利用不可",
    "unspecified": "条件記載なし",
}


def _dirs(base: Path):
    return sorted(d for d in base.iterdir() if d.is_dir()) if base.is_dir() else []


def _concept_labels(meta, field, vocabs, lang="ja"):
    out = []
    for value in meta.get(field) or []:
        if isinstance(value, str):
            concept = vocabs[field].get(value)
            out.append(localized(concept["prefLabel"], lang) if concept else value)
        else:
            out.append(localized(value.get("prefLabel"), lang) or value.get("id", ""))
    return "、".join(out)


def gather_items(vocabs, lang="ja"):
    items = []
    for scope, base in (("drafts", DRAFTS_DIR), ("resources", RESOURCES_DIR)):
        dirs = _dirs(base)
        if not dirs:
            continue   # 空リストを iter_resources に渡すと resources 全体へフォールバックするため
        for slug, directory, meta in iter_resources(dirs):
            meta = meta or {}
            provenance = meta.get("metadataProvenance") or {}
            quoted = (meta.get("quotedDescription") or {}).get("text")
            if isinstance(quoted, dict):
                quoted = "\n".join(quoted.values())
            ext = meta.get("extensions") or {}
            terms = meta.get("usageTerms") or {}
            collection = meta.get("sourceCollection") or {}
            page = SITE_DIR / "r" / slug / "index.html"
            items.append({
                "scope": scope,
                "slug": slug,
                "name": localized(meta.get("name"), lang) or "",
                "faculty": ext.get("faculty", ""),
                "year": str(meta.get("datePublished", "")),
                "about": _concept_labels(meta, "about", vocabs, lang),
                "level": _concept_labels(meta, "educationalLevel", vocabs, lang),
                "types": _concept_labels(meta, "learningResourceType", vocabs, lang),
                "description": localized(meta.get("description"), lang) or "",
                "quoted": quoted or "",
                "url": meta.get("externalUrl", ""),
                "source": localized(collection.get("name"), lang) or "",
                "reuse": REUSE_LABEL.get(terms.get("reuse"),
                                         meta.get("license", "") and "CC" or ""),
                "license": meta.get("license", ""),
                "confidence": provenance.get("confidence", ""),
                "method": provenance.get("method", ""),
                "reviewedBy": provenance.get("reviewedBy") or [],
                "materials": len(meta.get("materials") or []),
                "hasPage": page.exists(),
            })
    priority = {"low": 0}
    items.sort(key=lambda i: (0 if i["scope"] == "drafts" else 1,
                              priority.get(i["confidence"], 1),
                              0 if not i["quoted"] else 1,
                              i["slug"]))
    return items


def build_state(config, items):
    def count(scope):
        rows = [i for i in items if i["scope"] == scope]
        return {
            "total": len(rows),
            "low": sum(1 for i in rows if i["confidence"] == "low"),
            "noQuote": sum(1 for i in rows if not i["quoted"]),
            "unreviewedAi": sum(1 for i in rows
                                if i["method"] in ("ai_generated", "ai_assisted")
                                and not i["reviewedBy"]),
            "bySource": _tally(rows, "source"),
            "byReuse": _tally(rows, "reuse"),
        }
    return {
        "siteName": config["site_name"],
        "baseUrl": config["base_url"],
        "reviewPolicy": config["review_policy"],
        "feedbackUrl": config.get("feedback_url", ""),
        "drafts": count("drafts"),
        "resources": count("resources"),
        "siteBuilt": (SITE_DIR / "index.html").exists(),
    }


def _tally(rows, key):
    out = {}
    for row in rows:
        label = row[key] or "（なし）"
        out[label] = out.get(label, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))


class Api:
    """UI のバックエンド。検証・承認は CLI と同じ実装を呼ぶ。"""

    def __init__(self):
        self.config = load_config()
        self.vocabs = load_all_vocabs(self.config)
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            self.validator = jsonschema.Draft202012Validator(json.load(f))

    def state(self):
        return build_state(self.config, gather_items(self.vocabs))

    def items(self):
        return {"items": gather_items(self.vocabs)}

    def item(self, slug):
        for base in (DRAFTS_DIR, RESOURCES_DIR):
            path = base / slug / "metadata.yaml"
            if path.exists():
                return {"slug": slug, "yaml": path.read_text(encoding="utf-8")}
        return None

    def validate(self):
        policy = self.config["review_policy"]
        results, entries = [], []
        for scope, base in (("drafts", DRAFTS_DIR), ("resources", RESOURCES_DIR)):
            dirs = _dirs(base)
            if not dirs:
                continue
            for slug, directory, meta in iter_resources(dirs):
                errors, warnings = validate_resource(
                    slug, directory, meta, self.validator, self.vocabs, policy=policy)
                entries.append((slug, meta or {}))
                if errors or warnings:
                    results.append({"slug": slug, "scope": scope,
                                    "errors": errors, "warnings": warnings})
        cross = [{"level": level, "message": message}
                 for level, message in check_duplicates(entries)]
        return {"findings": results, "cross": cross,
                "ok": not any(r["errors"] for r in results)
                and not any(c["level"] == "ERROR" for c in cross)}

    def vocab_options(self):
        """作成フォーム用: 語彙の選択肢 (key + 日本語ラベル)。"""
        out = {}
        for field, vocab in self.vocabs.items():
            out[field] = [{"key": key, "label": localized(c["prefLabel"], "ja") or key}
                          for key, c in vocab.items()]
        return out

    def create(self, form):
        """フォーム入力から hosted の下書きを作る (personal/institutional の作成支援)。"""
        slug = (form.get("slug") or "").strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
            return {"error": "slug は小文字英数字とハイフン (例: intro-statistics-2026)"}
        if (DRAFTS_DIR / slug).exists() or (RESOURCES_DIR / slug).exists():
            return {"error": f"slug '{slug}' は既に使われています"}

        creator = {"type": "Person", "name": (form.get("creatorName") or "").strip()}
        if (form.get("affiliation") or "").strip():
            creator["affiliation"] = {"name": form["affiliation"].strip()}
        meta = {
            "slug": slug,
            "name": {"ja": (form.get("name") or "").strip()},
            "description": {"ja": (form.get("description") or "").strip()},
            "inLanguage": [form.get("language") or "ja"],
            "license": form.get("license") or "",
            "creator": [creator],
            "learningResourceType": form.get("types") or [],
            "about": form.get("about") or [],
            "datePublished": form.get("datePublished") or datetime.date.today().isoformat(),
            "metadataProvenance": {"method": "manual",
                                   "generatedDate": datetime.date.today().isoformat()},
        }
        if form.get("level"):
            meta["educationalLevel"] = [form["level"]]
        if form.get("audience"):
            meta["audience"] = form["audience"]
        keywords = [k.strip() for k in (form.get("keywords") or "").replace("、", ",").split(",")
                    if k.strip()]
        if keywords:
            meta["keywords"] = keywords

        directory = DRAFTS_DIR / slug
        errors, _w = validate_resource(slug, directory, meta, self.validator,
                                       self.vocabs, policy=self.config["review_policy"])
        if errors:
            return {"error": "入力に問題があります", "details": errors}
        directory.mkdir(parents=True)
        (directory / "content").mkdir()
        (directory / "assets").mkdir()
        import yaml as _yaml
        (directory / "metadata.yaml").write_text(
            "# oer-kit ui で作成した下書き。content/ にソース、assets/ に画像等を置く。\n"
            + _yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100),
            encoding="utf-8")
        return {"created": slug}

    def upload(self, slug, dest, files):
        """作成済みの下書きへファイルを保存する (content / assets)。"""
        base = DRAFTS_DIR / slug
        if not (base / "metadata.yaml").exists():
            base = RESOURCES_DIR / slug
            if not (base / "metadata.yaml").exists():
                return {"error": f"'{slug}' が見つかりません"}
        if dest not in ("content", "assets"):
            return {"error": "dest は content か assets"}
        target_dir = base / dest
        target_dir.mkdir(exist_ok=True)
        saved, skipped = [], []
        for filename, data in files:
            name = re.sub(r"[/\\\x00]", "_", Path(filename).name).strip() or "file"
            if len(data) > 100 * 1024 * 1024:
                skipped.append(f"{name}: 100MB 超はリポジトリに置かない設計 "
                               "(Git LFS か外部URL参照。design.md §4.2)")
                continue
            (target_dir / name).write_bytes(data)
            saved.append(name)
        return {"saved": saved, "skipped": skipped}

    def approve(self, slugs, by):
        policy = self.config["review_policy"]
        if policy != "aggregator" and not by:
            return {"error": f"review_policy={policy} ではレビュー者名が必須です"}
        existing = [(slug, meta or {}) for slug, _d, meta
                    in iter_resources(_dirs(RESOURCES_DIR))]
        approved, held, entries = [], [], []
        for slug in slugs:
            draft_dir = DRAFTS_DIR / slug
            metadata_path = draft_dir / "metadata.yaml"
            if not metadata_path.exists():
                held.append({"slug": slug, "reasons": ["drafts/ に無い"]})
                continue
            if by:
                meta = with_reviewer(metadata_path, by)
            else:
                import yaml as _yaml
                meta = _yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
            errors, _w = validate_resource(slug, draft_dir, meta, self.validator,
                                           self.vocabs, policy=policy)
            if errors:
                held.append({"slug": slug, "reasons": errors})
            else:
                approved.append((slug, draft_dir, metadata_path, meta))
                entries.append((slug, meta))

        duplicate_slugs = set()
        for level, message in check_duplicates(entries, existing):
            if level == "ERROR":
                held.append({"slug": "横断検査", "reasons": [message]})
                for candidate, *_ in approved:
                    if candidate in message:
                        duplicate_slugs.add(candidate)
        approved = [a for a in approved if a[0] not in duplicate_slugs]

        moved = []
        for slug, draft_dir, metadata_path, meta in approved:
            destination = RESOURCES_DIR / slug
            if destination.exists():
                held.append({"slug": slug, "reasons": ["resources/ に同名が既にある"]})
                continue
            if by:
                write_meta(metadata_path, meta)
            RESOURCES_DIR.mkdir(exist_ok=True)
            shutil.move(str(draft_dir), str(destination))
            moved.append(slug)
        return {"approved": moved, "held": held}


class Handler(BaseHTTPRequestHandler):
    api: Api = None
    static_dir: Path = None

    def log_message(self, *args):  # 静かに
        pass

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        data = body if isinstance(body, bytes) else json.dumps(
            body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                html = (self.static_dir / "index.html").read_bytes()
                return self._send(200, html, "text/html; charset=utf-8")
            if path == "/api/state":
                return self._send(200, self.api.state())
            if path == "/api/vocab":
                return self._send(200, self.api.vocab_options())
            if path == "/api/items":
                return self._send(200, self.api.items())
            if path.startswith("/api/item/"):
                found = self.api.item(path.rsplit("/", 1)[-1])
                return self._send(200 if found else 404, found or {"error": "not found"})
            if path.startswith("/site/"):
                return self._serve_site(path[len("/site/"):])
            return self._send(404, {"error": "not found"})
        except Exception as error:  # UI サーバは落とさない
            return self._send(500, {"error": f"{type(error).__name__}: {error}"})

    def _serve_site(self, rel):
        base = SITE_DIR.resolve()
        target = (base / rel).resolve()
        if target.is_dir():
            target = target / "index.html"
        if not str(target).startswith(str(base)) or not target.is_file():
            return self._send(404, {"error": "not found"})
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        return self._send(200, target.read_bytes(), content_type)

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        try:
            if path == "/api/upload":
                query = parse_qs(urlparse(self.path).query)
                files = _parse_multipart(self.headers.get("Content-Type", ""),
                                         self.rfile.read(length))
                result = self.api.upload((query.get("slug") or [""])[0],
                                         (query.get("dest") or ["content"])[0], files)
                return self._send(400 if result.get("error") else 200, result)
            body = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/validate":
                return self._send(200, self.api.validate())
            if path == "/api/approve":
                result = self.api.approve(body.get("slugs") or [], body.get("by") or "")
                return self._send(400 if result.get("error") else 200, result)
            if path == "/api/demote":
                return self._send(200, demote_slugs(body.get("slugs") or []))
            if path == "/api/ingest":
                from .ingest import ingest as run_ingest
                result = run_ingest(body.get("source") or "",
                                    prefix=body.get("prefix") or "",
                                    kind=body.get("kind") or "personal")
                return self._send(400 if result.get("error") else 200, result)
            if path == "/api/create":
                result = self.api.create(body)
                return self._send(400 if result.get("error") else 200, result)
            if path == "/api/withdraw":
                result = withdraw_slugs(body.get("slugs") or [],
                                        body.get("reason") or "", body.get("by") or "")
                return self._send(400 if result.get("error") else 200, result)
            return self._send(404, {"error": "not found"})
        except Exception as error:
            return self._send(500, {"error": f"{type(error).__name__}: {error}"})


def _parse_multipart(content_type: str, body: bytes):
    """multipart/form-data からファイル部を取り出す。(filename, bytes) のリストを返す。"""
    match = re.search(r'boundary="?([^\s";]+)"?', content_type)
    if not match:
        return []
    boundary = b"--" + match.group(1).encode()
    files = []
    for part in body.split(boundary):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        if b"\r\n\r\n" not in part:
            continue
        raw_headers, data = part.split(b"\r\n\r\n", 1)
        disposition = ""
        for line in raw_headers.decode("utf-8", errors="replace").splitlines():
            if line.lower().startswith("content-disposition"):
                disposition = line
        found = re.search(r'filename="([^"]*)"', disposition)
        if not found or not found.group(1):
            continue
        files.append((found.group(1), data.rstrip(b"\r\n").removesuffix(b"--").rstrip(b"\r\n")))
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="ブラウザを自動で開かない")
    args = parser.parse_args()

    Handler.api = Api()   # プロジェクト外なら common が明確なエラーで止める
    Handler.static_dir = Path(__file__).parent / "ui_static"

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"oer-kit ui: {url}  (プロジェクト: {Handler.api.config['site_name']} / "
          f"{Handler.api.config['review_policy']})  Ctrl-C で終了")
    if not args.no_open:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n終了")
    return 0


if __name__ == "__main__":
    sys.exit(main())
