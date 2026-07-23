"""名大の授業 (NU OCW) のコースページパーサ。

レンダリング済み HTML (fetch.py --engine playwright のキャッシュ) を前提とする。
ページ構造 (2026-07 時点): 講師 / 開講部局 / YYYY年度 学期 / 対象者 / タグ /
授業の内容・講義の概要・講義の内容・課題・スケジュール・講義ノート 等のセクション。
"""

from __future__ import annotations

import html as html_module
import re
from urllib.parse import urljoin

from extract import _page_label, visible_lines

SECTION_LABELS = [
    "授業の内容", "授業の概要", "授業の工夫", "講義の名称", "講義の概要", "講義の内容",
    "授業のねらい", "講義目的", "授業の目的", "到達目標", "授業計画", "教科書", "参考書",
    "参考資料", "課題", "スケジュール", "講義ノート", "成績評価", "履修条件", "その他",
]

# quotedDescription に採る見出し (この順に最大2つ)。SECTION_LABELS のうち
# 説明として通用するものだけを選ぶ。「授業の目的」「講義目的」は当初漏れており、
# 目的を明記した授業157件が引用なしになっていた
QUOTE_LABELS = ("講義の概要", "授業の概要", "授業の目的", "講義目的", "授業のねらい",
                "講義の内容", "授業の内容", "到達目標")

MATERIAL_SECTION_WORDS = ("講義ノート", "課題", "スライド", "配布資料", "参考資料", "レポート")

# サイト共通の案内文。説明文ではないので引用に使わない
SITE_BOILERPLATE = re.compile(
    r"Nagoya University OpenCourseWare|「名大の授業」|NUOCW\s*では|"
    r"名古屋大学で行われている講義の教材")

# og:description の末尾に付く省略記号 (" ...." / "…")。引用が原文と一致しなくなるため落とす
TRAILING_ELLIPSIS = re.compile(r"[\s　]*(?:\.{2,}|…+|・{3,})[\s　]*$")

# 説明文でなく見出し・ナビゲーションの羅列を弾くための語
NAVIGATION_WORDS = ("履修に必要な知識", "履修の際のアドバイス", "授業の進め方", "講義の進め方",
                    "達成目標", "バックグラウンドとなる科目", "授業内容", "テキスト",
                    "本講座の目的およびねらい", "実験資料", "開講部局", "対象者")


def _is_prose(text: str) -> bool:
    """散文の説明か、見出しの羅列かを判定する。"""
    if SITE_BOILERPLATE.search(text):
        return False
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 30:
        return False
    # 句点がなく、見出し語が並ぶだけのものは説明文ではない
    sentences = compact.count("。") + compact.count("．") + len(re.findall(r"[.!?]\s", text))
    nav_hits = sum(1 for w in NAVIGATION_WORDS if w in text)
    if sentences == 0 and nav_hits >= 1:
        return False
    if sentences == 0 and len(compact) < 80:
        return False
    return True

TITLE_SUFFIX = re.compile(r"[-‐−ー]((?:19|20)\d{2})$")
ACADEMIC_TITLE = re.compile(r"[ 　]*(特任|客員|名誉|招へい)?(教授|准教授|講師|助教授|助教|助手)$")

# 開講部局 → 主題分野 (ISCED-F ベースの vocabularies/subjects.yaml キー)。レビューで要確認
# 上から順に部分一致で判定する。特定分野の学部ではない組織 (教養教育院・附属学校・
# 社会連携) を先に置く — 「教養教育院」が「教育」に一致して education になる事故を防ぐ
# (実測で126件が誤分類)。ISCED-F の generic は大学の教養科目群に対応する
FACULTY_SUBJECT = [
    ("教養教育", "generic"), ("附属", "generic"), ("社会連携", "generic"),
    ("情報", "ict"), ("工学", "engineering"), ("環境", "engineering"),
    ("法学", "business_law"), ("経済", "social_sciences"), ("国際開発", "social_sciences"),
    ("教育学", "education"), ("教育発達", "education"),
    ("医学", "health_welfare"), ("創薬", "health_welfare"),
    ("農学", "agriculture"), ("理学", "natural_sciences_math"), ("数理", "natural_sciences_math"),
    ("文学", "arts_humanities"), ("人文", "arts_humanities"), ("言語文化", "arts_humanities"),
]


def _find_line(lines, label):
    try:
        return lines.index(label)
    except ValueError:
        return None


def _collect_until(lines, start, stop_labels, max_lines=6):
    out = []
    for line in lines[start:start + max_lines]:
        if line in stop_labels or line == "(":
            break
        out.append(line)
    return out


def _sections(lines):
    """セクション見出し行 → 次の見出しまでの本文、の辞書。"""
    indices = [(i, line) for i, line in enumerate(lines) if line in SECTION_LABELS]
    sections = {}
    for pos, (i, label) in enumerate(indices):
        end = indices[pos + 1][0] if pos + 1 < len(indices) else len(lines)
        body = "\n".join(lines[i + 1:end]).strip()
        if body and label not in sections:
            sections[label] = body
    return sections


