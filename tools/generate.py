#!/usr/bin/env python3
"""description（CC0 で提供する自作要約）の一括生成。

`quotedDescription`（原文の転載）はコードの仕事（extract.py）、`description` は
「自分の言葉による要約」なので LLM／人が書く（docs/design.md §7.3、tools/README.md）。
本ツールは後者だけを生成する。**原文の書き写しにならないこと**を機械検査してから書き戻す。

プロバイダ抽象化: OpenAI 互換の /chat/completions を叩くだけなので、base_url を
差し替えればローカル LLM（Ollama・llama.cpp・vLLM）でも動く。mock は API 不要。

過剰帰属への対処（LMS-NG docs/09・20 の実測に基づく）:
素朴な単発プロンプトは根拠のない断定を混ぜる。そこで2段構造を出力スキーマで強制する
— まず原文から読み取れた事実を列挙させ（facts）、その事実だけで要約を書かせる。
情報が足りなければ confidence=low を返させ、**書けないときは書かせない**。

使い方:
    python3 tools/generate.py --provider mock drafts/nagoya-u-course-0003   # API不要の試運転
    python3 tools/generate.py --limit 10                                   # まず10件で実測
    OPENAI_API_KEY=... python3 tools/generate.py --model gpt-5.4-mini drafts/nagoya-u-course-*
    python3 tools/generate.py --base-url http://localhost:11434/v1 --model qwen3 --api-key dummy
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
import yaml

from common import REPO_ROOT, iter_resources, localized
from validate import _squash, _text_values

DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"

SYSTEM_PROMPT = """\
あなたは教育資源（OER）のカタログ編集者です。教材1件について、カタログに載せる
**内容紹介**を日本語で書きます。

出力は次の順で行います（この順序を守ること）:

1. facts: 与えられた情報から**読み取れる事実だけ**を短く列挙する。
   推測・一般論・書かれていないことは入れない。
2. description: facts だけを使って2〜3文の内容紹介を書く。

description の規律:

- **出典の説明文を言い換えただけの文にしない**。原文の構成をなぞらず、
  「何を扱い、どこまで踏み込む教材か」を自分の言葉で述べる。
- 事実だけを書く。**難易度・評価・人気・受講者数・有用性の断定は書かない**
  （「わかりやすい」「充実した」「必見」などの評価語を使わない）。
- 講義名の単純な繰り返しにしない。
- 敬体ではなく常体（「〜する」「〜を扱う」）で書く。
- 情報が乏しく2文も書けない場合は、無理に埋めずに confidence を "low" にし、
  description には確実に言える範囲だけを書く。

