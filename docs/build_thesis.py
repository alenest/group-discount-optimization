"""Сборка тезиса в формате А5 по требованиям МНТК.

Источник текста: docs/thesis.md. Результат: docs/thesis.docx.
PDF собирается командой:
    soffice --headless --convert-to pdf --outdir docs docs/thesis.docx
"""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

DOCS = Path(__file__).resolve().parent
OUT_DOCX = DOCS / "thesis.docx"

AUTHOR = "А.С. Нестеров, студ.; рук. Д.М. Емельянов, к.т.н., доц. (НИУ «МЭИ»)"
TITLE = (
    "ИССЛЕДОВАНИЕ ТОЧНЫХ И ПРИБЛИЖЕННЫХ АЛГОРИТМОВ ОТБОРА РЕСУРСОВ "
    "С УЧЕТОМ ГРУППОВЫХ БОНУСОВ И СКИДОК"
)

PARAGRAPHS = [
    (
        "Задачи отбора ресурсов возникают в технико-экономических системах, например "
        "в облачных вычислениях, где провайдеры дают многоуровневые скидки. Нужно выбрать ровно <i>Q</i> объектов при ограничении их суммарного веса "
        "или стоимости [1, 2]; предмет <i>i</i> имеет вес <i>w</i><sub><i>i</i></sub> и полезность "
        "<i>u</i><sub><i>i</i></sub>. В классической задаче о рюкзаке вклад выбранных объектов аддитивен, "
        "однако в реальных системах поставок зачастую действуют групповые скидки и бонусы. Группа <i>k</i> с порогом <i>t</i><sub><i>k</i></sub> "
        "предоставляет скидку <i>d</i><sub><i>k</i></sub> и бонус <i>b</i><sub><i>k</i></sub>, "
        "если выбрано не меньше <i>t</i><sub><i>k</i></sub> её предметов; в таком случае вес и полезность "
        "каждого выбранного из группы предмета умножаются на "
        "(1 − <i>d</i><sub><i>k</i></sub>/100) и (1 + <i>b</i><sub><i>k</i></sub>/100). "
        "Разные значения <i>t</i><sub><i>k</i></sub>, <i>d</i><sub><i>k</i></sub> и "
        "<i>b</i><sub><i>k</i></sub> усложняют постановку: классические алгоритмы теряют "
        "эффективность и не гарантируют допустимого решения. Цель работы — разработка и "
        "исследование эвристических жадных алгоритмов и сравнение с полным перебором."
    ),
    (
        "Полный перебор (ПП) перебирает все <i>C</i>(<i>N</i>, <i>Q</i>) сочетаний, применяет к "
        "ним бонусы и скидки и возвращает наилучший допустимый вариант. Он гарантирует точное "
        "решение, но требует <i>O</i>(<i>C</i>(<i>N</i>, <i>Q</i>)<i>N</i>) операций: для каждого "
        "сочетания за <i>O</i>(<i>N</i>) пересчитываются веса и полезности с учётом групп. При "
        "<i>N</i> = 25 и <i>Q</i> = 10 это 3 268 760 наборов, поэтому ПП применим как эталон "
        "при малых <i>N</i>. Классический жадный алгоритм (КЖ) сортирует предметы по убыванию "
        "<i>u</i><sub><i>i</i></sub>/<i>w</i><sub><i>i</i></sub> и добавляет их в рюкзак, пока "
        "позволяет вес; вычислительная сложность <i>O</i>(<i>N</i><sup>2</sup>). Разработанный жадный групповой алгоритм "
        "(ГЖ) на каждом шаге выбирает, что выгоднее — отдельный предмет или добрать группу до "
        "порога <i>t</i><sub><i>k</i></sub> ради скидки и бонуса, — и распределяет <i>Q</i> мест "
        "по группам; сложность ГЖ — <i>O</i>(<i>N</i><sup>2</sup>)."
    ),
    (
        "Эксперименты проведены на 180 сгенерированных задачах с <i>N</i> от 12 "
        "до 100; ПП запускался при <i>N</i> ≤ 25. ГЖ был допустим на всех 180 экземплярах, совпал "
        "с оптимумом в 61 случае из 70 и дал среднее отклонение 0.26% (максимум 5.93%). КЖ был "
        "допустим в 92.8% случаев, а на 57 экземплярах из 70 уступал оптимуму на 8.19%. "
        "Без групп допустимы 127 из 180 решений (70.6%), а группы дают 49% прироста полезности. Время работы: ПП — от 0.002 с при <i>N</i> = 12 до 84 с при "
        "<i>N</i> = 25, ГЖ — 0.41 с при <i>N</i> = 100."
    ),
]

