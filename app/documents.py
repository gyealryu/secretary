"""업로드한 파일에서 글자를 뽑아냅니다."""

import io
from pathlib import Path

TEXT_EXTS = {
    ".txt", ".md", ".csv", ".log", ".json", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".java", ".c", ".cpp", ".h", ".cs", ".go", ".sql", ".xml", ".yaml", ".yml",
}


class UnsupportedFile(Exception):
    pass


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext in TEXT_EXTS:
        return _decode(data)
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if ext == ".docx":
        import docx

        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts).strip()
    raise UnsupportedFile(f"지원하지 않는 파일 형식입니다: {ext or filename} (txt, md, pdf, docx, 코드 파일 지원)")
