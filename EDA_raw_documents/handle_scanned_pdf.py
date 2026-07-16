from paddleocr import PaddleOCR
import fitz
import numpy as np
import tqdm


class EngineOCR:
    def __init__(self, language = "en", device = "gpu"):
        self.ocr = PaddleOCR(lang = language, device = device, use_doc_orientation_classify = False, use_doc_unwarping = False, use_textline_orientation = False)

    def ocr_image(self, image):
        results = self.ocr.predict(image)

        page_lines = []
        confidences = []

        # Return a list of results, each result is a list of tuples (box, text, confidence).
        if results:
            for res in results:
                # Check if the result has recognized text and confidence scores.
                if hasattr(res, "rec_texts"):
                    texts = res.rec_texts
                    scores = res.rec_scores

                    page_lines.extend(texts)
                    confidences.extend(scores)

        avg_conf = 0.0
        if confidences:
            avg_conf = float(sum(confidences) / len(confidences))

        return {
            "text": " ".join(page_lines),
            "confidence": round(avg_conf, 4),
            "line_count": len(page_lines),
            "word_count": sum(len(x.split()) for x in page_lines)
        }
    
def render_page(page, dpi = 300):
    """Render page to numpy RGB. """
    pix = page.get_pixmap(dpi=dpi)

    img = np.frombuffer(pix.samples, dtype = np.uint8).reshape(
        pix.height,
        pix.width,
        pix.n
    )

    # Remove alpha channel if present (RGBA to RGB)
    if pix.n == 4:
        img = img[:, :, :3]

    return img

def ocr_flagged_pages(document_path, analysis, engine=None, dpi=300):
    """
    OCR only scanned pages based on analysis output.
    """
    if engine is None:
        engine = EngineOCR()

    results = {
        "document_path": document_path,
        "backend": "PaddleOCR 3.x",
        "pages": {}
    }

    scanned_pages = analysis.get("scanned_page", [])

    with fitz.open(document_path) as pdf:
        for page_number in tqdm.tqdm(scanned_pages, desc="OCR Scanned Pages"):
            page = pdf[page_number - 1]  # fitz uses 0-based indexing
            img = render_page(page, dpi=dpi)
            ocr_result = engine.ocr_image(img)

            results["pages"][page_number] = ocr_result

    return results