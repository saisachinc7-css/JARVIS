"""
Document Parser for JARVIS Study Mode
Handles ingestion and text/table/diagram extraction from PDFs, DOCX, PPTX, TXT, MD, Images, URLs, and Copied Text.
"""

import os
import re
import urllib.parse
from typing import Dict, List, Any


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """Extract text, page numbers, and tables from a PDF file."""
    pages = []
    full_text_list = []
    
    # Try pdfplumber first for table + structured extraction
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                text = page.extract_text() or ""
                
                # Extract tables if any
                tables_text = ""
                try:
                    tables = page.extract_tables()
                    if tables:
                        tables_formatted = []
                        for tbl in tables:
                            for row in tbl:
                                clean_row = [str(cell).strip() if cell else "" for cell in row]
                                tables_formatted.append(" | ".join(clean_row))
                        tables_text = "\n[Extracted Table]:\n" + "\n".join(tables_formatted)
                except Exception:
                    pass

                combined_page = text
                if tables_text:
                    combined_page += f"\n{tables_text}"

                pages.append({
                    "page_number": page_num,
                    "content": combined_page.strip()
                })
                if combined_page.strip():
                    full_text_list.append(f"--- [Page {page_num}] ---\n{combined_page.strip()}")
    except Exception as e:
        print(f"[DocumentParser] pdfplumber failed ({e}), falling back to pypdf...")
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                page_num = i + 1
                text = page.extract_text() or ""
                pages.append({
                    "page_number": page_num,
                    "content": text.strip()
                })
                if text.strip():
                    full_text_list.append(f"--- [Page {page_num}] ---\n{text.strip()}")
        except Exception as pypdf_err:
            print(f"[DocumentParser] pypdf error: {pypdf_err}")

    raw_text = "\n\n".join(full_text_list)
    return {
        "title": os.path.basename(file_path),
        "file_type": "PDF",
        "file_path": file_path,
        "page_count": len(pages),
        "pages": pages,
        "raw_text": raw_text
    }


def parse_docx(file_path: str) -> Dict[str, Any]:
    """Extract paragraphs, headings, and tables from a Word (.docx) document."""
    try:
        import docx
        doc = docx.Document(file_path)
        
        elements = []
        sections = []
        current_section = "Main Content"
        section_content = []

        for p in doc.paragraphs:
            text = p.text.strip()
            if not text:
                continue
            
            # Check heading style
            if p.style.name.startswith("Heading"):
                if section_content:
                    sections.append({"section": current_section, "content": "\n".join(section_content)})
                    section_content = []
                current_section = text
                elements.append(f"## {text}")
            else:
                elements.append(text)
                section_content.append(text)

        # Tables extraction
        for table in doc.tables:
            table_lines = []
            for row in table.rows:
                row_vals = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                table_lines.append(" | ".join(row_vals))
            if table_lines:
                tbl_str = "\n[Table]:\n" + "\n".join(table_lines)
                elements.append(tbl_str)
                section_content.append(tbl_str)

        if section_content:
            sections.append({"section": current_section, "content": "\n".join(section_content)})

        raw_text = "\n\n".join(elements)
        page_count = max(1, len(sections))

        pages = []
        for idx, sec in enumerate(sections, 1):
            pages.append({
                "page_number": idx,
                "section_title": sec["section"],
                "content": sec["content"]
            })

        return {
            "title": os.path.basename(file_path),
            "file_type": "DOCX",
            "file_path": file_path,
            "page_count": page_count,
            "pages": pages,
            "raw_text": raw_text
        }
    except Exception as e:
        print(f"[DocumentParser] DOCX error: {e}")
        return {
            "title": os.path.basename(file_path),
            "file_type": "DOCX",
            "file_path": file_path,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error parsing DOCX: {e}"
        }


def parse_pptx(file_path: str) -> Dict[str, Any]:
    """Extract slide titles, text, tables, and notes from a PowerPoint (.pptx) file."""
    try:
        import pptx
        prs = pptx.Presentation(file_path)
        slides = []
        full_text_list = []

        for i, slide in enumerate(prs.slides):
            slide_num = i + 1
            slide_text = []
            title = f"Slide {slide_num}"

            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        txt = paragraph.text.strip()
                        if txt:
                            slide_text.append(txt)
                            if shape == slide.shapes.title:
                                title = txt

                if shape.has_table:
                    table_lines = []
                    for row in shape.table.rows:
                        row_vals = [cell.text.strip() for cell in row.cells]
                        table_lines.append(" | ".join(row_vals))
                    if table_lines:
                        slide_text.append("\n[Slide Table]:\n" + "\n".join(table_lines))

            # Slide notes
            try:
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes = slide.notes_slide.notes_text_frame.text.strip()
                    if notes:
                        slide_text.append(f"\n[Speaker Notes]: {notes}")
            except Exception:
                pass

            combined_slide = "\n".join(slide_text)
            slides.append({
                "page_number": slide_num,
                "title": title,
                "content": combined_slide
            })
            if combined_slide:
                full_text_list.append(f"--- [Slide {slide_num}: {title}] ---\n{combined_slide}")

        raw_text = "\n\n".join(full_text_list)
        return {
            "title": os.path.basename(file_path),
            "file_type": "PPTX",
            "file_path": file_path,
            "page_count": len(slides),
            "pages": slides,
            "raw_text": raw_text
        }
    except Exception as e:
        print(f"[DocumentParser] PPTX error: {e}")
        return {
            "title": os.path.basename(file_path),
            "file_type": "PPTX",
            "file_path": file_path,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error parsing PPTX: {e}"
        }


