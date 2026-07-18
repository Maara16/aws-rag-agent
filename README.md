# AWS SAA-C03 Exam Prep Agent
## WhatsApp-Integrated RAG + Quiz + Cheatsheet System

**Project Owner**: Maara (Meyi Cloud IT Solutions)  
**Status**: Foundation Build Phase  
**Learning Goals**: RAG, AI Agents, LangChain, Twilio WhatsApp Integration

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     WhatsApp User                               │
└────────────────────────────┬────────────────────────────────────┘
                             │ SMS/WhatsApp Message
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Twilio WhatsApp Webhook (FastAPI)                  │
│  (Validates Twilio auth, routes to agent handler)               │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          Agent Router (LangChain with tool selection)           │
│  Decides: RAG Mode | Quiz Mode | Cheatsheet Mode | Web Search   │
└──┬──────────────────┬──────────────────┬───────────────────┬───┘
   │                  │                  │                   │
   ▼                  ▼                  ▼                   ▼
┌────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐
│   RAG      │  │    QUIZ      │  │  CHEATSHEET  │  │   WEB      │
│   Agent    │  │    Agent     │  │    Agent     │  │  SEARCH    │
│            │  │              │  │              │  │            │
│ Retrieves  │  │ Generates Q/ │  │ Fast lookup  │  │ Real-time  │
│ + Answers  │  │ A, tracks    │  │ in concise   │  │ AWS news,  │
│ from slides│  │ progress     │  │ cheatsheet   │  │ services   │
└────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────────┘
     │                 │                 │
     └─────────────────┴─────────────────┘
              │
              ▼
   ┌──────────────────────────────────┐
   │     Vector Store (Chroma)        │
   │ [Cheatsheet + Course Slides]     │
   │ Embeddings: Sentence Transformers│
   └──────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────┐
   │    SQLite (Progress Tracking)    │
   │ - Quiz attempts per user         │
   │ - Weak topics identified         │
   │ - Time spent per domain          │
   └──────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────┐
   │   Twilio Response Handler        │
   │ Formats answer, sends back to WA │
   └──────────────────────────────────┘
                    │
                    ▼
            ┌───────────────────┐
            │  WhatsApp User    │
            │  (Gets Response)  │
            └───────────────────┘
