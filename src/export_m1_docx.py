"""Build a Word .docx of the M1 memo from docs/M1_Data_Acquisition_Plan.md for upload."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "docs" / "M1_Data_Acquisition_Plan.md"
OUT = ROOT / "docs" / "BUA3336_M1_Doge_Defenders.docx"

NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def para(text: str, bold: bool = False) -> str:
    if not text.strip():
        return f'<w:p xmlns:w="{NS}"/>'
    runs = escape(text)
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return (
        f'<w:p xmlns:w="{NS}">'
        f"<w:r>{rpr}<w:t xml:space=\"preserve\">{runs}</w:t></w:r>"
        f"</w:p>"
    )


def md_to_paragraphs(md: str) -> list[str]:
    out: list[str] = []
    for line in md.splitlines():
        if line.startswith("|") and "---" in line:
            continue
        if line.startswith("#"):
            text = re.sub(r"^#+\s*", "", line).strip()
            out.append(para(text, bold=True))
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            out.append(para(" | ".join(cells)))
        elif line.strip() == "---":
            continue
        else:
            # strip light markdown
            text = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            text = re.sub(r"`([^`]+)`", r"\1", text)
            out.append(para(text))
    return out


def main() -> None:
    body = "\n".join(md_to_paragraphs(MD.read_text(encoding="utf-8")))
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="{NS}">
  <w:body>
    {body}
    <w:sectPr/>
  </w:body>
</w:document>
"""
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document_xml)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
