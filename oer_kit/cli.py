"""oer-kit コマンド: サブコマンドで各ツールを呼ぶ。

    oer-kit init <dir>     新しい OER プロジェクトを作る (雛形の展開)
    oer-kit ui             管理UI (ダッシュボード + レビュー/承認) をブラウザで開く
    oer-kit validate       検証 (スキーマ・語彙・運用ポリシー・横断重複)
    oer-kit prerender      metadata.yaml → Quarto サイト入力
    ...                    (一覧は oer-kit --help)

インストールしていない場合は `PYTHONPATH=<oer-kitの場所> python -m oer_kit.cli ...`。
"""

from __future__ import annotations

import importlib
import importlib.resources
import shutil
import sys
from pathlib import Path

# サブコマンド → oer_kit 内のモジュール名
COMMANDS = [
    "ui",
    "validate", "jsonld", "prerender", "build-catalog",
    "discover", "fetch", "extract", "make-drafts", "generate", "ingest",
    "review-sheet", "approve", "withdraw", "diagnose",
    "harvest", "wayback", "convert-legacy",
]


ENGINE_GUIDE = """サイトエンジンを選んでください (docs/design.md §8.4):

  教材ページに次のいずれかを含めたい場合は quarto を選んでください:
  文献リスト (BibTeX からの引用・参考文献の自動生成)・
  実行可能なコード例 (実行結果や図表をビルド時に生成)・章や図表への相互参照。

  上記が不要なら hugo を選んでください。ビルドが速く、件数が増えても破綻しません。
  数式 (LaTeX 記法) はどちらでも使えます。
"""


def init(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        prog="oer-kit init", description="新しい OER プロジェクトを雛形から作る")
    parser.add_argument("directory", nargs="?", default=".")
    parser.add_argument("--engine", choices=["quarto", "hugo"],
                        help="サイトエンジン (未指定なら対話で選択)")
    args = parser.parse_args(argv)

    engine = args.engine
    if not engine:
        if sys.stdin.isatty():
            print(ENGINE_GUIDE)
            answer = input("engine [quarto/hugo] (既定 quarto): ").strip().lower()
            engine = answer if answer in ("quarto", "hugo") else "quarto"
        else:
            engine = "quarto"

    destination = Path(args.directory).resolve()
    if (destination / "config.yaml").exists():
        raise SystemExit(f"{destination} には既に config.yaml があります")
    scaffold = Path(str(importlib.resources.files("oer_kit"))) / "scaffold"

    destination.mkdir(parents=True, exist_ok=True)
    for item in scaffold.iterdir():
        if item.name == "site-hugo":
            continue                     # エンジン固有 (下で処理)
        if engine == "hugo" and item.name in ("site", "Makefile"):
            continue                     # Quarto 固有は使わない
        name = {"github": ".github", "gitignore": ".gitignore"}.get(item.name, item.name)
        target = destination / name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    if engine == "hugo":
        hugo_src = scaffold / "site-hugo"
        shutil.copy2(hugo_src / "Makefile", destination / "Makefile")
        shutil.copytree(hugo_src, destination / "site", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("Makefile"))
        # config.yaml にエンジンを記録する (既定は quarto)
        config_path = destination / "config.yaml"
        config_path.write_text(
            config_path.read_text(encoding="utf-8").replace(
                "site_engine: quarto", "site_engine: hugo"),
            encoding="utf-8")
    (destination / "resources").mkdir(exist_ok=True)
    (destination / "parsers").mkdir(exist_ok=True)

    print(f"プロジェクトを作成しました: {destination} (engine: {engine})")
    print("次にやること:")
    print("  1. config.yaml を編集 (site_name / base_url / review_policy)")
    print("  2. resources/ に教材を追加 (docs/user-guide.md 参照)")
    print("  3. oer-kit validate → make site")
    if engine == "hugo":
        print("  ※ hugo コマンドが必要です (例: brew install hugo)")
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
