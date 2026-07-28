#!/usr/bin/env python3
"""サイト入力の生成 (docs/design.md §8.1・§8.4)。エンジンは config.yaml の site_engine。

- quarto: site/_quarto.in.yml → site/_quarto.yml、resources → site/r/<slug>/index.qmd
- hugo:   site/hugo.in.yaml → site/hugo.yaml、resources → site/content/r/<slug>/index.md
  (本文は共通の Markdown。注意枠は Quarto では callout、Hugo では太字見出し付き
   引用ブロックとして出す。JSON-LD は front matter 経由でレイアウトが埋め込む)
- hosted リソースは content/ と assets/ をページ配下へコピーする

使い方:
    python -m oer_kit.prerender
    make render               # → _site/
"""

from __future__ import annotations

import json
import re
import shutil
import sys

import yaml

from .common import PROJECT_ROOT, expand_license, iter_resources, load_all_vocabs, load_config, localized
from .jsonld import build_jsonld

SITE_SRC = PROJECT_ROOT / "site"
R_DIR = SITE_SRC / "r"                       # quarto の出力先
HUGO_R_DIR = SITE_SRC / "content" / "r"      # hugo の出力先

# main() が config から設定する (build_body の注意枠の書式が変わる)
ENGINE = "quarto"


def callout(kind: str, title: str, body_lines: list[str],
            collapse: bool | None = None, minimal: bool = False) -> list[str]:
    """注意枠。Quarto は callout ブロック、Hugo は太字見出し付き引用ブロック
    (純 Markdown なのでどのレンダラでも壊れない。CSS は blockquote に当てる)。"""
    if ENGINE == "quarto":
        attrs = [f".callout-{kind}"]
        if minimal:
            attrs.append("appearance='minimal'")
        if collapse is not None:
            attrs.append(f"collapse=\"{'true' if collapse else 'false'}\"")
        head = f"::: {{{' '.join(attrs)} title=\"{title}\"}}"
        return [head, *body_lines, ":::", ""]
    quoted = [f"> **{title}**", ">"]
    for line in body_lines:
        quoted.append(f"> {line}")
    return [*quoted, ""]

SPDX_LABEL = {
    "CC0-1.0": "CC0 1.0",
    "CC-BY-4.0": "CC BY 4.0",
    "CC-BY-SA-4.0": "CC BY-SA 4.0",
    "CC-BY-NC-4.0": "CC BY-NC 4.0",
    "CC-BY-NC-SA-4.0": "CC BY-NC-SA 4.0",
    "CC-BY-ND-4.0": "CC BY-ND 4.0",
    "CC-BY-NC-ND-4.0": "CC BY-NC-ND 4.0",
}

PROVENANCE_METHOD_LABEL = {
    "manual": "手作業で作成",
    "ai_assisted": "AI 支援で作成（人手レビュー済み）",
    "ai_generated": "AI 生成（人手レビュー済み）",
}

REUSE_LABEL = {
    "allowed_with_conditions": "条件付き再利用可（独自ライセンス）",
    "not_allowed": "再利用不可（視聴のみ）",
    "unspecified": "利用条件の記載なし（原則閲覧のみ）",
}
REUSE_CATEGORY = {
    "allowed_with_conditions": "条件付き再利用可",
    "not_allowed": "再利用不可",
    "unspecified": "利用条件記載なし",
}


def license_label(value: str) -> str:
    if value in SPDX_LABEL:
        return SPDX_LABEL[value]
    m = re.search(r"creativecommons\.org/licenses/([a-z-]+)/([0-9.]+)(?:/([a-z]{2}))?/", value)
    if m:
        label = f"CC {m.group(1).upper()} {m.group(2)}"
        if m.group(3):
            label += f" {m.group(3).upper()}"
        return label
    if "publicdomain/zero" in value:
        return "CC0 1.0"
    if "publicdomain/mark" in value:
        return "Public Domain Mark 1.0"
    return value


def duration_label(value: str) -> str:
    m = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", value or "")
    if not m or not any(m.groups()):
        return value or ""
    hours, minutes, _seconds = m.groups()
    label = (f"{int(hours)}時間" if hours else "") + (f"{int(minutes)}分" if minutes else "")
    return label or value


def concept_labels(meta, field, vocabs, lang):
    out = []
    for v in meta.get(field, []) or []:
        if isinstance(v, str):
            out.append(localized(vocabs[field][v]["prefLabel"], lang) or v)
        else:
            out.append(localized(v.get("prefLabel"), lang) or v["id"])
    return out


