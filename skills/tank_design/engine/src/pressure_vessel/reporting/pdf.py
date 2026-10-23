"""HTML -> PDF with PyMuPDF's Story engine, then a running header/footer
with "page X of N" added in a second pass. Returns the page count."""

from __future__ import annotations

from pathlib import Path

from .calc_report import CSS


def html_to_pdf(html: str, out_path, header: str, footer: str) -> int:
    try:
        import pymupdf
    except ImportError as exc:   # pragma: no cover - environment dependent
        raise RuntimeError("PDF output needs PyMuPDF (pip install pymupdf); the HTML report was still written") from exc
    import io
    out_path = Path(out_path)
    story = pymupdf.Story(html, user_css=CSS)
    page = pymupdf.paper_rect("a4")
    where = page + (42, 56, -42, -50)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    more = 1
    while more:
        dev = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
    n = doc.page_count
    for i, pg in enumerate(doc, 1):
        pg.insert_text((42, 34), header, fontsize=7.5, fontname="helv")
        pg.draw_line((42, 40), (page.width - 42, 40), width=0.5)
        pg.draw_line((42, page.height - 38), (page.width - 42, page.height - 38), width=0.5)
        pg.insert_text((42, page.height - 26), footer, fontsize=7, fontname="helv")
        pg.insert_text((page.width - 110, page.height - 26), f"Page {i} of {n}", fontsize=7.5, fontname="helv")
    doc.set_metadata({"title": header, "author": "pressure_vessel (automated, unreviewed)", "subject": footer})
    doc.save(str(out_path), garbage=3, deflate=True)
    doc.close()
    return n


def check_pdf(path, must_contain=()) -> dict:
    """Open the PDF again and confirm pages, text and the required strings."""
    import unicodedata

    import pymupdf
    doc = pymupdf.open(str(path))
    # NFKC folds the typographic ligatures (fi, ff) the PDF text layer contains
    text = unicodedata.normalize("NFKC", "".join(p.get_text() for p in doc))
    missing = [s for s in must_contain if s not in text]
    out = {"file": str(path), "pages": doc.page_count, "bytes": Path(path).stat().st_size,
           "missing_strings": missing, "ok": doc.page_count > 0 and not missing}
    doc.close()
    return out
