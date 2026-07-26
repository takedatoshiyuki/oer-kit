"""oer_kit 共通ユーティリティ: プロジェクト探索・設定・統制語彙・リソースの読み込み。

oer_kit はモジュール (このパッケージ)、プロジェクトはそれを使って OER を収集・公開する
ディレクトリ、という分担 (docs/design.md §9.1 の3類型が各自のプロジェクトを持つ)。
プロジェクトのルートは「config.yaml のあるディレクトリ」をカレントから上へ探して決める。
"""

from __future__ import annotations

import sys
from importlib import resources as importlib_resources
from pathlib import Path

import yaml


def find_project_root() -> Path:
    for candidate in (Path.cwd(), *Path.cwd().parents):
        if (candidate / "config.yaml").exists():
            return candidate
    raise SystemExit(
        "config.yaml が見つかりません。OER プロジェクトのディレクトリ内で実行してください。\n"
        "新しいプロジェクトを作るには: python3 -m oer_kit.cli init <ディレクトリ>")


PROJECT_ROOT = find_project_root()
RESOURCES_DIR = PROJECT_ROOT / "resources"
DRAFTS_DIR = PROJECT_ROOT / "drafts"
VOCAB_DIR = PROJECT_ROOT / "vocabularies"
SITE_DIR = PROJECT_ROOT / "_site"
CACHE_DIR = PROJECT_ROOT / ".cache"

# スキーマと雛形はモジュール側が持つ (プロジェクトはフォークしない)
SCHEMA_PATH = Path(str(importlib_resources.files("oer_kit"))) / "schema" / "resource.schema.json"
SCAFFOLD_DIR = Path(str(importlib_resources.files("oer_kit"))) / "scaffold"

# metadata.yaml のフィールド → 語彙ファイル
VOCAB_FILES = {
    "learningResourceType": "learning-resource-types.yaml",
    "audience": "audiences.yaml",
    "educationalLevel": "educational-levels.yaml",
    "about": "subjects.yaml",
}

# 自リポジトリ定義の語彙 (概念に id が無いので base_url から合成する)
LOCAL_VOCAB_PATH = {
    "educationalLevel": "vocab/educational-level",
    "about": "vocab/subject",
}

LICENSE_URL = {
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC-BY-SA-4.0": "https://creativecommons.org/licenses/by-sa/4.0/",
    "CC-BY-NC-4.0": "https://creativecommons.org/licenses/by-nc/4.0/",
    "CC-BY-NC-SA-4.0": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
    "CC-BY-ND-4.0": "https://creativecommons.org/licenses/by-nd/4.0/",
    "CC-BY-NC-ND-4.0": "https://creativecommons.org/licenses/by-nc-nd/4.0/",
}


def load_yaml(path: Path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config() -> dict:
    path = PROJECT_ROOT / "config.yaml"
    config = load_yaml(path) if path.exists() else {}
    config.setdefault("site_name", "OER リポジトリ")
    config.setdefault("base_url", "https://oer.example.ac.jp")
    config["base_url"] = config["base_url"].rstrip("/")
    config.setdefault("primary_language", "ja")
    crawler = config.setdefault("crawler", {})
    crawler.setdefault("user_agent", "oer-repo-tools/0.1")
    crawler.setdefault("sleep_seconds", 1.0)
    config.setdefault("lib_paths", [])
    # レビュー方針 (docs/design.md §9.1)。未設定なら最も厳格な institutional
    config.setdefault("review_policy", "institutional")
    config.setdefault("feedback_url", "")
    return config


def add_lib_paths(config: dict) -> None:
    """config.lib_paths (common_knowledge 等) を sys.path に加える。"""
    for p in config.get("lib_paths", []):
        p = str(Path(p).expanduser())
        if p not in sys.path:
            sys.path.insert(0, p)


def load_vocab(field: str, config: dict) -> dict:
    """語彙ファイルを読み、{key: {id, prefLabel}} を返す。"""
    data = load_yaml(VOCAB_DIR / VOCAB_FILES[field])
    concepts = {}
    for c in data.get("concepts", []):
        concept_id = c.get("id")
        if not concept_id:
            concept_id = f"{config['base_url']}/{LOCAL_VOCAB_PATH[field]}/{c['key']}"
        concepts[c["key"]] = {"id": concept_id, "prefLabel": c.get("prefLabel", {})}
    return concepts


def load_all_vocabs(config: dict) -> dict:
    return {field: load_vocab(field, config) for field in VOCAB_FILES}


def iter_resources(paths=None):
    """(slug, ディレクトリ, metadata dict) を列挙する。paths 指定時はそのディレクトリのみ。"""
    if paths:
        dirs = [Path(p) for p in paths]
    else:
        dirs = sorted(d for d in RESOURCES_DIR.iterdir() if d.is_dir())
    for d in dirs:
        metadata_path = d / "metadata.yaml"
        if not metadata_path.exists():
            continue
        yield d.name, d, load_yaml(metadata_path)


def localized(value, lang: str = "ja"):
    """文字列 or 言語マップから表示値を1つ選ぶ。"""
    if value is None or isinstance(value, str):
        return value
    return value.get(lang) or value.get("ja") or next(iter(value.values()))


def expand_license(value: str) -> str:
    return LICENSE_URL.get(value, value)


def orcid_url(value: str) -> str:
    return value if value.startswith("http") else f"https://orcid.org/{value}"


def ror_url(value: str) -> str:
    return value if value.startswith("http") else f"https://ror.org/{value}"
