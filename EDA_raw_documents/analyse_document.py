import re
import pdfplumber

def split_sentence(text):
    """Split text into sentences.

    Uses lookahead: split after [.!?] when followed by whitespace + capital letter.
    Avoids false splits on abbreviations (Mr., e.g., U.S.A.) and decimals (3.14).
    """
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+(?=[A-Z])', text) if s.strip()]

def split_word(text):
    """Split text extracted into words."""
    return text.split()

def analyze_document(document_path):
    """
    Analyse a PDF document and return per-page text with statistics.

    Returns a dict with:
        - document_path: path to the PDF file.
        - num_page: total number of pages.
        - scanned_page: list of page numbers detected as scanned images.
        - pdf_type: 'text', 'scan', or 'mixed'.
        - pages: dict mapping page_number -> {text, char_count, word_count, sentence_count}.
    """
    scanned_page = []
    pages = {}

    with pdfplumber.open(document_path) as pdf:
        num_of_page = len(pdf.pages)

        for page in pdf.pages:
            text = page.extract_text() 

            # Check if the page is scanned or blank; heuristic: < 20 characters.
            if text is None or len(text.strip()) < 20:
                # Only flag as scanned if the page actually contains images.
                # Blank pages (no text, no images) are skipped — OCR won't help.
                if page.images:
                    scanned_page.append(page.page_number)
                continue

            words = split_word(text)
            sentences = split_sentence(text)

            # Store per-page text and stats for downstream merge.
            pages[page.page_number] = {
                "text": text,
                "char_count": len(text),
                "word_count": len(words),
                "sentence_count": len(sentences),
            }

    # Determine the type of PDF based on scanned pages.
    if len(scanned_page) == 0:
        pdf_type = "text"
    elif len(scanned_page) == num_of_page:
        pdf_type = "scan"
    else:
        pdf_type = "mixed"

    return {
        "document_path": document_path,
        "num_page": num_of_page,
        "scanned_page": scanned_page,
        "pdf_type": pdf_type,
        "pages": pages,
    }