```

---

## 3 Agent Modes Explained

### 1. **RAG Mode** — Deep Concept Explanation
**Trigger**: "Explain EC2 pricing" | "What's a security group?" | "Tell me about Aurora"

- **Flow**: 
  1. User question → Embed with Sentence Transformers
  2. Search Chroma for top-5 relevant chunks from slides
  3. Re-rank by relevance (BM25 + semantic)
  4. Pass top chunks + question to LLM
  5. LLM generates concise answer with sources

- **LLM Used**: Ollama (Mistral-7B or Llama2) or Claude API (for tier users)
- **Output**: Formatted WhatsApp message (usually 1-3 paragraphs)

### 2. **Quiz Mode** — Exam Simulation
**Trigger**: "Quiz on S3" | "Give me a random EC2 question" | "Quiz domain 1"

- **Flow**:
  1. Extract relevant concepts from slides for topic
  2. Generate 3-4 multiple-choice questions via LLM
  3. Store question ID + correct answer in SQLite
  4. Send question #1 to user
  5. User replies with answer → check → store result → send next Q
  6. After N questions: show score + weak areas

- **Progress Tracking**:
  - Per-user attempt history
  - Accuracy by domain
  - Time spent per quiz
  - Recommendations for weak areas

### 3. **Cheatsheet Mode** — Fast Lookup
**Trigger**: "Quick: VPC vs Security Group" | "Cheatsheet S3" | "Key facts on RDS"

- **Flow**:
  1. BM25 search (exact keyword match) in cheatsheet
  2. Extract bullet point answer
  3. Respond with concise, formatted text

- **Output**: Quick 2-5 line answer (no deep explanation)

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **Backend** | Python FastAPI | Async, WebHook-friendly, great for LLM integrations |
| **LLM** | Ollama (free) / Claude (paid) | Ollama for offline learning; Claude for production |
| **Embeddings** | Sentence Transformers (HuggingFace) | Free, fast, 384-dim vectors |
| **Vector DB** | Chroma | Embedded, free, no setup |
| **Chat LLM** | LangChain Runnable | Unified interface across Ollama/Claude |
| **Document Processing** | PyPDF2 + LangChain | Chunk + embed slides |
| **WhatsApp** | Twilio Business WhatsApp API | 100 free msgs/month, webhooks |
| **Database** | SQLite | Simple, file-based, ideal for hobby projects |
| **Deployment** | Docker + cheap VPS | Scale later to AWS Lambda/ECS |

---

## Project Structure

```
AWS_SAA_AGENT_PROJECT/
├── README.md (this file)
├── requirements.txt
├── .env.example
├── docker-compose.yml
├── Dockerfile
│
├── src/
│   ├── __init__.py
│   ├── main.py (FastAPI app + Twilio webhook)
│   ├── config.py (env vars, constants)
│   ├── database.py (SQLite schema + queries)
│   ├── vector_store.py (Chroma initialization + queries)
│   ├── document_processor.py (PDF ingestion, chunking)
│   ├── llm_client.py (Ollama / Claude wrapper)
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── rag_agent.py (Explain mode)
│   │   ├── quiz_agent.py (Quiz mode)
│   │   ├── cheatsheet_agent.py (Quick lookup)
│   │   └── router.py (Route user message to correct agent)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── text_formatter.py (WhatsApp message formatting)
│       ├── embeddings.py (wrapper for HF embeddings)
│       └── ranking.py (BM25 + semantic re-ranking)
│
├── data/
│   ├── cheatsheet.pdf (your cheatsheet)
│   ├── slides.pdf (Maarek 876-page course)
│   └── chroma_db/ (vector store, auto-created)
│
├── notebooks/
│   ├── 01_pdf_ingestion.ipynb (Extract + chunk PDFs)
│   ├── 02_vector_search_test.ipynb (Query chroma)
│   └── 03_agent_sandbox.ipynb (Test agents locally)
│
└── scripts/
    ├── ingest_documents.py (One-time: PDF → Chroma)
    ├── test_webhook.py (Local Twilio testing)
    └── reset_db.py (Clear vector store + SQLite)
```

---

## Quick Start (Phased Approach)

### Phase 1: Local Development (Today)
- [ ] Install dependencies
- [ ] Ingest PDFs into Chroma
- [ ] Test RAG agent locally (Jupyter notebook)
- [ ] Build FastAPI webhook (mock Twilio for testing)

### Phase 2: Agent Integration (Tomorrow)
- [ ] Implement router logic
- [ ] Build Quiz agent with SQLite tracking
- [ ] Build Cheatsheet agent
- [ ] Twilio WhatsApp sandbox (free testing account)

### Phase 3: Deployment & Polish (This week)
- [ ] Docker + Docker Compose
- [ ] Deploy to cheap VPS (Railway, Render, Heroku)
- [ ] Enable actual Twilio WhatsApp (100 free msgs/month to start)
- [ ] Build progress dashboard (optional)

---

## Key Learning Outcomes

By building this project, you'll master:

✅ **RAG Pipeline** — Document ingestion, chunking, embedding, retrieval, re-ranking  
✅ **LangChain** — Agent patterns, tool selection, state management  
✅ **Vector Databases** — Chroma, semantic search, hybrid search  
✅ **FastAPI Webhooks** — Async handlers, request validation, Twilio auth  
✅ **LLM Integration** — Ollama local + Claude API, prompt engineering  
✅ **SQLite for State** — Multi-turn conversations, progress tracking  
✅ **WhatsApp Bot Design** — UX for constrained mobile interface  
✅ **Docker & Deployment** — Containerization, secrets management, VPS setup  

**Bonus**: This becomes a **portfolio piece** + **case study for consulting** + **foundation for WhatsApp AI SaaS**.

---

## Next Immediate Steps

1. **Run Phase 1 setup** (see below)
2. **Ingest PDFs** into Chroma
3. **Test RAG locally** in Jupyter
4. **Come back with results**, we iterate

Let's start! 🚀