REFERENCES = [
    (
        "Kellerer H., Pferschy U., Pisinger D.",
        " Knapsack Problems. Berlin: Springer, 2004.",
    ),
    (
        "Martello S., Toth P.",
        " Knapsack Problems: Algorithms and Computer Implementations. Chichester: Wiley, 1990.",
    ),
]

TAG_RE = re.compile(r"<(/?)(i|b|sub|sup)>")


def _set_run_font(run, size: float, *, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), "Times New Roman")


def _mark_script(run, kind: str) -> None:
    """Оформить индекс как 75% кегля со сдвигом, без автоматического уменьшения."""
    run.font.subscript = False
    run.font.superscript = False
    run.font.size = Pt(7.5)
    rpr = run._element.get_or_add_rPr()
    position = rpr.makeelement(qn("w:position"), {})
    position.set(qn("w:val"), "-4" if kind == "sub" else "6")
    rpr.append(position)


def _add_rich(paragraph, text: str, size: float) -> None:
    text = text.replace(" = ", "\u00a0=\u00a0").replace(" ≤ ", "\u00a0≤\u00a0")
    bold = italic = sub = sup = False
    pos = 0
    for match in TAG_RE.finditer(text):
        chunk = text[pos : match.start()]
        if chunk:
            run = paragraph.add_run(chunk)
            _set_run_font(run, size, bold=bold, italic=italic)
            if sub:
                _mark_script(run, "sub")
            elif sup:
                _mark_script(run, "sup")
        closing, tag = match.group(1), match.group(2)
        value = not closing
        if tag == "i":
            italic = value
        elif tag == "b":
            bold = value
        elif tag == "sub":
            sub = value
        else:
            sup = value
        pos = match.end()
    tail = text[pos:]
    if tail:
        run = paragraph.add_run(tail)
        _set_run_font(run, size, bold=bold, italic=italic)
        if sub:
            _mark_script(run, "sub")
        elif sup:
            _mark_script(run, "sup")


def _base_paragraph(document: Document, text: str, size: float = 10) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    fmt = paragraph.paragraph_format
    fmt.first_line_indent = Cm(0.5)
    fmt.space_before = Pt(0)
    fmt.space_after = Pt(0)
    fmt.line_spacing = 1.0
    _add_rich(paragraph, text, size)


def build() -> Path:
    document = Document()
    document.core_properties.title = (
        "Исследование точных и приближенных алгоритмов отбора ресурсов "
        "с учетом групповых бонусов и скидок"
    )
    document.core_properties.author = "А.С. Нестеров"
    document.core_properties.subject = "Тезисы МНТК, секция 14. Прикладная математика"
    section = document.sections[0]
    section.page_width = Cm(14.8)
    section.page_height = Cm(21.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)
    section.left_margin = Cm(1.7)
    section.right_margin = Cm(1.7)
    section.header_distance = Cm(1.0)
    section.footer_distance = Cm(1.0)

    normal = document.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(10)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.0

    authors = document.add_paragraph()
    authors.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    authors.paragraph_format.space_before = Pt(0)
    authors.paragraph_format.space_after = Pt(0)
    authors.paragraph_format.line_spacing = 1.0
    run = authors.add_run(AUTHOR)
    _set_run_font(run, 10, bold=True, italic=True)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(6)
    title.paragraph_format.line_spacing = 1.0
    run = title.add_run(TITLE)
    _set_run_font(run, 11, bold=True)

    for text in PARAGRAPHS:
        _base_paragraph(document, text)

    heading = document.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    heading.paragraph_format.space_before = Pt(0)
    heading.paragraph_format.space_after = Pt(0)
    heading.paragraph_format.line_spacing = 1.0
    run = heading.add_run("Литература")
    _set_run_font(run, 10, bold=True)

    for number, (authors_text, rest) in enumerate(REFERENCES, start=1):
        paragraph = document.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        fmt = paragraph.paragraph_format
        fmt.left_indent = Cm(0.5)
        fmt.first_line_indent = Cm(-0.5)
        fmt.space_before = Pt(0)
        fmt.space_after = Pt(0)
        fmt.line_spacing = 1.0
        run = paragraph.add_run(f"{number}. ")
        _set_run_font(run, 9)
        run = paragraph.add_run(authors_text)
        _set_run_font(run, 9, bold=True)
        run = paragraph.add_run(rest)
        _set_run_font(run, 9)

    document.save(OUT_DOCX)
    return OUT_DOCX


if __name__ == "__main__":
    print(build())