日本語以外の教材でも、内容紹介は日本語で書く。"""

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["facts", "description", "confidence"],
    "properties": {
        "facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "与えられた情報から読み取れる事実の列挙",
        },
        "description": {"type": "string", "description": "2〜3文の内容紹介"},
        "confidence": {"enum": ["high", "low"]},
    },
}


def build_user_prompt(meta, lang="ja") -> str:
    ext = meta.get("extensions") or {}
    quoted = meta.get("quotedDescription") or {}
    quoted_text = ""
    if quoted.get("text"):
        quoted_text = "\n".join(_text_values(quoted["text"]))
    materials = meta.get("materials") or []
    material_names = [m["name"] for m in materials[:12]]

    lines = [
        f"講義名: {localized(meta.get('name'), lang)}",
        f"提供: {'、'.join(localized(p['name'], lang) for p in meta.get('publisher', []))}",
        f"担当: {'、'.join(localized(c['name'], lang) for c in meta.get('creator', []))}",
        f"開講年度: {meta.get('datePublished', '不明')}",
    ]
    if ext.get("faculty"):
        lines.append(f"開講部局: {ext['faculty']}")
    if ext.get("targetAudience"):
        lines.append(f"対象: {ext['targetAudience']}")
    if ext.get("term"):
        lines.append(f"開講時期: {ext['term']}")
    if meta.get("inLanguage"):
        lines.append(f"使用言語: {'、'.join(meta['inLanguage'])}")
    if material_names:
        lines.append(f"公開されている教材ファイル（{len(materials)}件）: "
                     + "、".join(material_names))
    if quoted_text:
        lines.append("\n出典サイトに掲載されている説明文:\n" + quoted_text)
    else:
        lines.append("\n（出典サイトに説明文なし。上の項目だけから書けることを書く）")
    return "\n".join(lines)


# ---- プロバイダ ----------------------------------------------------------

def call_mock(system, user, model):
    """API 不要の試運転用。入力から機械的に組み立てる（品質は問わない）。"""
    name = re.search(r"講義名: (.+)", user)
    faculty = re.search(r"開講部局: (.+)", user)
    files = re.search(r"教材ファイル（(\d+)件）", user)
    parts = [f"{name.group(1) if name else '本教材'}を扱う講義。"]
    if faculty:
        parts.append(f"{faculty.group(1)}で開講された。")
    if files:
        parts.append(f"講義資料 {files.group(1)} 件が公開されている。")
    return {"facts": ["mock"], "description": "".join(parts), "confidence": "low"}, {}


def call_openai_compatible(system, user, model, base_url, api_key, timeout=120):
    """OpenAI 互換 /chat/completions。ローカル LLM でも base_url を変えるだけで動く。"""
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "oer_description", "strict": True,
                            "schema": RESPONSE_SCHEMA},
        },
    }
    r = requests.post(f"{base_url.rstrip('/')}/chat/completions",
                      headers={"Authorization": f"Bearer {api_key}",
                               "Content-Type": "application/json"},
                      json=payload, timeout=timeout)
    if r.status_code == 400 and "response_format" in r.text:
        # json_schema 非対応のローカルサーバ向けフォールバック
        payload["response_format"] = {"type": "json_object"}
        payload["messages"][0]["content"] += (
            "\n\n次の JSON だけを出力する: "
            '{"facts": [string], "description": string, "confidence": "high"|"low"}')
        r = requests.post(f"{base_url.rstrip('/')}/chat/completions",
                          headers={"Authorization": f"Bearer {api_key}",
                                   "Content-Type": "application/json"},
                          json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content), data.get("usage", {})


# ---- 検査 ----------------------------------------------------------------

def check_output(result, meta):
    """生成物を機械検査する。戻り値は問題のリスト（空なら合格）。"""
    problems = []
    description = (result.get("description") or "").strip()
    if len(description) < 20:
        problems.append("短すぎる")

    quoted = meta.get("quotedDescription") or {}
    squashed = _squash(description)
    for value in _text_values(quoted.get("text", "")):
        original = _squash(value)
        if not original or not squashed:
            continue
        if squashed in original or original in squashed:
            problems.append("引用文の丸写し")
            break
        # 連続40字以上の一致は書き写しとみなす
        for i in range(0, max(0, len(squashed) - 40) + 1, 10):
            if squashed[i:i + 40] in original:
                problems.append("引用文と40字以上が一致（書き写しの疑い）")
                break
        else:
            continue
        break

    # 主観的な価値判断のみを弾く。「最適な」は「最適な投資額」のように数学・工学・
    # 経済学で技術用語として正当に使われるため対象にしない (実測で誤検出2件)
    for word in ("わかりやすい", "分かりやすい", "充実した", "必見", "おすすめ",
                 "優れた", "人気の"):
        if word in description:
            problems.append(f"評価語『{word}』を含む")
    return problems


def update_draft(path: Path, meta, result, model):
    """metadata.yaml に description を書き戻す（先頭のコメントは保つ）。"""
    raw = path.read_text(encoding="utf-8")
    header = "".join(line + "\n" for line in raw.splitlines()
                     if line.startswith("#") or not line.strip())
    header = "\n".join(l for l in header.splitlines() if l.startswith("#"))
    header = re.sub(r"description は未作成 \(TODO\)。?", "", header).rstrip()

    meta["description"] = {"ja": result["description"].strip()}
    provenance = meta.setdefault("metadataProvenance", {})
    provenance["method"] = "ai_generated"
    provenance["generator"] = model
    provenance["confidence"] = result.get("confidence", "high")
    notes = re.sub(r"description は未作成。?", "", provenance.get("notes", "")).strip()
    if notes and not notes.endswith("。"):
        notes += "。"
    provenance["notes"] = notes + f"description は {model} が生成。"

    body = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=100)
    path.write_text((header + "\n" if header else "") + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="対象ディレクトリ（省略時は drafts/ 全件）")
    parser.add_argument("--provider", choices=["openai", "mock"], default="openai")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL,
                        help="OpenAI 互換エンドポイント（ローカル LLM もこれで指定）")
    parser.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", ""))
    parser.add_argument("--limit", type=int, default=0, help="先頭 N 件だけ処理（実測用）")
    parser.add_argument("--force", action="store_true", help="生成済みも上書き")
    parser.add_argument("--sleep", type=float, default=0.5, help="リクエスト間隔（秒）")
    args = parser.parse_args()

    if args.provider == "openai" and not args.api_key:
        parser.error("OPENAI_API_KEY が未設定（--api-key か環境変数、または --provider mock）")

    paths = [Path(p) for p in args.paths] if args.paths else \
        sorted(d for d in (REPO_ROOT / "drafts").iterdir() if d.is_dir())

    targets = []
    for slug, directory, meta in iter_resources(paths):
        current = localized((meta or {}).get("description"), "ja") or ""
        if not args.force and current and "TODO" not in current:
            continue
        targets.append((slug, directory, meta))
    if args.limit:
        targets = targets[: args.limit]

    print(f"対象 {len(targets)} 件 / provider={args.provider} model={args.model}")
    done = skipped = failed = 0
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    low_confidence = []

    for index, (slug, directory, meta) in enumerate(targets, 1):
        user_prompt = build_user_prompt(meta)
        try:
            if args.provider == "mock":
                result, usage = call_mock(SYSTEM_PROMPT, user_prompt, args.model)
            else:
                result, usage = call_openai_compatible(
                    SYSTEM_PROMPT, user_prompt, args.model, args.base_url, args.api_key)
        except Exception as error:
            failed += 1
            print(f"  ! {slug}: {type(error).__name__}: {error}"[:160], flush=True)
            continue

        for key in usage_total:
            usage_total[key] += usage.get(key, 0)

        problems = check_output(result, meta)
        if problems:
            skipped += 1
            print(f"  - {slug}: 不採用（{'、'.join(problems)}）", flush=True)
            continue

        update_draft(directory / "metadata.yaml", meta, result, args.model)
        done += 1
        if result.get("confidence") == "low":
            low_confidence.append(slug)
        if index % 20 == 0 or index == len(targets):
            print(f"  {index}/{len(targets)}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    print(f"---\n生成 {done} / 不採用 {skipped} / 失敗 {failed}")
    if usage_total["total_tokens"]:
        n = max(1, done + skipped)
        print(f"トークン: 入力 {usage_total['prompt_tokens']:,} / "
              f"出力 {usage_total['completion_tokens']:,} / "
              f"合計 {usage_total['total_tokens']:,} "
              f"(1件あたり {usage_total['total_tokens'] / n:,.0f})")
    if low_confidence:
        print(f"confidence=low（要確認）{len(low_confidence)} 件: "
              + "、".join(low_confidence[:8]) + ("…" if len(low_confidence) > 8 else ""))
    print("次: python3 tools/validate.py --check-quotes drafts/<slug> でレビューへ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
