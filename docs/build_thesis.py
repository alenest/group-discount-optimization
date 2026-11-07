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
    "ПОЛНЫЙ ПЕРЕБОР И ЖАДКИЕ АЛГОРИТМЫ ДЛЯ ОТБОРА РЕСУРСОВ "
    "С ПОРОГОВЫМИ ГРУППОВЫМИ СКИДКАМИ"
)

PARAGRAPHS = [
    (
        "Задачи отбора ресурсов в технико-экономических системах часто "
        "сводятся к выбору ровно <i>Q</i> объектов при ограничении суммарного веса или стоимости "
        "[1, 2]. В классической задаче о рюкзаке вклад объектов аддитивен, но в системах поставок "
        "действуют групповые скидки. Группа <i>k</i> с порогом <i>t</i><sub><i>k</i></sub> даёт "
        "скидку <i>d</i><sub><i>k</i></sub> и бонус <i>b</i><sub><i>k</i></sub>, если выбрано не "
        "меньше <i>t</i><sub><i>k</i></sub> её предметов; тогда учитываемые вес и полезность "
        "каждого предмета умножаются на (1 − <i>d</i><sub><i>k</i></sub>/100) и "
        "(1 + <i>b</i><sub><i>k</i></sub>/100). Порог делает вклад предмета зависимым от состава "
        "набора, поэтому ранжирование по удельному весу не гарантирует допустимости. "
        "Цель работы состоит в сравнении точного и жадных алгоритмов и оценке цены отказа от "
        "учёта групп."
    ),
    (
        "Полный перебор проверяет все <i>C</i>(<i>n</i>, <i>Q</i>) сочетаний и сохраняет лучший "
        "допустимый вариант. Он даёт точный оптимум, но требует "
        "<i>O</i>(<i>C</i>(<i>n</i>, <i>Q</i>)<i>n</i>) операций: при <i>n</i> = 25 и <i>Q</i> = 10 "
        "это 3 268 760 наборов, поэтому перебор применим как эталон на малых <i>n</i>. Базовый "
        "жадный алгоритм сортирует предметы по <i>u</i><sub><i>i</i></sub>/<i>w</i><sub><i>i</i></sub> "
        "и добавляет их с проверкой веса; сортировка занимает <i>O</i>(<i>n</i> log <i>n</i>), "
        "повторные проверки дают <i>O</i>(<i>n</i><sup>2</sup>). Жадный алгоритм с учётом групп "
        "сравнивает добавление предмета и группового пакета до порога, а также перебирает "
        "распределение <i>Q</i> мест по группам и правила ранжирования. Единый оценщик точно "
        "учитывает скидку и бонус. При <i>Q</i> = 10 "
        "и не более трёх группах число распределений невелико, а сложность остаётся "
        "квадратичной по <i>n</i>."
    ),
    (
        "Эксперименты проведены на 180 экземплярах для <i>n</i> от 12 до 100. Полный "
        "перебор запускался при <i>n</i> ≤ 25. Жадный алгоритм с учётом групп был допустим на всех "
        "180 экземплярах и совпал с оптимумом в 61 случае из 70, среднее отклонение 0.26%, "
        "максимум 5.93%. Базовый жадный метод по <i>u</i>/<i>w</i> был допустим в 92.8% "
        "случаев; на 57 допустимых экземплярах из 70 среднее отклонение составило 8.19%. Без "
        "групповых эффектов допустимы 127 из 180 решений (70.6%); там группы давали в среднем "
        "49% прироста полезности. Время перебора растёт с 0.002 с при <i>n</i> = 12 до 84 с при "
        "<i>n</i> = 25, жадный с учётом групп при <i>n</i> = 100 работает 0.41 с. Явный учёт "
        "порогов необходим, а его цена приемлема."
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
        "Полный перебор и жадные алгоритмы для отбора ресурсов "
        "с пороговыми групповыми скидками"
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
