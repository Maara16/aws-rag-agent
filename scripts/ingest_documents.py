#!/usr/bin/env python3
"""
One-time document ingestion script.
Extracts text from PDFs, chunks them, and loads into Chroma vector store.

Usage:
    python scripts/ingest_documents.py --cheatsheet /path/to/cheatsheet.pdf --slides /path/to/slides.pdf
"""

import sys
import logging
from pathlib import Path
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.document_processor import DocumentProcessor
from src.vector_store import get_vector_store

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Ingest PDF documents into Chroma")
    parser.add_argument("--cheatsheet", type=str, help="Path to cheatsheet PDF")
    parser.add_argument("--slides", type=str, help="Path to course slides PDF")
    parser.add_argument("--chunk-size", type=int, default=1000, help="Chunk size in characters")
    parser.add_argument("--chunk-overlap", type=int, default=200, help="Overlap between chunks")
    parser.add_argument("--clear-first", action="store_true", help="Clear existing documents before ingesting")

    args = parser.parse_args()

    if not args.cheatsheet and not args.slides:
        parser.print_help()
        logger.error("Must provide at least --cheatsheet or --slides")
        sys.exit(1)

    # Initialize
    processor = DocumentProcessor(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap
    )
    vector_store = get_vector_store()

    if args.clear_first:
        logger.warning("Clearing existing documents...")
        vector_store.clear()

    all_chunks = []
    all_metadatas = []
    all_ids = []

    # Process cheatsheet
    if args.cheatsheet:
        cheatsheet_path = Path(args.cheatsheet)
        if not cheatsheet_path.exists():
            logger.error(f"Cheatsheet not found: {cheatsheet_path}")
            sys.exit(1)

        logger.info(f"\n{'='*60}")
        logger.info("PROCESSING CHEATSHEET")
        logger.info(f"{'='*60}")

        try:
            chunks = processor.process_cheatsheet(str(cheatsheet_path))
            logger.info(f"Cheatsheet: {len(chunks)} chunks")

            for chunk_text, metadata in chunks:
                all_chunks.append(chunk_text)
                all_metadatas.append(metadata)
                all_ids.append(f"cheatsheet_{len(all_ids)}")

        except Exception as e:
            logger.error(f"Failed to process cheatsheet: {e}")
            sys.exit(1)

    # Process slides
    if args.slides:
        slides_path = Path(args.slides)
        if not slides_path.exists():
            logger.error(f"Slides not found: {slides_path}")
            sys.exit(1)

        logger.info(f"\n{'='*60}")
        logger.info("PROCESSING COURSE SLIDES")
        logger.info(f"{'='*60}")

        try:
            chunks = processor.process_course_slides(str(slides_path))
            logger.info(f"Slides: {len(chunks)} chunks")

            for chunk_text, metadata in chunks:
                all_chunks.append(chunk_text)
                all_metadatas.append(metadata)
                all_ids.append(f"slides_{len(all_ids)}")

        except Exception as e:
            logger.error(f"Failed to process slides: {e}")
            sys.exit(1)

    # Ingest to vector store
    logger.info(f"\n{'='*60}")
    logger.info(f"INGESTING TO CHROMA")
    logger.info(f"{'='*60}")
    logger.info(f"Total chunks: {len(all_chunks)}")

    try:
        vector_store.add_documents(all_chunks, all_metadatas, all_ids)
        vector_store.persist()

        stats = vector_store.get_stats()
        logger.info(f"\n✅ Ingestion complete!")
        logger.info(f"Collection: {stats['collection_name']}")
        logger.info(f"Total documents: {stats['total_documents']}")
        logger.info(f"Embedding dimension: {stats['embedding_dimension']}")

    except Exception as e:
        logger.error(f"Failed to ingest documents: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
