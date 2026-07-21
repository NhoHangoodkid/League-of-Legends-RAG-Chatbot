"""
# 1 file
python final_analysis.py "path/to/file.pdf"

# Whole Folder
python final_analysis.py "path/to/documents/"

"""


import os
import sys
import json
from datetime import datetime, timezone

from analyse_document import analyze_document
from handle_scanned_pdf import ocr_flagged_pages, EngineOCR



def merge_document(document_path, analysis, ocr_results, language= "en", dpi=300, output_path = None):
    """Merge text-layer pages and OCR pages into a single per-page structure."""
    num_page = analysis["num_page"]
    text_pages = analysis.get("pages", {})
    ocr_pages = ocr_results.get("pages", {})

    merged_pages = {}
    for page_number in range(1, num_page + 1):
        page_key = str(page_number)
        if page_number in text_pages:
            info = text_pages[page_number]
            merged_pages[page_key] = {"source": "text", **info}
        elif page_number in ocr_pages:
            info = ocr_pages[page_number]
            merged_pages[page_key] = {"source": "ocr", **info}
        else:
            # Empty / unreadable page — placeholder so the pipeline never crashes.
            merged_pages[page_key] = {
                "source": "unknown",
                "text": "",
                "char_count": 0,
                "word_count": 0,
                "sentence_count": 0,
            }

    num_text = sum(1 for p in merged_pages.values() if p["source"] == "text")
    num_ocr = sum(1 for p in merged_pages.values() if p["source"] == "ocr")

    merged = {
        "document_path": document_path,
        "num_page": num_page,
        "pdf_type": analysis["pdf_type"],
        "num_text_pages": num_text,
        "num_scanned_pages": num_ocr,
        "metadata": {
            "ocr_backend": "PaddleOCR 3.x",
            "ocr_language": language,
            "ocr_dpi": dpi,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "pages": merged_pages,
    }

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    return merged


def summarize_merged(merged):
    """Compute document-level summary stats from a merged document dict."""
    import statistics
    pages = merged["pages"]
    total_char     = sum(p.get("char_count", 0) for p in pages.values())
    total_word     = sum(p.get("word_count", 0) for p in pages.values())
    total_sentence = sum(p.get("sentence_count", 0) for p in pages.values())

    num_page = merged["num_page"]
    avg_word_per_sentence = round(total_word / total_sentence, 2) if total_sentence else 0
    avg_word_per_page     = round(total_word / num_page, 2) if num_page else 0

    word_counts = [p.get("word_count", 0) for p in pages.values()]
    non_blank_wc = [w for w in word_counts if w >= 10]

    max_word_per_page    = max(word_counts) if word_counts else 0
    min_word_per_page    = min(word_counts) if word_counts else 0
    median_word_per_page = round(statistics.median(word_counts), 2) if word_counts else 0
    std_word_per_page    = round(statistics.pstdev(word_counts), 2) if len(word_counts) > 1 else 0
    blank_pages          = sum(1 for w in word_counts if w < 10)
    content_pages        = len(non_blank_wc)  # pages with >= 10 words

    # Lexical density: unique words / total words (approx. from page texts)
    all_text = " ".join(p.get("text", "") for p in pages.values() if p.get("text"))
    tokens_all  = all_text.lower().split()
    lexical_density = round(len(set(tokens_all)) / len(tokens_all), 4) if tokens_all else 0.0

    # Avg chars per word (text richness)
    avg_char_per_word = round(total_char / total_word, 2) if total_word else 0

    ocr_confs = [p["confidence"] for p in pages.values()
                 if p["source"] == "ocr" and isinstance(p.get("confidence"), (int, float))]
    avg_ocr_confidence = round(sum(ocr_confs) / len(ocr_confs), 4) if ocr_confs else 0.0
    min_ocr_confidence = round(min(ocr_confs), 4) if ocr_confs else 0.0

    return {
        "document_path":       merged["document_path"],
        "num_page":            num_page,
        "pdf_type":            merged["pdf_type"],
        "num_text_pages":      merged["num_text_pages"],
        "num_scanned_pages":   merged["num_scanned_pages"],
        "content_pages":       content_pages,
        "blank_pages":         blank_pages,
        "total_char":          total_char,
        "total_word":          total_word,
        "total_sentence":      total_sentence,
        "avg_word_per_sentence": avg_word_per_sentence,
        "avg_word_per_page":   avg_word_per_page,
        "median_word_per_page": median_word_per_page,
        "std_word_per_page":   std_word_per_page,
        "min_word_per_page":   min_word_per_page,
        "max_word_per_page":   max_word_per_page,
        "lexical_density":     lexical_density,
        "avg_char_per_word":   avg_char_per_word,
        "avg_ocr_confidence":  avg_ocr_confidence,
        "min_ocr_confidence":  min_ocr_confidence,
    }


def add_page_header(fig, title, page_num, total_pages, report_title):
    """Adds a consistent header and footer to each page."""
    import matplotlib.patches as mpatches
    from datetime import datetime
    # Header bar
    fig.patches.append(mpatches.FancyBboxPatch(
        (0, 0.96), 1, 0.04,
        transform=fig.transFigure, clip_on=False,
        facecolor="#1a3a5c", edgecolor='none', zorder=0
    ))
    fig.text(0.03, 0.979, report_title, ha='left', va='center',
             fontsize=10, color='white', fontweight='bold', transform=fig.transFigure)
    fig.text(0.97, 0.979, title, ha='right', va='center',
             fontsize=10, color='white', transform=fig.transFigure)

    # Footer bar
    fig.patches.append(mpatches.FancyBboxPatch(
        (0, 0), 1, 0.03,
        transform=fig.transFigure, clip_on=False,
        facecolor="#f0f0f0", edgecolor='none', zorder=0
    ))
    fig.text(0.03, 0.015, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Confidential",
             ha='left', va='center', fontsize=7, color='#666666', transform=fig.transFigure)
    fig.text(0.97, 0.015, f"Page {page_num} / {total_pages}",
             ha='right', va='center', fontsize=7, color='#666666', transform=fig.transFigure)


def generate_pdf_report(all_rows, output_path):
    """Generates an enterprise-grade multi-page EDA PDF report."""
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    from matplotlib.backends.backend_pdf import PdfPages
    import matplotlib.ticker as mticker
    import seaborn as sns
    import numpy as np
    from datetime import datetime

    BRAND_DARK   = "#1a3a5c"
    BRAND_MID    = "#2980b9"
    ACCENT_GREEN = "#27ae60"
    ACCENT_ORG   = "#e67e22"
    ACCENT_RED   = "#e74c3c"
    ACCENT_PUR   = "#8e44ad"
    NEUTRAL_LIGHT= "#ecf0f1"
    PALETTE      = [BRAND_MID, ACCENT_ORG, ACCENT_GREEN, ACCENT_RED, ACCENT_PUR, "#16a085", "#f39c12"]

    REPORT_TITLE = "Document Corpus EDA Report"
    TOTAL_PAGES  = 9

    plt.rcParams.update({
        "font.family":     "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.titlesize":  13,
        "axes.titleweight":"bold",
        "axes.titlepad":   12,
        "axes.labelsize":  10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "figure.dpi":      150,
    })

    df = pd.DataFrame(all_rows)
    df['filename'] = df['document_path'].apply(lambda x: x.replace('\\', '/').split('/')[-1])
    df['short_name'] = df['filename'].apply(lambda x: x[:26] + '..' if len(x) > 28 else x)

    total_docs      = len(df)
    total_pages_sum = int(df['num_page'].sum())
    total_words     = int(df['total_word'].sum())
    total_chars     = int(df['total_char'].sum())
    total_sentences = int(df['total_sentence'].sum())
    total_blank     = int(df['blank_pages'].sum())
    pct_scanned     = df['num_scanned_pages'].sum() / max(total_pages_sum, 1) * 100
    avg_words_pg    = round(df['avg_word_per_page'].mean(), 1)
    avg_confidence  = round(df.loc[df['avg_ocr_confidence'] > 0, 'avg_ocr_confidence'].mean(), 4) if (df['avg_ocr_confidence'] > 0).any() else None

    # Colour map for pdf_type — used across multiple pages
    type_vals = df['pdf_type'].unique()
    cmap_dict = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(type_vals)}

    with PdfPages(output_path) as pdf:

        # PAGE 1: COVER
        fig = plt.figure(figsize=(11.69, 8.27))  # A4 landscape

        # Full-bleed gradient background
        import matplotlib.colors as mcolors
        import matplotlib.patches as mpatches
        ax_bg = fig.add_axes([0, 0, 1, 1])
        ax_bg.set_xlim(0, 1); ax_bg.set_ylim(0, 1)
        ax_bg.axis('off')
        grad = np.linspace(0, 1, 256).reshape(256, 1)
        ax_bg.imshow(grad, extent=[0, 1, 0, 1], aspect='auto',
                     cmap=mcolors.LinearSegmentedColormap.from_list(
                         'cov', ['#0d2137', '#1a3a5c']), alpha=1, zorder=0)

        # Accent stripe
        ax_bg.add_patch(mpatches.Rectangle((0, 0.32), 1, 0.006,
                        color=BRAND_MID, zorder=1))
        ax_bg.add_patch(mpatches.Rectangle((0, 0.31), 0.04, 0.02,
                        color=ACCENT_ORG, zorder=1))

        fig.text(0.50, 0.64, REPORT_TITLE,
                 ha='center', va='center', fontsize=32, color='white',
                 fontweight='bold', transform=fig.transFigure)
        fig.text(0.50, 0.54, "Exploratory Data Analysis — Document Corpus",
                 ha='center', va='center', fontsize=16, color='#aac9e0',
                 transform=fig.transFigure)

        # KPI tiles on cover
        kpis = [
            ("Documents", f"{total_docs:,}"),
            ("Total Pages", f"{total_pages_sum:,}"),
            ("Total Words", f"{total_words:,}"),
            ("Total Chars", f"{total_chars:,}"),
        ]
        n_kpi = len(kpis)
        tile_w, tile_h = 0.16, 0.12
        x_start = (1 - n_kpi * tile_w - (n_kpi - 1) * 0.02) / 2
        for i, (label, val) in enumerate(kpis):
            x = x_start + i * (tile_w + 0.02)
            ax_bg.add_patch(mpatches.FancyBboxPatch(
                (x, 0.14), tile_w, tile_h, transform=fig.transFigure,
                boxstyle="round,pad=0.01", facecolor='#ffffff18',
                edgecolor='#ffffff44', linewidth=1, clip_on=False, zorder=2))
            fig.text(x + tile_w / 2, 0.14 + tile_h * 0.72, val,
                     ha='center', va='center', fontsize=18, color='white',
                     fontweight='bold', transform=fig.transFigure)
            fig.text(x + tile_w / 2, 0.14 + tile_h * 0.25, label,
                     ha='center', va='center', fontsize=9, color='#aac9e0',
                     transform=fig.transFigure)

        fig.text(0.97, 0.03, f"Prepared: {datetime.now().strftime('%B %d, %Y')}",
                 ha='right', va='bottom', fontsize=8, color='#6699bb',
                 transform=fig.transFigure)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)


        # PAGE 2: EXECUTIVE SUMMARY — KPI TABLE
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Executive Summary", 2, TOTAL_PAGES, REPORT_TITLE)

        ax = fig.add_axes([0.05, 0.08, 0.90, 0.84])
        ax.axis('off')

        kpi_rows = [
            ["Total Documents",         f"{total_docs:,}",             "Number of PDF files in corpus"],
            ["Total Pages",             f"{total_pages_sum:,}",        "Sum of all pages across documents"],
            ["Total Words",             f"{total_words:,}",            "Total word tokens extracted"],
            ["Total Characters",        f"{total_chars:,}",            "Total character count"],
            ["Total Sentences",         f"{total_sentences:,}",        "Total sentences detected"],
            ["Blank / Near-Empty Pages",f"{total_blank:,}",            "Pages with < 10 words"],
            ["Scanned Page Ratio",      f"{pct_scanned:.1f}%",         "Proportion of OCR-processed pages"],
            ["Avg Words per Page",      f"{avg_words_pg:,}",           "Mean word count across all pages"],
            ["Avg Lexical Density",     f"{df['lexical_density'].mean():.3f}", "Unique tokens / total tokens (vocabulary richness)"],
            ["Avg Chars per Word",      f"{df['avg_char_per_word'].mean():.2f}", "Avg character length per word"],
            ["Avg OCR Confidence",
             f"{avg_confidence:.4f}" if avg_confidence else "N/A",    "Mean PaddleOCR confidence score (OCR docs only)"],
        ]
        col_labels = ["Metric", "Value", "Description"]
        tbl = ax.table(
            cellText=kpi_rows, colLabels=col_labels,
            loc='center', cellLoc='left')
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 2.2)

        # Style header
        for c in range(3):
            tbl[0, c].set_facecolor(BRAND_DARK)
            tbl[0, c].set_text_props(color='white', fontweight='bold')
        # Style data rows
        for r in range(1, len(kpi_rows) + 1):
            bg = NEUTRAL_LIGHT if r % 2 == 0 else 'white'
            for c in range(3):
                tbl[r, c].set_facecolor(bg)
                tbl[r, c].set_edgecolor('#cccccc')
            # Highlight value column
            tbl[r, 1].set_text_props(fontweight='bold', color=BRAND_MID)

        tbl.auto_set_column_width([0, 1, 2])

        ax.set_title("Key Performance Indicators — Corpus Overview",
                     fontsize=14, fontweight='bold', color=BRAND_DARK, pad=16, loc='left')
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # PAGE 3: PDF TYPE DISTRIBUTION
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "PDF Type Distribution", 3, TOTAL_PAGES, REPORT_TITLE)

        gs = gridspec.GridSpec(1, 2, figure=fig, left=0.06, right=0.94,
                               top=0.90, bottom=0.08, wspace=0.35)
        ax1 = fig.add_subplot(gs[0])
        ax2 = fig.add_subplot(gs[1])

        # Donut — PDF type count
        pdf_types = df['pdf_type'].value_counts()
        wedge_props = {'width': 0.50, 'edgecolor': 'white', 'linewidth': 2}
        ax1.pie(pdf_types, labels=None, autopct='%1.1f%%', startangle=90,
                colors=PALETTE[:len(pdf_types)], wedgeprops=wedge_props,
                pctdistance=0.75, textprops={'fontsize': 10, 'fontweight': 'bold'})
        ax1.legend(pdf_types.index, title="PDF Type",
                   loc="lower center", bbox_to_anchor=(0.5, -0.12),
                   ncol=len(pdf_types), fontsize=9, frameon=False)
        ax1.set_title("Document Count by PDF Type", color=BRAND_DARK)

        # Donut — page composition
        total_text_pgs   = int(df['num_text_pages'].sum())
        total_scan_pgs   = int(df['num_scanned_pages'].sum())
        if total_text_pgs + total_scan_pgs > 0:
            ax2.pie([total_text_pgs, total_scan_pgs], labels=None,
                    autopct='%1.1f%%', startangle=90,
                    colors=[BRAND_MID, ACCENT_ORG], wedgeprops=wedge_props,
                    pctdistance=0.75, textprops={'fontsize': 10, 'fontweight': 'bold'})
            ax2.legend([f"Text ({total_text_pgs:,})", f"Scanned ({total_scan_pgs:,})"],
                       title="Page Type", loc="lower center",
                       bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=9, frameon=False)
        ax2.set_title("Page Composition: Text vs. Scanned", color=BRAND_DARK)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)


        # PAGE 4: PAGE COUNT & WORD COUNT DISTRIBUTIONS
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Page & Word Count Distributions", 4, TOTAL_PAGES, REPORT_TITLE)

        gs = gridspec.GridSpec(2, 1, figure=fig, left=0.06, right=0.94,
                               top=0.90, bottom=0.08, hspace=0.55)
        ax_p = fig.add_subplot(gs[0])
        ax_w = fig.add_subplot(gs[1])

        # Top: page count per document (horizontal bar, sorted)
        df_p = df.sort_values('num_page', ascending=True).tail(20)
        bars_p = ax_p.barh(df_p['short_name'], df_p['num_page'],
                           color=BRAND_MID, edgecolor='none', height=0.7)
        ax_p.set_xlabel("Number of Pages")
        ax_p.set_title("Top 20 Documents by Page Count", color=BRAND_DARK)
        ax_p.bar_label(bars_p, fmt='%d', padding=3, fontsize=7.5, color='#333')
        ax_p.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))

        # Bottom: word count (horizontal bar, sorted)
        df_w = df.sort_values('total_word', ascending=True).tail(20)
        bars_w = ax_w.barh(df_w['short_name'], df_w['total_word'],
                           color=ACCENT_ORG, edgecolor='none', height=0.7)
        ax_w.set_xlabel("Total Words")
        ax_w.set_title("Top 20 Documents by Word Count", color=BRAND_DARK)
        ax_w.bar_label(bars_w, fmt='%d', padding=3, fontsize=7.5, color='#333')
        ax_w.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)


        # PAGE 5: WORD / SENTENCE STATISTICS
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Linguistic Statistics", 5, TOTAL_PAGES, REPORT_TITLE)

        gs = gridspec.GridSpec(1, 2, figure=fig, left=0.06, right=0.94,
                               top=0.90, bottom=0.10, wspace=0.38)
        ax_wpp = fig.add_subplot(gs[0])
        ax_aws = fig.add_subplot(gs[1])

        # Histogram: avg words per page
        ax_wpp.hist(df['avg_word_per_page'], bins=20,
                    color=ACCENT_GREEN, edgecolor='white', linewidth=0.7)
        ax_wpp.axvline(df['avg_word_per_page'].mean(), color=ACCENT_RED,
                       linestyle='--', linewidth=1.5,
                       label=f"Mean = {df['avg_word_per_page'].mean():.0f}")
        ax_wpp.axvline(df['avg_word_per_page'].median(), color=BRAND_DARK,
                       linestyle=':', linewidth=1.5,
                       label=f"Median = {df['avg_word_per_page'].median():.0f}")
        ax_wpp.set_xlabel("Avg Words / Page")
        ax_wpp.set_ylabel("Document Count")
        ax_wpp.set_title("Distribution of Avg Words per Page", color=BRAND_DARK)
        ax_wpp.legend(fontsize=8, frameon=False)

        # Histogram: avg words per sentence
        ax_aws.hist(df['avg_word_per_sentence'], bins=20,
                    color=ACCENT_PUR, edgecolor='white', linewidth=0.7)
        ax_aws.axvline(df['avg_word_per_sentence'].mean(), color=ACCENT_RED,
                       linestyle='--', linewidth=1.5,
                       label=f"Mean = {df['avg_word_per_sentence'].mean():.1f}")
        ax_aws.axvline(df['avg_word_per_sentence'].median(), color=BRAND_DARK,
                       linestyle=':', linewidth=1.5,
                       label=f"Median = {df['avg_word_per_sentence'].median():.1f}")
        ax_aws.set_xlabel("Avg Words / Sentence")
        ax_aws.set_ylabel("Document Count")
        ax_aws.set_title("Distribution of Avg Words per Sentence", color=BRAND_DARK)
        ax_aws.legend(fontsize=8, frameon=False)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # PAGE 6: DESCRIPTIVE STATISTICS + BOXPLOT

        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Descriptive Statistics", 6, TOTAL_PAGES, REPORT_TITLE)

        gs6 = gridspec.GridSpec(1, 2, figure=fig, left=0.06, right=0.94,
                                top=0.90, bottom=0.08, wspace=0.38)
        ax_desc = fig.add_subplot(gs6[0])
        ax_box  = fig.add_subplot(gs6[1])

        # Left: descriptive stats table for key numeric columns
        desc_cols = ['num_page', 'total_word', 'avg_word_per_page',
                     'std_word_per_page', 'lexical_density', 'avg_char_per_word']
        desc_labels = ['Pages', 'Total Words', 'Avg W/Pg', 'Std W/Pg', 'Lex. Density', 'Avg Char/Word']
        desc_stats = []
        for col, lbl in zip(desc_cols, desc_labels):
            s = df[col]
            desc_stats.append([
                lbl,
                f"{s.min():.1f}",
                f"{s.quantile(0.25):.1f}",
                f"{s.median():.1f}",
                f"{s.quantile(0.75):.1f}",
                f"{s.max():.1f}",
                f"{s.mean():.1f}",
                f"{s.std():.1f}",
            ])
        desc_col_labels = ['Metric', 'Min', 'Q1', 'Median', 'Q3', 'Max', 'Mean', 'Std']
        ax_desc.axis('off')
        tbl_d = ax_desc.table(
            cellText=desc_stats, colLabels=desc_col_labels,
            loc='center', cellLoc='center')
        tbl_d.auto_set_font_size(False)
        tbl_d.set_fontsize(8)
        tbl_d.scale(1, 1.9)
        for c in range(len(desc_col_labels)):
            tbl_d[0, c].set_facecolor(BRAND_DARK)
            tbl_d[0, c].set_text_props(color='white', fontweight='bold')
        for r in range(1, len(desc_stats) + 1):
            bg = NEUTRAL_LIGHT if r % 2 == 0 else 'white'
            for c in range(len(desc_col_labels)):
                tbl_d[r, c].set_facecolor(bg)
                tbl_d[r, c].set_edgecolor('#cccccc')
        tbl_d.auto_set_column_width(list(range(len(desc_col_labels))))
        ax_desc.set_title("Descriptive Statistics — Key Metrics",
                          fontsize=11, fontweight='bold', color=BRAND_DARK,
                          pad=10, loc='left')

        # Right: Boxplot — avg_word_per_page grouped by pdf_type
        groups = [grp['avg_word_per_page'].values for _, grp in df.groupby('pdf_type')]
        labels_box = list(df.groupby('pdf_type').groups.keys())
        bp = ax_box.boxplot(groups, patch_artist=True, notch=False,
                            medianprops={'color': 'white', 'linewidth': 2})
        for patch, color in zip(bp['boxes'], PALETTE):
            patch.set_facecolor(color)
            patch.set_alpha(0.85)
        for element in ['whiskers', 'caps', 'fliers']:
            for item in bp[element]:
                item.set(color='#555555', linewidth=1)
        ax_box.set_xticklabels(labels_box, fontsize=9)
        ax_box.set_ylabel("Avg Words per Page")
        ax_box.set_title("Avg Words/Page by PDF Type",
                         color=BRAND_DARK, fontsize=11, fontweight='bold')
        # Overlay strip
        for i, (grp_vals, color) in enumerate(zip(groups, PALETTE), start=1):
            jitter = np.random.uniform(-0.15, 0.15, len(grp_vals))
            ax_box.scatter(i + jitter, grp_vals, alpha=0.5, s=18,
                           color=color, edgecolors='white', linewidths=0.4, zorder=3)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)


        # PAGE 7: LEXICAL DENSITY & CHAR/WORD ANALYSIS
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Vocabulary & Text Richness", 7, TOTAL_PAGES, REPORT_TITLE)

        gs7 = gridspec.GridSpec(1, 2, figure=fig, left=0.07, right=0.93,
                                top=0.90, bottom=0.10, wspace=0.38)
        ax_ld = fig.add_subplot(gs7[0])
        ax_cw = fig.add_subplot(gs7[1])

        # Histogram: lexical_density
        ax_ld.hist(df['lexical_density'], bins=20, color='#16a085',
                   edgecolor='white', linewidth=0.7)
        ax_ld.axvline(df['lexical_density'].mean(), color=ACCENT_RED,
                      linestyle='--', linewidth=1.5,
                      label=f"Mean = {df['lexical_density'].mean():.3f}")
        ax_ld.axvline(df['lexical_density'].median(), color=BRAND_DARK,
                      linestyle=':', linewidth=1.5,
                      label=f"Median = {df['lexical_density'].median():.3f}")
        ax_ld.set_xlabel("Lexical Density (unique / total tokens)")
        ax_ld.set_ylabel("Document Count")
        ax_ld.set_title("Distribution of Lexical Density", color=BRAND_DARK)
        ax_ld.legend(fontsize=8, frameon=False)

        # Scatter: lexical_density vs avg_word_per_page
        for ptype, grp in df.groupby('pdf_type'):
            ax_cw.scatter(grp['avg_word_per_page'], grp['lexical_density'],
                          label=ptype, color=cmap_dict.get(ptype, PALETTE[0]),
                          alpha=0.8, s=grp['num_page'].clip(1) / grp['num_page'].max() * 120 + 20,
                          edgecolors='white', linewidths=0.5)
        ax_cw.set_xlabel("Avg Words per Page")
        ax_cw.set_ylabel("Lexical Density")
        ax_cw.set_title("Lexical Density vs. Avg Words/Page\n(bubble size ∝ pages)",
                        color=BRAND_DARK)
        ax_cw.legend(title="PDF Type", fontsize=8, frameon=False)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # PAGE 8: OUTLIER / QUALITY ANALYSIS (Scatter)
        fig = plt.figure(figsize=(11.69, 8.27))
        add_page_header(fig, "Quality & Outlier Analysis", 8, TOTAL_PAGES, REPORT_TITLE)

        gs = gridspec.GridSpec(1, 2, figure=fig, left=0.06, right=0.92,
                               top=0.90, bottom=0.10, wspace=0.40)
        ax_s1 = fig.add_subplot(gs[0])
        ax_s2 = fig.add_subplot(gs[1])

        # Scatter 1: total_word vs num_page, coloured by pdf_type
        for ptype, grp in df.groupby('pdf_type'):
            ax_s1.scatter(grp['num_page'], grp['total_word'],
                          label=ptype, color=cmap_dict[ptype],
                          alpha=0.8, s=grp['blank_pages'].clip(1) * 12,
                          edgecolors='white', linewidths=0.5)
        ax_s1.set_xlabel("Number of Pages")
        ax_s1.set_ylabel("Total Words")
        ax_s1.set_title("Total Words vs. Pages\n(bubble size = blank pages)", color=BRAND_DARK)
        ax_s1.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
        ax_s1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{int(x):,}'))
        ax_s1.legend(title="PDF Type", fontsize=8, frameon=False)

        # Scatter 2: blank_pages vs avg_word_per_page
        for ptype, grp in df.groupby('pdf_type'):
            ax_s2.scatter(grp['blank_pages'], grp['avg_word_per_page'],
                          label=ptype, color=cmap_dict[ptype],
                          alpha=0.8, s=60, edgecolors='white', linewidths=0.5)
        ax_s2.set_xlabel("Blank / Near-Empty Pages")
        ax_s2.set_ylabel("Avg Words per Page")
        ax_s2.set_title("Avg Words/Page vs. Blank Pages\n(quality check)", color=BRAND_DARK)
        ax_s2.legend(title="PDF Type", fontsize=8, frameon=False)

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # PAGE 9: DOCUMENT-LEVEL DATA TABLE
        cols_show = ['filename', 'num_page', 'pdf_type', 'num_text_pages',
                     'num_scanned_pages', 'blank_pages', 'content_pages',
                     'total_word', 'avg_word_per_page', 'median_word_per_page',
                     'std_word_per_page', 'max_word_per_page',
                     'avg_word_per_sentence', 'lexical_density',
                     'avg_char_per_word', 'avg_ocr_confidence']
        col_labels = ['Document', 'Pages', 'Type', 'Text\nPgs', 'Scan\nPgs',
                      'Blank', 'Content\nPgs', 'Words', 'Avg\nW/Pg', 'Med\nW/Pg',
                      'Std\nW/Pg', 'Max\nW/Pg', 'Avg\nW/Sent',
                      'Lex\nDens', 'Avg\nCh/W', 'OCR\nConf']

        df_tbl = df[cols_show].copy()
        df_tbl['filename']         = df_tbl['filename'].apply(lambda x: x[:26] + '..' if len(x) > 28 else x)
        df_tbl['total_word']       = df_tbl['total_word'].apply(lambda x: f"{x:,}")
        df_tbl['lexical_density']  = df_tbl['lexical_density'].apply(lambda x: f"{x:.3f}")
        df_tbl['avg_ocr_confidence'] = df_tbl['avg_ocr_confidence'].apply(
            lambda x: f"{x:.3f}" if x > 0 else "—")

        # Split into pages of ~25 rows each
        page_size = 22
        chunks = [df_tbl.iloc[i:i + page_size] for i in range(0, len(df_tbl), page_size)]

        for ci, chunk in enumerate(chunks):
            fig = plt.figure(figsize=(16, 8.27))  # wider for table
            page_label = f"Document Detail Table ({ci + 1}/{len(chunks)})"
            add_page_header(fig, page_label, TOTAL_PAGES, TOTAL_PAGES, REPORT_TITLE)

            ax = fig.add_axes([0.01, 0.05, 0.98, 0.87])
            ax.axis('off')

            tbl = ax.table(
                cellText=chunk.values.tolist(),
                colLabels=col_labels,
                loc='center', cellLoc='center')

            tbl.auto_set_font_size(False)
            tbl.set_fontsize(7.5)
            tbl.scale(1, 1.65)

            # Header
            for c in range(len(col_labels)):
                tbl[0, c].set_facecolor(BRAND_DARK)
                tbl[0, c].set_text_props(color='white', fontweight='bold')
                tbl[0, c].set_height(0.055)

            # Alternate row colours
            for r in range(1, len(chunk) + 1):
                bg = NEUTRAL_LIGHT if r % 2 == 0 else 'white'
                for c in range(len(col_labels)):
                    tbl[r, c].set_facecolor(bg)
                    tbl[r, c].set_edgecolor('#dddddd')
                # Colour-code type column
                cell_txt = chunk.iloc[r - 1]['pdf_type']
                colour = BRAND_MID if cell_txt == 'text' else ACCENT_ORG if cell_txt == 'mixed' else ACCENT_RED
                tbl[r, 2].set_text_props(color=colour, fontweight='bold')

            tbl.auto_set_column_width(list(range(len(col_labels))))
            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)


