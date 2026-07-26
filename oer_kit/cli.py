"""oer-kit コマンド: サブコマンドで各ツールを呼ぶ。

    oer-kit init <dir>     新しい OER プロジェクトを作る (雛形の展開)
    oer-kit validate       検証 (スキーマ・語彙・運用ポリシー・横断重複)
    oer-kit prerender      metadata.yaml → Quarto サイト入力
    ...                    (一覧は oer-kit --help)

インストールしていない場合は `PYTHONPATH=<oer-kitの場所> python3 -m oer_kit.cli ...`。
"""

from __future__ import annotations

import importlib
import importlib.resources
import shutil
import sys
from pathlib import Path

# サブコマンド → oer_kit 内のモジュール名
COMMANDS = [
    "validate", "jsonld", "prerender", "build-catalog",
    "discover", "fetch", "extract", "make-drafts", "generate",
    "review-sheet", "approve", "diagnose",
    "harvest", "wayback", "convert-legacy",
]


def init(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="oer-kit init", description="新しい OER プロジェクトを雛形から作る")
    parser.add_argument("directory", nargs="?", default=".")
    args = parser.parse_args(argv)

    destination = Path(args.directory).resolve()
    if (destination / "config.yaml").exists():
        raise SystemExit(f"{destination} には既に config.yaml があります")
    scaffold = Path(str(importlib.resources.files("oer_kit"))) / "scaffold"

    destination.mkdir(parents=True, exist_ok=True)
    for item in scaffold.iterdir():
        name = {"github": ".github", "gitignore": ".gitignore"}.get(item.name, item.name)
        target = destination / name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    (destination / "resources").mkdir(exist_ok=True)
    (destination / "parsers").mkdir(exist_ok=True)

    print(f"プロジェクトを作成しました: {destination}")
    print("次にやること:")
    print("  1. config.yaml を編集 (site_name / base_url / review_policy)")
    print("  2. resources/ に教材を追加 (docs/user-guide.md 参照)")
    print("  3. oer-kit validate → make site")
    return 0


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        print("\ncommands: init, " + ", ".join(COMMANDS))
        return 0
    command, rest = argv[0], argv[1:]
    if command == "init":
        return init(rest)
    if command not in COMMANDS:
        raise SystemExit(f"不明なコマンド: {command} (一覧は oer-kit --help)")
    module = importlib.import_module("oer_kit." + command.replace("-", "_"))
    sys.argv = [f"oer-kit {command}", *rest]
    return module.main()


if __name__ == "__main__":
    sys.exit(main())