def _materials(html, url):
    """ファイルリンクを、直前のセクション語 (講義ノート/課題 等) を接頭辞にして列挙。"""
    label_positions = [(m.start(), m.group(1))
                       for m in re.finditer(r">\s*(" + "|".join(MATERIAL_SECTION_WORDS) + r")\s*<", html)]
    out, seen = [], set()
    for m in re.finditer(
            r'<a[^>]+href="([^"]+\.(?:pdf|pptx?|docx?|xlsx?|zip|mp4|mp3|ipynb|csv)[^"]*)"[^>]*>(.*?)</a>',
            html, re.S | re.I):
        content_url = urljoin(url, html_module.unescape(m.group(1)))
        if content_url in seen:
            continue
        seen.add(content_url)
        text = re.sub(r"\s+", " ",
                      html_module.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        section = ""
        for pos, label in label_positions:
            if pos < m.start():
                section = label
        name = f"{section}: {text}" if section and section not in text else (text or content_url.rsplit("/", 1)[-1])
        out.append({"name": name[:120], "contentUrl": content_url})
    return out


def parse_course(html: str, url: str):
    """コースページ → フィールド辞書。コースページでない場合は None。"""
    lines = visible_lines(html)
    i_lecturer = _find_line(lines, "講師")
    i_faculty = _find_line(lines, "開講部局")
    if i_faculty is None:
        return None

    title = _page_label(html)
    year_match = TITLE_SUFFIX.search(title)
    name_ja = TITLE_SUFFIX.sub("", title).strip() or title

    lecturers = []
    if i_lecturer is not None and i_lecturer < i_faculty:
        for line in lines[i_lecturer + 1:i_faculty]:
            person = ACADEMIC_TITLE.sub("", line).strip()
            if person and len(person) <= 30:
                lecturers.append(person)

    faculty = lines[i_faculty + 1] if i_faculty + 1 < len(lines) else ""
    year = term = None
    for line in lines[i_faculty + 1:i_faculty + 4]:
        m = re.match(r"((?:19|20)\d{2})年度\s*(.*)", line)
        if m:
            year, term = m.group(1), m.group(2).strip()
            break
    if not year and year_match:
        year = year_match.group(1)
    if not year:
        # URL 末尾の年度 (例: .../0846-...-2022/) → 和暦表記 (平成30年度) の順に拾う
        m = re.search(r"-((?:19|20)\d{2})/?$", url)
        if m:
            year = m.group(1)
        else:
            m = re.search(r"平成(\d{1,2})年度", title)
            if m:
                year = str(1988 + int(m.group(1)))

    i_target = _find_line(lines, "対象者")
    target = " ".join(_collect_until(lines, i_target + 1, {"タグ", *SECTION_LABELS}, 3)) if i_target is not None else ""

    i_tags = _find_line(lines, "タグ")
    tags = []
    if i_tags is not None:
        tags = [t for t in _collect_until(lines, i_tags + 1, set(SECTION_LABELS), 8)
                if len(t) <= 20 and not t.startswith("(")]

    sections = _sections(lines)
    quoted_parts, quoted_labels = [], []
    # 概要 → 目的 → 内容 の順に採る。「目的」を書いている授業はそれが最も的確な
    # 説明なので、要約に頼らず原文をそのまま見せる (レビューでの指摘に基づく)
    for label in QUOTE_LABELS:
        if label in sections and len(sections[label]) >= 20:
            quoted_parts.append(sections[label])
            quoted_labels.append(label)
        if len(quoted_parts) >= 2:
            break

    # セクションに説明が無い講義 (例: 民法II) は og:description へフォールバック。
    # サイト共通の定型文 (和文・英文とも) は説明ではないので使わない
    if not quoted_parts:
        m = re.search(r'property="og:description"[^>]*content="([^"]*)"', html) or \
            re.search(r'content="([^"]*)"[^>]*property="og:description"', html)
        og = html_module.unescape(m.group(1)).strip() if m else ""
        # og:description は本文を途中で切って省略記号 (" ....") を付す。
        # そのままだと原文と一致しない引用になるので、末尾の省略記号を落とす
        # (残る部分は原文どおりなので verbatim 検査を通る)
        og = TRAILING_ELLIPSIS.sub("", og).strip()
        if len(og) >= 30 and not SITE_BOILERPLATE.search(og):
            quoted_parts.append(og)
            quoted_labels.append("og:description")

    quoted_parts = [p for p in quoted_parts if _is_prose(p)]
    quoted_labels = quoted_labels[:len(quoted_parts)]

    name_en = None
    named = sections.get("講義の名称", "")
    m = re.search(r"[（(]([A-Za-z][^）)]{3,80})[）)]", named)
    if m:
        name_en = m.group(1).strip()

    all_text = " ".join(sections.values())
    languages = ["ja", "en"] if re.search(r"主として英語|英語で行|英語を用い|in English", all_text) else ["ja"]

    materials = _materials(html, url)

    resource_types = ["course"]
    if any("講義ノート" in m["name"] for m in materials) or "講義ノート" in sections:
        resource_types.append("script")
    if any("課題" in m["name"] for m in materials) or "課題" in sections:
        resource_types.append("assessment")
    if any("スライド" in m["name"] for m in materials):
        resource_types.append("slide")

    about = "generic"
    for keyword, subject in FACULTY_SUBJECT:
        if keyword in faculty:
            about = subject
            break

    level = None
    if target:
        level = "master" if re.search(r"大学院|研究科|博士|修士", target) else "bachelor"

    return {
        "name_ja": name_ja,
        "name_en": name_en,
        "lecturers": lecturers,
        "faculty": faculty,
        "year": year,
        "term": term,
        "target": target,
        "tags": tags,
        "quoted": "\n".join(quoted_parts),
        "quoted_labels": quoted_labels,
        "inLanguage": languages,
        "materials": materials,
        "learningResourceType": resource_types,
        "about": about,
        "educationalLevel": level,
    }