def agent_names(agents, lang):
    return [localized(a["name"], lang) for a in agents or []]


def jsonld_script(doc) -> str:
    payload = json.dumps(doc, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{payload}\n</script>'


def tasl_line(meta, url, config, lang) -> str:
    authors = "、".join(agent_names(meta.get("creator"), lang))
    title = localized(meta["name"], lang)
    if meta.get("license"):
        rights = license_label(meta["license"])
    else:
        rights = REUSE_LABEL.get(meta.get("usageTerms", {}).get("reuse"), "")
    return f"{authors}「{title}」{config['site_name']}. {rights}. {url}"


def text_item(value, lang) -> str:
    if isinstance(value, str):
        return value
    return localized(value.get("prefLabel"), lang) or value.get("id", "")


def build_body(slug, meta, config, vocabs, lang, mode, page_dir):
    lines = []
    if mode == "referenced":
        access = f"（最終確認: {meta['dateAccessed']}）" if meta.get("dateAccessed") else ""
        collection = meta.get("sourceCollection")
        site = (f"「{localized(collection['name'], lang)}」" if collection else "外部サイト")
        body = [f"教材本体は{site}にあります: <{meta['externalUrl']}>{access}"]
        if meta.get("archivedAt"):
            body.append(f"リンク切れの際は [Web アーカイブのスナップショット]({meta['archivedAt']}) を"
                        "参照してください。")
        lines += callout("important", f"外部教材の目録エントリ — {site}", body)

    terms = meta.get("usageTerms")
    if terms:
        kind = "warning" if terms["reuse"] in ("not_allowed", "unspecified") else "note"
        lines += callout(kind, REUSE_LABEL[terms["reuse"]],
                         [f"{localized(terms['summary'], lang)}"
                          f"（[利用条件の原文]({terms['url']})）"])

    # 概要はタイトル直下 (front matter の description) に全文が出るので本文には書かない。
    # 検索インデックスへは build_catalog.py が別途追記する
    # 内容紹介の出所を明示する。AI 生成なら誰が確認したかと確からしさまで示す
    provenance = meta.get("metadataProvenance") or {}
    if provenance.get("method") in ("ai_generated", "ai_assisted"):
        verb = "生成" if provenance["method"] == "ai_generated" else "作成支援"
        origin = f"上の内容紹介は AI（{provenance.get('generator', 'モデル不明')}）が{verb}したものです"
        reviewers = provenance.get("reviewedBy") or []
        origin += f"。{'、'.join(reviewers)}が確認済み" if reviewers else "（未確認）"
        if provenance.get("confidence") == "low":
            lines += callout("caution", "内容紹介の確からしさ: 低",
                             [f"{origin}。もとになる情報が少ないため、正確な内容は"
                              + ("下の引用と" if meta.get("quotedDescription") else "")
                              + "教材本体で確認してください。"], collapse=False)
        else:
            lines += callout("note", "内容紹介の出所（AI 生成）",
                             [f"{origin}。教材そのものの文章ではありません。"
                              + ("原文は下の引用を参照してください。"
                                 if meta.get("quotedDescription") else "")],
                             collapse=True, minimal=True)

    quoted = meta.get("quotedDescription")
    if quoted:
        text = quoted["text"]
        values = [text] if isinstance(text, str) else list(text.values())
        # 見出しを付ける。Quarto の検索インデックスは見出し単位で作られるため、
        # 見出しの無い引用ブロックは索引に入らない（要約が短い分ここが効く）
        lines += ["## 出典サイトの説明（原文）", ""]
        for value in values:
            lines += [f"> {l}" for l in value.strip().splitlines()]
            lines.append(">")
        source_label = quoted.get("note") or "出典サイトの説明"
        lines += [f"> — {source_label}: <{quoted['source']}>", ""]

    rows = []

    def add(label, value):
        if value:
            rows.append(f"| {label} | {value} |")

    collection = meta.get("sourceCollection")
    if collection:
        label = localized(collection["name"], lang)
        add("出典サイト", f"[{label}]({collection['url']})" if collection.get("url") else label)
    add("教材タイプ", "、".join(concept_labels(meta, "learningResourceType", vocabs, lang)))
    add("主題分野", "、".join(concept_labels(meta, "about", vocabs, lang)))
    add("教育段階", "、".join(concept_labels(meta, "educationalLevel", vocabs, lang)))
    add("想定利用者", "、".join(concept_labels(meta, "audience", vocabs, lang)))
    add("言語", "、".join(meta.get("inLanguage", [])))
    add("標準学習時間", duration_label(meta.get("timeRequired", "")))
    add("再生時間", duration_label(meta.get("duration", "")))
    if meta.get("license"):
        add("ライセンス", f"[{license_label(meta['license'])}]({expand_license(meta['license'])})")
    terms = meta.get("usageTerms")
    if terms:
        add("利用条件", f"[{REUSE_LABEL[terms['reuse']]}]({terms['url']})")
    add("公開日", meta.get("datePublished"))
    add("更新日", meta.get("dateModified"))
    add("版", meta.get("version"))
    lines += ["## 基本情報", "", "| 項目 | 内容 |", "|------|------|", *rows, ""]

    # キーワードは検索インデックスに効く（要約が短い分をここで補う）
    if meta.get("keywords"):
        lines += ["## キーワード", "、".join(meta["keywords"]), ""]

    if meta.get("teaches"):
        lines.append("## 学習目標")
        lines += [f"- {text_item(t, lang)}" for t in meta["teaches"]]
        lines.append("")
    if meta.get("competencyRequired"):
        lines.append("## 前提知識")
        lines += [f"- {text_item(t, lang)}" for t in meta["competencyRequired"]]
        lines.append("")

    if mode == "hosted":
        content_dir = page_dir / "content"
        if content_dir.is_dir():
            lines.append("## コンテンツ")
            for f in sorted(content_dir.rglob("*")):
                if f.is_file() and not f.name.startswith("."):
                    rel = f.relative_to(page_dir)
                    lines.append(f"- [{rel}]({rel})")
            lines.append("")
    else:
        button = (f"[教材本体を開く]({meta['externalUrl']}){{.btn .btn-primary}}"
                  if ENGINE == "quarto" else f"[教材本体を開く]({meta['externalUrl']})")
        lines += ["## 教材へのアクセス", button, ""]

    if meta.get("materials"):
        lines.append("## 教材ファイル")
        if mode == "referenced":
            lines.append("リンク先は外部サイト。利用は上記のライセンス・利用条件に従ってください。")
            lines.append("")
        for material in meta["materials"]:
            ext = material["contentUrl"].rsplit(".", 1)[-1].upper() if "." in material["contentUrl"] else ""
            suffix = f"（{ext}）" if ext and len(ext) <= 5 else ""
            lines.append(f"- [{material['name']}]({material['contentUrl']}){suffix}")
        lines.append("")

    if meta.get("attributions"):
        lines.append("## 収録している第三者素材")
        for att in meta["attributions"]:
            item = f"- 「{att['title']}」"
            extras = [x for x in (att.get("author"), att.get("license")) if x]
            if extras:
                item += f"（{'、'.join(extras)}）"
            if att.get("source"):
                item += f" — <{att['source']}>"
            if att.get("note"):
                item += f" ※{att['note']}"
            lines.append(item)
        lines.append("")

    cite_url = meta["externalUrl"] if mode == "referenced" else f"{config['base_url']}/r/{slug}"
    lines += ["## 引用・帰属表示の例", "```", tasl_line(meta, cite_url, config, lang), "```", ""]

    lines.append("## このメタデータについて")
    # サブパス配信 (GitHub Pages の user.github.io/repo/ 等) でも壊れないよう絶対URLにする
    lines.append("- メタデータは [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) で"
                 f"提供します（[JSON-LD]({config['base_url']}/jsonld/{slug}.json)）。")
    if provenance:
        detail = PROVENANCE_METHOD_LABEL.get(provenance.get("method"), provenance.get("method", ""))
        if provenance.get("generator"):
            detail += f"／使用モデル: {provenance['generator']}"
        if provenance.get("generatedDate"):
            detail += f"／作成日: {provenance['generatedDate']}"
        if provenance.get("confidence"):
            detail += f"／確からしさ: {'低（要確認）' if provenance['confidence'] == 'low' else '通常'}"
        if provenance.get("reviewedBy"):
            detail += f"／レビュー: {'、'.join(provenance['reviewedBy'])}"
        lines.append(f"- 作成方法: {detail}")
    for u in meta.get("isBasedOn", []) or []:
        lines.append(f"- 改変元: <{u}>")
    if config.get("feedback_url"):
        lines.append(f"- 誤りにお気づきの場合は[こちらから報告]({config['feedback_url']})して"
                     "ください。確認のうえ訂正します。")
    return "\n".join(lines) + "\n"


def render_site_config(config, engine):
    names = {"quarto": ("_quarto.in.yml", "_quarto.yml"),
             "hugo": ("hugo.in.yaml", "hugo.yaml")}[engine]
    template = (SITE_SRC / names[0]).read_text(encoding="utf-8")
    out = (template.replace("{{site_name}}", config["site_name"])
           .replace("{{base_url}}", config["base_url"])
           .replace("{{lang}}", config["primary_language"])
           .replace("{{feedback_url}}", config.get("feedback_url", "")))
    (SITE_SRC / names[1]).write_text(out, encoding="utf-8")


def main() -> int:
    global ENGINE
    config = load_config()
    ENGINE = config["site_engine"]
    vocabs = load_all_vocabs(config)
    render_site_config(config, ENGINE)

    out_dir = R_DIR if ENGINE == "quarto" else HUGO_R_DIR
    if out_dir.exists():
        shutil.rmtree(out_dir)

    count = 0
    for slug, resource_dir, meta in iter_resources():
        lang = meta["inLanguage"][0]
        mode = meta.get("mode", "hosted")
        page_dir = out_dir / slug
        page_dir.mkdir(parents=True)

        if mode == "hosted":
            for sub in ("content", "assets"):
                src = resource_dir / sub
                if src.is_dir():
                    shutil.copytree(src, page_dir / sub)

        doc = build_jsonld(slug, meta, config, vocabs)
        front = {"title": localized(meta["name"], lang)}
        authors = agent_names(meta.get("creator"), lang)
        if authors:
            front["author"] = authors
        if meta.get("datePublished"):
            # 年のみ・年月のみの日付を 1月1日 に補完して表示しない（精度を捏造しない。§5.2）
            published = str(meta["datePublished"])
            if ENGINE == "quarto":
                front["date"] = published
                front["date-format"] = {4: "YYYY年", 7: "YYYY年M月"}.get(len(published),
                                                                        "YYYY年M月D日")
            else:
                # Hugo の date は完全な日付のみ。粒度つき表示文字列を params で渡す
                if len(published) == 10:
                    front["date"] = published
                    front["dateDisplay"] = published
                elif len(published) == 7:
                    year, month = published.split("-")
                    front["dateDisplay"] = f"{year}年{int(month)}月"
                else:
                    front["dateDisplay"] = f"{published}年"
        # カタログ一覧では Quarto が自動で切り詰めるので、ここでは全文を渡す
        front["description"] = re.sub(r"\s+", " ", localized(meta["description"], lang)).strip()
        categories = (concept_labels(meta, "learningResourceType", vocabs, lang)
                      + concept_labels(meta, "about", vocabs, lang)
                      + concept_labels(meta, "educationalLevel", vocabs, lang))
        if meta.get("usageTerms"):
            categories.append(REUSE_CATEGORY[meta["usageTerms"]["reuse"]])
        # サイト名をカテゴリの先頭に置き、カタログでサイト別に絞り込めるようにする
        if meta.get("sourceCollection"):
            categories.insert(0, localized(meta["sourceCollection"]["name"], lang))
            # 個人公開はまとめて絞り込めるようにする (個人サイトはサイト数が多く1件ずつのため)
            if meta["sourceCollection"].get("kind") == "personal":
                categories.insert(1, "個人公開")
        if categories:
            front["categories"] = categories
        image = meta.get("image")
        if image and (image.startswith("http") or (page_dir / image).exists()):
            front["image"] = image
        if ENGINE == "quarto":
            front["format"] = {"html": {"include-in-header": {"text": jsonld_script(doc)}}}
            filename = "index.qmd"
        else:
            # レイアウト (partials/head.html) が params.jsonld を <head> に埋め込む
            front["jsonld"] = json.dumps(doc, ensure_ascii=False).replace("</", "<\\/")
            filename = "index.md"

        body = build_body(slug, meta, config, vocabs, lang, mode, page_dir)
        page = ("---\n"
                + yaml.safe_dump(front, allow_unicode=True, sort_keys=False, width=1000)
                + "---\n\n" + body)
        (page_dir / filename).write_text(page, encoding="utf-8")
        count += 1

    next_step = "quarto render site" if ENGINE == "quarto" else "make render (hugo)"
    print(f"{count} 件のページ → {out_dir}/  (次: {next_step})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
