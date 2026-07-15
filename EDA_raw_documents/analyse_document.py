import re
import pdfplumber

def split_sentence(text):
    """Split text extracted into sentences."""
    return [s for s in re.split(r'[.!?;]+', text) if s.strip()]

def split_word(text):
    """Split text extracted into words."""
    return text.split()

def analyze_document(document_path):
    """
    This function returns a dictionary of information about a PDF document:
        - Number of pages.
        - Number of words.
        - Number of sentences.
        - Average words per sentence.
        - Type of PDF (text, scan, mixed).
        - Scanned page numbers.
    """
    num_of_word = 0
    num_of_sentence = 0
    scanned_page = []

    with pdfplumber.open(document_path) as pdf:
        num_of_page = len(pdf.pages)

        for page in pdf.pages:
            text = page.extract_text() 

            # Check if the PDF is scanned or mixed; heuristic: < 20 characters
            if text is None or len(text.strip()) < 20:
                scanned_page.append(page.page_number)
                continue

            num_of_word += len(split_word(text))
            num_of_sentence += len(split_sentence(text))

    # Calculate average words per sentence
    avg_word_per_sentence = 0
    if num_of_sentence > 0:
        avg_word_per_sentence = num_of_word / num_of_sentence

    # Determine the type of PDF based on scanned pages
    if len(scanned_page) == 0:
        pdf_type = "text"
    elif len(scanned_page) == num_of_page:
        pdf_type = "scan"
    else:
        pdf_type = "mixed"

    return {
        "document_path": document_path,
        "num_word": num_of_word,
        "num_sentence": num_of_sentence,
        "num_page": num_of_page,
        "scanned_page": scanned_page,
        "avg_word_per_sentence": round(avg_word_per_sentence, 2), 
        "pdf_type": pdf_type
    }