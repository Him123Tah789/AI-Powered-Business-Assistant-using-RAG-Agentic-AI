import re
import logging
from pathlib import Path
from typing import List, Dict, Any
import pypdf

logger = logging.getLogger(__name__)

class DocumentIndexer:
    """
    Parses and chunks policy PDF documents with section headings and metadata.
    """

    def __init__(self, pdf_path: Path):
        self.pdf_path = Path(pdf_path)

    def extract_text_by_pages(self) -> List[Dict[str, Any]]:
        """
        Extracts raw text and page numbers from the PDF.
        """
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF document not found at: {self.pdf_path}")

        pages_data = []
        reader = pypdf.PdfReader(str(self.pdf_path))
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            # Clean up excessive whitespace
            clean_text = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
            pages_data.append({
                "page": page_idx + 1,
                "text": clean_text
            })
        return pages_data

    def create_chunks(self) -> List[Dict[str, Any]]:
        """
        Extracts structured semantic chunks from the policy PDF.
        Assigns policy reference and section metadata to each chunk.
        """
        pages = self.extract_text_by_pages()
        chunks = []

        # High-level document reference
        doc_ref = "Policy Reference: SRV-POL-001 (Service Management & Creation Policy)"

        for page_info in pages:
            page_num = page_info["page"]
            text = page_info["text"]

            # Split text by section markers like "1. ", "1.1 ", "2. ", "2.1 ", etc.
            # or double newlines
            lines = text.split("\n")
            current_section = f"Page {page_num}"
            current_subhead = ""
            chunk_buffer = []

            for line in lines:
                # Check for section header patterns (e.g., "1. Service Catalogue Principles" or "2.1 Maximum permitted price")
                sec_match = re.match(r"^(\d+(\.\d+)?)\s+([A-Z].+)$", line)
                if sec_match:
                    if chunk_buffer:
                        content = "\n".join(chunk_buffer).strip()
                        if len(content) > 30:
                            chunks.append({
                                "id": f"p{page_num}_sec_{len(chunks)}",
                                "page": page_num,
                                "policy_ref": "SRV-POL-001",
                                "section": current_section,
                                "title": current_subhead or current_section,
                                "content": content
                            })
                        chunk_buffer = []

                    current_section = f"Section {sec_match.group(1)}: {sec_match.group(3)}"
                    current_subhead = line
                    chunk_buffer.append(line)
                elif line.startswith("Policy Reference:"):
                    chunk_buffer.append(line)
                elif line.startswith("Purpose") or line.startswith("Scope") or line.startswith("Policy owner"):
                    if chunk_buffer:
                        chunks.append({
                            "id": f"p{page_num}_sec_{len(chunks)}",
                            "page": page_num,
                            "policy_ref": "SRV-POL-001",
                            "section": current_section,
                            "title": current_subhead or current_section,
                            "content": "\n".join(chunk_buffer).strip()
                        })
                        chunk_buffer = []
                    current_section = line
                    current_subhead = line
                    chunk_buffer.append(line)
                else:
                    chunk_buffer.append(line)

            if chunk_buffer:
                content = "\n".join(chunk_buffer).strip()
                if len(content) > 30:
                    chunks.append({
                        "id": f"p{page_num}_sec_{len(chunks)}",
                        "page": page_num,
                        "policy_ref": "SRV-POL-001",
                        "section": current_section,
                        "title": current_subhead or current_section,
                        "content": content
                    })

        logger.info(f"Indexed {len(chunks)} semantic chunks from {self.pdf_path.name}")
        return chunks

