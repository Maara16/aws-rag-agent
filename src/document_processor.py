"""
Document processing: Extract text from PDFs, chunk intelligently, and prepare for ingestion.
"""

import logging
from pathlib import Path
from typing import List, Tuple, Dict
import PyPDF2
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

        # Use LangChain's splitter for intelligent chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract all text from PDF file."""
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        logger.info(f"Extracting text from {pdf_path.name}")
        text = ""
        page_count = 0

        try:
            with open(pdf_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                page_count = len(pdf_reader.pages)

                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        page_text = page.extract_text()
                        if page_text:
                            text += f"\n[PAGE {page_num + 1}]\n{page_text}"
                    except Exception as e:
                        logger.warning(f"Error extracting page {page_num}: {e}")

            logger.info(f"Extracted {page_count} pages, {len(text)} characters total")
            return text

        except Exception as e:
            logger.error(f"Error reading PDF: {e}")
            raise

    def chunk_text(self, text: str, source_name: str = "unknown") -> List[Tuple[str, Dict]]:
        """
        Split text into chunks and create metadata.

        Returns:
            List of (chunk_text, metadata) tuples
        """
        logger.info(f"Chunking text from {source_name}")

        # Split text
        chunks = self.text_splitter.split_text(text)

        # Filter out very small chunks
        chunks = [c for c in chunks if len(c) >= self.min_chunk_size]

        logger.info(f"Created {len(chunks)} chunks (min size: {self.min_chunk_size})")

        # Create metadata for each chunk
        chunks_with_metadata = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source": source_name,
                "chunk_id": i,
                "char_count": len(chunk),
                "word_count": len(chunk.split())
            }
            chunks_with_metadata.append((chunk, metadata))

        return chunks_with_metadata

    def process_cheatsheet(self, pdf_path: str) -> List[Tuple[str, Dict]]:
        """Process cheatsheet PDF with special handling for sections."""
        text = self.extract_text_from_pdf(pdf_path)

        # Split by sections (domains)
        # Cheatsheet format: "1. IAM — Identity & Access Management"
        sections = text.split("\\n\\n")

        chunks_with_metadata = []
        current_domain = "General"

        for section in sections:
            # Detect domain headers
            if section.strip() and ("—" in section or "." in section[:3]):
                # This might be a domain header
                if len(section.split("\n")[0]) < 100:
                    current_domain = section.split("\n")[0].strip()

            if len(section.strip()) >= self.min_chunk_size:
                metadata = {
                    "source": "cheatsheet",
                    "domain": current_domain,
                    "char_count": len(section),
                    "word_count": len(section.split())
                }
                chunks_with_metadata.append((section, metadata))

        logger.info(f"Processed cheatsheet with {len(chunks_with_metadata)} domain sections")
        return chunks_with_metadata

    def process_course_slides(self, pdf_path: str) -> List[Tuple[str, Dict]]:
        """Process course slides with page-aware metadata."""
        text = self.extract_text_from_pdf(pdf_path)

        # Extract page references from [PAGE N] markers
        chunks_with_metadata = []
        page_chunks = text.split("[PAGE ")

        for page_chunk in page_chunks[1:]:  # Skip first empty split
            lines = page_chunk.split("\n", 1)
            if len(lines) >= 2:
                try:
                    page_num = int(lines[0].rstrip("]"))
                    page_content = lines[1]

                    # Further chunk by content size
                    sub_chunks = self.text_splitter.split_text(page_content)

                    for sub_chunk in sub_chunks:
                        if len(sub_chunk) >= self.min_chunk_size:
                            metadata = {
                                "source": "course_slides",
                                "page": page_num,
                                "char_count": len(sub_chunk),
                                "word_count": len(sub_chunk.split())
                            }
                            chunks_with_metadata.append((sub_chunk, metadata))

                except ValueError:
                    logger.warning(f"Could not parse page number: {lines[0]}")

        logger.info(f"Processed course slides with {len(chunks_with_metadata)} chunks across pages")
        return chunks_with_metadata

    @staticmethod
    def format_retrieved_chunk(chunk: str, metadata: Dict) -> str:
        """Format a retrieved chunk for LLM context."""
        source = metadata.get("source", "unknown")
        if source == "course_slides":
            page = metadata.get("page", "?")
            return f"[Slides - Page {page}]\n{chunk}"
        elif source == "cheatsheet":
            domain = metadata.get("domain", "General")
            return f"[Cheatsheet - {domain}]\n{chunk}"
        else:
            return chunk
