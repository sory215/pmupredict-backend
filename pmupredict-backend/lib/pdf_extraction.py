from pathlib import Path

import pdfplumber


def extract_pdf_text(pdf_path: str | Path) -> str:
    """Extract text from every page of a PDF using pdfplumber."""
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF introuvable: {path}")

    with pdfplumber.open(path) as pdf:
        return "\n\n".join(
            page.extract_text() or ""
            for page in pdf.pages
        ).strip()


def extract_pdf_pages(pdf_path: str | Path) -> list[dict]:
    """Extract page-by-page text for API/UI consumption."""
    path = Path(pdf_path)

    if not path.is_file():
        raise FileNotFoundError(f"PDF introuvable: {path}")

    with pdfplumber.open(path) as pdf:
        return [
            {
                "page": index,
                "text": page.extract_text() or "",
            }
            for index, page in enumerate(pdf.pages, start=1)
        ]