def parse_txt_or_md(file_path: str) -> Dict[str, Any]:
    """Parse text or markdown document into pages/sections."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()

        # Split into logical chunk pages (~1000 chars or by double line breaks)
        paragraphs = [p.strip() for p in raw_text.split("\n\n") if p.strip()]
        pages = []
        current_page = []
        curr_len = 0
        page_num = 1

        for p in paragraphs:
            current_page.append(p)
            curr_len += len(p)
            if curr_len >= 1200:
                pages.append({
                    "page_number": page_num,
                    "content": "\n\n".join(current_page)
                })
                page_num += 1
                current_page = []
                curr_len = 0

        if current_page:
            pages.append({
                "page_number": page_num,
                "content": "\n\n".join(current_page)
            })

        return {
            "title": os.path.basename(file_path),
            "file_type": "TXT/MD",
            "file_path": file_path,
            "page_count": len(pages),
            "pages": pages,
            "raw_text": raw_text
        }
    except Exception as e:
        return {
            "title": os.path.basename(file_path),
            "file_type": "TXT/MD",
            "file_path": file_path,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error reading file: {e}"
        }


def parse_url(url: str) -> Dict[str, Any]:
    """Fetch content from a web page URL and convert to cleaned study material."""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        resp = requests.get(url, headers=headers, timeout=12)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Remove script/style tags
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        title = soup.title.string.strip() if soup.title else url
        
        # Extract main text
        paragraphs = [p.get_text().strip() for p in soup.find_all(['h1', 'h2', 'h3', 'p', 'li']) if p.get_text().strip()]
        raw_text = "\n\n".join(paragraphs)

        # Chunk into pages
        pages = []
        page_num = 1
        curr_chunk = []
        curr_len = 0
        for p in paragraphs:
            curr_chunk.append(p)
            curr_len += len(p)
            if curr_len >= 1200:
                pages.append({"page_number": page_num, "content": "\n\n".join(curr_chunk)})
                page_num += 1
                curr_chunk = []
                curr_len = 0
        if curr_chunk:
            pages.append({"page_number": page_num, "content": "\n\n".join(curr_chunk)})

        return {
            "title": title,
            "file_type": "Web Article / URL",
            "file_path": url,
            "page_count": max(1, len(pages)),
            "pages": pages,
            "raw_text": raw_text
        }
    except Exception as e:
        return {
            "title": url,
            "file_type": "Web Article",
            "file_path": url,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error fetching web page: {e}"
        }


def parse_image(image_path: str) -> Dict[str, Any]:
    """
    Extract text, formulas, diagrams, and charts from an image using Vision model (Gemini / Ollama llava).
    """
    try:
        from Tools.screen_vision import get_screen_vision
        sv = get_screen_vision()
        result = sv.analyze(image_path)
        extracted_desc = result.get("description", "")
        
        # Prompt specifically for OCR and diagram analysis
        ocr_prompt = (
            "You are an expert OCR & Study Material analyzer. "
            "Examine this image and extract ALL written text, formulas, numbers, tables, "
            "and clearly describe any diagrams, flowcharts, or graphs present in detail."
        )
        
        description = ""
        # Try Gemini API directly for detailed OCR
        if sv._api_key:
            try:
                from google import genai
                from PIL import Image
                client = genai.Client(api_key=sv._api_key)
                img = Image.open(image_path)
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[ocr_prompt, img]
                )
                description = resp.text.strip()
            except Exception as e:
                print(f"[DocumentParser] Gemini OCR error: {e}")

        if not description:
            description = extracted_desc or "No readable text or diagram extracted from image."

        return {
            "title": os.path.basename(image_path),
            "file_type": "Image / OCR",
            "file_path": image_path,
            "page_count": 1,
            "pages": [{"page_number": 1, "content": description}],
            "raw_text": description
        }
    except Exception as e:
        return {
            "title": os.path.basename(image_path),
            "file_type": "Image",
            "file_path": image_path,
            "page_count": 1,
            "pages": [{"page_number": 1, "content": f"Image processing error: {e}"}],
            "raw_text": f"Error processing image: {e}"
        }


def parse_copied_text(text: str, title: str = "Copied Notes") -> Dict[str, Any]:
    """Parse raw text string pasted/provided by user."""
    clean_text = text.strip()
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    
    pages = []
    page_num = 1
    curr = []
    c_len = 0
    for p in paragraphs:
        curr.append(p)
        c_len += len(p)
        if c_len >= 1200:
            pages.append({"page_number": page_num, "content": "\n\n".join(curr)})
            page_num += 1
            curr = []
            c_len = 0
    if curr:
        pages.append({"page_number": page_num, "content": "\n\n".join(curr)})

    return {
        "title": title,
        "file_type": "Copied Text",
        "file_path": "clipboard/input",
        "page_count": max(1, len(pages)),
        "pages": pages,
        "raw_text": clean_text
    }


def parse_rtf(file_path: str) -> Dict[str, Any]:
    """Parse Rich Text Format (.rtf) file and extract plain text using a robust regex-based stripper."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Simple RTF text extraction
        text = content
        # Remove groups/destinations like {\*\generator...}
        text = re.sub(r'\{\\\*\\?[^{}]*\}', '', text)
        # Remove RTF control words
        text = re.sub(r'\\[a-z0-9\-]+ ?', '', text)
        # Remove RTF character formatting or control signs
        text = re.sub(r'\\\'[a-f0-9]{2}', '', text)
        text = re.sub(r'\\~', ' ', text)
        text = re.sub(r'\\[|{}~-]', '', text)
        # Strip brackets
        text = text.replace('{', '').replace('}', '')
        
        # Clean lines
        lines = [line.strip() for line in text.splitlines()]
        cleaned_text = "\n".join([l for l in lines if l])
        
        paragraphs = [p.strip() for p in cleaned_text.split("\n\n") if p.strip()]
        pages = []
        page_num = 1
        curr = []
        c_len = 0
        for p in paragraphs:
            curr.append(p)
            c_len += len(p)
            if c_len >= 1200:
                pages.append({"page_number": page_num, "content": "\n\n".join(curr)})
                page_num += 1
                curr = []
                c_len = 0
        if curr:
            pages.append({"page_number": page_num, "content": "\n\n".join(curr)})
            
        return {
            "title": os.path.basename(file_path),
            "file_type": "RTF",
            "file_path": file_path,
            "page_count": max(1, len(pages)),
            "pages": pages,
            "raw_text": cleaned_text
        }
    except Exception as e:
        return {
            "title": os.path.basename(file_path),
            "file_type": "RTF",
            "file_path": file_path,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error parsing RTF: {e}"
        }


