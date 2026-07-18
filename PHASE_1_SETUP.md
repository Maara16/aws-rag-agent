# Phase 1: Local Development Setup

This guide walks you through getting the AWS SAA Agent running locally on your machine.

## Prerequisites

- Python 3.9+ (check: `python --version`)
- pip (comes with Python)
- ~2GB free disk space (for PDF text extraction + vector embeddings)
- ~10 minutes

## Step 1: Project Setup

```bash
# Clone/navigate to project
cd AWS_SAA_AGENT_PROJECT

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Place Your PDF Files

Copy your PDFs into the `data/` directory:

```bash
mkdir -p data
cp /path/to/SAA_C03_Complete_Cheatsheet_Maara_2_.pdf data/cheatsheet.pdf
cp /path/to/AWS_Certified_Solutions_Architect_Slides_v48.pdf data/slides.pdf

# Verify
ls -lh data/*.pdf
```

## Step 3: Ingest Documents into Chroma

This is a one-time operation that:
1. Extracts text from PDFs
2. Chunks intelligently (respects boundaries)
3. Embeds with Sentence Transformers
4. Stores in Chroma (local SQLite backend)

**Expected time: 10-15 minutes** (depends on your machine)

```bash
python scripts/ingest_documents.py \
  --cheatsheet data/cheatsheet.pdf \
  --slides data/slides.pdf \
  --clear-first
```

**Output should look like:**
```
INFO - Extracting text from cheatsheet.pdf
INFO - Extracted X pages, YYYY characters total
INFO - Chunking text from cheatsheet
INFO - Created N chunks (min size: 100)

INFO - Extracting text from slides.pdf
INFO - Extracted 876 pages, ZZZZ characters total
INFO - Chunking text from course_slides
INFO - Created M chunks (min size: 100)

INFO - INGESTING TO CHROMA
INFO - Total chunks: N+M
✅ Ingestion complete!
Collection: aws_saa_docs
Total documents: N+M
Embedding dimension: 384
```

**Troubleshooting:**
- `ModuleNotFoundError`: Run `pip install -r requirements.txt` again
- `FileNotFoundError`: Verify PDFs are in `data/` directory
- Memory error on large PDFs: Reduce `--chunk-size` to 500
- Slow ingestion: Normal for 876-page slides. Get some coffee ☕

## Step 4: Test Vector Search Locally

Create a quick test file to verify search works:

```bash
# Create test file
cat > test_search.py << 'EOF'
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.vector_store import get_vector_store

# Get vector store
vs = get_vector_store()

# Test queries
queries = [
    "What is EC2 and how does it pricing work?",
    "Explain RDS Multi-AZ vs Read Replicas",
    "How do I secure my VPC?",
    "What's the difference between DynamoDB and RDS?",
]

for query in queries:
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print(f"{'='*60}")

    results = vs.search(query, k=3)

    for i, (text, distance, metadata) in enumerate(results, 1):
        print(f"\n[Result {i}] Distance: {distance:.3f}")
        print(f"Source: {metadata['source']}")
        if 'domain' in metadata:
            print(f"Domain: {metadata['domain']}")
        if 'page' in metadata:
            print(f"Page: {metadata['page']}")
        print(f"Preview: {text[:200]}...")
EOF

python test_search.py
```

**Expected output:**
```
============================================================
Query: What is EC2 and how does it pricing work?
============================================================

[Result 1] Distance: 0.234
Source: course_slides
Page: 45
Preview: EC2 — Elastic Compute Cloud. Instance Types: General Purpose (M...
```

✅ If you see results, vector search is working!

## Step 5: Verify Database Schema

```bash
# Check SQLite database created
ls -lh data/app.db

# (Optional) View schema
sqlite3 data/app.db ".schema"
```

## What's Ready Now?

✅ Vector store with all AWS SAA documents  
✅ SQLite database for user tracking  
✅ Semantic search working locally  
✅ Document chunking pipeline validated  

## What's Next? (Phase 2)

Once you confirm everything works above:
1. **Build RAG Agent** — Combines retrieval + LLM reasoning
2. **Build Quiz Agent** — Generates questions, tracks progress
3. **Implement Router** — Routes user messages to correct agent
4. **FastAPI Webhook** — Accept WhatsApp messages locally

**Ready to move to Phase 2?** Ping me with test results! 🚀

---

## Common Issues & Fixes

### Issue: `chromadb.errors.InvalidDimensionError`
**Cause**: Embedding dimension mismatch  
**Fix**: Delete `data/chroma_db/` and run ingestion again
```bash
rm -rf data/chroma_db/
python scripts/ingest_documents.py --cheatsheet data/cheatsheet.pdf --slides data/slides.pdf
```

### Issue: Out of Memory
**Cause**: Large PDFs + batch processing  
**Fix**: Reduce batch size in `ingest_documents.py`
```python
# Line ~XX, change:
vector_store.add_documents(all_chunks, all_metadatas, all_ids, batch_size=50)  # was 100
```

### Issue: Slow Search
**Cause**: First search loads model from disk  
**Fix**: Normal! Second+ searches are much faster. This is Sentence Transformers initialization.

### Issue: "No module named 'src'"
**Cause**: Working directory not set correctly  
**Fix**: Run scripts from project root:
```bash
cd AWS_SAA_AGENT_PROJECT
python scripts/ingest_documents.py ...
```

---

## Next Commands (After Confirming Phase 1)

```bash
# Phase 2: Build FastAPI app with agents
# (We'll scaffold this together)

# Test RAG agent
python notebooks/02_vector_search_test.ipynb

# Start FastAPI server (once built)
uvicorn src.main:app --reload --port 8000
```

Good luck! Let me know when you hit ✅ "Ingestion complete!" 🎉
