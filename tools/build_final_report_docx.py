#!/usr/bin/env python3
"""Build a redacted Vietnamese Word report from the final Markdown draft.

This intentionally uses only Python's standard library.  It supports the
restricted Markdown vocabulary used by docs/final-report-draft.md and writes a
standards-compliant Office Open XML package without reading any secret files or
runtime result bodies.
"""

from __future__ import annotations

import argparse
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
DC = "http://purl.org/dc/elements/1.1/"
DCTERMS = "http://purl.org/dc/terms/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

for prefix, uri in {"w": W, "r": R, "dc": DC, "dcterms": DCTERMS, "xsi": XSI}.items():
    ET.register_namespace(prefix, uri)


def qn(name: str) -> str:
    return f"{{{W}}}{name}"


def rqn(name: str) -> str:
    return f"{{{R}}}{name}"


def w_element(name: str, **attrs: str) -> ET.Element:
    return ET.Element(qn(name), {qn(key): value for key, value in attrs.items()})


def add_text(parent: ET.Element, text: str, *, bold: bool = False, italic: bool = False,
             code: bool = False) -> None:
    if not text:
        return
    run = ET.SubElement(parent, qn("r"))
    if bold or italic or code:
        props = ET.SubElement(run, qn("rPr"))
        if bold:
            ET.SubElement(props, qn("b"))
        if italic:
            ET.SubElement(props, qn("i"))
        if code:
            ET.SubElement(props, qn("rFonts"), {qn("ascii"): "Consolas", qn("hAnsi"): "Consolas"})
            ET.SubElement(props, qn("sz"), {qn("val"): "18"})
            ET.SubElement(props, qn("shd"), {qn("val"): "clear", qn("fill"): "F2F2F2"})
    text_node = ET.SubElement(run, qn("t"))
    if text[:1].isspace() or text[-1:].isspace():
        text_node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text_node.text = text


def add_inline(parent: ET.Element, text: str) -> None:
    """Write the bold, italic and inline-code syntax used by the report."""
    token = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)")
    position = 0
    for match in token.finditer(text):
        add_text(parent, text[position:match.start()])
        value = match.group(0)
        if value.startswith("**"):
            add_text(parent, value[2:-2], bold=True)
        elif value.startswith("`"):
            add_text(parent, value[1:-1], code=True)
        else:
            add_text(parent, value[1:-1], italic=True)
        position = match.end()
    add_text(parent, text[position:])


def paragraph(style: str | None = None, *, page_break_before: bool = False,
              bottom_border: bool = False, alignment: str | None = None) -> ET.Element:
    node = w_element("p")
    props = ET.SubElement(node, qn("pPr"))
    if style:
        ET.SubElement(props, qn("pStyle"), {qn("val"): style})
    if page_break_before:
        ET.SubElement(props, qn("pageBreakBefore"))
    if alignment:
        ET.SubElement(props, qn("jc"), {qn("val"): alignment})
    if bottom_border:
        borders = ET.SubElement(props, qn("pBdr"))
        ET.SubElement(borders, qn("bottom"), {
            qn("val"): "single", qn("sz"): "6", qn("space"): "1", qn("color"): "808080"
        })
    return node


def add_page_break(body: ET.Element) -> None:
    node = paragraph()
    run = ET.SubElement(node, qn("r"))
    ET.SubElement(run, qn("br"), {qn("type"): "page"})
    body.append(node)


def add_list_item(body: ET.Element, text: str, *, numbered: bool) -> None:
    node = paragraph("ListParagraph")
    props = node.find(qn("pPr"))
    num_props = ET.SubElement(props, qn("numPr"))
    ET.SubElement(num_props, qn("ilvl"), {qn("val"): "0"})
    ET.SubElement(num_props, qn("numId"), {qn("val"): "1" if numbered else "2"})
    add_inline(node, text)
    body.append(node)


def add_code_block(body: ET.Element, lines: list[str], *, mermaid: bool = False) -> None:
    for index, line in enumerate(lines):
        node = paragraph("Diagram" if mermaid else "CodeBlock")
        if index == 0:
            props = node.find(qn("pPr"))
            spacing = ET.SubElement(props, qn("spacing"))
            spacing.set(qn("before"), "80")
        add_text(node, line or " ", code=True)
        body.append(node)