def parse_html_file(file_path: str) -> Dict[str, Any]:
    """Parse local HTML document using BeautifulSoup to extract clean text content."""
    try:
        from bs4 import BeautifulSoup
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            html_content = f.read()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove script, style, nav, footer, header, aside elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()
            
        title = soup.title.string.strip() if (soup.title and soup.title.string) else os.path.basename(file_path)
        
        paragraphs = [p.get_text().strip() for p in soup.find_all(['h1', 'h2', 'h3', 'p', 'li', 'td', 'tr']) if p.get_text().strip()]
        raw_text = "\n\n".join(paragraphs)
        
        pages = []
        page_num = 1
        curr_chunk = []
        curr_len = 0
        for p in paragraphs:
            curr_chunk.append(p)
            curr_len += len(p)
            if curr_len >= 1200:
                pages.append({"page_number": page_num, "content": "\n\n".join(curr_chunk)})
                page_num += 1
                curr_chunk = []
                curr_len = 0
        if curr_chunk:
            pages.append({"page_number": page_num, "content": "\n\n".join(curr_chunk)})
            
        return {
            "title": title,
            "file_type": "HTML",
            "file_path": file_path,
            "page_count": max(1, len(pages)),
            "pages": pages,
            "raw_text": raw_text
        }
    except Exception as e:
        return {
            "title": os.path.basename(file_path),
            "file_type": "HTML",
            "file_path": file_path,
            "page_count": 0,
            "pages": [],
            "raw_text": f"Error parsing HTML file: {e}"
        }


def parse_file(source: str) -> Dict[str, Any]:
    """
    Auto-detect input format and parse accordingly.
    Supports file paths (.pdf, .docx, .pptx, .txt, .md, .png, .jpg...), URLs, or raw text.
    """
    source_clean = source.strip().strip('"').strip("'")

    # URL check
    if source_clean.startswith("http://") or source_clean.startswith("https://"):
        return parse_url(source_clean)

    # Existing file check
    if os.path.exists(source_clean):
        ext = os.path.splitext(source_clean)[1].lower()
        if ext == ".pdf":
            return parse_pdf(source_clean)
        elif ext in [".docx", ".doc"]:
            return parse_docx(source_clean)
        elif ext in [".pptx", ".ppt"]:
            return parse_pptx(source_clean)
        elif ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
            return parse_image(source_clean)
        elif ext == ".rtf":
            return parse_rtf(source_clean)
        elif ext in [".html", ".htm"]:
            return parse_html_file(source_clean)
        elif ext in [".txt", ".md", ".json", ".csv", ".py", ".cpp", ".java"]:
            return parse_txt_or_md(source_clean)

    # Fallback: Treat source as raw text / copied notes
    return parse_copied_text(source)