def final_analysis(document_path, engine, language="en", device="gpu", dpi=300, output_dir="output"):
    """Run the full pipeline: analyse -> OCR scanned pages -> merge -> JSON output."""
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(document_path))[0]

    merged_json_path = os.path.join(output_dir, f"{base_name} merged_document.json")

    # 1. Document-level statistics + per-page text (pdfplumber, one pass).
    analysis = analyze_document(document_path)

    # 2. OCR only the flagged scanned pages
    if analysis.get("scanned_page"):
        ocr_results = ocr_flagged_pages(document_path, analysis, engine=engine, dpi=dpi)
    else:
        ocr_results = {"pages": {}}

    # 3. Merge text-layer + OCR into one unified JSON per page.
    merged = merge_document(
        document_path, analysis, ocr_results,
        language = language, dpi = dpi,
        output_path = merged_json_path,
    )

    return {
        "merged_document": merged,
        "merged_json": merged_json_path,
    }


if __name__ == "__main__":
    import argparse
    import glob

    # Fix Windows console encoding: avoid UnicodeEncodeError for non-ASCII paths
    # (e.g. Vietnamese file names on cp1252 terminals).
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run the full PDF analysis pipeline.")
    parser.add_argument("path", help="Path to a PDF file or a directory containing PDFs.")
    parser.add_argument("--language", default="en", help="OCR language (default: en).")
    parser.add_argument("--device", default="gpu", help="PaddleOCR device: gpu or cpu.")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering scanned pages (default: 300).")
    parser.add_argument("--output-dir", default="output", help="Directory for output files (default: output).")
    parser.add_argument("--force", action="store_true",
                        help="Re-process files even if output already exists.")
    args = parser.parse_args()

    # Collect PDF files: single file or recursive directory scan.
    if os.path.isfile(args.path):
        pdf_files = [args.path]
    elif os.path.isdir(args.path):
        pdf_files = sorted(glob.glob(os.path.join(args.path, "**", "*.pdf"), recursive=True))
    else:
        print(f"Error: '{args.path}' is not a valid file or directory.")
        exit(1)

    if not pdf_files:
        print(f"No PDF files found in '{args.path}'.")
        exit(1)

    print(f"Found {len(pdf_files)} PDF(s).\n")

    # Initialize OCR engine once for the entire batch
    engine = EngineOCR(language=args.language, device=args.device)

    skipped = 0
    for i, pdf_path in enumerate(pdf_files, 1):
        # Incremental mode: skip files whose output already exists.
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        merged_json_path = os.path.join(args.output_dir, f"{base_name} merged_document.json")
        if not args.force and os.path.isfile(merged_json_path):
            print(f"[{i}/{len(pdf_files)}] SKIP (already exists): {pdf_path}")
            skipped += 1
            continue

        print(f"[{i}/{len(pdf_files)}] {pdf_path}")
        try:
            result = final_analysis(
                pdf_path,
                engine=engine,
                language = args.language,
                device = args.device,
                dpi = args.dpi,
                output_dir = args.output_dir,
            )
            print(f"  PDF type:    {result['merged_document']['pdf_type']}")
            print(f"  Merged JSON: {result['merged_json']}")
        except Exception as e:
            # Log error and continue processing remaining files.
            print(f"  ERROR: {e}")
        print()

    print(f"Done. {len(pdf_files) - skipped} processed, {skipped} skipped.")

    # 5. Consolidated summary: generate EDA PDF Report from all merged_document.json files.
    merged_jsons = sorted(glob.glob(os.path.join(args.output_dir, "* merged_document.json")))
    if merged_jsons:
        all_summaries_path = os.path.join(args.output_dir, "eda_report.pdf")
        all_rows = []
        for json_path in merged_jsons:
            with open(json_path, "r", encoding="utf-8") as f:
                merged = json.load(f)
            all_rows.append(summarize_merged(merged))

        try:
            generate_pdf_report(all_rows, all_summaries_path)
            print(f"\nConsolidated EDA PDF report generated: {all_summaries_path} ({len(all_rows)} documents)")
        except ImportError as e:
            print(f"\nCould not generate PDF report. Missing dependency: {e}")
            print("Please install pandas, matplotlib, and seaborn.")