def cell_text(cell: str) -> str:
    return cell.strip().replace(r"\|", "|")


def add_table(body: ET.Element, rows: list[list[str]]) -> None:
    table = w_element("tbl")
    properties = ET.SubElement(table, qn("tblPr"))
    ET.SubElement(properties, qn("tblW"), {qn("w"): "0", qn("type"): "auto"})
    borders = ET.SubElement(properties, qn("tblBorders"))
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        ET.SubElement(borders, qn(edge), {qn("val"): "single", qn("sz"): "4", qn("color"): "A6A6A6"})
    grid = ET.SubElement(table, qn("tblGrid"))
    width = max((len(row) for row in rows), default=1)
    for _ in range(width):
        ET.SubElement(grid, qn("gridCol"), {qn("w"): str(9000 // width)})

    for row_index, row in enumerate(rows):
        tr = ET.SubElement(table, qn("tr"))
        for column in range(width):
            tc = ET.SubElement(tr, qn("tc"))
            tc_props = ET.SubElement(tc, qn("tcPr"))
            if row_index == 0:
                ET.SubElement(tc_props, qn("shd"), {qn("val"): "clear", qn("fill"): "D9EAF7"})
            cell_para = paragraph("TableText")
            add_inline(cell_para, cell_text(row[column]) if column < len(row) else "")
            tc.append(cell_para)
    body.append(table)


def split_table_row(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [item.strip() for item in re.split(r"(?<!\\)\|", stripped)]


def is_table_divider(line: str) -> bool:
    fields = split_table_row(line)
    return bool(fields) and all(re.fullmatch(r":?-{3,}:?", field.strip()) for field in fields)


def parse_markdown(source: str) -> list[tuple[str, object]]:
    """Convert the report's intentionally small Markdown dialect to block data."""
    lines = source.splitlines()
    blocks: list[tuple[str, object]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            index += 1
            code: list[str] = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            if index >= len(lines):
                raise ValueError("Unclosed fenced block in Markdown source")
            blocks.append(("mermaid" if language == "mermaid" else "code", code))
            index += 1
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            blocks.append(("heading", (len(heading.group(1)), heading.group(2).strip())))
            index += 1
            continue
        if line.strip() == "---":
            blocks.append(("rule", None))
            index += 1
            continue
        if line.startswith("> "):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].startswith("> "):
                quote_lines.append(lines[index][2:])
                index += 1
            blocks.append(("quote", " ".join(quote_lines)))
            continue
        if "|" in line and line.strip().startswith("|") and index + 1 < len(lines) and is_table_divider(lines[index + 1]):
            table_rows = [split_table_row(line)]
            index += 2
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_rows.append(split_table_row(lines[index]))
                index += 1
            blocks.append(("table", table_rows))
            continue
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered:
            items: list[str] = []
            while index < len(lines):
                candidate = re.match(r"^\d+\.\s+(.+)$", lines[index])
                if not candidate:
                    break
                items.append(candidate.group(1))
                index += 1
            blocks.append(("ordered", items))
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(lines[index][2:])
                index += 1
            blocks.append(("bullet", items))
            continue
        paragraph_lines = [line.strip()]
        index += 1
        while index < len(lines):
            next_line = lines[index]
            if (not next_line.strip() or next_line.startswith("#") or next_line.startswith("```")
                    or next_line.startswith("> ") or next_line.strip() == "---"
                    or next_line.startswith("- ") or re.match(r"^\d+\.\s+", next_line)
                    or (next_line.strip().startswith("|") and index + 1 < len(lines) and is_table_divider(lines[index + 1]))):
                break
            paragraph_lines.append(next_line.strip())
            index += 1
        blocks.append(("paragraph", " ".join(paragraph_lines)))
    return blocks


def styles_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="{W}">
  <w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman" w:eastAsia="Times New Roman" w:cs="Times New Roman"/><w:lang w:val="vi-VN" w:eastAsia="vi-VN"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/><w:rPr><w:sz w:val="26"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:jc w:val="center"/><w:spacing w:after="360"/></w:pPr><w:rPr><w:b/><w:color w:val="1F4E79"/><w:sz w:val="36"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="360" w:after="180"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="1F4E79"/><w:sz w:val="30"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="300" w:after="140"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="2F75B5"/><w:sz w:val="28"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="220" w:after="100"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:color w:val="3F3F3F"/><w:sz w:val="26"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720" w:right="360"/><w:spacing w:before="120" w:after="120"/></w:pPr><w:rPr><w:i/><w:color w:val="595959"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="CodeBlock"><w:name w:val="Code Block"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="360" w:right="360"/><w:spacing w:before="0" w:after="0"/><w:shd w:val="clear" w:fill="F2F2F2"/></w:pPr><w:rPr><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/><w:sz w:val="18"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="Diagram"><w:name w:val="Diagram"/><w:basedOn w:val="CodeBlock"/><w:pPr><w:jc w:val="center"/><w:ind w:left="0" w:right="0"/></w:pPr></w:style>
  <w:style w:type="paragraph" w:styleId="TableText"><w:name w:val="Table Text"/><w:basedOn w:val="Normal"/><w:pPr><w:spacing w:after="0" w:line="220" w:lineRule="auto"/></w:pPr><w:rPr><w:sz w:val="20"/></w:rPr></w:style>
  <w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr></w:style>
</w:styles>'''.encode("utf-8")


def numbering_xml() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="{W}">
 <w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
 <w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="singleLevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr><w:pPr><w:tabs><w:tab w:val="num" w:pos="720"/></w:tabs><w:ind w:left="720" w:hanging="360"/></w:pPr></w:lvl></w:abstractNum>
 <w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>
</w:numbering>'''.encode("utf-8")


def footer_xml() -> bytes:
    root = w_element("ftr")
    node = paragraph(alignment="center")
    add_text(node, "Báo cáo cuối kỳ — Kiểm thử Broken Access Control cho VAmPI local | Trang ")
    run = ET.SubElement(node, qn("r"))
    ET.SubElement(run, qn("fldChar"), {qn("fldCharType"): "begin"})
    ET.SubElement(run, qn("instrText")).text = " PAGE "
    ET.SubElement(run, qn("fldChar"), {qn("fldCharType"): "separate"})
    ET.SubElement(run, qn("t")).text = "1"
    ET.SubElement(run, qn("fldChar"), {qn("fldCharType"): "end"})
    root.append(node)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def toc_paragraph() -> ET.Element:
    node = paragraph("Heading1")
    add_text(node, "Mục lục")
    return node


def toc_field() -> ET.Element:
    node = paragraph()
    begin = ET.SubElement(node, qn("r"))
    ET.SubElement(begin, qn("fldChar"), {qn("fldCharType"): "begin", qn("dirty"): "true"})
    instruction = ET.SubElement(node, qn("r"))
    ET.SubElement(instruction, qn("instrText")).text = ' TOC \\o "1-3" \\h \\z \\u '
    separate = ET.SubElement(node, qn("r"))
    ET.SubElement(separate, qn("fldChar"), {qn("fldCharType"): "separate"})
    add_text(node, "Mở tài liệu trong Microsoft Word hoặc LibreOffice và cập nhật trường để tạo mục lục.", italic=True)
    end = ET.SubElement(node, qn("r"))
    ET.SubElement(end, qn("fldChar"), {qn("fldCharType"): "end"})
    return node


def make_document(markdown: str) -> bytes:
    document = w_element("document")
    body = ET.SubElement(document, qn("body"))
    blocks = parse_markdown(markdown)
    toc_inserted = False

    for kind, value in blocks:
        if kind == "heading":
            level, title = value  # type: ignore[misc]
            if level == 1:
                node = paragraph("Title", alignment="center")
                add_inline(node, title)
                body.append(node)
                continue
            if not toc_inserted and title == "Tóm tắt":
                add_page_break(body)
                body.append(toc_paragraph())
                body.append(toc_field())
                add_page_break(body)
                toc_inserted = True
            start_new_page = level == 2 and (title.startswith("Phần ") or title.startswith("Phụ lục") or title == "Tài liệu tham khảo")
            style = f"Heading{min(level - 1, 3)}"
            node = paragraph(style, page_break_before=start_new_page)
            add_inline(node, title)
            body.append(node)
        elif kind == "paragraph":
            node = paragraph()
            add_inline(node, value)  # type: ignore[arg-type]
            body.append(node)
        elif kind == "quote":
            node = paragraph("Quote")
            add_inline(node, value)  # type: ignore[arg-type]
            body.append(node)
        elif kind == "rule":
            body.append(paragraph(bottom_border=True))
        elif kind == "ordered":
            for item in value:  # type: ignore[union-attr]
                add_list_item(body, item, numbered=True)
        elif kind == "bullet":
            for item in value:  # type: ignore[union-attr]
                add_list_item(body, item, numbered=False)
        elif kind == "table":
            add_table(body, value)  # type: ignore[arg-type]
        elif kind == "code":
            add_code_block(body, value)  # type: ignore[arg-type]
        elif kind == "mermaid":
            label = paragraph("Quote", alignment="center")
            add_text(label, "Sơ đồ nguồn Mermaid (dạng văn bản; xem Markdown nguồn để render đồ họa).", italic=True)
            body.append(label)
            add_code_block(body, value, mermaid=True)  # type: ignore[arg-type]
        else:
            raise AssertionError(f"Unhandled Markdown block: {kind}")

    section = ET.SubElement(body, qn("sectPr"))
    ET.SubElement(section, qn("pgSz"), {qn("w"): "11906", qn("h"): "16838"})  # A4
    ET.SubElement(section, qn("pgMar"), {
        qn("top"): "1134", qn("right"): "1134", qn("bottom"): "1134", qn("left"): "1134",
        qn("header"): "567", qn("footer"): "567", qn("gutter"): "0"
    })
    ET.SubElement(section, qn("footerReference"), {qn("type"): "default", rqn("id"): "rId1"})
    return ET.tostring(document, encoding="utf-8", xml_declaration=True)


def content_types() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="xml" ContentType="application/xml"/>
 <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
 <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
 <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
 <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
 <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
 <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
</Types>'''


def package_rels() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
 <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
 <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def document_rels() -> bytes:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="{REL}">
 <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
 <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
 <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
</Relationships>'''.encode("utf-8")


def core_properties() -> bytes:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="{DC}" xmlns:dcterms="{DCTERMS}" xmlns:xsi="{XSI}">
 <dc:title>Báo cáo cuối kỳ — Kiểm thử Broken Access Control cho VAmPI local</dc:title>
 <dc:creator>VAmPI authorization-testing lab</dc:creator>
 <dc:subject>BOLA, BFLA và kiểm thử authorization có kiểm soát</dc:subject>
 <dc:description>Derived from docs/final-report-draft.md without secret evidence.</dc:description>
 <dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created>
 <dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified>
</cp:coreProperties>'''.encode("utf-8")


def app_properties() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
 <Application>VAmPI authorization report generator</Application><DocSecurity>0</DocSecurity><ScaleCrop>false</ScaleCrop>
 <HeadingPairs><vt:vector size="2" baseType="variant"><vt:variant><vt:lpstr>Title</vt:lpstr></vt:variant><vt:variant><vt:i4>1</vt:i4></vt:variant></vt:vector></HeadingPairs>
 <TitlesOfParts><vt:vector size="1" baseType="lpstr"><vt:lpstr>Document</vt:lpstr></vt:vector></TitlesOfParts>
 <Company></Company><LinksUpToDate>false</LinksUpToDate><SharedDoc>false</SharedDoc><HyperlinksChanged>false</HyperlinksChanged><AppVersion>1.0</AppVersion>
</Properties>'''


def build(source: Path, output: Path) -> None:
    markdown = source.read_text(encoding="utf-8")
    document = make_document(markdown)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types())
        archive.writestr("_rels/.rels", package_rels())
        archive.writestr("docProps/core.xml", core_properties())
        archive.writestr("docProps/app.xml", app_properties())
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles_xml())
        archive.writestr("word/numbering.xml", numbering_xml())
        archive.writestr("word/footer1.xml", footer_xml())
        archive.writestr("word/_rels/document.xml.rels", document_rels())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("docs/final-report-draft.md"))
    parser.add_argument("--output", type=Path, default=Path("docs/final-report-vampi-authz.docx"))
    args = parser.parse_args()
    build(args.source, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
